from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from mmir.benchmark.samples import load_samples
from mmir.indexing.document_builder import entity_id, load_structure, module_id
from mmir.indexing.entities import (
    entities_overlapping_lines,
    extract_entities_from_structure_file,
    normalize_path,
)
from mmir.output.writer import write_json
from mmir.schema import Sample


LEVELS = ("file", "module", "function")
CUTOFFS = list(range(1, 16))
SET_METRIC_CUTOFFS = ("8", "10", "15", "all")


def _patch_targets(patch: str) -> tuple[set[str], dict[str, set[int]]]:
    files: set[str] = set()
    changed_lines: dict[str, set[int]] = defaultdict(set)
    current_file = ""
    old_line = 0
    hunk_re = re.compile(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
    for raw in (patch or "").splitlines():
        if raw.startswith("diff --git "):
            parts = raw.split()
            if len(parts) >= 4:
                current_file = normalize_path(parts[2][2:] if parts[2].startswith("a/") else parts[2])
                files.add(current_file)
            continue
        if raw.startswith("--- ") or raw.startswith("+++ "):
            continue
        match = hunk_re.match(raw)
        if match:
            old_line = int(match.group(1))
            continue
        if not current_file or not raw:
            continue
        marker = raw[0]
        if marker == "-":
            changed_lines[current_file].add(old_line)
            old_line += 1
        elif marker == "+":
            changed_lines[current_file].add(max(old_line, 1))
        elif marker == " ":
            old_line += 1
    return files, changed_lines


def _ground_truth(sample: Sample, structure_dir: str | Path) -> dict[str, set[str]]:
    patch_files, changed_lines = _patch_targets(sample.patch)
    gt_files = {normalize_path(path) for path in (sample.files or [])} | patch_files
    gt_modules: set[str] = set()
    gt_functions: set[str] = set()
    try:
        structure = load_structure(structure_dir, sample.instance_id)
    except FileNotFoundError:
        return {"file": gt_files, "module": set(), "function": set()}
    for file_path in gt_files:
        file_node = _structure_file_node(structure, file_path)
        entities = extract_entities_from_structure_file(file_path, file_node) if file_node else []
        lines = changed_lines.get(file_path, set())
        if not lines:
            continue
        for entity in entities_overlapping_lines(entities, lines):
            if entity.kind == "class":
                gt_modules.add(module_id(entity))
            else:
                gt_functions.add(entity_id(entity))
                parent = module_id(entity)
                if parent:
                    gt_modules.add(parent)
    return {"file": gt_files, "module": gt_modules, "function": gt_functions}


def _prediction_ids(row: dict[str, Any], level: str) -> list[str]:
    if level == "file":
        values = row.get("found_files") or [item.get("id") for item in row.get("ranked_files", []) if isinstance(item, dict)]
        return [normalize_path(value) for value in values if value]
    if level == "module":
        values = row.get("found_modules") or [item.get("id") for item in row.get("ranked_modules", []) if isinstance(item, dict)]
        return [str(value) for value in values if value]
    values = row.get("found_functions") or [item.get("id") for item in row.get("ranked_functions", []) if isinstance(item, dict)]
    return [str(value) for value in values if value]


def _first_hit_rank(preds: list[str], gold: set[str], cutoff: int) -> int | None:
    for idx, pred in enumerate(preds[:cutoff], start=1):
        if pred in gold:
            return idx
    return None


def _average_precision(preds: list[str], gold: set[str], cutoff: int) -> float:
    if not gold:
        return 0.0
    hits = 0
    total = 0.0
    seen: set[str] = set()
    for idx, pred in enumerate(preds[:cutoff], start=1):
        if pred in seen:
            continue
        seen.add(pred)
        if pred in gold:
            hits += 1
            total += hits / idx
    return total / max(1, len(gold))


def _pct(value: float) -> float:
    return round(value * 100, 2)


def _structure_file_node(structure: dict[str, Any], file_path: str) -> dict[str, Any] | None:
    node: Any = structure
    for part in normalize_path(file_path).split("/"):
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    if isinstance(node, dict) and "text" in node:
        return node
    return None


def _top_predictions(preds: list[str], cutoff: str) -> list[str]:
    if cutoff == "all":
        return preds
    return preds[: int(cutoff)]


def evaluate(
    samples_path: str | Path,
    predictions_path: str | Path,
    structure_dir: str | Path,
    output_dir: str | Path,
    *,
    limit: int | None = None,
) -> dict[str, Any]:
    samples = load_samples(samples_path)
    if limit:
        samples = samples[:limit]
    predictions = json.loads(Path(predictions_path).read_text(encoding="utf-8"))
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    sample_rows: list[dict[str, Any]] = []
    metrics: dict[str, Any] = {
        "evaluated": len(samples),
        "ranking": {},
        "set_metrics": {},
    }
    per_level_data: dict[str, list[tuple[set[str], list[str]]]] = {level: [] for level in LEVELS}
    for sample in samples:
        gt = _ground_truth(sample, structure_dir)
        pred_row = predictions.get(sample.instance_id, {})
        row: dict[str, Any] = {"instance_id": sample.instance_id}
        for level in LEVELS:
            preds = _prediction_ids(pred_row, level)
            per_level_data[level].append((gt[level], preds))
            row[f"{level}_gold"] = "|".join(sorted(gt[level]))
            row[f"{level}_pred"] = "|".join(preds)
        sample_rows.append(row)

    for level, rows in per_level_data.items():
        ranking: dict[str, float] = {}
        for cutoff in CUTOFFS:
            ranking[f"acc@{cutoff}"] = _pct(sum(1 for gold, preds in rows if _first_hit_rank(preds, gold, cutoff)) / max(1, len(rows)))
        reciprocal = []
        average_precisions = []
        for gold, preds in rows:
            rank = _first_hit_rank(preds, gold, 15)
            reciprocal.append(1 / rank if rank else 0.0)
            average_precisions.append(_average_precision(preds, gold, 15))
        ranking["mrr@15"] = _pct(sum(reciprocal) / max(1, len(reciprocal)))
        ranking["map@15"] = _pct(sum(average_precisions) / max(1, len(average_precisions)))
        ranking["empty"] = _pct(sum(1 for _, preds in rows if not preds) / max(1, len(rows)))
        metrics["ranking"][level] = ranking

        for cutoff in SET_METRIC_CUTOFFS:
            successes = []
            recalls = []
            precisions = []
            f1s = []
            for gold, preds in rows:
                top = _top_predictions(preds, cutoff)
                pred_set = set(top)
                hits = len(pred_set & gold)
                recall = hits / len(gold) if gold else 0.0
                precision = hits / len(pred_set) if pred_set else 0.0
                f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
                successes.append(1.0 if gold and gold <= pred_set else 0.0)
                recalls.append(recall)
                precisions.append(precision)
                f1s.append(f1)
            metrics["set_metrics"].setdefault(cutoff, {})[level] = {
                "sl": _pct(sum(successes) / max(1, len(successes))),
                "rec": _pct(sum(recalls) / max(1, len(recalls))),
                "pre": _pct(sum(precisions) / max(1, len(precisions))),
                "f1": _pct(sum(f1s) / max(1, len(f1s))),
            }

    write_json(out_dir / "metrics_3level.json", metrics)
    with (out_dir / "per_instance_metrics_3level.csv").open("w", encoding="utf-8", newline="") as fh:
        fieldnames = list(sample_rows[0].keys()) if sample_rows else ["instance_id"]
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sample_rows)
    (out_dir / "metrics_3level.md").write_text(_render_markdown(metrics), encoding="utf-8")
    return metrics


