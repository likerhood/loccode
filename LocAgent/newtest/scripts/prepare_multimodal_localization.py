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
import urllib.request
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


def load_json_or_jsonl(path: Path) -> list[dict[str, Any]]:
    if path.suffix == ".jsonl":
        return load_jsonl(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [dict(item) for item in payload]
    if isinstance(payload, dict):
        if "instances" in payload and isinstance(payload["instances"], list):
            return [dict(item) for item in payload["instances"]]
        return [dict(item) for item in payload.values() if isinstance(item, dict)]
    raise TypeError(f"Unsupported source payload in {path}: {type(payload).__name__}")


def load_records(dataset: str, split: str, source_jsonl: str = "") -> list[dict[str, Any]]:
    if source_jsonl:
        source_path = Path(source_jsonl)
        if not source_path.exists():
            raise FileNotFoundError(
                f"Source JSONL does not exist: {source_path}. "
                "Set SOURCE_JSONL/--source-jsonl to an existing OmniGIRL JSONL, "
                "or prepare MM-IR/data/omnigirl-full-candidates/source_omnigirl_full.jsonl."
            )
        return load_json_or_jsonl(source_path)
    if not dataset:
        raise FileNotFoundError(
            "No dataset id or source JSONL was provided. For OmniGIRL, set "
            "SOURCE_JSONL=/path/to/samples.jsonl or place one of the known local "
            "source files under LocAgent/test/OmniGIRL_small60/test60/ or "
            "MM-IR/data/omnigirl-full-candidates/."
        )
    from datasets import load_dataset

    try:
        return [dict(item) for item in load_dataset(dataset, split=split)]
    except Exception as exc:
        if dataset == "SWE-bench/SWE-bench_Multimodal":
            endpoint = os.getenv("HF_ENDPOINT", "https://huggingface.co").rstrip("/")
            parquet_urls = [
                f"{endpoint}/datasets/{dataset}/resolve/main/data/{split}-00000-of-00001.parquet",
                f"https://huggingface.co/datasets/{dataset}/resolve/main/data/{split}-00000-of-00001.parquet",
            ]
            print(
                "[prepare] load_dataset failed; falling back to direct parquet download\n"
                f"[prepare] original error: {type(exc).__name__}: {exc}",
                flush=True,
            )
            return load_swebench_multimodal_parquet_direct(parquet_urls, split)
        raise


def load_swebench_multimodal_parquet_direct(urls: list[str], split: str) -> list[dict[str, Any]]:
    import pandas as pd

    cache_root = Path(os.getenv("HF_HOME") or Path.home() / ".cache" / "huggingface")
    cache_dir = cache_root / "direct_datasets" / "SWE-bench__SWE-bench_Multimodal"
    cache_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = cache_dir / f"{split}-00000-of-00001.parquet"

    if not parquet_path.exists() or parquet_path.stat().st_size == 0:
        errors: list[str] = []
        seen: set[str] = set()
        for url in urls:
            if url in seen:
                continue
            seen.add(url)
            try:
                print(f"[prepare] downloading parquet: {url}", flush=True)
                request = urllib.request.Request(url, headers={"User-Agent": "loccode-prepare/1.0"})
                with urllib.request.urlopen(request, timeout=120) as response:
                    data = response.read()
                parquet_path.write_bytes(data)
                print(f"[prepare] saved parquet: {parquet_path} ({parquet_path.stat().st_size} bytes)", flush=True)
                break
            except Exception as download_exc:
                errors.append(f"{url}: {type(download_exc).__name__}: {download_exc}")
                if parquet_path.exists():
                    parquet_path.unlink()
        else:
            raise RuntimeError("Failed to download SWE-bench Multimodal parquet:\n" + "\n".join(errors))

    df = pd.read_parquet(parquet_path)
    return df.to_dict(orient="records")


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
        repo_root = Path(__file__).resolve().parents[3]
        candidates = [
            os.getenv("OMNIGIRL_SOURCE_JSONL", ""),
            str(repo_root / "LocAgent/test/OmniGIRL_small60/test60/samples.jsonl"),
            str(repo_root / "OmniGIRL/omnigirl/harness/benchmark/OmniGIRL.json"),
            str(repo_root / "MM-IR/data/omnigirl-full-candidates/source_omnigirl_full.jsonl"),
            str(repo_root / "MM-IR/data/omnigirl-full-candidates/samples.jsonl"),
        ]
        for candidate in candidates:
            if candidate and Path(candidate).exists():
                return "", "test", candidate
        return "Deep-Software-Analytics/OmniGIRL", "test", ""
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
