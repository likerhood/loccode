#!/usr/bin/env python3
"""Download/copy image assets using GALA's expected local naming convention."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from PIL import Image, ImageFile, UnidentifiedImageError

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
    parser.add_argument("--retries", type=int, default=int(os.getenv("IMAGE_DOWNLOAD_RETRIES", "3")))
    parser.add_argument("--retry-sleep", type=float, default=float(os.getenv("IMAGE_DOWNLOAD_RETRY_SLEEP", "10")))
    parser.add_argument("--backoff", type=float, default=float(os.getenv("IMAGE_DOWNLOAD_BACKOFF", "2")))
    return parser.parse_args()


def validate_image_file(path: Path) -> None:
    if not path.exists() or path.stat().st_size <= 0:
        raise ValueError("downloaded image is empty")
    if path.suffix.lower() == ".svg":
        text = path.read_text(encoding="utf-8", errors="ignore").lstrip()[:200].lower()
        if "<svg" not in text:
            raise ValueError("downloaded svg does not look like svg")
        return

    original_flag = ImageFile.LOAD_TRUNCATED_IMAGES
    try:
        try:
            with Image.open(path) as image:
                image.verify()
        except UnidentifiedImageError:
            ImageFile.LOAD_TRUNCATED_IMAGES = True
            with Image.open(path) as image:
                image.load()
    finally:
        ImageFile.LOAD_TRUNCATED_IMAGES = original_flag


def download_or_copy(image_ref: str, target: Path, timeout: int) -> None:
    parsed = urlparse(image_ref)
    if parsed.scheme in {"http", "https"}:
        response = requests.get(
            image_ref,
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 GALA-image-downloader"},
        )
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").lower()
        if "text/html" in content_type:
            raise ValueError(f"unexpected html response content-type={content_type}")
        target.write_bytes(response.content)
    else:
        source = Path(image_ref)
        if not source.exists():
            raise FileNotFoundError(str(source))
        shutil.copyfile(source, target)
    validate_image_file(target)


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
            last_error = ""
            for attempt in range(1, max(args.retries, 1) + 1):
                try:
                    download_or_copy(image_ref, target, timeout=args.timeout)
                    success += 1
                    last_error = ""
                    break
                except Exception as exc:
                    last_error = str(exc)
                    if target.exists():
                        try:
                            target.unlink()
                        except OSError:
                            pass
                    if attempt < max(args.retries, 1):
                        sleep_s = args.retry_sleep * (args.backoff ** (attempt - 1))
                        print(
                            f"[download_images][warn] {instance_id} image retry "
                            f"{attempt}/{args.retries} after {sleep_s:.1f}s: {last_error}"
                        )
                        time.sleep(sleep_s)
            if last_error:
                failures.append({"instance_id": instance_id, "image": image_ref, "error": last_error})

    failures_file = args.failures_file or str(image_dir.parent / "data" / "image_download_failures.json")
    write_json(failures_file, failures)
    print(f"Images ready: {success}")
    print(f"Failures: {len(failures)}")
    print(f"Failure log: {failures_file}")


if __name__ == "__main__":
    main()
