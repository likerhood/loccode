#!/usr/bin/env python3
"""Strictly evaluate GALA localization-only artifacts.

The native GALA artifacts are staged file candidates.  When repository
structures are available, this script derives module/function predictions from
those files with the same lightweight entity-overlap protocol used by the other
localization baselines.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

from mytest_utils import (
    acc_at_k,
    average_precision,
    normalize_file_path,
    ordered_unique,
    reciprocal_rank,
    summarize_metrics,
    write_csv,
    write_json,
)


TOP_K_VALUES = tuple(range(1, 16))
RANK_METRIC_K = 15
SET_METRIC_K_VALUES = ("8", "10", "15", "all")
STAGES = ("snapshot_seed", "code_seed", "matched", "edit_target", "final")
PATCH_HEADER_RE = re.compile(r"^\+\+\+ b/(.+)$")
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


@dataclass(frozen=True)
class CodeEntity:
    file: str
    kind: str
    name: str
    qualified_name: str
    start_line: int
    end_line: int


def predictions_at_cutoff(predictions: Sequence[str], cutoff: str) -> List[str]:
    if cutoff == "all":
        return list(predictions)
    return list(predictions[: int(cutoff)])


def strict_acc_at_k(predictions: Sequence[str], gt_values: Sequence[str], k: int) -> float:
    pred_set = set(ordered_unique(predictions_at_cutoff(predictions, str(k))))
    gt_set = {normalize_file_path(item) for item in gt_values if normalize_file_path(item)}
    return float(bool(gt_set) and gt_set <= pred_set)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-dir", required=True)
    parser.add_argument("--gt-file", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--loc-output", default="")
    parser.add_argument("--samples", default="", help="Prepared samples JSON/JSONL with patches.")
    parser.add_argument(
        "--structure-dir",
        default="",
        help="Directory containing repo_structures/<instance_id>.json for three-level evaluation.",
    )
    return parser.parse_args()


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as infile:
        return json.load(infile)


def load_samples(path: str) -> Dict[str, Dict[str, Any]]:
    if not path:
        return {}
    sample_path = Path(path)
    if not sample_path.exists():
        return {}
    if sample_path.suffix == ".jsonl":
        rows = []
        with sample_path.open(encoding="utf-8") as infile:
            for line in infile:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        return {str(row.get("instance_id")): row for row in rows if row.get("instance_id")}
    payload = load_json(sample_path)
    if isinstance(payload, dict):
        return {
            str(instance_id): dict(row, instance_id=str(instance_id))
            for instance_id, row in payload.items()
            if isinstance(row, dict)
        }
    if isinstance(payload, list):
        return {str(row.get("instance_id")): row for row in payload if isinstance(row, dict) and row.get("instance_id")}
    return {}


def collect_key_recursively(obj: Any, key: str) -> List[Any]:
    found: List[Any] = []
    if isinstance(obj, dict):
        for item_key, value in obj.items():
            if item_key == key:
                found.append(value)
            found.extend(collect_key_recursively(value, key))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(collect_key_recursively(item, key))
    return found


def flatten_file_values(values: Iterable[Any]) -> List[str]:
    files: List[str] = []
    for value in values:
        if isinstance(value, str):
            files.append(value)
        elif isinstance(value, dict):
            for key in ("file", "path", "filename"):
                if value.get(key):
                    files.append(str(value[key]))
        elif isinstance(value, list):
            files.extend(flatten_file_values(value))
    return ordered_unique(files)


def flatten_symbol_values(values: Iterable[Any], symbol_key: str) -> List[Dict[str, str]]:
    symbols: List[Dict[str, str]] = []
    for value in values:
        if isinstance(value, dict):
            file_path = normalize_file_path(value.get("file") or value.get("path") or value.get("filename"))
            symbol_name = str(value.get(symbol_key) or value.get("name") or "").strip()
            if file_path and symbol_name:
                symbols.append({"file": file_path, "name": symbol_name})
        elif isinstance(value, list):
            symbols.extend(flatten_symbol_values(value, symbol_key))
    return symbols


def extract_edit_target_files(code_graph: Dict[str, Any]) -> List[str]:
    values = collect_key_recursively(code_graph, "edit_targets")
    return flatten_file_values(values)


def extract_edit_target_symbols(code_graph: Dict[str, Any], symbol_key: str) -> List[Dict[str, str]]:
    values = collect_key_recursively(code_graph, "edit_targets")
    return flatten_symbol_values(values, symbol_key)


def extract_matched_files(code_graph: Dict[str, Any]) -> List[str]:
    values = collect_key_recursively(code_graph, "matched_files")
    return flatten_file_values(values)


def load_snapshot_seed_files(instance_dir: Path, instance_id: str) -> List[str]:
    path = instance_dir / f"repo_structure_{instance_id}.json"
    if not path.exists():
        return []
    payload = load_json(path)
    snapshot = payload.get("code_graph_snapshot", {}) if isinstance(payload, dict) else {}
    return ordered_unique(snapshot.get("seed_files", []) if isinstance(snapshot, dict) else [])


def load_code_graph_files(instance_dir: Path, instance_id: str) -> Dict[str, Any]:
    path = instance_dir / f"code_graph_{instance_id}.json"
    if not path.exists():
        return {
            "seed_files": [],
            "matched_files": [],
            "edit_target_files": [],
            "edit_target_functions": [],
            "edit_target_modules": [],
        }
    payload = load_json(path)
    code_graph = payload.get("code_graph", payload) if isinstance(payload, dict) else {}
    if not isinstance(code_graph, dict):
        code_graph = {}
    return {
        "seed_files": ordered_unique(code_graph.get("seed_files", [])),
        "matched_files": extract_matched_files(code_graph),
        "edit_target_files": extract_edit_target_files(code_graph),
        "edit_target_functions": extract_edit_target_symbols(code_graph, "function"),
        "edit_target_modules": extract_edit_target_symbols(code_graph, "class"),
    }


def build_stage_metrics(instance_id: str, stage: str, predictions: List[str], gt_files: List[str]) -> Dict[str, Any]:
    gt_set = {normalize_file_path(item) for item in gt_files if normalize_file_path(item)}
    metrics = {
        "instance_id": instance_id,
        f"{stage}_count": len(predictions),
        f"{stage}_empty": int(len(predictions) == 0),
        f"{stage}_mrr": reciprocal_rank(predictions, gt_files, k=RANK_METRIC_K),
        f"{stage}_map": average_precision(predictions, gt_files, k=RANK_METRIC_K),
    }
    for k in TOP_K_VALUES:
        metrics[f"{stage}_acc@{k}"] = strict_acc_at_k(predictions, gt_files, k)
    for k in SET_METRIC_K_VALUES:
        pred_topk = ordered_unique(predictions_at_cutoff(predictions, k))
        pred_topk_set = set(pred_topk)
        hit_count = len(gt_set & pred_topk_set)
        recall = hit_count / len(gt_set) if gt_set else 0.0
        precision = hit_count / len(pred_topk_set) if pred_topk_set else 0.0
        f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
        metrics.update(
            {
                f"{stage}_success_location@{k}": float(bool(gt_set) and gt_set <= pred_topk_set),
                f"{stage}_recall@{k}": recall,
                f"{stage}_precision@{k}": precision,
                f"{stage}_f1@{k}": f1,
            }
        )
    return metrics


def build_generic_metrics(prefix: str, predictions: Sequence[str], gt_values: Sequence[str]) -> Dict[str, Any]:
    gt_set = {normalize_file_path(item) for item in gt_values if normalize_file_path(item)}
    pred = ordered_unique(predictions)
    metrics: Dict[str, Any] = {
        f"{prefix}_count": len(pred),
        f"{prefix}_empty": int(len(pred) == 0),
        f"{prefix}_mrr": reciprocal_rank(pred, list(gt_set), k=RANK_METRIC_K),
        f"{prefix}_map": average_precision(pred, list(gt_set), k=RANK_METRIC_K),
    }
    for k in TOP_K_VALUES:
        metrics[f"{prefix}_acc@{k}"] = strict_acc_at_k(pred, list(gt_set), k)
    for k in SET_METRIC_K_VALUES:
        pred_topk = ordered_unique(predictions_at_cutoff(pred, k))
        pred_topk_set = set(pred_topk)
        hit_count = len(gt_set & pred_topk_set)
        recall = hit_count / len(gt_set) if gt_set else 0.0
        precision = hit_count / len(pred_topk_set) if pred_topk_set else 0.0
        f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
        metrics.update(
            {
                f"{prefix}_success_location@{k}": float(bool(gt_set) and gt_set <= pred_topk_set),
                f"{prefix}_recall@{k}": recall,
                f"{prefix}_precision@{k}": precision,
                f"{prefix}_f1@{k}": f1,
            }
        )
    return metrics


def parse_changed_old_lines(patch_text: Any) -> Dict[str, set[int]]:
    current_file = ""
    old_line = 0
    changed: Dict[str, set[int]] = {}
    for raw_line in str(patch_text or "").splitlines():
        file_match = PATCH_HEADER_RE.match(raw_line)
        if file_match:
            current_file = normalize_file_path(file_match.group(1))
            changed.setdefault(current_file, set())
            continue
        hunk_match = HUNK_RE.match(raw_line)
        if hunk_match:
            old_line = int(hunk_match.group(1))
            continue
        if not current_file or raw_line.startswith(("diff --git", "--- ")):
            continue
        if raw_line.startswith("-") and not raw_line.startswith("---"):
            changed[current_file].add(max(1, old_line))
            old_line += 1
        elif raw_line.startswith("+") and not raw_line.startswith("+++"):
            changed[current_file].add(max(1, old_line))
        else:
            old_line += 1
    return changed


def _line_number(value: Any, default: int = 1) -> int:
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return default


def _iter_file_nodes(structure: Any, path_parts: List[str] | None = None) -> Iterable[tuple[str, Dict[str, Any]]]:
    path_parts = path_parts or []
    if not isinstance(structure, dict):
        return
    if {"text", "classes", "functions"} <= set(structure.keys()):
        yield normalize_file_path("/".join(path_parts)), structure
        return
    for name, value in structure.items():
        if isinstance(value, dict):
            yield from _iter_file_nodes(value, path_parts + [str(name)])


def extract_entities_from_structure(structure: Dict[str, Any]) -> Dict[str, List[CodeEntity]]:
    entities_by_file: Dict[str, List[CodeEntity]] = {}
    for file_path, file_node in _iter_file_nodes(structure):
        if not file_path:
            continue
        entities: List[CodeEntity] = []
        classes = file_node.get("classes", [])
        if isinstance(classes, list):
            for clazz in classes:
                if not isinstance(clazz, dict):
                    continue
                class_name = str(clazz.get("name") or "").strip()
                if class_name:
                    start = _line_number(clazz.get("start_line"))
                    end = _line_number(clazz.get("end_line"), start)
                    entities.append(
                        CodeEntity(
                            file=file_path,
                            kind="class",
                            name=class_name,
                            qualified_name=class_name,
                            start_line=start,
                            end_line=max(start, end),
                        )
                    )
                methods = clazz.get("methods", [])
                if isinstance(methods, list):
                    for method in methods:
                        if not isinstance(method, dict):
                            continue
                        method_name = str(method.get("name") or "").strip()
                        if not method_name:
                            continue
                        qualified = f"{class_name}.{method_name}" if class_name else method_name
                        start = _line_number(method.get("start_line"))
                        end = _line_number(method.get("end_line"), start)
                        entities.append(
                            CodeEntity(
                                file=file_path,
                                kind="method",
                                name=method_name,
                                qualified_name=qualified,
                                start_line=start,
                                end_line=max(start, end),
                            )
                        )
        functions = file_node.get("functions", [])
        if isinstance(functions, list):
            for function in functions:
                if not isinstance(function, dict):
                    continue
                function_name = str(function.get("name") or "").strip()
                if not function_name:
                    continue
                start = _line_number(function.get("start_line"))
                end = _line_number(function.get("end_line"), start)
                entities.append(
                    CodeEntity(
                        file=file_path,
                        kind="function",
                        name=function_name,
                        qualified_name=function_name,
                        start_line=start,
                        end_line=max(start, end),
                    )
                )
        entities_by_file[file_path] = sorted(entities, key=lambda item: (item.start_line, item.end_line, item.kind))
    return entities_by_file


def entities_overlapping_lines(entities: Sequence[CodeEntity], lines: set[int]) -> List[CodeEntity]:
    if not lines:
        return []
    return [entity for entity in entities if any(entity.start_line <= line <= entity.end_line for line in lines)]


def entity_id(entity: CodeEntity) -> str:
    return f"{entity.file}::{entity.qualified_name}"


def module_id(entity: CodeEntity) -> str:
    if entity.kind == "class":
        return f"{entity.file}::{entity.qualified_name}"
    if "." in entity.qualified_name:
        return f"{entity.file}::{entity.qualified_name.rsplit('.', 1)[0]}"
    return entity.file


def terms(text: str) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"[A-Za-z_$][A-Za-z0-9_$]{2,}", text or "")
        if token.lower() not in {"the", "and", "for", "with", "this", "that", "from", "function", "class"}
    }


def rank_entities(entities: Sequence[CodeEntity], context: str, limit: int = 15) -> List[CodeEntity]:
    context_terms = terms(context)
    scored = []
    for index, entity in enumerate(entities):
        name_terms = terms(entity.name + " " + entity.qualified_name)
        score = len(context_terms & name_terms)
        if entity.name and entity.name in context:
            score += 3
        if entity.qualified_name and entity.qualified_name in context:
            score += 5
        scored.append((score, -(entity.end_line - entity.start_line), -index, entity.start_line, entity))
    scored.sort(key=lambda item: item[:4], reverse=True)
    return [item[-1] for item in scored[:limit]]


def find_entity_by_symbol(entities: Sequence[CodeEntity], file_path: str, symbol_name: str) -> CodeEntity | None:
    target_file = normalize_file_path(file_path)
    target_name = str(symbol_name or "").strip()
    if not target_file or not target_name:
        return None
    for entity in entities:
        if entity.file != target_file:
            continue
        if entity.qualified_name == target_name or entity.name == target_name or entity.qualified_name.endswith(f".{target_name}"):
            return entity
    return None


def derive_three_level_predictions(
    stage_files: Dict[str, List[str]],
    graph_files: Dict[str, Any],
    entities_by_file: Dict[str, List[CodeEntity]],
    context: str,
) -> tuple[List[str], List[str]]:
    all_entities = [entity for entities in entities_by_file.values() for entity in entities]
    explicit_functions: List[CodeEntity] = []
    explicit_modules: List[CodeEntity] = []
    for item in graph_files.get("edit_target_functions", []):
        entity = find_entity_by_symbol(all_entities, item.get("file", ""), item.get("name", ""))
        if entity and entity.kind in {"function", "method"}:
            explicit_functions.append(entity)
            explicit_modules.append(entity)
    for item in graph_files.get("edit_target_modules", []):
        entity = find_entity_by_symbol(all_entities, item.get("file", ""), item.get("name", ""))
        if entity:
            explicit_modules.append(entity)

    ordered_entities: List[CodeEntity] = []
    seen_entity_ids: set[str] = set()

    def add_entities(entities: Iterable[CodeEntity]) -> None:
        for entity in entities:
            key = entity_id(entity)
            if key in seen_entity_ids:
                continue
            seen_entity_ids.add(key)
            ordered_entities.append(entity)

    add_entities(explicit_functions)
    add_entities(explicit_modules)
    for stage in ("edit_target", "matched", "code_seed", "snapshot_seed"):
        candidates: List[CodeEntity] = []
        for file_path in stage_files.get(stage, []):
            candidates.extend(entities_by_file.get(normalize_file_path(file_path), []))
        add_entities(rank_entities(candidates, context, limit=15))

    pred_functions = ordered_unique([entity_id(entity) for entity in ordered_entities if entity.kind in {"function", "method"}])
    pred_modules = ordered_unique([module_id(entity) for entity in ordered_entities])
    return pred_modules[:15], pred_functions[:15]


def ground_truth_three_level(sample: Dict[str, Any], entities_by_file: Dict[str, List[CodeEntity]]) -> tuple[List[str], List[str]]:
    gt_modules: set[str] = set()
    gt_functions: set[str] = set()
    changed_lines = parse_changed_old_lines(sample.get("patch", ""))
    for file_path, lines in changed_lines.items():
        overlaps = entities_overlapping_lines(entities_by_file.get(file_path, []), lines)
        for entity in overlaps:
            if entity.kind == "class":
                gt_modules.add(module_id(entity))
            elif entity.kind in {"function", "method"}:
                gt_functions.add(entity_id(entity))
                gt_modules.add(module_id(entity))
    return sorted(gt_modules), sorted(gt_functions)


def format_percent(value: float) -> str:
    return f"{value * 100:.2f}"


def write_metrics_md(path: Path, metrics: Dict[str, float], three_level_enabled: bool) -> None:
    ranking_headers = [f"Acc@{k}" for k in TOP_K_VALUES] + [f"MRR@{RANK_METRIC_K}", f"MAP@{RANK_METRIC_K}", "Empty"]
    lines = [
        "# Strict Three-Level Localization Metrics",
        "",
        f"- Evaluated: {int(metrics.get('final_total', 0))}",
        (
            "- Note: Module/Function are derived from GALA staged file candidates and repo_structures."
            if three_level_enabled
            else "- Note: GALA 当前 localization 产物是 file-level 候选；Module/Function 未启用，统一表中以 N/A 标记。"
        ),
        "",
        "## Ranking Metrics",
        "",
    ]
    lines.append("| " + " | ".join(["Level"] + ranking_headers) + " |")
    lines.append("|---|" + "|".join(["---:"] * len(ranking_headers)) + "|")
    final_file_cells = [format_percent(metrics.get(f"final_acc@{k}", 0.0)) for k in TOP_K_VALUES] + [
        format_percent(metrics.get("final_mrr", 0.0)),
        format_percent(metrics.get("final_map", 0.0)),
        format_percent(metrics.get("final_empty_rate", 0.0)),
    ]
    lines.append("| " + " | ".join(["File"] + final_file_cells) + " |")
    for prefix, title in (("module", "Module"), ("function", "Function")):
        if three_level_enabled:
            cells = [format_percent(metrics.get(f"{prefix}_acc@{k}", 0.0)) for k in TOP_K_VALUES] + [
                format_percent(metrics.get(f"{prefix}_mrr", 0.0)),
                format_percent(metrics.get(f"{prefix}_map", 0.0)),
                format_percent(metrics.get(f"{prefix}_empty_rate", 0.0)),
            ]
        else:
            cells = ["N/A"] * len(ranking_headers)
        lines.append("| " + " | ".join([title] + cells) + " |")
    lines.append("")

    set_headers = [
        "File SL",
        "File REC",
        "File PRE",
        "File F1",
        "Module SL",
        "Module REC",
        "Module PRE",
        "Module F1",
        "Function SL",
        "Function REC",
        "Function PRE",
        "Function F1",
    ]
    lines.extend(
        [
            "## Metric Notes",
            "",
            "`Acc@K` uses the strict LocAgent-style full-coverage standard: it is 1 only when top-k predictions cover all gold locations for that level.",
            "",
            "`Set Metrics @8/@10/@15` evaluate only the top-k predictions. `Set Metrics @All` evaluates the full prediction set without truncation.",
            "",
            "`SL` is strict full-coverage success: it is 1 only when all gold locations for that level are included in the evaluated prediction set.",
            "",
        ]
    )
    for cutoff in SET_METRIC_K_VALUES:
        cutoff_label = "All" if cutoff == "all" else cutoff
        lines.extend(
            [
                "",
                f"## Set Metrics @{cutoff_label}",
                "",
            ]
        )
        lines.append("| " + " | ".join(set_headers) + " |")
        lines.append("|" + "|".join(["---:"] * len(set_headers)) + "|")
        file_cells = [
            format_percent(metrics.get(f"final_success_location@{cutoff}", 0.0)),
            format_percent(metrics.get(f"final_recall@{cutoff}", 0.0)),
            format_percent(metrics.get(f"final_precision@{cutoff}", 0.0)),
            format_percent(metrics.get(f"final_f1@{cutoff}", 0.0)),
        ]
        if three_level_enabled:
            extra_cells = []
            for prefix in ("module", "function"):
                extra_cells.extend(
                    [
                        format_percent(metrics.get(f"{prefix}_success_location@{cutoff}", 0.0)),
                        format_percent(metrics.get(f"{prefix}_recall@{cutoff}", 0.0)),
                        format_percent(metrics.get(f"{prefix}_precision@{cutoff}", 0.0)),
                        format_percent(metrics.get(f"{prefix}_f1@{cutoff}", 0.0)),
                    ]
                )
        else:
            extra_cells = ["N/A"] * 8
        lines.append("| " + " | ".join(file_cells + extra_cells) + " |")

    lines.extend(["", "## Stage Breakdown", ""])
    lines.append("| Stage | Total | Acc@1 | Acc@5 | Acc@10 | Acc@15 | MRR@15 | MAP@15 | Empty |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for stage in STAGES:
        lines.append(
            f"| {stage} | {int(metrics.get(f'{stage}_total', 0))} | "
            f"{format_percent(metrics.get(f'{stage}_acc@1', 0.0))} | "
            f"{format_percent(metrics.get(f'{stage}_acc@5', 0.0))} | "
            f"{format_percent(metrics.get(f'{stage}_acc@10', 0.0))} | "
            f"{format_percent(metrics.get(f'{stage}_acc@15', 0.0))} | "
            f"{format_percent(metrics.get(f'{stage}_mrr', 0.0))} | "
            f"{format_percent(metrics.get(f'{stage}_map', 0.0))} | "
            f"{format_percent(metrics.get(f'{stage}_empty_rate', 0.0))} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    result_dir = Path(args.result_dir)
    output_dir = Path(args.output_dir)
    gt_payload = load_json(Path(args.gt_file))
    if not isinstance(gt_payload, dict):
        raise ValueError("gt-file must be a dict JSON keyed by instance_id")

    loc_results: Dict[str, Dict[str, Any]] = {}
    per_instance_rows: List[Dict[str, Any]] = []
    stage_rows = {stage: [] for stage in STAGES}
    module_rows: List[Dict[str, Any]] = []
    function_rows: List[Dict[str, Any]] = []
    samples_by_id = load_samples(args.samples)
    structure_dir = Path(args.structure_dir) if args.structure_dir else None
    three_level_enabled = bool(structure_dir and structure_dir.is_dir() and samples_by_id)

    for instance_id in sorted(gt_payload):
        gt_files = ordered_unique(gt_payload.get(instance_id, []))
        instance_dir = result_dir / instance_id
        snapshot_seed = load_snapshot_seed_files(instance_dir, instance_id)
        graph_files = load_code_graph_files(instance_dir, instance_id)
        code_seed = graph_files["seed_files"]
        matched = graph_files["matched_files"]
        edit_target = graph_files["edit_target_files"]
        stage_files = {
            "snapshot_seed": snapshot_seed,
            "code_seed": code_seed,
            "matched": matched,
            "edit_target": edit_target,
        }
        final = ordered_unique(edit_target + matched + code_seed + snapshot_seed)
        gt_modules: List[str] = []
        gt_functions: List[str] = []
        pred_modules: List[str] = []
        pred_functions: List[str] = []
        if three_level_enabled and structure_dir is not None:
            structure_path = structure_dir / f"{instance_id}.json"
            sample = samples_by_id.get(instance_id, {})
            if structure_path.exists() and sample:
                structure_payload = load_json(structure_path)
                structure = structure_payload.get("structure", structure_payload)
                entities_by_file = extract_entities_from_structure(structure)
                gt_modules, gt_functions = ground_truth_three_level(sample, entities_by_file)
                context = str(sample.get("problem_statement") or "")
                pred_modules, pred_functions = derive_three_level_predictions(
                    stage_files=stage_files,
                    graph_files=graph_files,
                    entities_by_file=entities_by_file,
                    context=context,
                )

        loc_results[instance_id] = {
            "gt_files": gt_files,
            "gt_modules": gt_modules,
            "gt_functions": gt_functions,
            "snapshot_seed_files": snapshot_seed,
            "code_seed_files": code_seed,
            "matched_files": matched,
            "edit_target_files": edit_target,
            "final_files": final,
            "final_modules": pred_modules,
            "final_functions": pred_functions,
        }

        row: Dict[str, Any] = {
            "instance_id": instance_id,
            "gt_files": ";".join(gt_files),
            "final_files": ";".join(final),
            "gt_modules": ";".join(gt_modules),
            "gt_functions": ";".join(gt_functions),
            "final_modules": ";".join(pred_modules),
            "final_functions": ";".join(pred_functions),
        }
        for stage, predictions in (
            ("snapshot_seed", snapshot_seed),
            ("code_seed", code_seed),
            ("matched", matched),
            ("edit_target", edit_target),
            ("final", final),
        ):
            stage_metric = build_stage_metrics(instance_id, stage, predictions, gt_files)
            stage_rows[stage].append(stage_metric)
            row.update(stage_metric)
        per_instance_rows.append(row)
        if three_level_enabled:
            module_metric = build_generic_metrics("module", pred_modules, gt_modules)
            function_metric = build_generic_metrics("function", pred_functions, gt_functions)
            module_rows.append(module_metric)
            function_rows.append(function_metric)
            row.update(module_metric)
            row.update(function_metric)

    metrics: Dict[str, float] = {}
    for stage, rows in stage_rows.items():
        metrics.update(summarize_metrics(rows, stage))
    if three_level_enabled:
        metrics.update(summarize_metrics(module_rows, "module"))
        metrics.update(summarize_metrics(function_rows, "function"))

    output_dir.mkdir(parents=True, exist_ok=True)
    loc_output = Path(args.loc_output) if args.loc_output else output_dir.parent / "loc_results.json"
    write_json(loc_output, loc_results)
    write_json(output_dir / "metrics.json", metrics)
    write_json(output_dir / "metrics_3level.json", metrics)
    write_metrics_md(output_dir / "metrics.md", metrics, three_level_enabled=three_level_enabled)
    write_metrics_md(output_dir / "metrics_3level.md", metrics, three_level_enabled=three_level_enabled)

    fieldnames = list(per_instance_rows[0].keys()) if per_instance_rows else ["instance_id"]
    write_csv(output_dir / "per_instance_metrics.csv", per_instance_rows, fieldnames)
    print(f"Wrote {loc_output}")
    print(f"Wrote {output_dir / 'metrics.md'}")
    print(f"Wrote {output_dir / 'metrics_3level.md'}")


if __name__ == "__main__":
    main()
