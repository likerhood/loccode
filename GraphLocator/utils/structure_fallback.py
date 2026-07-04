"""Supplement GraphLocator file predictions with structure-derived symbols."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from muladapter.entities.extractor import CodeEntity, extract_entities_from_structure


def _normalize(path: Any, repo: Any = "") -> str:
    text = str(path or "").strip().replace("\\", "/").lstrip("./")
    if text.startswith(("a/", "b/")):
        text = text[2:]
    repo_leaf = str(repo or "").strip().replace("\\", "/").rstrip("/").split("/")[-1]
    if repo_leaf and text.startswith(f"{repo_leaf}/"):
        text = text[len(repo_leaf) + 1:]
    return text


def _entity_id(entity: CodeEntity) -> str:
    return f"{entity.file}::{entity.qualified_name}"


def _module_id(entity: CodeEntity) -> str:
    if entity.kind == "class":
        return f"{entity.file}::{entity.qualified_name}"
    if "." in entity.qualified_name:
        return f"{entity.file}::{entity.qualified_name.rsplit('.', 1)[0]}"
    return entity.file


def _terms(text: str) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"[A-Za-z_$][A-Za-z0-9_$]{2,}", text or "")
        if token.lower()
        not in {"the", "and", "for", "with", "this", "that", "from", "function", "class"}
    }


def _ordered_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def _rank_entities(entities: list[CodeEntity], context: str, limit: int) -> list[CodeEntity]:
    context_terms = _terms(context)
    scored = []
    for entity in entities:
        name_terms = _terms(f"{entity.name} {entity.qualified_name} {entity.file}")
        score = len(context_terms & name_terms)
        if entity.name and entity.name in context:
            score += 3
        if entity.qualified_name and entity.qualified_name in context:
            score += 5
        if entity.kind in {"function", "method"}:
            score += 1
        scored.append((score, -entity.start_line, entity))
    scored.sort(key=lambda item: item[:2], reverse=True)
    return [item[-1] for item in scored[:limit]]


def _rank_files(entities_by_file: dict[str, list[CodeEntity]], context: str, limit: int) -> list[str]:
    context_terms = _terms(context)
    scored: list[tuple[int, str]] = []
    for file_path, entities in entities_by_file.items():
        file_terms = _terms(file_path)
        symbol_terms: set[str] = set()
        for entity in entities[:200]:
            symbol_terms |= _terms(f"{entity.name} {entity.qualified_name}")
        score = len(context_terms & file_terms) * 3 + len(context_terms & symbol_terms)
        if file_path and file_path in context:
            score += 8
        scored.append((score, file_path))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [file_path for score, file_path in scored[:limit] if file_path and score > 0]


def supplement_results_with_structure(
    results: dict[str, list[str]],
    issue: dict[str, Any],
    structure_dir: str | Path | None,
    *,
    limit: int = 15,
) -> dict[str, list[str]]:
    if not structure_dir:
        return results
    structure_path = Path(structure_dir) / f"{issue.get('instance_id')}.json"
    if not structure_path.exists():
        return results

    try:
        payload = json.loads(structure_path.read_text(encoding="utf-8"))
        entities_by_file = extract_entities_from_structure(payload["structure"])
    except Exception as exc:
        print(f"Structure fallback failed for {issue.get('instance_id')}: {exc}")
        return results

    repo = issue.get("repo", "")
    files = [_normalize(path, repo) for path in results.get("found_files", [])]
    context = str(issue.get("problem_statement") or "")
    if not files:
        files = _rank_files(entities_by_file, context, limit=limit)
    results["found_files"] = _ordered_unique(files)

    candidate_entities: list[CodeEntity] = []
    for file_path in results["found_files"]:
        candidate_entities.extend(entities_by_file.get(file_path, []))
    if not candidate_entities:
        return results

    ranked = _rank_entities(candidate_entities, context, limit=limit)

    modules = list(results.get("found_modules") or [])
    functions = list(results.get("found_functions") or [])
    modules.extend(_module_id(entity) for entity in ranked)
    functions.extend(
        _entity_id(entity)
        for entity in ranked
        if entity.kind in {"function", "method"}
    )
    results["found_modules"] = _ordered_unique(modules)[:limit]
    results["found_functions"] = _ordered_unique(functions)[:limit]
    return results
