#!/usr/bin/env python3
"""CodeV-style multimodal context builder for local muladapter use.

This module is deliberately self-contained. It converts image and web evidence
into concise textual context that existing text-only localization baselines can
consume without changing their internal search or graph logic.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


URL_RE = re.compile(r"https?://[^\s)>\]\"']+")
IMAGE_RE = re.compile(r"\.(?:png|jpg|jpeg|gif|webp|svg)(?:\?.*)?$", re.I)
DANGEROUS_WEB_RE = re.compile(r"/(?:commit|pull|compare)/|\.patch(?:\?|$)|\.diff(?:\?|$)", re.I)
TAG_RE = re.compile(r"<[^>]+>")
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
META_DESC_RE = re.compile(
    r"<meta[^>]+(?:name|property)=[\"'](?:description|og:description)[\"'][^>]+content=[\"'](.*?)[\"'][^>]*>",
    re.I | re.S,
)
HEADING_RE = re.compile(r"<h[1-2][^>]*>(.*?)</h[1-2]>", re.I | re.S)


def _env_flag(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def adapter_mode(default: str = "url_only") -> str:
    return os.getenv("MULADAPTER_MODE", default).strip().lower() or default


def collect_urls(sample: dict, text: str = "") -> tuple[list[str], list[str]]:
    images: set[str] = set()
    webs: set[str] = set()

    def add_url(url: str) -> None:
        clean = str(url).strip().rstrip(".,;")
        if not clean:
            return
        if IMAGE_RE.search(clean) or "user-attachments/assets" in clean:
            images.add(clean)
        else:
            webs.add(clean)

    def add_many(value: Any) -> None:
        if not value:
            return
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except Exception:
                parsed = None
            if isinstance(parsed, dict):
                add_many(parsed)
            elif isinstance(parsed, list):
                add_many(parsed)
            else:
                for url in URL_RE.findall(value):
                    add_url(url)
            return
        if isinstance(value, dict):
            for item in value.values():
                add_many(item)
            return
        if isinstance(value, (list, tuple, set)):
            for item in value:
                add_many(item)

    for key in (
        "image_assets",
        "image_urls",
        "images",
        "image",
        "web_urls",
        "urls",
        "website links",
        "website_links",
        "links",
    ):
        add_many(sample.get(key))
    add_many(text or sample.get("problem_statement") or sample.get("issue") or sample.get("body") or "")
    return sorted(images), sorted(webs)


def _cache_path() -> Path:
    configured = os.getenv("MULADAPTER_CACHE_FILE")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parent / "cache" / "codev_context_cache.json"


def _load_cache() -> dict:
    path = _cache_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_cache(cache: dict) -> None:
    path = _cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _cache_key(kind: str, url: str, model: str) -> str:
    digest = hashlib.sha1(f"{kind}\0{url}\0{model}".encode("utf-8")).hexdigest()[:16]
    return f"{kind}:{digest}:{url}"


def _truncate(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", (text or "")).strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _strip_html(raw: str) -> str:
    raw = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", raw or "")
    return html.unescape(TAG_RE.sub(" ", raw))


def _extract_first(pattern: re.Pattern, raw: str) -> str:
    match = pattern.search(raw or "")
    if not match:
        return ""
    return _truncate(html.unescape(TAG_RE.sub(" ", match.group(1))), 300)


def summarize_web_url(url: str) -> dict:
    model = "web"
    key = _cache_key("web", url, model)
    cache = _load_cache()
    if key in cache:
        return cache[key]

    if DANGEROUS_WEB_RE.search(url):
        record = {
            "status": "skipped",
            "url": url,
            "reason": "Possible patch/PR/commit link; kept as URL only to avoid answer leakage.",
        }
        cache[key] = record
        _save_cache(cache)
        return record

    timeout = float(os.getenv("MULADAPTER_WEB_TIMEOUT", "8"))
    limit = int(os.getenv("MULADAPTER_WEB_SUMMARY_CHARS", "1200"))
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "muladapter/0.1"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get("content-type", "")
            raw_bytes = response.read(300_000)
        if "text/html" not in content_type and "text/plain" not in content_type:
            raise ValueError(f"unsupported content-type: {content_type}")
        raw = raw_bytes.decode("utf-8", errors="ignore")
        headings = [_truncate(_strip_html(h), 160) for h in HEADING_RE.findall(raw)[:4]]
        record = {
            "status": "ok",
            "url": url,
            "title": _extract_first(TITLE_RE, raw),
            "description": _extract_first(META_DESC_RE, raw),
            "headings": [h for h in headings if h],
            "summary": _truncate(_strip_html(raw), limit),
        }
    except Exception as exc:
        record = {"status": "failed", "url": url, "error": str(exc)}

    cache[key] = record
    _save_cache(cache)
    return record


def _chat_completion(messages: list[dict]) -> str:
    base_url = os.getenv("MULADAPTER_BASE_URL", "").rstrip("/")
    model = os.getenv("MULADAPTER_MODEL", "")
    api_key = os.getenv("MULADAPTER_API_KEY", os.getenv("OPENAI_API_KEY", "dummy"))
    if not base_url or not model:
        raise RuntimeError("MULADAPTER_BASE_URL and MULADAPTER_MODEL are required for image captioning")
    payload = {
        "model": model,
        "messages": messages,
        "temperature": float(os.getenv("MULADAPTER_TEMPERATURE", "0")),
        "max_tokens": int(os.getenv("MULADAPTER_MAX_TOKENS", "700")),
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        base_url + "/chat/completions",
        data=data,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    timeout = float(os.getenv("MULADAPTER_REQUEST_TIMEOUT", "120"))
    with urllib.request.urlopen(req, timeout=timeout) as response:
        result = json.loads(response.read().decode("utf-8"))
    return result["choices"][0]["message"]["content"]


def describe_image_url(url: str, issue_text: str) -> dict:
    model = os.getenv("MULADAPTER_MODEL", "")
    key = _cache_key("image", url, model or "no-model")
    cache = _load_cache()
    if key in cache:
        return cache[key]

    system = (
        "You are a visual software issue analyst. Convert visual issue evidence "
        "into concise text for code localization. Do not infer gold patch files."
    )
    user_text = (
        "Given the issue text and image, produce three short sections:\n"
        "Raw Visual Description, Issue-Relevant Analysis, Localization Clues.\n"
        "Focus on UI elements, chart elements, visible text, expected/actual behavior, "
        "and likely code component types. Keep it concise.\n\n"
        f"Issue text:\n{_truncate(issue_text, 3500)}"
    )
    record: dict
    try:
        content = _chat_completion([
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": url}},
                    {"type": "text", "text": user_text},
                ],
            },
        ])
        record = {"status": "ok", "url": url, "caption": _truncate(content, 1800)}
    except Exception as exc:
        record = {"status": "failed", "url": url, "error": str(exc)}

    cache[key] = record
    _save_cache(cache)
    time.sleep(float(os.getenv("MULADAPTER_REQUEST_DELAY", "0")))
    return record


def build_codev_context(sample: dict, *, compact: bool = False) -> str:
    text = sample.get("problem_statement") or sample.get("issue") or sample.get("body") or ""
    image_urls, web_urls = collect_urls(sample, text)
    enable_image = _env_flag("MULADAPTER_ENABLE_IMAGE", True)
    enable_web = _env_flag("MULADAPTER_ENABLE_WEB", True)

    blocks: list[str] = []
    if enable_image and image_urls:
        blocks.append("[Visual Evidence]")
        for i, url in enumerate(image_urls, start=1):
            record = describe_image_url(url, text)
            if record.get("status") == "ok":
                blocks.append(f"Image {i}: {url}\n{record.get('caption', '')}")
            else:
                blocks.append(f"Image {i}: {url}\nVisual processing failed; use the URL and issue text only. Error: {record.get('error', record.get('reason', 'unknown'))}")

    if enable_web and web_urls:
        blocks.append("[Web Evidence]")
        for i, url in enumerate(web_urls, start=1):
            record = summarize_web_url(url)
            if record.get("status") == "ok":
                if compact:
                    summary = " ".join(x for x in [record.get("title"), record.get("description"), record.get("summary")] if x)
                    blocks.append(f"URL {i}: {url}\nSummary: {_truncate(summary, 700)}")
                else:
                    headings = "; ".join(record.get("headings") or [])
                    blocks.append(
                        f"URL {i}: {url}\n"
                        f"Title: {record.get('title', '')}\n"
                        f"Description: {record.get('description', '')}\n"
                        f"Headings: {headings}\n"
                        f"Summary: {record.get('summary', '')}"
                    )
            elif record.get("status") == "skipped":
                blocks.append(f"URL {i}: {url}\nSkipped detailed fetch: {record.get('reason')}")
            else:
                blocks.append(f"URL {i}: {url}\nWeb processing failed; use URL only. Error: {record.get('error', 'unknown')}")

    if not blocks:
        return ""
    if compact:
        joined = "\n\n".join(blocks)
        return "[Multimodal Context - Compact]\n" + _truncate(joined, int(os.getenv("MULADAPTER_COMPACT_CHARS", "2500")))
    return "\n\n".join(blocks)


def enhance_with_codev_context(sample: dict, *, compact: bool = False) -> dict:
    sample = dict(sample)
    text = sample.get("problem_statement") or sample.get("issue") or sample.get("body") or ""
    image_urls, web_urls = collect_urls(sample, text)
    sample["image_urls"] = image_urls
    sample["web_urls"] = web_urls
    context = build_codev_context(sample, compact=compact)
    if context:
        sample["problem_statement"] = (
            "[Original Issue]\n"
            + text.rstrip()
            + "\n\n"
            + context.strip()
            + "\n\n[Adapter Note]\nUse the multimodal context only as auxiliary evidence for code localization.\n"
        )
    else:
        sample["problem_statement"] = text.rstrip() + "\n"
    return sample