def _render_markdown(metrics: dict[str, Any]) -> str:
    lines = [
        "# Three-Level Localization Metrics",
        "",
        f"- Evaluated: {metrics['evaluated']}",
        "",
        "## Ranking Metrics",
        "",
        "| Level | Acc@1 | Acc@2 | Acc@3 | Acc@4 | Acc@5 | Acc@6 | Acc@7 | Acc@8 | Acc@9 | Acc@10 | Acc@11 | Acc@12 | Acc@13 | Acc@14 | Acc@15 | MRR@15 | MAP@15 | Empty |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    labels = {"file": "File", "module": "Module", "function": "Function"}
    for level in LEVELS:
        row = metrics["ranking"][level]
        values = [row[f"acc@{cutoff}"] for cutoff in CUTOFFS] + [row["mrr@15"], row["map@15"], row["empty"]]
        lines.append(f"| {labels[level]} | " + " | ".join(f"{value:.2f}" for value in values) + " |")
    lines.extend([
        "",
        "## Metric Notes",
        "",
        "`Set Metrics @8/@10/@15` evaluate only the top-k predictions. `Set Metrics @All` evaluates the full prediction set without truncation.",
        "",
        "`SL` is strict full-coverage success: it is 1 only when all gold locations for that level are included in the evaluated prediction set.",
    ])
    for cutoff in SET_METRIC_CUTOFFS:
        cutoff_label = "All" if cutoff == "all" else cutoff
        lines.extend([
            "",
            f"## Set Metrics @{cutoff_label}",
            "",
            "| File SL | File REC | File PRE | File F1 | Module SL | Module REC | Module PRE | Module F1 | Function SL | Function REC | Function PRE | Function F1 |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ])
        values: list[float] = []
        for level in LEVELS:
            item = metrics["set_metrics"][cutoff][level]
            values.extend([item["sl"], item["rec"], item["pre"], item["f1"]])
        lines.append("| " + " | ".join(f"{value:.2f}" for value in values) + " |")
    lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate MM-IR three-level localization.")
    parser.add_argument("--samples", required=True)
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--structure-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--limit", type=int, default=0)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    evaluate(args.samples, args.predictions, args.structure_dir, args.output_dir, limit=args.limit or None)


if __name__ == "__main__":
    main()
