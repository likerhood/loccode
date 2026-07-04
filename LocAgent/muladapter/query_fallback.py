"""Fallback query generation for malformed LocAgent tool calls."""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Any


STOPWORDS = {
    "about",
    "after",
    "again",
    "because",
    "before",
    "being",
    "between",
    "could",
    "description",
    "error",
    "expected",
    "from",
    "github",
    "have",
    "instead",
    "issue",
    "problem",
    "should",
    "that",
    "their",
    "there",
    "these",
    "this",
    "through",
    "when",
    "where",
    "while",
    "with",
    "would",
}


def _ordered_add(values: list[str], seen: set[str], value: str) -> None:
    value = value.strip().strip("`'\"").strip()
    if len(value) < 3:
        return
    key = value.lower()
    if key not in seen and key not in STOPWORDS:
        seen.add(key)
        values.append(value)


def issue_text(instance: dict[str, Any] | None) -> str:
    if not instance:
        return ""
    parts = [
        str(instance.get("problem_statement") or ""),
        str(instance.get("title") or ""),
        str(instance.get("description") or ""),
    ]
    return "\n".join(part for part in parts if part)


def fallback_search_terms(instance: dict[str, Any] | None, *, limit: int = 8) -> list[str]:
    text = issue_text(instance)
    if not text:
        return []
    terms: list[str] = []
    seen: set[str] = set()

    for match in re.findall(r"`([^`]{3,120})`", text):
        _ordered_add(terms, seen, match)

    for match in re.findall(r"(/[A-Za-z0-9_./{}:-]{3,})", text):
        _ordered_add(terms, seen, match)
        for part in PurePosixPath(match).parts:
            _ordered_add(terms, seen, part)

    for match in re.findall(r"[A-Za-z_$][A-Za-z0-9_$]*(?:[-_/][A-Za-z0-9_$]+)+", text):
        _ordered_add(terms, seen, match)
        for part in re.split(r"[-_/]", match):
            _ordered_add(terms, seen, part)

    for match in re.findall(r"[A-Z][A-Za-z0-9_$]{3,}|[a-z][A-Za-z0-9_$]{3,}", text):
        _ordered_add(terms, seen, match)

    return terms[:limit]


def empty_search_hint(instance: dict[str, Any] | None) -> str:
    terms = fallback_search_terms(instance)
    if terms:
        return (
            "search_code_snippets was called without search_terms or line_nums. "
            f"Auto-filled search_terms from the issue context: {terms!r}.\n"
        )
    return (
        "Invalid search_code_snippets call: provide search_terms or line_nums. "
        "For JS/TS repositories, use file_path_or_pattern='**/*' or a specific JS/TS glob.\n"
    )
