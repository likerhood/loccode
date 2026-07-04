"""Utilities for normalizing multi-language localization file paths.

The original CoSIL file parser only accepted Python files.  These helpers keep
the compatibility patch isolated from the core localization algorithm.
"""

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
    ".kts",
    ".go",
    ".rs",
    ".c",
    ".cc",
    ".cpp",
    ".cxx",
    ".h",
    ".hh",
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
    ".xml",
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


def _fenced_or_full_text(content: str) -> str:
    blocks = re.findall(r"```(?:[a-zA-Z0-9_-]+)?\n(.*?)```", content, re.DOTALL)
    if blocks:
        return "\n".join(blocks)
    return content


def _trim_to_supported_suffix(token: str) -> str:
    lower = token.lower()
    best_end = -1
    for ext in SUPPORTED_FILE_EXTENSIONS:
        idx = lower.find(ext)
        if idx != -1:
            best_end = max(best_end, idx + len(ext))
    return token[:best_end] if best_end != -1 else token


def parse_file_candidates(content: str) -> list[str]:
    """Extract likely file path candidates from an LLM response.

    Candidates may be exact files (``src/foo.tsx``) or directory/module-like
    hints (``client/jetpack-connect/jetpack-new-site``).  Resolution against
    repository files happens in :func:`resolve_file_candidates`.
    """
    if not content:
        return []

    text = _fenced_or_full_text(content)
    candidates: list[str] = []
    seen: set[str] = set()

    path_token = re.compile(r"[\w@./+-]+(?:/[\w@./+-]+)+")
    for raw_line in text.splitlines():
        line = normalize_path(raw_line)
        if not line:
            continue

        tokens = [line]
        if " " in line or "\t" in line:
            tokens = path_token.findall(line)

        for token in tokens:
            token = normalize_path(_trim_to_supported_suffix(token))
            if not token or token in {".", "/"}:
                continue
            if "/" not in token and not token.lower().endswith(SUPPORTED_FILE_EXTENSIONS):
                continue
            if token not in seen:
                seen.add(token)
                candidates.append(token)

    return candidates


def _index_file_matches(candidate: str, all_files: list[str]) -> list[str]:
    prefix = candidate.rstrip("/") + "/"
    matches = [f for f in all_files if f.startswith(prefix)]
    if not matches:
        return []

    preferred = []
    for file_path in matches:
        if PurePosixPath(file_path).name in INDEX_FILE_NAMES:
            preferred.append(file_path)
    return preferred or matches


def resolve_file_candidates(
    candidates: list[str],
    all_files: list[str],
    *,
    limit: int | None = 5,
    fuzzy_cutoff: float = 0.74,
) -> list[str]:
    """Map LLM file candidates onto real repository files."""
    original_files = [
        f
        for f in all_files
        if normalize_path(f).lower().endswith(SUPPORTED_FILE_EXTENSIONS)
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
                    candidate,
                    normalized_files,
                    n=1,
                    cutoff=fuzzy_cutoff,
                )
                if matches:
                    add(matches[0])

        if limit is not None and len(resolved) >= limit:
            break

    return resolved
