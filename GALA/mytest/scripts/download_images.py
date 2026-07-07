#!/usr/bin/env python3
"""Download/copy image assets using GALA's expected local naming convention."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path
from urllib.parse import urlparse

import requests

from mytest_utils import parse_image_assets, write_json


def local_image_name(instance_id: str, image_ref: str, index: int) -> str:
    parsed = urlparse(image_ref)
    filename = os.path.basename(parsed.path)
    if not filename:
        filename = f"image_{index}.jpg"
    return f"{instance_id}_{filename}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-data", required=True)
    parser.add_argument("--image-dir", required=True)
    parser.add_argument("--failures-file", default="")
    parser.add_argument("--timeout", type=int, default=30)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    image_dir = Path(args.image_dir)
    image_dir.mkdir(parents=True, exist_ok=True)
    with open(args.input_data, encoding="utf-8") as infile:
        data = json.load(infile)
    if not isinstance(data, dict):
        raise ValueError("input-data must be a dict JSON keyed by instance_id")

    failures = []
    success = 0
    for instance_id, doc in data.items():
        images = parse_image_assets(doc.get("image_assets")).get("problem_statement", [])
        for index, image_ref in enumerate(images):
            target = image_dir / local_image_name(instance_id, image_ref, index)
            if target.exists() and target.stat().st_size > 0:
                success += 1
                continue
            parsed = urlparse(image_ref)
            try:
                if parsed.scheme in {"http", "https"}:
                    response = requests.get(image_ref, timeout=args.timeout)
                    response.raise_for_status()
                    target.write_bytes(response.content)
                else:
                    source = Path(image_ref)
                    if not source.exists():
                        raise FileNotFoundError(str(source))
                    shutil.copyfile(source, target)
                success += 1
            except Exception as exc:
                failures.append({"instance_id": instance_id, "image": image_ref, "error": str(exc)})

    failures_file = args.failures_file or str(image_dir.parent / "data" / "image_download_failures.json")
    write_json(failures_file, failures)
    print(f"Images ready: {success}")
    print(f"Failures: {len(failures)}")
    print(f"Failure log: {failures_file}")


if __name__ == "__main__":
    main()

