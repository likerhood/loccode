"""Build LocAgent-compatible graphs for multilingual repositories."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import networkx as nx

from dependency_graph.build_graph import (
    EDGE_TYPE_CONTAINS,
    NODE_TYPE_CLASS,
    NODE_TYPE_DIRECTORY,
    NODE_TYPE_FILE,
    NODE_TYPE_FUNCTION,
)
from muladapter.entities.extractor import CodeEntity, extract_entities_from_structure_file
from muladapter.search_defaults import is_source_file, normalize_repo_path

logger = logging.getLogger(__name__)

SKIP_DIRS = {".git", "node_modules", "dist", "build", "__pycache__", ".venv", "venv"}


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None
    except OSError as exc:
        logger.debug("Failed to read %s: %s", path, exc)
        return None


def _entity_code(text: str, entity: CodeEntity) -> str:
    lines = text.splitlines()
    start = max(1, entity.start_line)
    end = max(start, min(len(lines), entity.end_line))
    return "\n".join(lines[start - 1:end])


def _add_directory_chain(graph: nx.MultiDiGraph, file_path: str) -> None:
    graph.add_node("/", type=NODE_TYPE_DIRECTORY)
    parent = "/"
    parts = file_path.split("/")[:-1]
    current = ""
    for part in parts:
        current = f"{current}/{part}" if current else part
        if current not in graph:
            graph.add_node(current, type=NODE_TYPE_DIRECTORY)
        graph.add_edge(parent, current, type=EDGE_TYPE_CONTAINS)
        parent = current
    graph.add_edge(parent, file_path, type=EDGE_TYPE_CONTAINS)


def _add_file(graph: nx.MultiDiGraph, file_path: str, text: str) -> None:
    line_count = max(1, len(text.split("\n")))
    graph.add_node(
        file_path,
        type=NODE_TYPE_FILE,
        code=text,
        start_line=1,
        end_line=line_count,
    )
    _add_directory_chain(graph, file_path)


def _add_entity(graph: nx.MultiDiGraph, file_path: str, text: str, entity: CodeEntity) -> None:
    node_type = NODE_TYPE_CLASS if entity.kind == "class" else NODE_TYPE_FUNCTION
    node_id = f"{file_path}:{entity.qualified_name}"
    graph.add_node(
        node_id,
        type=node_type,
        code=_entity_code(text, entity),
        start_line=entity.start_line,
        end_line=entity.end_line,
    )
    parent_id = file_path
    if "." in entity.qualified_name:
        class_name = entity.qualified_name.split(".", 1)[0]
        class_id = f"{file_path}:{class_name}"
        if class_id in graph:
            parent_id = class_id
    graph.add_edge(parent_id, node_id, type=EDGE_TYPE_CONTAINS)


def _iter_repo_files(repo_dir: Path):
    for path in sorted(repo_dir.rglob("*")):
        if not path.is_file() or any(part in SKIP_DIRS for part in path.parts):
            continue
        rel_path = normalize_repo_path(path.relative_to(repo_dir).as_posix())
        if not is_source_file(rel_path):
            continue
        text = _read_text(path)
        if text is not None:
            yield rel_path, text


def build_multilang_graph(repo_dir: str | os.PathLike) -> nx.MultiDiGraph:
    """Build a lightweight graph for Python/JS/TS/etc. source files.

    The graph intentionally emits the same node and edge types as
    dependency_graph.build_graph so existing LocAgent searchers keep working.
    Dependency edges beyond containment are not inferred here; this fallback is
    for localization symbols and code retrieval, not whole-program analysis.
    """
    repo_path = Path(repo_dir)
    graph = nx.MultiDiGraph()
    graph.add_node("/", type=NODE_TYPE_DIRECTORY)

    for file_path, text in _iter_repo_files(repo_path):
        _add_file(graph, file_path, text)
        file_node = {
            "text": text,
            "classes": [],
            "functions": [],
        }
        entities = extract_entities_from_structure_file(file_path, file_node)
        for entity in entities:
            _add_entity(graph, file_path, text, entity)

    logger.info(
        "Built multilingual graph for %s: nodes=%s edges=%s",
        repo_path,
        graph.number_of_nodes(),
        graph.number_of_edges(),
    )
    return graph
