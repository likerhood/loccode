#!/usr/bin/env python3
"""Collect existing baseline outputs into one review-friendly result view.

The script never reruns localization. It can:

1. scan standard result trees and unpacked archives;
2. copy compact prediction, metric, log, and trajectory artifacts;
3. optionally re-evaluate each result on a Clean15 subset;
4. write MANIFEST.json, INDEX.csv, and SUMMARY.md.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


ROOT_DIR = Path(__file__).resolve().parents[1]
BUILD_CLEAN = ROOT_DIR / "scripts/build_three_level_clean_subset.py"
REEVAL_CLEAN = ROOT_DIR / "scripts/reevaluate_existing_results_clean15.py"

KNOWN_BENCHMARKS = (
    "swebench_multimodal-full-dev",
    "swebench_multimodal-full-candidates",
    "swebench_multimodal-60",
    "omnigirl-full-candidates",
    "omnigirl-unified60",
    "omnigirl-60",
    "omnigirl-js-ts-multimodal-60",
    "swebench-multimodal-60",
)

SKIP_DIR_NAMES = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    "repo_playground",
    "repo_structures",
    "repo_skeleton",
    "repo_work",
    "repos",
    "repo_cache",
    "data",
    "clean_subsets",
    "collected_results",
    "result_archives",
}

PRIMARY_PRED_NAMES = {
    "loc_results.json",
    "merged_loc_outputs_mrr.jsonl",
    "loc_outputs.jsonl",
}

EVAL_DIRS = {
    "eval",
    "eval_strict",
    "eval_clean15",
    "eval_strict_clean15",
    "filtered_predictions_clean15",
}


@dataclass
class ResultSource:
    label: str
    baseline: str
    benchmark: str
    model: str
    result_dir: Path
    pred_file: Path
    method: str = ""
    samples: Path | None = None
    structure_dir: Path | None = None
    logs: list[Path] = field(default_factory=list)
    source_root: Path | None = None
    source_type: str = "scan"

    @property
    def baseline_key(self) -> str:
        if self.baseline == "mmir" and self.method:
            return f"mmir_{self.method}"
        return self.baseline


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT_DIR))
    except ValueError:
        return str(path.resolve())


def sanitize(value: str) -> str:
    value = value.strip() or "unknown"
    value = value.replace("/", "_")
    value = re.sub(r"[^0-9A-Za-z._-]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "unknown"


def normalize_model(value: str) -> str:
    value = value.strip() or "unknown"
    if value.startswith("openai_"):
        return value[len("openai_") :]
    if value.startswith("openai/"):
        return value[len("openai/") :]
    return value


def is_ignored_prediction_path(path: Path) -> bool:
    parts = set(path.parts)
    ignored = {
        "eval",
        "eval_strict",
        "eval_clean15",
        "eval_strict_clean15",
        "filtered_predictions_clean15",
    }
    return bool(parts & ignored)


def detect_baseline(path: Path) -> tuple[str, str]:
    parts = list(path.parts)
    if "LocAgent" in parts:
        return "locagent", ""
    if "CoSIL" in parts:
        return "cosil", ""
    if "GraphLocator" in parts:
        return "graphlocator", ""
    if "GALA" in parts:
        return "gala", ""
    if "MM-IR" in parts:
        method = ""
        if "results" in parts:
            idx = parts.index("results")
            if len(parts) > idx + 2:
                method = parts[idx + 2]
        return "mmir", method
    return "unknown", ""


def detect_benchmark(path: Path) -> str:
    parts = list(path.parts)
    for part in parts:
        if part in KNOWN_BENCHMARKS:
            return part
    text = str(path)
    for name in KNOWN_BENCHMARKS:
        if name in text:
            return name
    return "unknown"


def infer_result_dir(pred_file: Path, baseline: str) -> Path | None:
    if pred_file.name == "merged_loc_outputs_mrr.jsonl":
        if pred_file.parent.name == "location":
            return pred_file.parent.parent
        return pred_file.parent
    if pred_file.name == "loc_outputs.jsonl":
        if pred_file.parent.name in {"location", "file_level"}:
            return pred_file.parent.parent
        return pred_file.parent
    if pred_file.name == "loc_results.json":
        return pred_file.parent
    return None


def detect_model(result_dir: Path, baseline: str, method: str) -> str:
    if baseline == "mmir":
        return "retrieval"
    return normalize_model(result_dir.name)


def preferred_prediction(files: Iterable[Path]) -> Path:
    files = list(files)
    order = {
        "merged_loc_outputs_mrr.jsonl": 0,
        "loc_results.json": 1,
        "loc_outputs.jsonl": 2,
    }
    return sorted(files, key=lambda p: (order.get(p.name, 99), str(p)))[0]


def walk_prediction_files(root: Path) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        pruned: list[str] = []
        for name in dirnames:
            if name in SKIP_DIR_NAMES:
                continue
            if name.startswith("repo_"):
                continue
            pruned.append(name)
        dirnames[:] = pruned
        if is_ignored_prediction_path(current):
            dirnames[:] = []
            continue
        for filename in filenames:
            if filename in PRIMARY_PRED_NAMES:
                path = current / filename
                if path.name == "loc_outputs.jsonl" and path.parent.name not in {"location", "file_level"}:
                    continue
                yield path


def sample_source_defaults(repo_root: Path, benchmark: str) -> tuple[Path | None, Path | None]:
    mapping = {
        "swebench_multimodal-full-dev": (
            repo_root / "LocAgent/newtest/swebench_multimodal-full-dev/data/samples.jsonl",
            repo_root / "LocAgent/newtest/swebench_multimodal-full-dev/repo_structures",
        ),
        "swebench_multimodal-full-candidates": (
            repo_root / "MM-IR/data/swebench_multimodal-full-candidates/samples.jsonl",
            repo_root / "MM-IR/data/swebench_multimodal-full-candidates/repo_structures",
        ),
        "swebench_multimodal-60": (
            repo_root / "LocAgent/newtest/swebench_multimodal-60/data/samples.jsonl",
            repo_root / "LocAgent/newtest/swebench_multimodal-60/repo_structures",
        ),
        "omnigirl-full-candidates": (
            repo_root / "MM-IR/data/omnigirl-full-candidates/samples.jsonl",
            repo_root / "MM-IR/data/omnigirl-full-candidates/repo_structures",
        ),
        "omnigirl-unified60": (
            repo_root / "LocAgent/newtest/omnigirl-unified60/data/samples.jsonl",
            repo_root / "LocAgent/newtest/omnigirl-unified60/repo_structures",
        ),
        "omnigirl-60": (
            repo_root / "LocAgent/newtest/omnigirl-60/data/samples.jsonl",
            repo_root / "LocAgent/newtest/omnigirl-60/repo_structures",
        ),
    }
    return mapping.get(benchmark, (None, None))


def parse_sample_source(value: str) -> tuple[str, Path, Path]:
    if "=" not in value or "," not in value:
        raise argparse.ArgumentTypeError(
            "--sample-source must be benchmark=/path/samples.jsonl,/path/repo_structures"
        )
    benchmark, rest = value.split("=", 1)
    samples, structure = rest.split(",", 1)
    return benchmark.strip(), Path(samples).expanduser().resolve(), Path(structure).expanduser().resolve()


def load_config(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def source_from_config(item: dict[str, Any], repo_root: Path) -> ResultSource:
    result_dir = (repo_root / item["result_dir"]).resolve() if not Path(item["result_dir"]).is_absolute() else Path(item["result_dir"]).resolve()
    pred_file_raw = item.get("pred_file")
    if pred_file_raw:
        pred_file = (repo_root / pred_file_raw).resolve() if not Path(pred_file_raw).is_absolute() else Path(pred_file_raw).resolve()
    else:
        pred_file = preferred_prediction(find_prediction_files_in_result_dir(result_dir))
    baseline = item.get("baseline") or detect_baseline(result_dir)[0]
    method = item.get("method") or detect_baseline(result_dir)[1]
    benchmark = item.get("benchmark") or detect_benchmark(result_dir)
    model = item.get("model") or detect_model(result_dir, baseline, method)
    samples = item.get("samples")
    structure = item.get("structure_dir")
    logs = item.get("logs") or []
    return ResultSource(
        label=item.get("label") or f"{benchmark}_{model}_{baseline}_{method}".strip("_"),
        baseline=baseline,
        method=method,
        benchmark=benchmark,
        model=normalize_model(model),
        result_dir=result_dir,
        pred_file=pred_file,
        samples=(repo_root / samples).resolve() if samples and not Path(samples).is_absolute() else (Path(samples).resolve() if samples else None),
        structure_dir=(repo_root / structure).resolve() if structure and not Path(structure).is_absolute() else (Path(structure).resolve() if structure else None),
        logs=[(repo_root / p).resolve() if not Path(p).is_absolute() else Path(p).resolve() for p in logs],
        source_type="config",
    )


def find_prediction_files_in_result_dir(result_dir: Path) -> list[Path]:
    files: list[Path] = []
    candidates = [
        result_dir / "location/merged_loc_outputs_mrr.jsonl",
        result_dir / "location/loc_outputs.jsonl",
        result_dir / "file_level/loc_outputs.jsonl",
        result_dir / "loc_results.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            files.append(candidate)
    return files


def discover_sources(roots: list[Path], repo_root: Path) -> list[ResultSource]:
    grouped: dict[Path, list[Path]] = {}
    for root in roots:
        if not root.exists():
            print(f"[warn] scan root not found: {root}", file=sys.stderr)
            continue
        if root.is_file():
            pred = root.resolve()
            baseline, _ = detect_baseline(pred)
            result_dir = infer_result_dir(pred, baseline)
            if result_dir:
                grouped.setdefault(result_dir.resolve(), []).append(pred)
            continue
        for pred in walk_prediction_files(root.resolve()):
            baseline, _ = detect_baseline(pred)
            result_dir = infer_result_dir(pred, baseline)
            if result_dir:
                grouped.setdefault(result_dir.resolve(), []).append(pred.resolve())

    sources: list[ResultSource] = []
    for result_dir, files in sorted(grouped.items(), key=lambda kv: str(kv[0])):
        pred_file = preferred_prediction(files)
        baseline, method = detect_baseline(result_dir)
        benchmark = detect_benchmark(result_dir)
        model = detect_model(result_dir, baseline, method)
        if baseline == "unknown" or benchmark == "unknown":
            continue
        sources.append(
            ResultSource(
                label=f"{benchmark}_{model}_{baseline}_{method}".strip("_"),
                baseline=baseline,
                method=method,
                benchmark=benchmark,
                model=model,
                result_dir=result_dir,
                pred_file=pred_file,
                source_root=next((root for root in roots if str(result_dir).startswith(str(root.resolve()))), None),
                source_type="scan",
            )
        )
    return sources


def apply_sample_sources(
    sources: list[ResultSource],
    repo_root: Path,
    sample_sources: dict[str, tuple[Path, Path]],
) -> None:
    for source in sources:
        if source.samples and source.structure_dir:
            continue
        samples, structure = sample_sources.get(source.benchmark, (None, None))
        if not samples or not structure:
            samples, structure = sample_source_defaults(repo_root, source.benchmark)
        if samples and samples.exists():
            source.samples = samples
        if structure and structure.exists():
            source.structure_dir = structure


def filter_sources(
    sources: list[ResultSource],
    benchmarks: set[str],
    models: set[str],
    baselines: set[str],
) -> list[ResultSource]:
    kept: list[ResultSource] = []
    for source in sources:
        model_keys = {source.model, normalize_model(source.model), source.result_dir.name}
        baseline_keys = {source.baseline, source.baseline_key}
        if benchmarks and source.benchmark not in benchmarks:
            continue
        if models and not (model_keys & models):
            continue
        if baselines and not (baseline_keys & baselines):
            continue
        kept.append(source)
    return kept


def file_digest(path: Path) -> str:
    h = hashlib.sha1()
    h.update(str(path.resolve()).encode("utf-8", errors="ignore"))
    return h.hexdigest()[:8]


def copy_or_link(src: Path, dst: Path, link: bool, dry_run: bool) -> None:
    if not src.exists():
        return
    print(f"[copy] {rel(src)} -> {rel(dst)}")
    if dry_run:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() or dst.is_symlink():
        if dst.is_dir() and not dst.is_symlink():
            shutil.rmtree(dst)
        else:
            dst.unlink()
    if link:
        dst.symlink_to(src.resolve())
    else:
        shutil.copy2(src, dst)


def copy_tree_selected(src_dir: Path, dst_dir: Path, link: bool, dry_run: bool) -> int:
    if not src_dir.exists() or not src_dir.is_dir():
        return 0
    count = 0
    for path in sorted(src_dir.rglob("*")):
        if not path.is_file():
            continue
        rel_path = path.relative_to(src_dir)
        copy_or_link(path, dst_dir / rel_path, link, dry_run)
        count += 1
    return count


def is_compact_artifact(path: Path) -> bool:
    name = path.name
    if name in {"args.json", "localize.log"}:
        return True
    lowered = name.lower()
    if "traj" in lowered and path.suffix in {".json", ".jsonl", ".log"}:
        return True
    if "trajectory" in lowered and path.suffix in {".json", ".jsonl", ".log"}:
        return True
    if lowered.endswith(".log") and path.parent.name not in EVAL_DIRS:
        return True
    return False


def collect_result_files(
    source: ResultSource,
    dest_dir: Path,
    include_large: bool,
    include_instance_logs: bool,
    link: bool,
    dry_run: bool,
) -> dict[str, Any]:
    copied: dict[str, Any] = {
        "prediction_files": [],
        "metric_dirs": [],
        "artifact_files": [],
        "log_files": [],
        "full_tree": False,
    }
    primary_dst = dest_dir / "predictions" / source.pred_file.name
    copy_or_link(source.pred_file, primary_dst, link, dry_run)
    copied["prediction_files"].append(str(primary_dst.relative_to(dest_dir)))

    for pred in find_prediction_files_in_result_dir(source.result_dir):
        if pred.resolve() == source.pred_file.resolve():
            continue
        dst = dest_dir / "predictions" / pred.relative_to(source.result_dir)
        copy_or_link(pred, dst, link, dry_run)
        copied["prediction_files"].append(str(dst.relative_to(dest_dir)))

    for dirname in sorted(EVAL_DIRS):
        src = source.result_dir / dirname
        if src.exists():
            dst = dest_dir / ("metrics_clean15" if "clean15" in dirname or dirname.startswith("filtered") else "metrics_original") / dirname
            count = copy_tree_selected(src, dst, link, dry_run)
            if count:
                copied["metric_dirs"].append(str(dst.relative_to(dest_dir)))

    for path in sorted(source.result_dir.rglob("*")):
        if not path.is_file():
            continue
        rel_path = path.relative_to(source.result_dir)
        if rel_path.parts and rel_path.parts[0] in EVAL_DIRS:
            continue
        if path.resolve() == source.pred_file.resolve():
            continue
        if not include_large and not is_compact_artifact(path):
            continue
        if not include_instance_logs and path.suffix == ".log" and len(rel_path.parts) > 2:
            continue
        dst = dest_dir / ("full_result_tree" if include_large else "artifacts") / rel_path
        copy_or_link(path, dst, link, dry_run)
        copied["artifact_files"].append(str(dst.relative_to(dest_dir)))

    for log in source.logs:
        if log.exists():
            dst = dest_dir / "logs" / log.name
            copy_or_link(log, dst, link, dry_run)
            copied["log_files"].append(str(dst.relative_to(dest_dir)))

    copied["full_tree"] = include_large
    return copied


def metric_value(metrics: dict[str, Any], key: str) -> str:
    value = metrics.get(key)
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return f"{value * 100:.2f}"
    return str(value)


def load_metrics(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def first_metrics(paths: Iterable[Path]) -> dict[str, Any]:
    for path in paths:
        metrics = load_metrics(path)
        if metrics:
            return metrics
    return {}


def summarize_metrics(result_dir: Path) -> dict[str, str]:
    relaxed = first_metrics(
        [
            result_dir / "metrics_original/eval/metrics_3level.json",
            result_dir / "eval/metrics_3level.json",
        ]
    )
    strict = first_metrics(
        [
            result_dir / "metrics_original/eval_strict/metrics_3level.json",
            result_dir / "eval_strict/metrics_3level.json",
        ]
    )
    clean = first_metrics(
        [
            result_dir / "metrics_clean15/eval_clean15/metrics_3level.json",
            result_dir / "eval_clean15/metrics_3level.json",
        ]
    )
    clean_strict = first_metrics(
        [
            result_dir / "metrics_clean15/eval_strict_clean15/metrics_3level.json",
            result_dir / "eval_strict_clean15/metrics_3level.json",
        ]
    )
    return {
        "evaluated": str(relaxed.get("evaluated", "")),
        "file_acc1": metric_value(relaxed, "file_acc@1"),
        "file_acc5": metric_value(relaxed, "file_acc@5"),
        "file_acc15": metric_value(relaxed, "file_acc@15"),
        "module_acc15": metric_value(relaxed, "module_acc@15"),
        "function_acc15": metric_value(relaxed, "function_acc@15"),
        "strict_file_acc15": metric_value(strict, "file_acc@15"),
        "clean_evaluated": str(clean.get("evaluated", "")),
        "clean_file_acc15": metric_value(clean, "file_acc@15"),
        "clean_module_acc15": metric_value(clean, "module_acc@15"),
        "clean_function_acc15": metric_value(clean, "function_acc@15"),
        "clean_strict_file_acc15": metric_value(clean_strict, "file_acc@15"),
    }


def run_cmd(cmd: list[str], dry_run: bool) -> None:
    print("+ " + " ".join(cmd))
    if dry_run:
        return
    subprocess.run(cmd, check=True)


def detect_python(conda_env_root: str | None) -> str:
    env_python = os.environ.get("PYTHON_BIN")
    if env_python:
        return env_python
    if conda_env_root:
        candidate = Path(conda_env_root).expanduser() / "locagent/bin/python"
        if candidate.exists():
            return str(candidate)
    for candidate in (
        Path("/data2/like/envs/locagent/bin/python"),
        Path("/data/like/envs/locagent/bin/python"),
    ):
        if candidate.exists():
            return str(candidate)
    return sys.executable


def build_clean_subset(
    benchmark: str,
    samples: Path,
    structure_dir: Path,
    clean_root: Path,
    max_gold: int,
    mode: str,
    python_bin: str,
    dry_run: bool,
) -> Path:
    prefix = clean_root / f"{benchmark}.clean{max_gold}"
    clean_samples = Path(str(prefix) + ".samples.jsonl")
    if clean_samples.exists() and clean_samples.stat().st_size > 0:
        return clean_samples
    cmd = [
        python_bin,
        str(BUILD_CLEAN),
        "--samples",
        str(samples),
        "--structure-dir",
        str(structure_dir),
        "--output-prefix",
        str(prefix),
        "--mode",
        mode,
        "--max-gold",
        str(max_gold),
        "--write-diagnostic",
    ]
    run_cmd(cmd, dry_run)
    return clean_samples


def run_clean15_reeval(
    source: ResultSource,
    dest_dir: Path,
    clean_samples: Path,
    python_bin: str,
    suffix: str,
    force: bool,
    dry_run: bool,
) -> bool:
    if not source.structure_dir or not source.structure_dir.exists():
        print(f"[skip] {source.label}: structure dir missing; clean re-eval disabled")
        return False
    cmd = [
        python_bin,
        str(REEVAL_CLEAN),
        "--samples",
        str(clean_samples),
        "--pred-file",
        str(source.pred_file),
        "--structure-dir",
        str(source.structure_dir),
        "--result-dir",
        str(dest_dir),
        "--suffix",
        suffix,
        "--python",
        python_bin,
    ]
    if force:
        cmd.append("--force")
    if dry_run:
        cmd.append("--dry-run")
    run_cmd(cmd, dry_run)
    return True


def write_index(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "collection",
        "benchmark",
        "model",
        "baseline",
        "method",
        "status",
        "source_result_dir",
        "source_pred_file",
        "collected_dir",
        "evaluated",
        "file_acc1",
        "file_acc5",
        "file_acc15",
        "module_acc15",
        "function_acc15",
        "strict_file_acc15",
        "clean_evaluated",
        "clean_file_acc15",
        "clean_module_acc15",
        "clean_function_acc15",
        "clean_strict_file_acc15",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def write_summary(path: Path, name: str, rows: list[dict[str, Any]], manifests: list[dict[str, Any]]) -> None:
    lines: list[str] = []
    lines.append(f"# 结果汇总视图：{name}")
    lines.append("")
    lines.append(f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- 收集结果数：{len(rows)}")
    lines.append("- 指标数值单位：百分比；空白表示源结果中没有对应指标。")
    lines.append("")
    lines.append("## 结果索引")
    lines.append("")
    headers = [
        "Benchmark",
        "模型",
        "Baseline",
        "状态",
        "Eval",
        "File@1",
        "File@15",
        "Module@15",
        "Function@15",
        "Clean Eval",
        "Clean File@15",
        "Clean Module@15",
        "Clean Function@15",
    ]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join(["---"] * len(headers)) + "|")
    for row in rows:
        baseline = row["baseline"] if not row.get("method") else f"{row['baseline']}:{row['method']}"
        values = [
            row.get("benchmark", ""),
            row.get("model", ""),
            baseline,
            row.get("status", ""),
            row.get("evaluated", ""),
            row.get("file_acc1", ""),
            row.get("file_acc15", ""),
            row.get("module_acc15", ""),
            row.get("function_acc15", ""),
            row.get("clean_evaluated", ""),
            row.get("clean_file_acc15", ""),
            row.get("clean_module_acc15", ""),
            row.get("clean_function_acc15", ""),
        ]
        lines.append("| " + " | ".join(str(v) for v in values) + " |")
    lines.append("")
    lines.append("## 目录说明")
    lines.append("")
    lines.append("- `predictions/`：原始定位输出或过滤后的定位输出。")
    lines.append("- `metrics_original/`：原始 relaxed/strict 评估结果。")
    lines.append("- `metrics_clean15/`：Clean15 复评估结果和过滤后的预测文件。")
    lines.append("- `artifacts/`：轻量轨迹、参数和日志。")
    lines.append("- `logs/`：显式指定的运行日志。")
    lines.append("")
    lines.append("## 源结果")
    lines.append("")
    for item in manifests:
        lines.append(f"### {item['id']}")
        lines.append("")
        lines.append(f"- 源目录：`{item['source_result_dir']}`")
        lines.append(f"- 预测文件：`{item['source_pred_file']}`")
        lines.append(f"- 汇总目录：`{item['collected_dir']}`")
        if item.get("samples"):
            lines.append(f"- 样本文件：`{item['samples']}`")
        if item.get("structure_dir"):
            lines.append(f"- 结构目录：`{item['structure_dir']}`")
        if item.get("warnings"):
            lines.append(f"- 警告：{'; '.join(item['warnings'])}")
        lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect baseline results into one unified review folder.")
    parser.add_argument("--name", default="", help="Collection name. Defaults to timestamp.")
    parser.add_argument("--output-root", default=str(ROOT_DIR / "collected_results"))
    parser.add_argument("--scan-root", action="append", default=[], help="Root to scan. Can be repeated.")
    parser.add_argument("--result-dir", action="append", default=[], help="Explicit result dir to scan. Can be repeated.")
    parser.add_argument("--config", default="", help="JSON config with explicit result sources.")
    parser.add_argument("--sample-source", action="append", default=[], type=parse_sample_source)
    parser.add_argument("--benchmark", action="append", default=[], help="Keep only this benchmark. Can be repeated.")
    parser.add_argument("--model", action="append", default=[], help="Keep only this model tag. Can be repeated.")
    parser.add_argument("--baseline", action="append", default=[], help="Keep only this baseline. Can be repeated.")
    parser.add_argument("--clean15", action="store_true", help="Run Clean15 re-evaluation into the collected view.")
    parser.add_argument("--max-gold", type=int, default=15)
    parser.add_argument("--clean-mode", default="three-level", choices=("three-level", "file-only"))
    parser.add_argument("--clean-suffix", default="clean15")
    parser.add_argument("--python", default="")
    parser.add_argument("--conda-env-root", default=os.environ.get("CONDA_ENV_ROOT", ""))
    parser.add_argument("--include-large", action="store_true", help="Copy full result trees instead of compact artifacts.")
    parser.add_argument("--include-instance-logs", action="store_true", help="Include nested per-instance logs.")
    parser.add_argument("--link", action="store_true", help="Symlink instead of copying files.")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing collection directory.")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    repo_root = ROOT_DIR
    name = sanitize(args.name or f"result_view_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    output_root = Path(args.output_root).expanduser().resolve()
    collection_dir = output_root / name
    python_bin = args.python or detect_python(args.conda_env_root)

    if collection_dir.exists() and not args.force and not args.dry_run:
        raise SystemExit(f"collection already exists: {collection_dir}. Use --force or a new --name.")
    if collection_dir.exists() and args.force and not args.dry_run:
        shutil.rmtree(collection_dir)
    if not args.dry_run:
        collection_dir.mkdir(parents=True, exist_ok=True)

    sample_sources: dict[str, tuple[Path, Path]] = {k: (s, d) for k, s, d in args.sample_source}
    config: dict[str, Any] = {}
    sources: list[ResultSource] = []
    if args.config:
        config_path = Path(args.config).expanduser().resolve()
        config = load_config(config_path)
        if not args.name and config.get("name"):
            name = sanitize(config["name"])
            collection_dir = output_root / name
            if collection_dir.exists() and args.force and not args.dry_run:
                shutil.rmtree(collection_dir)
            if not args.dry_run:
                collection_dir.mkdir(parents=True, exist_ok=True)
        for bench, spec in (config.get("sample_sources") or {}).items():
            sample_sources[bench] = (
                (repo_root / spec["samples"]).resolve() if not Path(spec["samples"]).is_absolute() else Path(spec["samples"]).resolve(),
                (repo_root / spec["structure_dir"]).resolve()
                if not Path(spec["structure_dir"]).is_absolute()
                else Path(spec["structure_dir"]).resolve(),
            )
        for item in config.get("items", []):
            sources.append(source_from_config(item, repo_root))

    scan_roots = [Path(p).expanduser().resolve() for p in args.scan_root]
    scan_roots.extend(Path(p).expanduser().resolve() for p in args.result_dir)
    if not scan_roots and not sources:
        scan_roots = [repo_root, repo_root / "unpacked_results"]
    if scan_roots:
        sources.extend(discover_sources(scan_roots, repo_root))

    # Deduplicate by source result dir and prediction file.
    dedup: dict[tuple[str, str], ResultSource] = {}
    for source in sources:
        dedup[(str(source.result_dir), str(source.pred_file))] = source
    sources = list(dedup.values())

    apply_sample_sources(sources, repo_root, sample_sources)
    sources = filter_sources(sources, set(args.benchmark), set(args.model), set(args.baseline))

    print(f"Collection: {name}")
    print(f"Output:     {collection_dir}")
    print(f"Python:     {python_bin}")
    print(f"Sources:    {len(sources)}")
    print(f"Clean15:    {int(args.clean15)}")

    clean_cache: dict[tuple[str, str, str], Path] = {}
    rows: list[dict[str, Any]] = []
    manifest_items: list[dict[str, Any]] = []

    for source in sorted(sources, key=lambda s: (s.benchmark, s.model, s.baseline_key, str(s.result_dir))):
        item_id_base = f"{sanitize(source.benchmark)}/{sanitize(source.model)}/{sanitize(source.baseline_key)}"
        item_dir = collection_dir / item_id_base
        if item_dir.exists():
            item_dir = collection_dir / item_id_base / file_digest(source.result_dir)
        warnings: list[str] = []
        status = "ok"
        if not source.pred_file.exists():
            status = "missing_prediction"
            warnings.append("prediction file missing")
        if args.clean15 and not source.samples:
            warnings.append("samples missing; clean re-eval skipped")
        if args.clean15 and not source.structure_dir:
            warnings.append("structure dir missing; clean re-eval skipped")

        print("")
        print(f"========== Collect {source.benchmark} / {source.model} / {source.baseline_key} ==========")
        print(f"[source] {source.result_dir}")
        print(f"[pred]   {source.pred_file}")
        print(f"[dest]   {item_dir}")

        copied = collect_result_files(
            source,
            item_dir,
            include_large=args.include_large,
            include_instance_logs=args.include_instance_logs,
            link=args.link,
            dry_run=args.dry_run,
        )

        clean_ran = False
        if args.clean15 and source.samples and source.structure_dir and source.pred_file.exists():
            clean_key = (source.benchmark, str(source.samples), str(source.structure_dir))
            clean_samples = clean_cache.get(clean_key)
            if clean_samples is None:
                clean_samples = build_clean_subset(
                    source.benchmark,
                    source.samples,
                    source.structure_dir,
                    collection_dir / "clean_subsets",
                    args.max_gold,
                    args.clean_mode,
                    python_bin,
                    args.dry_run,
                )
                clean_cache[clean_key] = clean_samples
            clean_ran = run_clean15_reeval(
                source,
                item_dir / "metrics_clean15",
                clean_samples,
                python_bin,
                args.clean_suffix,
                args.force,
                args.dry_run,
            )
            if not clean_ran:
                warnings.append("clean re-eval skipped")

        metrics = summarize_metrics(item_dir)
        row = {
            "collection": name,
            "benchmark": source.benchmark,
            "model": source.model,
            "baseline": source.baseline,
            "method": source.method,
            "status": status,
            "source_result_dir": str(source.result_dir),
            "source_pred_file": str(source.pred_file),
            "collected_dir": str(item_dir),
            **metrics,
        }
        rows.append(row)
        manifest_items.append(
            {
                "id": item_id_base,
                "label": source.label,
                "baseline": source.baseline,
                "method": source.method,
                "benchmark": source.benchmark,
                "model": source.model,
                "status": status,
                "source_type": source.source_type,
                "source_result_dir": str(source.result_dir),
                "source_pred_file": str(source.pred_file),
                "collected_dir": str(item_dir),
                "samples": str(source.samples) if source.samples else "",
                "structure_dir": str(source.structure_dir) if source.structure_dir else "",
                "copied": copied,
                "clean15_ran": clean_ran,
                "warnings": warnings,
            }
        )

    manifest = {
        "name": name,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "root_dir": str(repo_root),
        "output_dir": str(collection_dir),
        "clean15": bool(args.clean15),
        "max_gold": args.max_gold,
        "clean_mode": args.clean_mode,
        "items": manifest_items,
    }

    if not args.dry_run:
        (collection_dir / "MANIFEST.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        write_index(collection_dir / "INDEX.csv", rows)
        write_summary(collection_dir / "SUMMARY.md", name, rows, manifest_items)

    print("")
    print("Done.")
    print(f"  {collection_dir / 'SUMMARY.md'}")
    print(f"  {collection_dir / 'INDEX.csv'}")
    print(f"  {collection_dir / 'MANIFEST.json'}")


if __name__ == "__main__":
    main()
