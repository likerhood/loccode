#!/usr/bin/env python3
"""Prepare a GALA localization subset from SWE-bench Multimodal."""

from __future__ import annotations

import argparse
from pathlib import Path

from mytest_utils import build_prepared_dataset, load_hf_records, load_records, select_records


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="SWE-bench/SWE-bench_Multimodal")
    parser.add_argument("--split", default="test")
    parser.add_argument("--input-file", default="", help="Optional local json/jsonl/parquet file.")
    parser.add_argument("--sample-size", type=int, default=60)
    parser.add_argument("--seed", type=int, default=20260625)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--allow-no-images", action="store_true")
    parser.add_argument("--allow-non-gala-files", action="store_true")
    parser.add_argument("--allow-missing-patch", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.input_file:
        records = load_records(args.input_file)
        source = args.input_file
    else:
        records = load_hf_records(args.dataset, args.split)
        source = f"{args.dataset}:{args.split}"

    selected = select_records(
        records,
        sample_size=args.sample_size,
        seed=args.seed,
        require_images=not args.allow_no_images,
        require_gala_compatible=not args.allow_non_gala_files,
        allow_missing_patch=args.allow_missing_patch,
    )
    summary = build_prepared_dataset(selected, Path(args.output_dir))
    summary["source"] = source
    summary["requested_sample_size"] = args.sample_size
    summary["seed"] = args.seed
    print(f"Prepared {summary['sample_count']} samples from {source}")
    print(f"Output: {Path(args.output_dir).resolve()}")


if __name__ == "__main__":
    main()
