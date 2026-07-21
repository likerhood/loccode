#!/usr/bin/env python3
"""Check whether GALA image_ir_data.json covers all processable local images."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

from PIL import Image, ImageFile, UnidentifiedImageError

from mytest_utils import parse_image_assets, write_json


def resolve_local_image_path(img_url: str, image_dir: str, instance_id: str) -> Path:
    from urllib.parse import urlparse

    parsed_url = urlparse(img_url)
    if parsed_url.scheme in ("http", "https", "ftp", "ftps"):
        filename = os.path.basename(parsed_url.path)
        if not filename:
            filename = f"{instance_id}.jpg"
        return Path(image_dir) / f"{instance_id}_{filename}"
    return Path(img_url)


def is_processable_image(path: Path, allow_svg: bool = False) -> Tuple[bool, str]:
    if not path.exists():
        return False, "missing"
    if path.stat().st_size <= 0:
        return False, "empty"

    suffix = path.suffix.lower()
    if suffix == ".svg":
        return (True, "svg-allowed") if allow_svg else (False, "svg-skipped")

    original_flag = ImageFile.LOAD_TRUNCATED_IMAGES
    try:
        try:
            with Image.open(path) as image:
                image.verify()
            return True, "ok"
        except UnidentifiedImageError:
            ImageFile.LOAD_TRUNCATED_IMAGES = True
            with Image.open(path) as image:
                image.load()
            return True, "ok-truncated"
    except Exception as exc:
        return False, f"unreadable:{exc}"
    finally:
        ImageFile.LOAD_TRUNCATED_IMAGES = original_flag


def load_json_dict(path: Path) -> Dict[str, Any]:
    if not path.exists() or path.stat().st_size <= 0:
        return {}
    with path.open(encoding="utf-8") as infile:
        loaded = json.load(infile)
    if not isinstance(loaded, dict):
        raise ValueError(f"Expected dict JSON: {path}")
    return loaded


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", required=True)
    parser.add_argument("--image-dir", required=True)
    parser.add_argument("--image-ir", required=True)
    parser.add_argument("--report", default="")
    parser.add_argument("--allow-svg", action="store_true")
    args = parser.parse_args()

    samples_path = Path(args.samples)
    image_ir_path = Path(args.image_ir)

    samples = load_json_dict(samples_path)
    image_ir = load_json_dict(image_ir_path)

    total_expected = 0
    total_actual = 0
    incomplete: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []

    for instance_id, doc in samples.items():
        images = parse_image_assets(doc.get("image_assets")).get("problem_statement", [])
        expected_paths = []
        for image_ref in images:
            local_path = resolve_local_image_path(image_ref, args.image_dir, instance_id)
            processable, reason = is_processable_image(local_path, allow_svg=args.allow_svg)
            if processable:
                expected_paths.append(str(local_path))
            elif images:
                skipped.append(
                    {
                        "instance_id": instance_id,
                        "image": image_ref,
                        "local_path": str(local_path),
                        "reason": reason,
                    }
                )

        expected = len(expected_paths)
        total_expected += expected
        actual_graphs = image_ir.get(instance_id, {}).get("image_graphs", [])
        actual = len(actual_graphs) if isinstance(actual_graphs, list) else 0
        total_actual += min(actual, expected)

        if actual < expected:
            incomplete.append(
                {
                    "instance_id": instance_id,
                    "expected_processable_images": expected,
                    "actual_image_graphs": actual,
                    "processable_paths": expected_paths,
                }
            )

    report = {
        "samples": len(samples),
        "expected_processable_images": total_expected,
        "covered_image_graphs": total_actual,
        "incomplete_instances": len(incomplete),
        "skipped_images": len(skipped),
        "complete": not incomplete,
        "incomplete": incomplete,
        "skipped": skipped,
    }

    if args.report:
        write_json(args.report, report)

    print(
        "Image IR completeness: "
        f"expected={total_expected} covered={total_actual} "
        f"incomplete_instances={len(incomplete)} skipped_images={len(skipped)}"
    )
    if incomplete[:10]:
        print("First incomplete instances:")
        for item in incomplete[:10]:
            print(
                f"  {item['instance_id']}: "
                f"expected={item['expected_processable_images']} "
                f"actual={item['actual_image_graphs']}"
            )

    return 0 if not incomplete else 1


if __name__ == "__main__":
    sys.exit(main())
