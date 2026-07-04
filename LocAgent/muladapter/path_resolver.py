"""Multi-language file path normalization for LocAgent outputs."""

from __future__ import annotations

import difflib
import re
from pathlib import PurePosixPath


SUPPORTED_FILE_EXTENSIONS = (
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".mjs",
    ".cjs",
    ".java",
    ".kt",
    ".go",
    ".rs",
    ".c",
    ".cc",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".php",
    ".rb",
    ".scala",
    ".swift",
    ".vue",
    ".svelte",
    ".css",
    ".scss",
    ".less",
    ".html",
    ".json",
    ".yaml",
    ".yml",
)

INDEX_FILE_NAMES = (
    "index.js",
    "index.jsx",
    "index.ts",
    "index.tsx",
    "index.mjs",
    "index.cjs",
    "__init__.py",
)


def normalize_path(path: str) -> str:
    path = path.strip().strip("`'\"")
    path = path.replace("\\", "/")
    path = re.sub(r"^\s*(?:[-*+]|\d+[.)])\s+", "", path)
    path = re.sub(r"\s+#.*$", "", path)
    path = re.sub(r"\s+\(.*?\)\s*$", "", path)
    path = path.strip().rstrip(":,;")
    while path.startswith("./"):
        path = path[2:]
    return path


def parse_file_candidates(content: str) -> list[str]:
    if not content:
        return []
    blocks = re.findall(r"```(?:[a-zA-Z0-9_-]+)?\n(.*?)```", content, re.DOTALL)
    text = "\n".join(blocks) if blocks else content
    path_token = re.compile(r"[\w@./+-]+(?:/[\w@./+-]+)+")
    candidates: list[str] = []
    seen: set[str] = set()
    for raw_line in text.splitlines():
        line = normalize_path(raw_line)
        if not line:
            continue
        tokens = [line] if not re.search(r"\s", line) else path_token.findall(line)
        for token in tokens:
            token = normalize_path(token)
            if not token or "/" not in token:
                continue
            if token not in seen:
                seen.add(token)
                candidates.append(token)
    return candidates


def _index_file_matches(candidate: str, all_files: list[str]) -> list[str]:
    prefix = candidate.rstrip("/") + "/"
    matches = [f for f in all_files if f.startswith(prefix)]
    preferred = [f for f in matches if PurePosixPath(f).name in INDEX_FILE_NAMES]
    return preferred or matches


def resolve_file_candidates(
    candidates: list[str],
    all_files: list[str],
    *,
    limit: int | None = 5,
    fuzzy_cutoff: float = 0.74,
) -> list[str]:
    original_files = [
        f for f in all_files if normalize_path(f).lower().endswith(SUPPORTED_FILE_EXTENSIONS)
    ]
    if not original_files:
        original_files = list(all_files)
    normalized_files = [normalize_path(f) for f in original_files]
    normalized_to_original = dict(zip(normalized_files, original_files))
    file_set = set(normalized_files)
    basename_map: dict[str, list[str]] = {}
    for file_path in normalized_files:
        basename_map.setdefault(PurePosixPath(file_path).name, []).append(file_path)

    resolved: list[str] = []
    seen: set[str] = set()

    def add(path: str) -> bool:
        original = normalized_to_original.get(path, path)
        if original not in seen:
            seen.add(original)
            resolved.append(original)
            return True
        return False

    for raw_candidate in candidates:
        candidate = normalize_path(raw_candidate)
        if not candidate:
            continue
        matched = False
        if candidate in file_set:
            matched = add(candidate)
        else:
            for match in _index_file_matches(candidate, normalized_files):
                matched = add(match) or matched
                break
            if not matched:
                basename_matches = basename_map.get(PurePosixPath(candidate).name, [])
                if len(basename_matches) == 1:
                    matched = add(basename_matches[0])
            if not matched:
                suffix_matches = [f for f in normalized_files if f.endswith("/" + candidate)]
                if len(suffix_matches) == 1:
                    matched = add(suffix_matches[0])
            if not matched:
                matches = difflib.get_close_matches(
                    candidate, normalized_files, n=1, cutoff=fuzzy_cutoff
                )
                if matches:
                    add(matches[0])
        if limit is not None and len(resolved) >= limit:
            break
    return resolved
