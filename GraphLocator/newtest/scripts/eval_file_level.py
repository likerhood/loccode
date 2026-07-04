#!/usr/bin/env python3
"""Evaluate file-level localization outputs from multiple baselines."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


TOP_K_VALUES = tuple(range(1, 16))
RANK_METRIC_K = 15
SET_METRIC_K_VALUES = (10, 15)


def normalize(path: Any, repo: Any = "") -> str:
    text = str(path or "").strip().replace("\\", "/")
    if text.startswith("a/") or text.startswith("b/"):
        text = text[2:]
    text = text.lstrip("./")
    repo_leaf = str(repo or "").strip().replace("\\", "/").rstrip("/").split("/")[-1]
    if repo_leaf and text.startswith(f"{repo_leaf}/"):
        text = text[len(repo_leaf) + 1:]
    return text


def ordered_unique(values: list[Any], repo: Any = "") -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in values:
        normalized = normalize(item, repo)
        if normalized and normalized not in seen:
            seen.add(normalized)
            out.append(normalized)
    return out


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_predictions(path: Path) -> dict[str, list[str]]:
    if not path.exists():
        return {}
    if path.suffix == ".jsonl":
        rows = load_jsonl(path)
        return {str(row.get("instance_id")): prediction_files(row) for row in rows}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return {str(row.get("instance_id")): prediction_files(row) for row in payload if isinstance(row, dict)}
    if isinstance(payload, dict):
        out: dict[str, list[str]] = {}
        for instance_id, value in payload.items():
            if isinstance(value, dict):
                out[str(instance_id)] = prediction_files(value)
            elif isinstance(value, list):
                out[str(instance_id)] = ordered_unique(value)
        return out
    return {}


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
        for key in ("file_path", "file", "path", "filename"):
            if values.get(key):
                return [values[key]]
    return []


def prediction_files(row: dict[str, Any]) -> list[str]:
    for key in ("found_files", "final_files", "pred_files", "files"):
        if key in row:
            return ordered_unique(flatten(row.get(key)))
    if "bug_locations" in row:
        return ordered_unique(flatten(row.get("bug_locations")))
    return []


def acc_at_k(pred: list[str], gt: set[str], k: int) -> float:
    return float(bool(gt & set(pred[:k])))


def reciprocal_rank(pred: list[str], gt: set[str], k: int | None = None) -> float:
    candidates = pred[:k] if k is not None else pred
    for index, item in enumerate(candidates, start=1):
        if item in gt:
            return 1.0 / index
    return 0.0


def average_precision(pred: list[str], gt: set[str], k: int | None = None) -> float:
    if not gt:
        return 0.0
    hits = 0
    score = 0.0
    seen: set[str] = set()
    candidates = pred[:k] if k is not None else pred
    for index, item in enumerate(candidates, start=1):
        if item in seen:
            continue
        seen.add(item)
        if item in gt:
            hits += 1
            score += hits / index
    return score / len(gt)


def set_metrics_at_k(pred: list[str], gt: set[str], k: int) -> dict[str, float]:
    pred_set = set(pred[:k])
    hit_count = len(gt & pred_set)
    recall = hit_count / len(gt) if gt else 0.0
    precision = hit_count / len(pred_set) if pred_set else 0.0
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return {
        f"success_location@{k}": float(bool(gt) and gt <= pred_set),
        f"recall@{k}": recall,
        f"precision@{k}": precision,
        f"f1@{k}": f1,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", required=True)
    parser.add_argument("--pred-file", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    samples = load_jsonl(Path(args.samples))
    preds = load_predictions(Path(args.pred_file))
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)

    rows = []
    metric_keys = [f"acc@{k}" for k in TOP_K_VALUES] + ["mrr", "map", "empty"]
    for k in SET_METRIC_K_VALUES:
        metric_keys.extend([f"success_location@{k}", f"recall@{k}", f"precision@{k}", f"f1@{k}"])
    totals = {key: 0.0 for key in metric_keys}
    for sample in samples:
        instance_id = str(sample["instance_id"])
        repo = sample.get("repo", "")
        gt = {normalize(path, repo) for path in sample.get("files", []) if normalize(path, repo)}
        pred = ordered_unique(preds.get(instance_id, []), repo)
        row = {
            "instance_id": instance_id,
            "repo": sample.get("repo", ""),
            "gt_files": ";".join(sorted(gt)),
            "pred_files": ";".join(pred),
            "pred_count": len(pred),
            "empty": int(not pred),
        }
        for k in TOP_K_VALUES:
            row[f"acc@{k}"] = acc_at_k(pred, gt, k)
            totals[f"acc@{k}"] += row[f"acc@{k}"]
        for k in SET_METRIC_K_VALUES:
            for key, value in set_metrics_at_k(pred, gt, k).items():
                row[key] = value
                totals[key] += value
        row["mrr"] = reciprocal_rank(pred, gt, RANK_METRIC_K)
        row["map"] = average_precision(pred, gt, RANK_METRIC_K)
        totals["mrr"] += row["mrr"]
        totals["map"] += row["map"]
        totals["empty"] += row["empty"]
        rows.append(row)

    n = len(rows)
    metrics = {
        "evaluated": n,
        "prediction_instances": len(preds),
        **{key: (value / n if n else 0.0) for key, value in totals.items()},
    }
    (output / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if rows:
        with (output / "per_instance_metrics.csv").open("w", encoding="utf-8", newline="") as outfile:
            writer = csv.DictWriter(outfile, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    lines = [
        "# File-Level Localization Metrics",
        "",
        f"- Evaluated: {n}",
        f"- Prediction instances: {len(preds)}",
        "",
        "## Acc@k",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]
    for key in [f"acc@{k}" for k in TOP_K_VALUES] + [f"mrr@{RANK_METRIC_K}", f"map@{RANK_METRIC_K}", "empty"]:
        metric_key = "mrr" if key.startswith("mrr@") else "map" if key.startswith("map@") else key
        lines.append(f"| {key} | {metrics[metric_key] * 100:.2f}% |")
    for cutoff in SET_METRIC_K_VALUES:
        lines.extend(
            [
                "",
                f"## Set Metrics @{cutoff}",
                "",
                "| Metric | Value |",
                "|---|---:|",
            ]
        )
        for key in (
            f"success_location@{cutoff}",
            f"recall@{cutoff}",
            f"precision@{cutoff}",
            f"f1@{cutoff}",
        ):
            lines.append(f"| {key} | {metrics[key] * 100:.2f}% |")
    (output / "metrics.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {output / 'metrics.md'}")


if __name__ == "__main__":
    main()
