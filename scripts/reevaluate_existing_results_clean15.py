#!/usr/bin/env python3
"""Re-evaluate existing localization predictions on a clean sample subset.

This script does not rerun any baseline. It optionally writes a filtered copy of
the prediction file for readability, then runs the shared LocAgent file-level
and three-level evaluators against the clean samples.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
LOCAGENT_ROOT = ROOT_DIR / "LocAgent"
EVAL_FILE = LOCAGENT_ROOT / "newtest/scripts/eval_file_level.py"
EVAL_THREE = LOCAGENT_ROOT / "newtest/scripts/eval_3level_localization.py"
EVAL_STRICT = LOCAGENT_ROOT / "newtest/scripts/eval_3level_localization_strict.py"
EVAL_FAST = ROOT_DIR / "scripts/eval_3level_localization_fast.py"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def sample_ids(path: Path) -> set[str]:
    return {str(row.get("instance_id")) for row in load_jsonl(path) if row.get("instance_id")}


def prediction_instance_id(row: dict[str, Any]) -> str:
    for key in ("instance_id", "id", "instance"):
        if row.get(key):
            return str(row[key])
    return ""


def filter_predictions(pred_file: Path, ids: set[str], output_file: Path) -> tuple[int, int]:
    """Filter common JSON/JSONL prediction formats.

    Returns (input_count, kept_count). Unknown formats are copied as-is only if
    they are already a dict keyed by instance_id.
    """
    output_file.parent.mkdir(parents=True, exist_ok=True)
    if pred_file.suffix == ".jsonl":
        rows = load_jsonl(pred_file)
        kept = [row for row in rows if prediction_instance_id(row) in ids]
        with output_file.open("w", encoding="utf-8") as fh:
            for row in kept:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        return len(rows), len(kept)

    payload = json.loads(pred_file.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        kept_rows = [row for row in payload if isinstance(row, dict) and prediction_instance_id(row) in ids]
        output_file.write_text(json.dumps(kept_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return len(payload), len(kept_rows)

    if isinstance(payload, dict):
        if isinstance(payload.get("results"), list):
            rows = payload["results"]
            kept_rows = [row for row in rows if isinstance(row, dict) and prediction_instance_id(row) in ids]
            filtered = dict(payload)
            filtered["results"] = kept_rows
            output_file.write_text(json.dumps(filtered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return len(rows), len(kept_rows)
        if isinstance(payload.get("loc_results"), dict):
            rows = payload["loc_results"]
            kept = {key: value for key, value in rows.items() if str(key) in ids}
            filtered = dict(payload)
            filtered["loc_results"] = kept
            output_file.write_text(json.dumps(filtered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return len(rows), len(kept)
        kept = {key: value for key, value in payload.items() if str(key) in ids}
        output_file.write_text(json.dumps(kept, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return len(payload), len(kept)

    raise ValueError(f"Unsupported prediction payload in {pred_file}")


def run_cmd(cmd: list[str], dry_run: bool) -> None:
    print("+ " + " ".join(cmd))
    if dry_run:
        return
    subprocess.run(cmd, check=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Re-evaluate existing predictions on clean samples.")
    parser.add_argument("--samples", required=True, help="Clean samples JSONL.")
    parser.add_argument("--pred-file", required=True, help="Existing prediction file.")
    parser.add_argument("--structure-dir", required=True, help="repo_structures matching the original samples.")
    parser.add_argument("--result-dir", required=True, help="Baseline result directory where eval_clean15 will be written.")
    parser.add_argument("--suffix", default="clean15", help="Output suffix, e.g. clean15.")
    parser.add_argument("--python", default=sys.executable, help="Python executable for evaluators.")
    parser.add_argument("--skip-filtered-predictions", action="store_true", help="Do not write filtered_predictions_<suffix>.")
    parser.add_argument(
        "--eval-backend",
        choices=("fast", "official"),
        default="fast",
        help="fast parses only touched/predicted files; official reuses LocAgent's full repo_structure evaluator.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing clean metrics.")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    samples = Path(args.samples).resolve()
    pred_file = Path(args.pred_file).resolve()
    structure_dir = Path(args.structure_dir).resolve()
    result_dir = Path(args.result_dir).resolve()

    if not samples.exists():
        raise SystemExit(f"clean samples not found: {samples}")
    if not pred_file.exists():
        raise SystemExit(f"prediction file not found: {pred_file}")
    if not structure_dir.exists():
        raise SystemExit(f"structure dir not found: {structure_dir}")

    eval_dir = result_dir / f"eval_{args.suffix}"
    strict_dir = result_dir / f"eval_strict_{args.suffix}"
    relaxed_marker = eval_dir / "metrics_3level.md"
    strict_marker = strict_dir / "metrics_3level.md"
    if relaxed_marker.exists() and strict_marker.exists() and not args.force:
        print(f"[skip] clean metrics already exist: {relaxed_marker}")
        print(f"[skip] clean metrics already exist: {strict_marker}")
        return

    result_dir.mkdir(parents=True, exist_ok=True)
    eval_dir.mkdir(parents=True, exist_ok=True)
    strict_dir.mkdir(parents=True, exist_ok=True)

    eval_pred = pred_file
    if not args.skip_filtered_predictions:
        ids = sample_ids(samples)
        filtered_dir = result_dir / f"filtered_predictions_{args.suffix}"
        filtered_path = filtered_dir / pred_file.name
        total, kept = filter_predictions(pred_file, ids, filtered_path)
        eval_pred = filtered_path
        print(f"[filter] predictions total={total}, kept={kept}, output={filtered_path}")

    run_cmd(
        [
            args.python,
            str(EVAL_FILE),
            "--samples",
            str(samples),
            "--pred-file",
            str(eval_pred),
            "--output-dir",
            str(eval_dir),
        ],
        args.dry_run,
    )
    if args.eval_backend == "fast":
        relaxed_script = strict_script = EVAL_FAST
        relaxed_extra: list[str] = []
        strict_extra = ["--strict"]
    else:
        relaxed_script = EVAL_THREE
        strict_script = EVAL_STRICT
        relaxed_extra = []
        strict_extra = []

    run_cmd(
        [
            args.python,
            str(relaxed_script),
            "--samples",
            str(samples),
            "--pred-file",
            str(eval_pred),
            "--structure-dir",
            str(structure_dir),
            "--output-dir",
            str(eval_dir),
            *relaxed_extra,
        ],
        args.dry_run,
    )
    run_cmd(
        [
            args.python,
            str(strict_script),
            "--samples",
            str(samples),
            "--pred-file",
            str(eval_pred),
            "--structure-dir",
            str(structure_dir),
            "--output-dir",
            str(strict_dir),
            *strict_extra,
        ],
        args.dry_run,
    )
    print(f"[done] relaxed: {eval_dir / 'metrics_3level.md'}")
    print(f"[done] strict:  {strict_dir / 'metrics_3level.md'}")


if __name__ == "__main__":
    main()
