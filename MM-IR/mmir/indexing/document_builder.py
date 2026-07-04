from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mmir.indexing.entities import extract_entities_from_structure, is_indexable_code_path, iter_structure_files
from mmir.schema import CodeEntity, Document, Sample


def load_structure(structure_dir: str | Path, instance_id: str) -> dict[str, Any]:
    path = Path(structure_dir) / f"{instance_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Structure file not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload["structure"]


def entity_id(entity: CodeEntity) -> str:
    return f"{entity.file}::{entity.qualified_name}"


def module_id(entity: CodeEntity) -> str:
    if entity.kind == "class":
        return f"{entity.file}::{entity.qualified_name}"
    if "." in entity.qualified_name:
        return f"{entity.file}::{entity.qualified_name.rsplit('.', 1)[0]}"
    return entity.file


def _snippet(text: str, start: int, end: int, *, max_chars: int = 4000) -> str:
    lines = text.splitlines()
    selected = "\n".join(lines[max(start - 1, 0): max(end, start)])
    return selected[:max_chars]


def _file_doc_text(file_path: str, file_node: dict[str, Any], entities: list[CodeEntity]) -> str:
    text = file_node.get("text") or ""
    entity_names = " ".join(entity.qualified_name for entity in entities)
    return "\n".join([
        file_path,
        Path(file_path).name,
        entity_names,
        str(text)[:12000],
    ])


def build_documents(sample: Sample, structure_dir: str | Path) -> tuple[list[Document], dict[str, list[CodeEntity]]]:
    structure = load_structure(structure_dir, sample.instance_id)
    entities_by_file = extract_entities_from_structure(structure)
    docs: list[Document] = []
    for file_path, file_node in iter_structure_files(structure):
        if not is_indexable_code_path(file_path):
            continue
        text = file_node.get("text") or ""
        entities = entities_by_file.get(file_path, [])
        docs.append(
            Document(
                doc_id=f"file::{file_path}",
                level="file",
                file=file_path,
                text=_file_doc_text(file_path, file_node, entities),
                metadata={"repo": sample.repo},
            )
        )
        if entities:
            docs.append(
                Document(
                    doc_id=f"module::{file_path}",
                    level="module",
                    file=file_path,
                    symbol=file_path,
                    text="\n".join([file_path, " ".join(entity.qualified_name for entity in entities), str(text)[:6000]]),
                    metadata={"module_id": file_path},
                )
            )
        for entity in entities:
            doc_level = "module" if entity.kind == "class" else "function"
            doc_id = f"{doc_level}::{entity_id(entity)}"
            docs.append(
                Document(
                    doc_id=doc_id,
                    level=doc_level,
                    file=file_path,
                    symbol=entity.qualified_name,
                    text="\n".join([
                        file_path,
                        entity.name,
                        entity.qualified_name,
                        _snippet(str(text), entity.start_line, entity.end_line),
                    ]),
                    start_line=entity.start_line,
                    end_line=entity.end_line,
                    metadata={
                        "kind": entity.kind,
                        "entity_id": entity_id(entity),
                        "module_id": module_id(entity),
                        "language": entity.language,
                    },
                )
            )
    return docs, entities_by_file
