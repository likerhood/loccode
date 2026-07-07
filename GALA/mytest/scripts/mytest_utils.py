#!/usr/bin/env python3
"""Utilities for GALA localization-only experiments.

The helpers in this file are intentionally local to ``mytest`` so the test
pipeline stays independent from GALA's research pipeline.
"""

from __future__ import annotations

import csv
import json
import os
import random
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence


GALA_SOURCE_EXTENSIONS = {
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".scss",
    ".css",
    ".json",
    ".html",
    ".md",
    ".mdx",
    ".svg",
    ".frag",
    ".vert",
}


def ordered_unique(values: Iterable[str]) -> List[str]:
    seen = set()
    output: List[str] = []
    for value in values:
        normalized = normalize_file_path(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        output.append(normalized)
    return output


def normalize_file_path(path: Any) -> str:
    if path is None:
        return ""
    text = str(path).strip().replace("\\", "/")
    if not text:
        return ""
    text = re.sub(r"^['\"]|['\"]$", "", text)
    text = re.sub(r"^[ab]/", "", text)
    text = text.lstrip("./")
    while "//" in text:
        text = text.replace("//", "/")
    return text


def patch_modified_files(patch_text: Any) -> List[str]:
    """Extract modified file paths from a unified git patch."""
    if not patch_text:
        return []
    files: List[str] = []
    for raw_line in str(patch_text).splitlines():
        line = raw_line.strip()
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4:
                left = normalize_file_path(parts[2])
                right = normalize_file_path(parts[3])
                if right != "dev/null":
                    files.append(right)
                elif left != "dev/null":
                    files.append(left)
        elif line.startswith("+++ "):
            candidate = normalize_file_path(line[4:].strip())
            if candidate != "dev/null":
                files.append(candidate)
    return ordered_unique(files)


def is_gala_compatible_file(path: str) -> bool:
    suffix = Path(normalize_file_path(path)).suffix.lower()
    return suffix in GALA_SOURCE_EXTENSIONS


def is_gala_compatible_record(record: Dict[str, Any], allow_missing_patch: bool = False) -> bool:
    files = patch_modified_files(record.get("patch") or record.get("gold_patch") or "")
    if not files and allow_missing_patch:
        return True
    return any(is_gala_compatible_file(path) for path in files)


def parse_image_assets(raw_assets: Any) -> Dict[str, List[str]]:
    if raw_assets is None or raw_assets == "":
        return {"problem_statement": []}
    parsed: Any
    if isinstance(raw_assets, str):
        try:
            parsed = json.loads(raw_assets)
        except json.JSONDecodeError:
            return {"problem_statement": []}
    else:
        parsed = raw_assets
    if not isinstance(parsed, dict):
        return {"problem_statement": []}
    images = parsed.get("problem_statement", [])
    if isinstance(images, str):
        images = [images]
    if not isinstance(images, list):
        images = []
    return {"problem_statement": [str(item) for item in images if str(item).strip()]}


def _coerce_string_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, list):
                return [str(item) for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            pass
        return [stripped]
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return []


def extract_problem_images(record: Dict[str, Any]) -> List[str]:
    images = parse_image_assets(record.get("image_assets")).get("problem_statement", [])
    if images:
        return images
    return _coerce_string_list(record.get("image_urls"))


def has_problem_images(record: Dict[str, Any]) -> bool:
    return bool(extract_problem_images(record))


def coerce_record_id(record: Dict[str, Any], fallback: str = "") -> str:
    for key in ("instance_id", "id", "task_id"):
        value = str(record.get(key) or "").strip()
        if value:
            return value
    return fallback


def coerce_repo(record: Dict[str, Any]) -> str:
    for key in ("repo", "repository", "repo_name"):
        value = str(record.get(key) or "").strip()
        if value:
            return value
    return ""


def coerce_problem_statement(record: Dict[str, Any]) -> str:
    parts = []
    for key in ("problem_statement", "issue", "issue_text", "body", "description", "title"):
        value = str(record.get(key) or "").strip()
        if value and value not in parts:
            parts.append(value)
    website_links = _coerce_string_list(record.get("website links") or record.get("website_links") or record.get("urls"))
    if website_links:
        parts.append("Related website links:\n" + "\n".join(f"- {url}" for url in website_links))
    return "\n\n".join(parts)


def to_gala_doc(record: Dict[str, Any], instance_id: str | None = None) -> Dict[str, Any]:
    resolved_id = instance_id or coerce_record_id(record)
    image_assets = {"problem_statement": extract_problem_images(record)}
    return {
        "repo": coerce_repo(record),
        "instance_id": resolved_id,
        "base_commit": str(record.get("base_commit") or record.get("commit") or "").strip(),
        "patch": str(record.get("patch") or record.get("gold_patch") or ""),
        "test_patch": str(record.get("test_patch") or ""),
        "problem_statement": coerce_problem_statement(record),
        "hints_text": str(record.get("hints_text") or ""),
        "created_at": str(record.get("created_at") or ""),
        "image_assets": json.dumps(image_assets, ensure_ascii=False),
    }


def load_records(path: str) -> List[Dict[str, Any]]:
    input_path = Path(path)
    suffix = input_path.suffix.lower()
    if suffix == ".jsonl":
        rows = []
        with input_path.open(encoding="utf-8") as infile:
            for line in infile:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        return rows
    if suffix == ".json":
        with input_path.open(encoding="utf-8") as infile:
            loaded = json.load(infile)
        if isinstance(loaded, dict):
            rows = []
            for key, value in loaded.items():
                if isinstance(value, dict):
                    row = dict(value)
                    row.setdefault("instance_id", key)
                    rows.append(row)
            return rows
        if isinstance(loaded, list):
            return [row for row in loaded if isinstance(row, dict)]
        raise ValueError(f"Unsupported JSON structure: {path}")
    if suffix == ".parquet":
        import pandas as pd  # Imported lazily for lightweight unit tests.

        df = pd.read_parquet(input_path)
        return [row for row in df.to_dict(orient="records") if isinstance(row, dict)]
    raise ValueError(f"Unsupported input file type: {path}")


def load_hf_records(dataset: str, split: str) -> List[Dict[str, Any]]:
    from datasets import load_dataset  # Imported lazily.

    ds = load_dataset(dataset, split=split)
    return [dict(row) for row in ds]


def select_records(
    records: Sequence[Dict[str, Any]],
    sample_size: int,
    seed: int,
    require_images: bool = True,
    require_gala_compatible: bool = True,
    allow_missing_patch: bool = False,
) -> List[Dict[str, Any]]:
    filtered = []
    for record in records:
        if require_images and not has_problem_images(record):
            continue
        if require_gala_compatible and not is_gala_compatible_record(record, allow_missing_patch=allow_missing_patch):
            continue
        filtered.append(record)
    rng = random.Random(seed)
    filtered = list(filtered)
    rng.shuffle(filtered)
    return filtered[:sample_size]


def write_json(path: str | Path, payload: Any) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_jsonl(path: str | Path, rows: Sequence[Dict[str, Any]]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as outfile:
        for row in rows:
            outfile.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_csv(path: str | Path, rows: Sequence[Dict[str, Any]], fieldnames: Sequence[str]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def build_prepared_dataset(
    selected: Sequence[Dict[str, Any]],
    output_dir: str | Path,
) -> Dict[str, Any]:
    output = Path(output_dir)
    docs: Dict[str, Dict[str, Any]] = {}
    gt_files: Dict[str, List[str]] = {}
    rows: List[Dict[str, Any]] = []
    repo_urls: Dict[str, str] = {}

    for index, record in enumerate(selected):
        instance_id = coerce_record_id(record, fallback=f"sample_{index:04d}")
        doc = to_gala_doc(record, instance_id=instance_id)
        docs[instance_id] = doc
        rows.append(doc)
        gt_files[instance_id] = patch_modified_files(doc.get("patch", ""))
        repo = doc.get("repo", "")
        if repo and "/" in repo:
            repo_urls[repo] = f"https://github.com/{repo}.git"

    write_json(output / "samples.json", docs)
    write_jsonl(output / "samples.jsonl", rows)
    write_json(output / "gt_files.json", gt_files)
    write_json(output / "repo_urls.json", repo_urls)
    summary = {
        "sample_count": len(docs),
        "repo_count": len(repo_urls),
        "instances": list(docs),
    }
    write_json(output / "dataset_summary.json", summary)
    return summary


def acc_at_k(predictions: Sequence[str], gt_files: Sequence[str], k: int) -> int:
    gt_set = {normalize_file_path(item) for item in gt_files if normalize_file_path(item)}
    if not gt_set:
        return 0
    return int(any(normalize_file_path(item) in gt_set for item in predictions[:k]))


def reciprocal_rank(predictions: Sequence[str], gt_files: Sequence[str], k: int | None = None) -> float:
    gt_set = {normalize_file_path(item) for item in gt_files if normalize_file_path(item)}
    if not gt_set:
        return 0.0
    candidates = predictions[:k] if k is not None else predictions
    for index, item in enumerate(candidates, start=1):
        if normalize_file_path(item) in gt_set:
            return 1.0 / index
    return 0.0


def average_precision(predictions: Sequence[str], gt_files: Sequence[str], k: int | None = None) -> float:
    gt_set = {normalize_file_path(item) for item in gt_files if normalize_file_path(item)}
    if not gt_set:
        return 0.0
    hits = 0
    score = 0.0
    seen = set()
    candidates = predictions[:k] if k is not None else predictions
    for index, item in enumerate(candidates, start=1):
        normalized = normalize_file_path(item)
        if normalized in seen:
            continue
        seen.add(normalized)
        if normalized in gt_set:
            hits += 1
            score += hits / index
    return score / len(gt_set)


def summarize_metrics(per_instance: Sequence[Dict[str, Any]], prefix: str) -> Dict[str, float]:
    total = len(per_instance)
    acc_keys = [f"{prefix}_acc@{k}" for k in range(1, 16)]
    set_metric_keys = []
    for k in ("8", "10", "15", "all"):
        set_metric_keys.extend(
            [
                f"{prefix}_success_location@{k}",
                f"{prefix}_recall@{k}",
                f"{prefix}_precision@{k}",
                f"{prefix}_f1@{k}",
            ]
        )
    if total == 0:
        empty_metrics = {
            f"{prefix}_total": 0,
            f"{prefix}_mrr": 0.0,
            f"{prefix}_map": 0.0,
            f"{prefix}_empty_rate": 0.0,
        }
        empty_metrics.update({key: 0.0 for key in acc_keys + set_metric_keys})
        return empty_metrics
    metrics = {
        f"{prefix}_total": total,
        f"{prefix}_mrr": sum(row[f"{prefix}_mrr"] for row in per_instance) / total,
        f"{prefix}_map": sum(row[f"{prefix}_map"] for row in per_instance) / total,
        f"{prefix}_empty_rate": sum(row[f"{prefix}_empty"] for row in per_instance) / total,
    }
    for key in acc_keys + set_metric_keys:
        metrics[key] = sum(row.get(key, 0.0) for row in per_instance) / total
    return metrics


def maybe_prefixed_github_url(repo: str, mirror_prefix: str = "") -> str:
    url = f"https://github.com/{repo}.git"
    prefix = mirror_prefix.strip()
    if not prefix:
        return url
    return prefix.rstrip("/") + "/" + url
