#!/usr/bin/env python3
"""Prepare multimodal localization subsets for baseline adapters.

The script is intentionally self-contained inside each repository's
``newtest`` folder. It normalizes SWE-bench Multimodal or OmniGIRL records,
applies the local ``muladapter`` issue-text enrichment, and writes file-level
ground truth extracted from the gold patch.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
from collections import Counter
from pathlib import Path
from typing import Any


PATCH_FILE_RE = re.compile(r"^\+\+\+ b/(.+)$", re.MULTILINE)
URL_RE = re.compile(r"https?://[^\s)>\]\"']+")
IMAGE_RE = re.compile(r"\.(?:png|jpg|jpeg|gif|webp|svg)(?:\?.*)?$", re.I)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as infile:
        for line in infile:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def load_records(dataset: str, split: str, source_jsonl: str = "") -> list[dict[str, Any]]:
    if source_jsonl:
        return load_jsonl(Path(source_jsonl))
    from datasets import load_dataset

    return [dict(item) for item in load_dataset(dataset, split=split)]


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as outfile:
        for row in rows:
            outfile.write(json.dumps(row, ensure_ascii=False) + "\n")


def normalize_path(path: Any) -> str:
    text = str(path or "").strip().replace("\\", "/")
    text = re.sub(r"^['\"]|['\"]$", "", text)
    text = re.sub(r"^[ab]/", "", text)
    return text.lstrip("./")


def patch_files(patch: Any) -> list[str]:
    files = [normalize_path(match) for match in PATCH_FILE_RE.findall(str(patch or ""))]
    seen: set[str] = set()
    out: list[str] = []
    for file_path in files:
        if file_path and file_path != "dev/null" and file_path not in seen:
            seen.add(file_path)
            out.append(file_path)
    return out


def parse_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return [str(item) for item in parsed if str(item).strip()]
        return [text]
    return []


def parse_image_assets(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return []
    if not isinstance(value, dict):
        return []
    urls: list[str] = []
    for item in value.values():
        urls.extend(parse_string_list(item))
    return urls


def split_urls(text: str) -> tuple[list[str], list[str]]:
    image_urls: set[str] = set()
    web_urls: set[str] = set()
    for match in URL_RE.findall(text or ""):
        url = match.rstrip(".,;")
        if IMAGE_RE.search(url) or "user-attachments/assets" in url:
            image_urls.add(url)
        else:
            web_urls.add(url)
    return sorted(image_urls), sorted(web_urls)


def coerce_problem_statement(row: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("problem_statement", "issue", "issue_text", "body", "description", "title"):
        value = str(row.get(key) or "").strip()
        if value and value not in parts:
            parts.append(value)
    return "\n\n".join(parts)


def normalize_record(row: dict[str, Any], enrich: bool = True) -> dict[str, Any]:
    text = coerce_problem_statement(row)
    image_urls = set(parse_image_assets(row.get("image_assets")))
    for key in ("image_urls", "images", "screenshots"):
        image_urls.update(parse_string_list(row.get(key)))
    web_urls = set(parse_string_list(row.get("website_links") or row.get("website links")))
    web_urls.update(parse_string_list(row.get("web_urls") or row.get("urls")))
    found_images, found_webs = split_urls(text)
    image_urls.update(found_images)
    web_urls.update(found_webs)

    patch = str(row.get("patch") or row.get("gold_patch") or "")
    normalized = {
        **row,
        "repo": str(row.get("repo") or row.get("repository") or ""),
        "instance_id": str(row.get("instance_id") or row.get("id") or row.get("task_id") or ""),
        "base_commit": str(row.get("base_commit") or row.get("commit") or ""),
        "patch": patch,
        "test_patch": str(row.get("test_patch") or ""),
        "problem_statement": text,
        "hints_text": str(row.get("hints_text") or ""),
        "created_at": str(row.get("created_at") or ""),
        "version": str(row.get("version") or ""),
        "FAIL_TO_PASS": str(row.get("FAIL_TO_PASS") or "[]"),
        "PASS_TO_PASS": str(row.get("PASS_TO_PASS") or "[]"),
        "environment_setup_commit": str(row.get("environment_setup_commit") or ""),
        "image_urls": sorted(url for url in image_urls if url),
        "web_urls": sorted(url for url in web_urls if url),
        "files": patch_files(patch),
    }

    if not enrich:
        return normalized

    try:
        from muladapter.adapter import enrich_problem_statement

        normalized = enrich_problem_statement(normalized)
    except Exception as exc:
        sections = [normalized["problem_statement"].rstrip()]
        if normalized["image_urls"]:
            sections += ["", "Attached Images:"] + [f"- {url}" for url in normalized["image_urls"]]
        if normalized["web_urls"]:
            sections += ["", "Related URLs:"] + [f"- {url}" for url in normalized["web_urls"]]
        normalized["problem_statement"] = "\n".join(sections).strip() + f"\n\n[adapter_fallback={type(exc).__name__}]\n"
    return normalized


def benchmark_defaults(benchmark: str) -> tuple[str, str, str]:
    if benchmark == "swebench_multimodal":
        return "SWE-bench/SWE-bench_Multimodal", "dev", ""
    if benchmark == "omnigirl":
        return "", "train", "/home/like/locCode/LocAgent/test/OmniGIRL_small60/test60/samples.jsonl"
    raise ValueError(f"Unsupported benchmark: {benchmark}")


def select_rows(
    rows: list[dict[str, Any]],
    sample_size: int,
    seed: int,
    allow_text_only: bool = False,
) -> list[dict[str, Any]]:
    candidates = [
        row for row in rows
        if row.get("instance_id") and row.get("repo") and row.get("base_commit")
        and row.get("files")
        and (allow_text_only or row.get("image_urls") or row.get("web_urls"))
    ]
    rng = random.Random(seed)
    rng.shuffle(candidates)
    if sample_size > 0:
        candidates = candidates[:sample_size]
    return sorted(candidates, key=lambda item: item["instance_id"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", choices=["swebench_multimodal", "omnigirl"], default="swebench_multimodal")
    parser.add_argument("--dataset", default="")
    parser.add_argument("--split", default="")
    parser.add_argument("--source-jsonl", default="")
    parser.add_argument("--sample-size", type=int, default=60)
    parser.add_argument("--seed", type=int, default=20260614)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--used-list-name", default="newtest_instances")
    parser.add_argument(
        "--allow-text-only",
        action="store_true",
        help="Keep text-only samples. Useful when running a fixed OmniGIRL subset.",
    )
    args = parser.parse_args()

    default_dataset, default_split, default_source = benchmark_defaults(args.benchmark)
    dataset = args.dataset or default_dataset
    split = args.split or default_split
    source_jsonl = args.source_jsonl or default_source

    print(
        f"[prepare] loading records benchmark={args.benchmark} "
        f"dataset={dataset or '<local>'} split={split} source={source_jsonl or '<hf>'}",
        flush=True,
    )
    raw_rows = load_records(dataset, split, source_jsonl)
    print(f"[prepare] loaded {len(raw_rows)} raw records", flush=True)

    # Build cheap metadata for all rows first. Multimodal/web enrichment may
    # call a VLM and fetch URLs, so it must run only after sampling.
    normalized = [normalize_record(row, enrich=False) for row in raw_rows]
    selected = select_rows(normalized, args.sample_size, args.seed, args.allow_text_only)
    print(
        f"[prepare] selected {len(selected)} records "
        f"(requested={args.sample_size}, seed={args.seed})",
        flush=True,
    )
    if selected:
        print("[prepare] enriching selected issue texts with muladapter", flush=True)
    enriched: list[dict[str, Any]] = []
    for index, row in enumerate(selected, start=1):
        instance_id = row.get("instance_id", f"sample-{index}")
        image_count = len(row.get("image_urls") or [])
        web_count = len(row.get("web_urls") or [])
        print(
            f"[prepare:{index}/{len(selected)}] {instance_id} "
            f"images={image_count} urls={web_count}",
            flush=True,
        )
        enriched.append(normalize_record(row, enrich=True))
    selected = enriched

    output = Path(args.output_dir)
    write_jsonl(output / "samples.jsonl", selected)
    write_json(output / "samples.json", selected)
    gt_files = {row["instance_id"]: row["files"] for row in selected}
    write_json(output / "gt_files.json", gt_files)
    instance_ids = [row["instance_id"] for row in selected]
    write_json(output / "instance_ids.json", instance_ids)
    (output / "instance_ids.txt").write_text("\n".join(instance_ids) + "\n", encoding="utf-8")
    toml_list = ", ".join(json.dumps(item) for item in instance_ids)
    (output / "config.newtest.toml").write_text(f"{args.used_list_name} = [ {toml_list} ]\n", encoding="utf-8")

    with (output / "samples.csv").open("w", encoding="utf-8", newline="") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=["instance_id", "repo", "base_commit", "image_count", "web_count", "gt_files"])
        writer.writeheader()
        for row in selected:
            writer.writerow({
                "instance_id": row["instance_id"],
                "repo": row["repo"],
                "base_commit": row["base_commit"],
                "image_count": len(row.get("image_urls") or []),
                "web_count": len(row.get("web_urls") or []),
                "gt_files": ";".join(row.get("files") or []),
            })

    summary = {
        "benchmark": args.benchmark,
        "dataset": dataset,
        "split": split,
        "source_jsonl": source_jsonl,
        "sample_size": len(selected),
        "source_rows": len(raw_rows),
        "candidate_rows": len(select_rows(normalized, 0, args.seed, args.allow_text_only)),
        "seed": args.seed,
        "repo_counts": dict(Counter(row["repo"] for row in selected)),
        "total_images": sum(len(row.get("image_urls") or []) for row in selected),
        "total_web_urls": sum(len(row.get("web_urls") or []) for row in selected),
        "muladapter_mode": os.getenv("MULADAPTER_MODE") or os.getenv("MULADAPTER_DEFAULT_MODE") or "url_only",
    }
    write_json(output / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
