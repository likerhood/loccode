"""Repository-structure backed symbol index.

LocAgent's original dependency graph is Python-AST based. For multilingual
benchmarks we already have repo_structures containing file text and lightweight
symbols. This module provides a compact, read-only index over that structure so
tools and post-processing can recover file/class/function/line evidence even
when the dependency graph is empty.
"""

from __future__ import annotations

import difflib
import json
import logging
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Iterable

from muladapter.entities.extractor import (
    CodeEntity,
    extract_entities_from_structure,
    iter_structure_files,
)
from muladapter.search_defaults import normalize_repo_path

logger = logging.getLogger(__name__)


def _structure_dir(structure_dir: str | None = None) -> str | None:
    return structure_dir or os.getenv("LOCAGENT_STRUCTURE_DIR")


def _file_text(file_node: dict[str, Any]) -> str:
    text = file_node.get("text") or ""
    if isinstance(text, str):
        return text
    if isinstance(text, list):
        return "\n".join(str(line) for line in text)
    return str(text)


def _entity_id(file_path: str, qualified_name: str) -> str:
    return f"{file_path}:{qualified_name}"


def _eval_entity_id(file_path: str, qualified_name: str) -> str:
    return f"{file_path}::{qualified_name}"


def _normalize_symbol_name(name: str) -> str:
    name = str(name or "").strip().strip("`'\"")
    name = re.sub(r"^(?:class|function|method)\s*:\s*", "", name, flags=re.I)
    return name.strip().strip("()")


@dataclass(frozen=True)
class StructureMatch:
    file_path: str
    entity: CodeEntity | None = None

    @property
    def graph_id(self) -> str:
        if self.entity is None:
            return self.file_path
        return _entity_id(self.file_path, self.entity.qualified_name)

    @property
    def eval_id(self) -> str:
        if self.entity is None:
            return self.file_path
        return _eval_entity_id(self.file_path, self.entity.qualified_name)


