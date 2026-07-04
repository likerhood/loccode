from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from mmir.schema import Evidence, Sample


IDENTIFIER_RE = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]{2,}")
PATH_RE = re.compile(r"(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+\.[A-Za-z0-9]+")
QUOTED_RE = re.compile(r"[`'\"]([^`'\"]{3,120})[`'\"]")


def _load_cache(path: str | Path | None) -> dict[str, str]:
    if not path:
        return {}
    cache_path = Path(path)
    if not cache_path.exists():
        return {}
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return {str(key): str(value) for key, value in payload.items()}
    if isinstance(payload, list):
        out: dict[str, str] = {}
        for row in payload:
            if isinstance(row, dict):
                key = row.get("url") or row.get("image_url") or row.get("web_url")
                text = row.get("text") or row.get("ocr_text") or row.get("content")
                if key and text:
                    out[str(key)] = str(text)
        return out
    return {}


def extract_symbols(text: str) -> list[str]:
    symbols: list[str] = []
    symbols.extend(PATH_RE.findall(text or ""))
    symbols.extend(match.group(1) for match in QUOTED_RE.finditer(text or ""))
    for token in IDENTIFIER_RE.findall(text or ""):
        if any(char.isupper() for char in token) or "_" in token or "$" in token:
            symbols.append(token)
    seen: set[str] = set()
    out: list[str] = []
    for symbol in symbols:
        normalized = symbol.strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            out.append(normalized)
    return out[:200]


def build_evidence(
    sample: Sample,
    *,
    ocr_cache: str | Path | None = None,
    web_cache: str | Path | None = None,
) -> Evidence:
    ocr = _load_cache(ocr_cache)
    web = _load_cache(web_cache)
    ocr_text = "\n".join(ocr.get(url, "") for url in sample.image_urls if ocr.get(url))
    web_text = "\n".join(web.get(url, "") for url in sample.web_urls if web.get(url))
    issue_text = sample.problem_statement
    symbols = extract_symbols("\n".join([issue_text, ocr_text, web_text]))
    return Evidence(issue_text=issue_text, ocr_text=ocr_text, web_text=web_text, symbols=symbols)
