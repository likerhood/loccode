#!/usr/bin/env python3
"""Normalize CoSIL file-level outputs for multi-language benchmarks."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from muladapter.path_resolver import parse_file_candidates, resolve_file_candidates
from muladapter.entities.extractor import CodeEntity, extract_entities_from_structure


def terms(text: str) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"[A-Za-z_$][A-Za-z0-9_$]{2,}", text or "")
        if token.lower() not in {"the", "and", "for", "with", "this", "that", "from", "function", "class"}
    }


def entity_id(entity: CodeEntity) -> str:
    return f"{entity.file}::{entity.qualified_name}"


def module_id(entity: CodeEntity) -> str:
    if entity.kind == "class":
        return f"{entity.file}::{entity.qualified_name}"
    if "." in entity.qualified_name:
        return f"{entity.file}::{entity.qualified_name.rsplit('.', 1)[0]}"
    return entity.file


def ordered_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def rank_entities(entities: list[CodeEntity], context: str, limit: int = 15) -> list[CodeEntity]:
    context_terms = terms(context)
    scored = []
    for index, entity in enumerate(entities):
        name_terms = terms(f"{entity.file} {entity.name} {entity.qualified_name}")
        score = len(context_terms & name_terms)
        if entity.name and entity.name in context:
            score += 3
        if entity.qualified_name and entity.qualified_name in context:
            score += 5
        scored.append((score, -(entity.end_line - entity.start_line), -index, entity.start_line, entity))
    scored.sort(key=lambda item: item[:4], reverse=True)
    return [item[-1] for item in scored[:limit]]


def load_repo_files(structure_path: Path) -> list[str]:
    data = json.loads(structure_path.read_text())
    structure = data["structure"]
    files: list[str] = []

    def walk(node: dict, prefix: str = "") -> None:
        for name, content in node.items():
            path = f"{prefix}/{name}" if prefix else name
            if isinstance(content, dict) and "text" in content:
                files.append(path)
            elif isinstance(content, dict):
                walk(content, path)

    walk(structure)
    return files


def normalize_row(row: dict, structure_dir: Path, *, force: bool = False) -> dict:
    found_files = row.get("found_files") or []
    instance_id = row.get("instance_id")
    if not instance_id:
        return row

    structure_path = structure_dir / f"{instance_id}.json"
    if not structure_path.exists():
        return row

    response = (row.get("file_traj") or {}).get("response", "")

    all_files = load_repo_files(structure_path)
    if not found_files or force:
        candidates = parse_file_candidates(response)
        resolved = resolve_file_candidates(candidates, all_files, limit=5) if candidates else []
    else:
        resolved = resolve_file_candidates(found_files, all_files, limit=max(5, len(found_files)))

    if resolved and (force or not found_files):
        row["found_files"] = resolved
        artifact = row.setdefault("normalization_artifact", {})
        artifact["raw_candidates"] = candidates[:10] if "candidates" in locals() else found_files[:10]
        artifact["source"] = "file_traj.response"
    elif resolved:
        row["found_files"] = resolved

    if row.get("found_files") and (force or not row.get("found_modules") or not row.get("found_functions")):
        try:
            structure = json.loads(structure_path.read_text())["structure"]
            entities_by_file = extract_entities_from_structure(structure)
            candidate_entities: list[CodeEntity] = []
            for file_path in row.get("found_files") or []:
                candidate_entities.extend(entities_by_file.get(file_path, []))
            ranked = rank_entities(candidate_entities, response, limit=15)
            if force or not row.get("found_modules"):
                row["found_modules"] = ordered_unique([module_id(entity) for entity in ranked])[:15]
            if force or not row.get("found_functions"):
                row["found_functions"] = ordered_unique(
                    [entity_id(entity) for entity in ranked if entity.kind in {"function", "method"}]
                )[:15]
            artifact = row.setdefault("normalization_artifact", {})
            artifact["symbol_source"] = "repo_structures"
        except Exception as exc:
            artifact = row.setdefault("normalization_artifact", {})
            artifact["symbol_error"] = str(exc)
    return row


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--structure-dir", required=True)
    parser.add_argument("--output", default="")
    parser.add_argument("--force", action="store_true", help="recompute found_files even when they are already non-empty")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else input_path
    structure_dir = Path(args.structure_dir)

    rows = []
    for line in input_path.read_text(errors="ignore").splitlines():
        if not line.strip():
            continue
        rows.append(normalize_row(json.loads(line), structure_dir, force=args.force))

    if output_path == input_path:
        with NamedTemporaryFile("w", delete=False, dir=str(input_path.parent)) as tmp:
            tmp_path = Path(tmp.name)
            for row in rows:
                tmp.write(json.dumps(row) + "\n")
        tmp_path.replace(input_path)
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w") as f:
            for row in rows:
                f.write(json.dumps(row) + "\n")

    nonempty = sum(bool(row.get("found_files")) for row in rows)
    print(f"Normalized {len(rows)} rows; non-empty found_files: {nonempty}")


if __name__ == "__main__":
    main()
