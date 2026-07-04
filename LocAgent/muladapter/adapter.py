#!/usr/bin/env python3
"""Small self-contained adapter for multilingual/multimodal benchmark inputs.

The adapter is intentionally local to this repository. It prepares enriched
issue text, scans multilingual source files, extracts lightweight symbols, and
exports LocAgent-friendly file/symbol indexes without changing LocAgent's core
agent logic.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

try:
    from muladapter.codev_context import adapter_mode, enhance_with_codev_context
except ModuleNotFoundError:  # Support direct execution as python muladapter/adapter.py.
    from codev_context import adapter_mode, enhance_with_codev_context


LANGUAGE_BY_SUFFIX = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".c": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".h": "c/cpp-header",
    ".hpp": "cpp-header",
    ".go": "go",
    ".rs": "rust",
    ".vue": "vue",
    ".svelte": "svelte",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".md": "markdown",
    ".rst": "restructuredtext",
}

SKIP_DIRS = {".git", "node_modules", "dist", "build", "__pycache__", ".venv", "venv"}
URL_RE = re.compile(r"https?://[^\s)>\]\"']+")
IMAGE_RE = re.compile(r"\.(?:png|jpg|jpeg|gif|webp|svg)(?:\?.*)?$", re.I)


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def detect_language(path: str) -> str:
    return LANGUAGE_BY_SUFFIX.get(Path(path).suffix.lower(), "text")


def split_urls(text: str) -> tuple[list[str], list[str]]:
    image_urls, web_urls = [], []
    for url in URL_RE.findall(text or ""):
        clean = url.rstrip(".,;")
        if IMAGE_RE.search(clean) or "user-attachments/assets" in clean:
            image_urls.append(clean)
        else:
            web_urls.append(clean)
    return sorted(set(image_urls)), sorted(set(web_urls))


def enrich_problem_statement(sample: dict) -> dict:
    sample = dict(sample)
    text = sample.get("problem_statement") or sample.get("issue") or sample.get("body") or ""
    image_urls = set(sample.get("image_urls") or sample.get("images") or [])
    web_urls = set(sample.get("web_urls") or sample.get("urls") or [])
    found_images, found_webs = split_urls(text)
    image_urls.update(found_images)
    web_urls.update(found_webs)

    mode = adapter_mode(os.getenv("MULADAPTER_DEFAULT_MODE", "url_only"))
    if mode in {"off", "none", "text_only"}:
        sample["image_urls"] = sorted(image_urls)
        sample["web_urls"] = sorted(web_urls)
        sample["problem_statement"] = text.rstrip() + "\n"
        return sample
    if mode in {"codev_caption", "codev", "visual_caption"}:
        sample["image_urls"] = sorted(image_urls)
        sample["web_urls"] = sorted(web_urls)
        return enhance_with_codev_context(sample, compact=False)
    if mode in {"codev_compact", "compact", "graphlocator_compact"}:
        sample["image_urls"] = sorted(image_urls)
        sample["web_urls"] = sorted(web_urls)
        return enhance_with_codev_context(sample, compact=True)

    sections = [text.rstrip()]
    if image_urls:
        sections.extend(["", "Attached Images:"])
        sections.extend(f"- {url}" for url in sorted(image_urls))
    if web_urls:
        sections.extend(["", "Related URLs:"])
        sections.extend(f"- {url}" for url in sorted(web_urls))
    if image_urls or web_urls:
        sections.extend([
            "",
            "Note: The issue may include visual or web-based evidence. Consider the linked resources when localizing relevant code.",
        ])

    sample["image_urls"] = sorted(image_urls)
    sample["web_urls"] = sorted(web_urls)
    sample["problem_statement"] = "\n".join(sections).strip() + "\n"
    return sample


def _line_start_offsets(text: str) -> list[int]:
    offsets = [0]
    for match in re.finditer(r"\n", text):
        offsets.append(match.end())
    return offsets


def _line_no(offsets: list[int], pos: int) -> int:
    line = 1
    for i, start in enumerate(offsets, start=1):
        if start > pos:
            break
        line = i
    return line


def extract_symbols(path: str, content: str) -> list[dict]:
    lang = detect_language(path)
    offsets = _line_start_offsets(content)
    patterns = []
    if lang == "python":
        patterns = [
            ("class", re.compile(r"^\s*class\s+([A-Za-z_]\w*)", re.M)),
            ("function", re.compile(r"^\s*def\s+([A-Za-z_]\w*)", re.M)),
        ]
    elif lang in {"javascript", "typescript", "vue", "svelte"}:
        patterns = [
            ("class", re.compile(r"\bclass\s+([A-Za-z_$][\w$]*)")),
            ("function", re.compile(r"\bfunction\s+([A-Za-z_$][\w$]*)\s*\(")),
            ("function", re.compile(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>")),
            ("component", re.compile(r"\bexport\s+default\s+function\s+([A-Za-z_$][\w$]*)\s*\(")),
        ]
    elif lang == "java":
        patterns = [
            ("class", re.compile(r"\bclass\s+([A-Za-z_]\w*)")),
            ("function", re.compile(r"\b(?:public|private|protected)?\s*(?:static\s+)?[A-Za-z_<>\[\]]+\s+([A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{")),
        ]
    elif lang in {"c", "cpp", "c/cpp-header", "cpp-header", "go", "rust"}:
        patterns = [
            ("function", re.compile(r"\b([A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{")),
            ("class", re.compile(r"\b(?:class|struct)\s+([A-Za-z_]\w*)")),
            ("function", re.compile(r"\bfunc\s+([A-Za-z_]\w*)\s*\(")),
            ("function", re.compile(r"\bfn\s+([A-Za-z_]\w*)\s*\(")),
        ]

    symbols = []
    seen = set()
    for symbol_type, pattern in patterns:
        for match in pattern.finditer(content):
            name = match.group(1)
            key = (symbol_type, name, match.start())
            if key in seen:
                continue
            seen.add(key)
            start_line = _line_no(offsets, match.start())
            snippet = "\n".join(content.splitlines()[max(0, start_line - 1): start_line + 20])
            symbols.append({
                "type": symbol_type,
                "name": name,
                "path": path,
                "start_line": start_line,
                "end_line": start_line + max(0, len(snippet.splitlines()) - 1),
                "content": snippet,
            })
    return symbols


def scan_repo(repo_dir: Path) -> dict:
    files = []
    for path in sorted(repo_dir.rglob("*")):
        if not path.is_file() or any(part in SKIP_DIRS for part in path.parts):
            continue
        rel = path.relative_to(repo_dir).as_posix()
        lang = detect_language(rel)
        if lang == "text" and path.suffix:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        files.append({
            "path": rel,
            "language": lang,
            "content": content,
            "symbols": extract_symbols(rel, content),
        })
    return {"repo_dir": str(repo_dir), "files": files}


def export_for_locagent(parsed: dict, samples: list[dict], output_dir: Path) -> None:
    files = [
        {"path": item["path"], "language": item["language"], "text": item["content"]}
        for item in parsed["files"]
    ]
    symbols = []
    for item in parsed["files"]:
        for symbol in item["symbols"]:
            symbols.append({
                "path": symbol["path"],
                "language": item["language"],
                "symbol_type": symbol["type"],
                "name": symbol["name"],
                "start_line": symbol["start_line"],
                "end_line": symbol["end_line"],
                "text": symbol["content"],
            })
    write_jsonl(output_dir / "repo_index" / "files.jsonl", files)
    write_jsonl(output_dir / "repo_index" / "symbols.jsonl", symbols)
    write_jsonl(output_dir / "data" / "samples_enriched.jsonl", [enrich_problem_statement(s) for s in samples])


def command_smoke(args: argparse.Namespace) -> None:
    samples = read_jsonl(Path(args.samples))
    parsed = scan_repo(Path(args.repo))
    export_for_locagent(parsed, samples[: args.limit], Path(args.output_dir))
    print(f"files={len(parsed['files'])}")
    print(f"symbols={sum(len(item['symbols']) for item in parsed['files'])}")
    print(f"output={args.output_dir}")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    smoke = sub.add_parser("smoke-export")
    smoke.add_argument("--repo", required=True)
    smoke.add_argument("--samples", required=True)
    smoke.add_argument("--output-dir", required=True)
    smoke.add_argument("--limit", type=int, default=2)
    smoke.set_defaults(func=command_smoke)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