class StructureIndex:
    """Lookup helper around one instance's repo_structure JSON."""

    def __init__(self, instance_id: str, structure: dict[str, Any]):
        self.instance_id = instance_id
        self.structure = structure
        self.file_nodes: dict[str, dict[str, Any]] = {
            normalize_repo_path(path): node
            for path, node in iter_structure_files(structure)
        }
        self.file_texts: dict[str, str] = {
            path: _file_text(node) for path, node in self.file_nodes.items()
        }
        self.entities_by_file: dict[str, list[CodeEntity]] = {
            normalize_repo_path(path): entities
            for path, entities in extract_entities_from_structure(structure).items()
        }

    def available(self) -> bool:
        return bool(self.file_nodes)

    def list_files(self) -> list[str]:
        return sorted(self.file_nodes)

    def get_file_text(self, file_path: str) -> str:
        resolved = self.resolve_file(file_path)
        return self.file_texts.get(resolved or normalize_repo_path(file_path), "")

    def resolve_file(self, file_path: str | None) -> str | None:
        if not file_path:
            return None
        candidate = normalize_repo_path(str(file_path).strip().strip("`'\""))
        if candidate in self.file_nodes:
            return candidate
        suffix_matches = [path for path in self.file_nodes if path.endswith(candidate)]
        if len(suffix_matches) == 1:
            return suffix_matches[0]
        base = os.path.basename(candidate)
        base_matches = [path for path in self.file_nodes if os.path.basename(path) == base]
        if len(base_matches) == 1:
            return base_matches[0]
        close = difflib.get_close_matches(candidate, self.file_nodes.keys(), n=1, cutoff=0.82)
        return close[0] if close else None

    def entities_for_file(self, file_path: str) -> list[CodeEntity]:
        resolved = self.resolve_file(file_path) or normalize_repo_path(file_path)
        return list(self.entities_by_file.get(resolved, []))

    def iter_entities(self) -> Iterable[CodeEntity]:
        for entities in self.entities_by_file.values():
            yield from entities

    def resolve_graph_id(self, name: str) -> StructureMatch | None:
        name = str(name or "").strip().strip(".")
        if not name:
            return None
        if ":" in name:
            file_part, symbol_part = name.split(":", 1)
            file_path = self.resolve_file(file_part)
            if not file_path:
                return None
            if not symbol_part:
                return StructureMatch(file_path)
            entity = self.resolve_symbol(file_path, symbol_part)
            return StructureMatch(file_path, entity) if entity else None
        file_path = self.resolve_file(name)
        if file_path:
            return StructureMatch(file_path)
        symbol_name = _normalize_symbol_name(name)
        matches = [
            StructureMatch(entity.file, entity)
            for entity in self.iter_entities()
            if entity.name == symbol_name or entity.qualified_name == symbol_name
        ]
        return matches[0] if len(matches) == 1 else None

    def resolve_symbol(self, file_path: str, symbol_name: str) -> CodeEntity | None:
        resolved = self.resolve_file(file_path) or normalize_repo_path(file_path)
        symbol_name = _normalize_symbol_name(symbol_name)
        if not symbol_name:
            return None
        entities = self.entities_by_file.get(resolved, [])
        for entity in entities:
            if entity.qualified_name == symbol_name or entity.name == symbol_name:
                return entity
        lowered = symbol_name.lower()
        for entity in entities:
            if entity.qualified_name.lower() == lowered or entity.name.lower() == lowered:
                return entity
        close = difflib.get_close_matches(
            lowered,
            [entity.qualified_name.lower() for entity in entities],
            n=1,
            cutoff=0.84,
        )
        if close:
            for entity in entities:
                if entity.qualified_name.lower() == close[0]:
                    return entity
        return None

    def resolve_line(self, file_path: str, line_number: int) -> CodeEntity | None:
        resolved = self.resolve_file(file_path) or normalize_repo_path(file_path)
        candidates = [
            entity for entity in self.entities_by_file.get(resolved, [])
            if entity.start_line <= line_number <= entity.end_line
        ]
        if not candidates:
            return None
        return sorted(
            candidates,
            key=lambda entity: (
                0 if entity.kind in {"function", "method"} else 1,
                entity.end_line - entity.start_line,
                entity.start_line,
            ),
        )[0]

    def slice_text(self, file_path: str, start_line: int, end_line: int) -> str:
        text = self.get_file_text(file_path)
        if not text:
            return ""
        lines = text.splitlines()
        start = max(1, start_line)
        end = max(start, min(len(lines), end_line))
        width = len(str(end))
        return "\n".join(
            f"{str(line_no).rjust(width)} | {lines[line_no - 1]}"
            for line_no in range(start, end + 1)
        )

    def format_entity(self, match: StructureMatch, include_code: bool = True) -> str:
        if match.entity is None:
            return self.format_file_summary(match.file_path, include_code=include_code)
        entity = match.entity
        lines = [
            f"node_id: {_entity_id(match.file_path, entity.qualified_name)}",
            f"type: {'function' if entity.kind == 'method' else entity.kind}",
            f"file: {match.file_path}",
            f"name: {entity.qualified_name}",
            f"line: {entity.start_line}-{entity.end_line}",
        ]
        if include_code:
            snippet = self.slice_text(match.file_path, entity.start_line, entity.end_line)
            if snippet:
                lines.extend(["```", snippet, "```"])
        return "\n".join(lines)

    def format_file_summary(
            self,
            file_path: str,
            *,
            include_code: bool = False,
            max_symbols: int = 40,
    ) -> str:
        resolved = self.resolve_file(file_path) or normalize_repo_path(file_path)
        lines = [f"file: {resolved}"]
        entities = self.entities_by_file.get(resolved, [])
        if entities:
            lines.append("symbols:")
            for entity in entities[:max_symbols]:
                label = "function" if entity.kind == "method" else entity.kind
                lines.append(
                    f"- {label}: {entity.qualified_name} "
                    f"(line {entity.start_line}-{entity.end_line})"
                )
        if include_code:
            text = self.get_file_text(resolved)
            if text:
                lines.extend(["```", text, "```"])
        return "\n".join(lines)

    def ranked_symbols_for_file(
            self,
            file_path: str,
            problem_context: str = "",
            *,
            limit: int = 3,
    ) -> list[CodeEntity]:
        terms = {
            term.lower()
            for term in re.findall(r"[A-Za-z][A-Za-z0-9_$-]{2,}", problem_context or "")
        }
        entities = self.entities_for_file(file_path)
        if not entities:
            return []

        def score(entity: CodeEntity) -> tuple[int, int, int]:
            haystack = f"{entity.file} {entity.qualified_name}".lower()
            overlap = sum(1 for term in terms if term in haystack)
            kind_bonus = 2 if entity.kind in {"function", "method"} else 1
            return (overlap, kind_bonus, -entity.start_line)

        return sorted(entities, key=score, reverse=True)[:limit]


@lru_cache(maxsize=512)
def load_structure_index(instance_id: str, structure_dir: str | None = None) -> StructureIndex | None:
    directory = _structure_dir(structure_dir)
    if not directory or not instance_id:
        return None
    structure_path = os.path.join(directory, f"{instance_id}.json")
    if not os.path.exists(structure_path):
        return None
    try:
        with open(structure_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        structure = payload.get("structure", payload)
        index = StructureIndex(instance_id, structure)
        return index if index.available() else None
    except Exception as exc:
        logger.warning("Failed to load structure index for %s: %s", instance_id, exc)
        return None
