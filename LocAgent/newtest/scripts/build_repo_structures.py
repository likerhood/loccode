#!/usr/bin/env python3
"""Build local repo_structures for LocAgent newtest runs.

This script keeps LocAgent decoupled from CoSIL by generating the lightweight
``repo_structures/*.json`` files inside LocAgent's own ``newtest`` directory.
The output schema is intentionally compatible with ``eval_3level_localization``:

{
  "instance_id": "...",
  "repo": "...",
  "base_commit": "...",
  "structure": {
    "src": {
      "file.js": {
        "text": "...",
        "classes": [{"name": "...", "start_line": 1, "end_line": 10}],
        "functions": [{"name": "...", "start_line": 12, "end_line": 20}]
      }
    }
  }
}
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from muladapter.adapter import scan_repo  # noqa: E402
from util.benchmark.setup_repo import setup_repo  # noqa: E402


SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    "node_modules",
    "bower_components",
    "dist",
    "build",
    "coverage",
    ".next",
    ".nuxt",
    ".cache",
    "vendor",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def should_skip(path: str) -> bool:
    return bool(set(Path(path).parts) & SKIP_DIRS)


def add_nested_file(structure: dict[str, Any], file_path: str, file_node: dict[str, Any]) -> None:
    parts = [part for part in file_path.replace("\\", "/").split("/") if part]
    current = structure
    for part in parts[:-1]:
        current = current.setdefault(part, {})
    current[parts[-1]] = file_node


def to_file_node(file_row: dict[str, Any]) -> dict[str, Any]:
    classes: list[dict[str, Any]] = []
    functions: list[dict[str, Any]] = []
    for symbol in file_row.get("symbols") or []:
        item = {
            "name": symbol.get("name", ""),
            "start_line": symbol.get("start_line", 1),
            "end_line": symbol.get("end_line") or symbol.get("start_line", 1),
        }
        if symbol.get("type") == "class":
            classes.append({**item, "methods": []})
        elif symbol.get("type") in {"function", "method", "component"}:
            functions.append(item)
    return {
        "text": file_row.get("content", ""),
        "classes": classes,
        "functions": functions,
    }


def build_structure(repo_dir: Path) -> dict[str, Any]:
    parsed = scan_repo(repo_dir)
    structure: dict[str, Any] = {}
    for file_row in parsed.get("files") or []:
        file_path = str(file_row.get("path") or "")
        if not file_path or should_skip(file_path):
            continue
        add_nested_file(structure, file_path, to_file_node(file_row))
    return structure


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--repo-base-dir", default="")
    parser.add_argument("--dataset", default="newtest")
    parser.add_argument("--split", default="train")
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true",
                        help="Continue processing other repos even if one fails")
    args = parser.parse_args()

    samples = load_jsonl(Path(args.samples))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    repo_base_dir = args.repo_base_dir or os.environ.get("LOCAGENT_REPO_CACHE_DIR", "repo_newtest")

    # 跟踪成功和失败的实例
    succeeded = []
    failed = []
    skipped = []

    for index, sample in enumerate(samples, start=1):
        instance_id = str(sample.get("instance_id") or "")
        if not instance_id:
            continue
        output_path = output_dir / f"{instance_id}.json"
        if args.skip_existing and output_path.exists():
            print(f"[structure:{index}/{len(samples)}] skip existing {instance_id}", flush=True)
            skipped.append(instance_id)
            continue
        print(f"[structure:{index}/{len(samples)}] checkout and scan {instance_id}", flush=True)
        try:
            repo_dir = setup_repo(
                instance_data=sample,
                repo_base_dir=repo_base_dir,
                dataset=args.dataset,
                split=args.split,
            )
            structure = build_structure(Path(repo_dir))
            write_json(
                output_path,
                {
                    "instance_id": instance_id,
                    "repo": sample.get("repo", ""),
                    "base_commit": sample.get("base_commit", ""),
                    "structure": structure,
                },
            )
            print(f"[structure:{index}/{len(samples)}] wrote {output_path}", flush=True)
            succeeded.append(instance_id)
        except Exception as e:
            error_msg = f"[structure:{index}/{len(samples)}] FAILED {instance_id}: {e}"
            print(error_msg, flush=True)
            failed.append({"instance_id": instance_id, "error": str(e)})

            if not args.continue_on_error:
                print(f"\nStopping due to error. Use --continue-on-error to skip failed repos.", flush=True)
                # 打印失败摘要
                _print_summary(succeeded, failed, skipped, len(samples))
                raise

    # 打印最终摘要
    _print_summary(succeeded, failed, skipped, len(samples))

    # 如果有失败且不是 continue-on_error 模式，返回非零退出码
    if failed and not args.continue_on_error:
        raise SystemExit(1)


def _print_summary(succeeded: list, failed: list, skipped: list, total: int) -> None:
    """打印处理结果摘要"""
    print("\n" + "=" * 60, flush=True)
    print(f"Build repo_structures summary:", flush=True)
    print(f"  Total samples: {total}", flush=True)
    print(f"  Succeeded:     {len(succeeded)}", flush=True)
    print(f"  Skipped:       {len(skipped)}", flush=True)
    print(f"  Failed:        {len(failed)}", flush=True)

    if failed:
        print(f"\nFailed repositories:", flush=True)
        for item in failed:
            print(f"  - {item['instance_id']}: {item['error']}", flush=True)
    print("=" * 60, flush=True)


if __name__ == "__main__":
    main()
