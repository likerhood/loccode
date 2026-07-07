#!/usr/bin/env python3
"""Prepare a JS/TS multimodal subset from OmniGIRL for GALA."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from mytest_utils import (
    build_prepared_dataset,
    extract_problem_images,
    load_hf_records,
    load_records,
    patch_modified_files,
    select_records,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="Deep-Software-Analytics/OmniGIRL")
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
    output_dir = Path(args.output_dir)
    summary = build_prepared_dataset(selected, output_dir)
    summary["source"] = source
    summary["requested_sample_size"] = args.sample_size
    summary["seed"] = args.seed
    summary["filters"] = {
        "require_images": not args.allow_no_images,
        "require_gala_compatible_files": not args.allow_non_gala_files,
        "allow_missing_patch": args.allow_missing_patch,
    }
    summary["image_sample_count"] = sum(1 for row in selected if extract_problem_images(row))
    summary["text_only_sample_count"] = summary["sample_count"] - summary["image_sample_count"]
    extension_counts: Counter[str] = Counter()
    for row in selected:
        for file_path in patch_modified_files(row.get("patch") or row.get("gold_patch") or ""):
            suffix = Path(file_path).suffix.lower() or "<no_ext>"
            extension_counts[suffix] += 1
    summary["gt_file_extension_counts"] = dict(sorted(extension_counts.items()))
    write_json(output_dir / "dataset_summary.json", summary)
    print(f"Prepared {summary['sample_count']} OmniGIRL localization samples from {source}")
    print(f"Filters: {summary['filters']}")
    print(
        f"Images: {summary['image_sample_count']} with images, "
        f"{summary['text_only_sample_count']} text-only"
    )
    print(f"Output: {output_dir.resolve()}")


if __name__ == "__main__":
    main()
