#!/usr/bin/env python3
"""Build clean subsets for three-level localization evaluation.

The default "three-level" policy keeps samples whose gold file/module/function
counts are all within [1, max_gold]. This is useful when Acc@15 should not be
penalized by samples whose gold set itself is larger than 15, and when
module/function gold is unmappable under the current repo_structures.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
LOCAGENT_ROOT = ROOT_DIR / "LocAgent"
EXTRACTOR_PATH = LOCAGENT_ROOT / "muladapter/entities/extractor.py"
spec = importlib.util.spec_from_file_location("locagent_entity_extractor", EXTRACTOR_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Cannot load entity extractor: {EXTRACTOR_PATH}")
extractor = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = extractor
spec.loader.exec_module(extractor)

CodeEntity = extractor.CodeEntity
entities_overlapping_lines = extractor.entities_overlapping_lines
extract_entities_from_structure_file = extractor.extract_entities_from_structure_file


PATCH_HEADER_RE = re.compile(r"^\+\+\+ b/(.+)$")
DIFF_HEADER_RE = re.compile(r"^diff --git a/(.*?) b/(.*?)$")
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def normalize(path: Any) -> str:
    text = str(path or "").strip().replace("\\", "/")
    if text.startswith(("a/", "b/")):
        text = text[2:]
    return text.lstrip("./")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def ordered_unique(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = normalize(value)
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def patch_files(patch: str) -> list[str]:
    files: list[str] = []
    for line in str(patch or "").splitlines():
        match = DIFF_HEADER_RE.match(line)
        if match:
            files.append(normalize(match.group(2)))
            continue
        match = PATCH_HEADER_RE.match(line)
        if match:
            files.append(normalize(match.group(1)))
    return ordered_unique(files)


def sample_files(row: dict[str, Any]) -> list[str]:
    values = row.get("files")
    if isinstance(values, list):
        files = [normalize(value) for value in values if normalize(value)]
    else:
        files = []
    if not files:
        files = patch_files(row.get("patch", ""))
    return ordered_unique(files)


def parse_changed_old_lines(patch: str) -> dict[str, set[int]]:
    current_file = ""
    old_line = 0
    changed: dict[str, set[int]] = {}
    for line in str(patch or "").splitlines():
        file_match = PATCH_HEADER_RE.match(line)
        if file_match:
            current_file = normalize(file_match.group(1))
            changed.setdefault(current_file, set())
            continue
        hunk_match = HUNK_RE.match(line)
        if hunk_match:
            old_line = int(hunk_match.group(1))
            continue
        if not current_file or line.startswith(("diff --git", "--- ")):
            continue
        if line.startswith("-") and not line.startswith("---"):
            changed[current_file].add(max(1, old_line))
            old_line += 1
        elif line.startswith("+") and not line.startswith("+++"):
            changed[current_file].add(max(1, old_line))
        else:
            old_line += 1
    return changed


def entity_id(entity: CodeEntity) -> str:
    return f"{entity.file}::{entity.qualified_name}"


def module_id(entity: CodeEntity) -> str:
    if entity.kind == "class":
        return f"{entity.file}::{entity.qualified_name}"
    if "." in entity.qualified_name:
        return f"{entity.file}::{entity.qualified_name.rsplit('.', 1)[0]}"
    return entity.file


def structure_file_node(structure: dict[str, Any], file_path: str) -> dict[str, Any] | None:
    parts = [part for part in normalize(file_path).split("/") if part]
    node: Any = structure
    for part in parts:
        if not isinstance(node, dict) or part not in node:
            node = None
            break
        node = node[part]
    if isinstance(node, dict) and "text" in node:
        return node

    target = normalize(file_path)
    found: dict[str, Any] | None = None

    def walk(current: Any, prefix: str = "") -> None:
        nonlocal found
        if found is not None or not isinstance(current, dict):
            return
        if "text" in current and normalize(prefix) == target:
            found = current
            return
        for name, child in current.items():
            if name in {"text", "classes", "functions"}:
                continue
            next_prefix = f"{prefix}/{name}" if prefix else str(name)
            walk(child, next_prefix)

    walk(structure)
    return found


def compute_gold_entities(instance_id: str, patch: str, structure_dir: Path) -> tuple[set[str], set[str], list[str]]:
    structure_path = structure_dir / f"{instance_id}.json"
    warnings: list[str] = []
    if not structure_path.exists():
        return set(), set(), ["missing_structure"]
    try:
        payload = json.loads(structure_path.read_text(encoding="utf-8", errors="ignore"))
        structure = payload.get("structure", payload)
    except Exception as exc:
        return set(), set(), [f"bad_structure:{type(exc).__name__}"]

    changed_lines = parse_changed_old_lines(patch)
    gt_modules: set[str] = set()
    gt_functions: set[str] = set()
    for file_path, lines in changed_lines.items():
        file_node = structure_file_node(structure, file_path)
        if not file_node:
            warnings.append(f"missing_file_node:{file_path}")
            continue
        try:
            entities = extract_entities_from_structure_file(file_path, file_node)
        except Exception as exc:
            warnings.append(f"extract_failed:{file_path}:{type(exc).__name__}")
            continue
        overlaps = entities_overlapping_lines(entities, lines)
        for entity in overlaps:
            if entity.kind == "class":
                gt_modules.add(module_id(entity))
            elif entity.kind in {"function", "method"}:
                gt_functions.add(entity_id(entity))
                gt_modules.add(module_id(entity))
    return gt_modules, gt_functions, warnings


def clean_predicate(mode: str, file_count: int, module_count: int, function_count: int, max_gold: int) -> bool:
    file_ok = 1 <= file_count <= max_gold
    module_ok = 1 <= module_count <= max_gold
    function_ok = 1 <= function_count <= max_gold
    if mode == "file":
        return file_ok
    if mode == "entity":
        return module_ok and function_ok
    if mode == "three-level":
        return file_ok and module_ok and function_ok
    raise ValueError(f"Unsupported clean mode: {mode}")


def exclusion_reasons(file_count: int, module_count: int, function_count: int, max_gold: int) -> list[str]:
    reasons: list[str] = []
    if file_count == 0:
        reasons.append("file_zero")
    if file_count > max_gold:
        reasons.append("file_gt_max")
    if module_count == 0:
        reasons.append("module_zero")
    if module_count > max_gold:
        reasons.append("module_gt_max")
    if function_count == 0:
        reasons.append("function_zero")
    if function_count > max_gold:
        reasons.append("function_gt_max")
    return reasons


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build clean samples for three-level localization re-evaluation.")
    parser.add_argument("--samples", required=True, help="Original samples.jsonl.")
    parser.add_argument("--structure-dir", required=True, help="repo_structures directory for the same samples.")
    parser.add_argument("--output-prefix", required=True, help="Output prefix, e.g. clean_subsets/swe60.clean15.")
    parser.add_argument(
        "--mode",
        choices=("file", "entity", "three-level"),
        default="three-level",
        help="Clean policy. Default keeps samples whose file/module/function gold counts are all 1..max_gold.",
    )
    parser.add_argument("--max-gold", type=int, default=15, help="Maximum allowed gold count for each evaluated level.")
    parser.add_argument("--write-diagnostic", action="store_true", help="Also write the excluded samples JSONL.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    samples_path = Path(args.samples).resolve()
    structure_dir = Path(args.structure_dir).resolve()
    output_prefix = Path(args.output_prefix).resolve()
    rows = load_jsonl(samples_path)

    kept: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    per_sample: list[dict[str, Any]] = []
    reason_counter: Counter[str] = Counter()
    total_counter: Counter[str] = Counter()

    for row in rows:
        instance_id = str(row.get("instance_id", ""))
        files = sample_files(row)
        modules, functions, warnings = compute_gold_entities(instance_id, row.get("patch", ""), structure_dir)
        file_count = len(files)
        module_count = len(modules)
        function_count = len(functions)
        reasons = exclusion_reasons(file_count, module_count, function_count, args.max_gold)
        is_clean = clean_predicate(args.mode, file_count, module_count, function_count, args.max_gold)

        fixed_row = dict(row)
        if not fixed_row.get("files") and files:
            fixed_row["files"] = files
        record = {
            "instance_id": instance_id,
            "repo": row.get("repo", ""),
            "gold_file_count": file_count,
            "gold_module_count": module_count,
            "gold_function_count": function_count,
            "clean": is_clean,
            "reasons": reasons,
            "warnings": warnings,
        }
        per_sample.append(record)
        if is_clean:
            kept.append(fixed_row)
        else:
            excluded_row = dict(fixed_row)
            excluded_row["_clean15"] = record
            excluded.append(excluded_row)
            for reason in reasons or ["excluded_by_policy"]:
                reason_counter[reason] += 1
        for reason in reasons:
            total_counter[reason] += 1

    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    samples_out = Path(str(output_prefix) + ".samples.jsonl")
    ids_out = Path(str(output_prefix) + ".ids.txt")
    excluded_out = Path(str(output_prefix) + ".excluded.jsonl")
    per_sample_out = Path(str(output_prefix) + ".per_sample.jsonl")
    manifest_out = Path(str(output_prefix) + ".manifest.json")

    write_jsonl(samples_out, kept)
    ids_out.write_text("\n".join(str(row["instance_id"]) for row in kept) + ("\n" if kept else ""), encoding="utf-8")
    write_jsonl(per_sample_out, per_sample)
    if args.write_diagnostic:
        write_jsonl(excluded_out, excluded)

    manifest = {
        "samples": str(samples_path),
        "structure_dir": str(structure_dir),
        "mode": args.mode,
        "max_gold": args.max_gold,
        "total": len(rows),
        "kept": len(kept),
        "excluded": len(excluded),
        "reason_counts_for_excluded": dict(sorted(reason_counter.items())),
        "reason_counts_all_samples": dict(sorted(total_counter.items())),
        "outputs": {
            "samples": str(samples_out),
            "ids": str(ids_out),
            "per_sample": str(per_sample_out),
            "excluded": str(excluded_out) if args.write_diagnostic else "",
        },
    }
    manifest_out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"[clean-subset] total={len(rows)} kept={len(kept)} excluded={len(excluded)}")
    print(f"[clean-subset] samples:  {samples_out}")
    print(f"[clean-subset] ids:      {ids_out}")
    print(f"[clean-subset] manifest: {manifest_out}")
    if args.write_diagnostic:
        print(f"[clean-subset] excluded: {excluded_out}")


if __name__ == "__main__":
    main()
