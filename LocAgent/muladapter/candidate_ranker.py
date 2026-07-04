"""Collect and rank repository file candidates observed during localization."""

from __future__ import annotations

import re
from collections import Counter

from muladapter.entities.structure_index import load_structure_index
from muladapter.search_defaults import is_source_file, normalize_repo_path


_FILE_CANDIDATE_RE = re.compile(
    r"[\w@.+/-]+\.(?:tsx|jsx|mjs|cjs|hpp|cpp|scss|less|html|java|scala|swift|svelte|vue|ts|js|py|kt|go|rs|cc|cs|php|rb|css|c|h)"
    r"(?::impl(?::\d+)?)?"
)


def _clean_file_candidate(path: str) -> str:
    path = normalize_repo_path(path)
    path = path.strip().strip("`'\"")
    path = re.sub(r":impl(?::\d+)?$", "", path)
    return normalize_repo_path(path).rstrip(".,;:")


def _looks_like_tool_or_environment_path(path: str) -> bool:
    normalized = normalize_repo_path(path)
    lowered = normalized.lower()
    blocked_parts = (
        "loccode/locagent/",
        "plugins/location_tools/",
        "miniconda",
        "site-packages/",
        "__pycache__/",
    )
    if lowered.startswith(("home/", "users/", "usr/", "opt/", "var/", "tmp/")):
        return True
    return any(part in lowered for part in blocked_parts)


def extract_file_candidates(text: str) -> list[str]:
    """Extract source file paths from model messages and tool observations."""
    if not text:
        return []

    candidates: list[str] = []
    seen: set[str] = set()
    for match in _FILE_CANDIDATE_RE.finditer(text):
        path = _clean_file_candidate(match.group(0))
        if not path or "/" not in path or not is_source_file(path):
            continue
        if _looks_like_tool_or_environment_path(path):
            continue
        if path not in seen:
            seen.add(path)
            candidates.append(path)
    return candidates


def _problem_terms(problem_statement: str) -> set[str]:
    terms = {
        term.lower()
        for term in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", problem_statement or "")
    }
    stop = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "this",
        "that",
        "when",
        "what",
        "instead",
        "expected",
        "happened",
        "context",
        "source",
        "image",
        "visual",
        "issue",
        "problem",
    }
    return {term for term in terms if term not in stop}


def rank_file_candidates(
    candidates: list[str],
    problem_statement: str = "",
    *,
    limit: int = 15,
) -> list[str]:
    """Rank observed file candidates by frequency and lexical overlap with the issue."""
    if not candidates:
        return []

    cleaned_candidates = [
        _clean_file_candidate(candidate)
        for candidate in candidates
    ]
    counts = Counter(
        candidate for candidate in cleaned_candidates
        if candidate and not _looks_like_tool_or_environment_path(candidate)
    )
    if not counts:
        return []
    terms = _problem_terms(problem_statement)

    def score(path: str) -> tuple[int, int, int, str]:
        lowered = path.lower()
        overlap = sum(1 for term in terms if term in lowered)
        depth_bonus = lowered.count("/")
        return (counts[path], overlap, depth_bonus, path)

    ranked = sorted(counts, key=score, reverse=True)
    return ranked[:limit]


def format_ranked_candidates(
    candidates: list[str],
    problem_statement: str = "",
    *,
    limit: int = 15,
) -> str:
    ranked = rank_file_candidates(candidates, problem_statement, limit=limit)
    if not ranked:
        return ""
    return "```\n" + "\n\n".join(ranked) + "\n```"


def format_ranked_symbol_candidates(
    candidates: list[str],
    problem_statement: str = "",
    *,
    instance_id: str | None = None,
    limit: int = 15,
) -> str:
    """Format fallback locations with best-effort symbols and lines."""
    structure_index = load_structure_index(instance_id) if instance_id else None
    if structure_index:
        resolved_candidates: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            if _looks_like_tool_or_environment_path(candidate):
                continue
            resolved = structure_index.resolve_file(candidate)
            if resolved and resolved not in seen:
                seen.add(resolved)
                resolved_candidates.append(resolved)
        candidates = resolved_candidates
    else:
        candidates = [
            candidate for candidate in candidates
            if not _looks_like_tool_or_environment_path(candidate)
        ]

    ranked = rank_file_candidates(candidates, problem_statement, limit=limit)
    if not ranked:
        return ""

    blocks: list[str] = []
    for file_path in ranked:
        if not structure_index:
            blocks.append(file_path)
            continue
        resolved = structure_index.resolve_file(file_path) or file_path
        symbols = structure_index.ranked_symbols_for_file(
            resolved,
            problem_statement,
            limit=2,
        )
        if not symbols:
            blocks.append(resolved)
            continue
        lines = [resolved]
        for symbol in symbols:
            label = "class" if symbol.kind == "class" else "function"
            lines.append(f"{label}: {symbol.qualified_name}")
            lines.append(f"line: {symbol.start_line}")
        blocks.append("\n".join(lines))

    return "```\n" + "\n\n".join(blocks) + "\n```"
