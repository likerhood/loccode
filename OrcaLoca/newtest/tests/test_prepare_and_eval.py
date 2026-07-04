#!/usr/bin/env python3
"""Smoke tests for newtest data preparation helpers."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as outfile:
        for row in rows:
            outfile.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        source = tmpdir / "source.jsonl"
        write_jsonl(
            source,
            [
                {
                    "repo": "owner/repo",
                    "instance_id": "owner__repo-1",
                    "base_commit": "abc",
                    "problem_statement": "Screenshot: https://example.com/a.png",
                    "patch": "diff --git a/src/a.js b/src/a.js\n--- a/src/a.js\n+++ b/src/a.js\n@@ -1 +1 @@\n",
                }
            ],
        )
        data_dir = tmpdir / "data"
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "prepare_multimodal_localization.py"),
                "--benchmark",
                "omnigirl",
                "--source-jsonl",
                str(source),
                "--output-dir",
                str(data_dir),
                "--sample-size",
                "1",
            ],
            cwd=ROOT.parents[0],
            check=True,
        )
        pred = tmpdir / "pred.jsonl"
        write_jsonl(pred, [{"instance_id": "owner__repo-1", "found_files": ["src/a.js"]}])
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "eval_file_level.py"),
                "--samples",
                str(data_dir / "samples.jsonl"),
                "--pred-file",
                str(pred),
                "--output-dir",
                str(tmpdir / "eval"),
            ],
            check=True,
        )
        metrics = json.loads((tmpdir / "eval" / "metrics.json").read_text(encoding="utf-8"))
        assert metrics["acc@1"] == 1.0, metrics
    print("newtest smoke tests passed")


if __name__ == "__main__":
    main()
