#!/usr/bin/env python3
"""Fast file/module/function localization evaluator.

This evaluator follows the same metric formulas as LocAgent's three-level
evaluator, but only extracts entities from gold-touched files and predicted
files instead of expanding every file in the repository structure. It is meant
for re-evaluating existing predictions on filtered/clean subsets.
"""

from __future__ import annotations

import argparse
import csv
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


TOP_K_VALUES = tuple(range(1, 16))
RANK_METRIC_K = 15
SET_METRIC_K_VALUES = ("8", "10", "15", "all")
PATCH_HEADER_RE = re.compile(r"^\+\+\+ b/(.+)$")
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def normalize(path: Any) -> str:
    text = str(path or "").strip().replace("\\", "/")
    if text.startswith(("a/", "b/")):
        text = text[2:]
    return text.lstrip("./")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip()]


def flatten(values: Any) -> list[Any]:
    if values is None:
        return []
    if isinstance(values, str):
        return [values]
    if isinstance(values, list):
        out: list[Any] = []
        for item in values:
            out.extend(flatten(item))
        return out
    if isinstance(values, dict):
        for key in ("file_path", "file", "path", "filename", "name", "qualified_name"):
            if values.get(key):
                return [values[key]]
    return []


def ordered_unique(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = normalize(value)
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def prediction_values(row: dict[str, Any], keys: tuple[str, ...]) -> list[str]:
    for key in keys:
        if key in row:
            return ordered_unique(flatten(row.get(key)))
    return []


def load_predictions(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    if path.suffix == ".jsonl":
        payload: Any = load_jsonl(path)
    else:
        payload = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, dict[str, Any]] = {}
    if isinstance(payload, dict):
        iterable = payload.items()
    else:
        iterable = ((row.get("instance_id"), row) for row in payload if isinstance(row, dict))
    for instance_id, row in iterable:
        if not instance_id:
            continue
        if not isinstance(row, dict):
            row = {"found_files": row}
        out[str(instance_id)] = {
            "files": prediction_values(row, ("found_files", "final_files", "pred_files", "files")),
            "modules": prediction_values(row, ("found_modules", "pred_modules", "modules")),
            "functions": prediction_values(row, ("found_functions", "pred_functions", "functions")),
            "response": str((row.get("file_traj") or {}).get("response") or row.get("raw_output") or ""),
        }
    return out


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


def entities_for_files(structure: dict[str, Any], files: list[str]) -> dict[str, list[CodeEntity]]:
    out: dict[str, list[CodeEntity]] = {}
    for file_path in ordered_unique(files):
        file_node = structure_file_node(structure, file_path)
        if not file_node:
            out[file_path] = []
            continue
        try:
            out[file_path] = extract_entities_from_structure_file(file_path, file_node)
        except Exception:
            out[file_path] = []
    return out


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


def rank_entities(entities: list[CodeEntity], context: str, limit: int = 15) -> list[CodeEntity]:
    context_terms = terms(context)
    scored = []
    for entity in entities:
        name_terms = terms(entity.name + " " + entity.qualified_name)
        score = len(context_terms & name_terms)
        if entity.name and entity.name in context:
            score += 3
        if entity.qualified_name and entity.qualified_name in context:
            score += 5
        scored.append((score, -(entity.end_line - entity.start_line), entity.start_line, entity))
    scored.sort(key=lambda item: item[:3], reverse=True)
    return [item[-1] for item in scored[:limit]]


def acc_at_k(pred: list[str], gt: set[str], k: int, strict: bool) -> float:
    pred_set = set(pred[:k])
    if strict:
        return float(bool(gt) and gt <= pred_set)
    return float(bool(gt & pred_set))


def reciprocal_rank(pred: list[str], gt: set[str], k: int) -> float:
    for index, item in enumerate(pred[:k], start=1):
        if item in gt:
            return 1.0 / index
    return 0.0


def average_precision(pred: list[str], gt: set[str], k: int) -> float:
    if not gt:
        return 0.0
    hits = 0
    score = 0.0
    seen: set[str] = set()
    for index, item in enumerate(pred[:k], start=1):
        if item in seen:
            continue
        seen.add(item)
        if item in gt:
            hits += 1
            score += hits / index
    return score / len(gt)


def predictions_at_cutoff(pred: list[str], cutoff: str) -> list[str]:
    if cutoff == "all":
        return pred
    return pred[: int(cutoff)]


def set_metrics_at_k(pred: list[str], gt: set[str], cutoff: str) -> dict[str, float]:
    pred_set = set(predictions_at_cutoff(pred, cutoff))
    hit_count = len(gt & pred_set)
    recall = hit_count / len(gt) if gt else 0.0
    precision = hit_count / len(pred_set) if pred_set else 0.0
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return {
        "sl": float(bool(gt) and gt <= pred_set),
        "rec": recall,
        "pre": precision,
        "f1": f1,
    }


def add_rank_metrics(prefix: str, pred: list[str], gt: set[str], row: dict[str, Any], totals: Counter, strict: bool) -> None:
    for k in TOP_K_VALUES:
        key = f"{prefix}_acc@{k}"
        row[key] = acc_at_k(pred, gt, k, strict)
        totals[key] += row[key]
    for key, value in {
        f"{prefix}_mrr": reciprocal_rank(pred, gt, RANK_METRIC_K),
        f"{prefix}_map": average_precision(pred, gt, RANK_METRIC_K),
        f"{prefix}_empty": float(not pred),
    }.items():
        row[key] = value
        totals[key] += value
    for cutoff in SET_METRIC_K_VALUES:
        for name, value in set_metrics_at_k(pred, gt, cutoff).items():
            key = f"{prefix}_{name}@{cutoff}"
            row[key] = value
            totals[key] += value


def render_markdown(metrics: dict[str, float], n: int, strict: bool) -> str:
    title = "Strict Three-Level Localization Metrics" if strict else "Three-Level Localization Metrics"
    lines = [f"# {title}", "", f"- Evaluated: {n}", "", "## Ranking Metrics", ""]
    ranking_headers = ["Level"] + [f"Acc@{k}" for k in TOP_K_VALUES] + [f"MRR@{RANK_METRIC_K}", f"MAP@{RANK_METRIC_K}", "Empty"]
    lines.append("| " + " | ".join(ranking_headers) + " |")
    lines.append("|---|" + "|".join(["---:"] * (len(ranking_headers) - 1)) + "|")
    for prefix, label in (("file", "File"), ("module", "Module"), ("function", "Function")):
        values = [metrics.get(f"{prefix}_acc@{k}", 0.0) * 100 for k in TOP_K_VALUES]
        values += [
            metrics.get(f"{prefix}_mrr", 0.0) * 100,
            metrics.get(f"{prefix}_map", 0.0) * 100,
            metrics.get(f"{prefix}_empty", 0.0) * 100,
        ]
        lines.append("| " + " | ".join([label] + [f"{value:.2f}" for value in values]) + " |")
    lines.append("")
    lines += ["## Metric Notes", ""]
    if strict:
        lines.append("`Acc@K` uses the strict full-coverage standard: it is 1 only when top-k predictions cover all gold locations for that level.")
    else:
        lines.append("`Acc@K` is hit-based: it is 1 when top-k predictions include at least one gold location for that level.")
    lines += [
        "",
        "`Set Metrics @8/@10/@15` evaluate only the top-k predictions. `Set Metrics @All` evaluates the full prediction set without truncation.",
        "",
        "`SL` is strict full-coverage success: it is 1 only when all gold locations for that level are included in the evaluated prediction set.",
        "",
    ]
    set_headers = [
        "File SL", "File REC", "File PRE", "File F1",
        "Module SL", "Module REC", "Module PRE", "Module F1",
        "Function SL", "Function REC", "Function PRE", "Function F1",
    ]
    for cutoff in SET_METRIC_K_VALUES:
        cutoff_label = "All" if cutoff == "all" else cutoff
        lines += [f"## Set Metrics @{cutoff_label}", ""]
        lines.append("| " + " | ".join(set_headers) + " |")
        lines.append("|" + "|".join(["---:"] * len(set_headers)) + "|")
        values = []
        for prefix in ("file", "module", "function"):
            values.extend(
                [
                    metrics.get(f"{prefix}_sl@{cutoff}", 0.0) * 100,
                    metrics.get(f"{prefix}_rec@{cutoff}", 0.0) * 100,
                    metrics.get(f"{prefix}_pre@{cutoff}", 0.0) * 100,
                    metrics.get(f"{prefix}_f1@{cutoff}", 0.0) * 100,
                ]
            )
        lines.append("| " + " | ".join(f"{value:.2f}" for value in values) + " |")
        lines.append("")
    return "\n".join(lines) + "\n"


def evaluate(samples: list[dict[str, Any]], preds: dict[str, dict[str, Any]], structure_dir: Path, output: Path, strict: bool) -> None:
    output.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    augmented_predictions: list[dict[str, Any]] = []
    totals: Counter = Counter()

    for sample in samples:
        instance_id = str(sample["instance_id"])
        pred = preds.get(instance_id, {"files": [], "modules": [], "functions": [], "response": ""})
        structure_path = structure_dir / f"{instance_id}.json"
        if not structure_path.exists():
            continue
        payload = json.loads(structure_path.read_text(encoding="utf-8", errors="ignore"))
        structure = payload.get("structure", payload)
        changed_lines = parse_changed_old_lines(sample.get("patch", ""))
        gt_files = {normalize(path) for path in sample.get("files", []) if normalize(path)}
        needed_files = ordered_unique(list(changed_lines) + pred["files"])
        entities_by_file = entities_for_files(structure, needed_files)

        gt_modules: set[str] = set()
        gt_functions: set[str] = set()
        for file_path, lines in changed_lines.items():
            overlaps = entities_overlapping_lines(entities_by_file.get(file_path, []), lines)
            for entity in overlaps:
                if entity.kind == "class":
                    gt_modules.add(module_id(entity))
                elif entity.kind in {"function", "method"}:
                    gt_functions.add(entity_id(entity))
                    gt_modules.add(module_id(entity))

        pred_files = pred["files"]
        context = sample.get("problem_statement", "") + "\n" + pred.get("response", "")
        candidate_entities: list[CodeEntity] = []
        for file_path in pred_files:
            candidate_entities.extend(entities_by_file.get(file_path, []))
        ranked_entities = rank_entities(candidate_entities, context, limit=15)
        pred_functions = pred["functions"] or [entity_id(e) for e in ranked_entities if e.kind in {"function", "method"}]
        pred_modules = pred["modules"] or [module_id(e) for e in ranked_entities]
        pred_modules = ordered_unique(pred_modules)
        pred_functions = ordered_unique(pred_functions)

        row: dict[str, Any] = {
            "instance_id": instance_id,
            "repo": sample.get("repo", ""),
            "gt_files": ";".join(sorted(gt_files)),
            "gt_modules": ";".join(sorted(gt_modules)),
            "gt_functions": ";".join(sorted(gt_functions)),
            "pred_files": ";".join(pred_files),
            "pred_modules": ";".join(pred_modules),
            "pred_functions": ";".join(pred_functions),
        }
        add_rank_metrics("file", pred_files, gt_files, row, totals, strict)
        add_rank_metrics("module", pred_modules, gt_modules, row, totals, strict)
        add_rank_metrics("function", pred_functions, gt_functions, row, totals, strict)
        rows.append(row)
        augmented_predictions.append(
            {
                "instance_id": instance_id,
                "found_files": pred_files,
                "found_modules": pred_modules,
                "found_functions": pred_functions,
            }
        )

    n = len(rows)
    metrics = {"evaluated": n, **{key: value / n for key, value in totals.items()}} if n else {"evaluated": 0}
    (output / "metrics_3level.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (output / "augmented_predictions.jsonl").open("w", encoding="utf-8") as fh:
        for row in augmented_predictions:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    if rows:
        with (output / "per_instance_metrics_3level.csv").open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    (output / "metrics_3level.md").write_text(render_markdown(metrics, n, strict), encoding="utf-8")
    print(f"Wrote {output / 'metrics_3level.md'}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fast three-level localization evaluator.")
    parser.add_argument("--samples", required=True)
    parser.add_argument("--pred-file", required=True)
    parser.add_argument("--structure-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--strict", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    evaluate(
        samples=load_jsonl(Path(args.samples)),
        preds=load_predictions(Path(args.pred_file)),
        structure_dir=Path(args.structure_dir),
        output=Path(args.output_dir),
        strict=args.strict,
    )


if __name__ == "__main__":
    main()
