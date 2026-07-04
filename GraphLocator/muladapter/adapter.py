#!/usr/bin/env python3
"""GraphLocator-local adapter for multilingual/multimodal benchmark inputs.

This module only creates adapter-side skeleton data. It does not modify
GraphLocator's RDFS/CIG implementation.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

try:
    from muladapter.codev_context import adapter_mode, enhance_with_codev_context
except ModuleNotFoundError:
    from codev_context import adapter_mode, enhance_with_codev_context


LANGUAGE_BY_SUFFIX = {
    ".py": "python", ".js": "javascript", ".jsx": "javascript",
    ".ts": "typescript", ".tsx": "typescript", ".java": "java",
    ".c": "c", ".cc": "cpp", ".cpp": "cpp", ".h": "c/cpp-header",
    ".hpp": "cpp-header", ".go": "go", ".rs": "rust", ".vue": "vue",
    ".svelte": "svelte", ".html": "html", ".css": "css", ".scss": "scss",
    ".json": "json", ".yaml": "yaml", ".yml": "yaml", ".toml": "toml",
    ".md": "markdown", ".rst": "restructuredtext",
}
SKIP_DIRS = {".git", "node_modules", "dist", "build", "__pycache__", ".venv", "venv"}
URL_RE = re.compile(r"https?://[^\s)>\]\"']+")
IMAGE_RE = re.compile(r"\.(?:png|jpg|jpeg|gif|webp|svg)(?:\?.*)?$", re.I)


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def detect_language(path: str) -> str:
    return LANGUAGE_BY_SUFFIX.get(Path(path).suffix.lower(), "text")


def split_urls(text: str) -> tuple[list[str], list[str]]:
    images, webs = [], []
    for url in URL_RE.findall(text or ""):
        clean = url.rstrip(".,;")
        if IMAGE_RE.search(clean) or "user-attachments/assets" in clean:
            images.append(clean)
        else:
            webs.append(clean)
    return sorted(set(images)), sorted(set(webs))


def enrich_problem_statement(sample: dict) -> dict:
    sample = dict(sample)
    text = sample.get("problem_statement") or sample.get("issue") or sample.get("body") or ""
    images = set(sample.get("image_urls") or sample.get("images") or [])
    webs = set(sample.get("web_urls") or sample.get("urls") or [])
    found_images, found_webs = split_urls(text)
    images.update(found_images)
    webs.update(found_webs)
    mode = adapter_mode(os.getenv("MULADAPTER_DEFAULT_MODE", "url_only"))
    if mode in {"off", "none", "text_only"}:
        sample["image_urls"] = sorted(images)
        sample["web_urls"] = sorted(webs)
        sample["problem_statement"] = text.rstrip() + "\n"
        return sample
    if mode in {"codev_caption", "codev", "visual_caption"}:
        sample["image_urls"] = sorted(images)
        sample["web_urls"] = sorted(webs)
        return enhance_with_codev_context(sample, compact=False)
    if mode in {"codev_compact", "compact", "graphlocator_compact"}:
        sample["image_urls"] = sorted(images)
        sample["web_urls"] = sorted(webs)
        return enhance_with_codev_context(sample, compact=True)
    parts = [text.rstrip()]
    if images:
        parts += ["", "Attached Images:", *[f"- {url}" for url in sorted(images)]]
    if webs:
        parts += ["", "Related URLs:", *[f"- {url}" for url in sorted(webs)]]
    if images or webs:
        parts += ["", "Note: Consider the linked visual/web resources when localizing relevant code."]
    sample["image_urls"] = sorted(images)
    sample["web_urls"] = sorted(webs)
    sample["problem_statement"] = "\n".join(parts).strip() + "\n"
    return sample


def _line_no(content: str, pos: int) -> int:
    return content.count("\n", 0, pos) + 1


def extract_symbols(path: str, content: str) -> list[dict]:
    lang = detect_language(path)
    if lang == "python":
        patterns = [("CLASS", r"^\s*class\s+([A-Za-z_]\w*)"), ("FUNCTION", r"^\s*def\s+([A-Za-z_]\w*)")]
        flags = re.M
    elif lang in {"javascript", "typescript", "vue", "svelte"}:
        patterns = [("CLASS", r"\bclass\s+([A-Za-z_$][\w$]*)"), ("FUNCTION", r"\bfunction\s+([A-Za-z_$][\w$]*)\s*\("), ("FUNCTION", r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>")]
        flags = 0
    elif lang == "java":
        patterns = [("CLASS", r"\bclass\s+([A-Za-z_]\w*)"), ("FUNCTION", r"\b(?:public|private|protected)?\s*(?:static\s+)?[A-Za-z_<>\[\]]+\s+([A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{")]
        flags = 0
    else:
        patterns = [("FUNCTION", r"\b([A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{")]
        flags = 0
    symbols, seen = [], set()
    for typ, raw in patterns:
        for m in re.finditer(raw, content, flags):
            key = (typ, m.group(1), m.start())
            if key in seen:
                continue
            seen.add(key)
            line = _line_no(content, m.start())
            snippet = "\n".join(content.splitlines()[max(0, line - 1): line + 20])
            symbols.append({"type": typ, "name": m.group(1), "path": path, "start_line": line, "end_line": line + len(snippet.splitlines()) - 1, "content": snippet})
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
        files.append({"path": rel, "language": lang, "content": content, "symbols": extract_symbols(rel, content)})
    return {"repo_dir": str(repo_dir), "files": files}


def export_for_graphlocator(parsed: dict, samples: list[dict], output_dir: Path) -> None:
    nodes, edges = [], []
    for item in parsed["files"]:
        file_id = f"FILE::{item['path']}"
        nodes.append({"id": file_id, "type": "FILE", "name": Path(item["path"]).name, "path": item["path"], "language": item["language"], "content": item["content"]})
        for symbol in item["symbols"]:
            symbol_id = f"{symbol['type']}::{item['path']}::{symbol['name']}::{symbol['start_line']}"
            nodes.append({"id": symbol_id, "type": symbol["type"], "name": symbol["name"], "path": item["path"], "start_line": symbol["start_line"], "end_line": symbol["end_line"], "content": symbol["content"]})
            edges.append({"src": file_id, "trg": symbol_id, "relation": "HasMember"})
    skeleton = {"adapter_schema": "graphlocator-muladapter-v1", "nodes": nodes, "edges": edges}
    for sample in samples:
        instance_id = sample.get("instance_id", "sample")
        write_json(output_dir / "repo_skeleton" / f"{instance_id}.json", skeleton)
    write_jsonl(output_dir / "data" / "samples_enriched.jsonl", [enrich_problem_statement(s) for s in samples])


def command_smoke(args: argparse.Namespace) -> None:
    samples = read_jsonl(Path(args.samples))[: args.limit]
    parsed = scan_repo(Path(args.repo))
    export_for_graphlocator(parsed, samples, Path(args.output_dir))
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
