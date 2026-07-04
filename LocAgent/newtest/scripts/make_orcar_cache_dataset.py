#!/usr/bin/env python3
"""Write a local json cache that OrcaLoca's dataset loader can consume."""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", required=True)
    parser.add_argument("--dataset-name", default="newtest_swebench_multimodal_60")
    parser.add_argument("--split", default="dev")
    args = parser.parse_args()

    cache_dir = Path.home() / ".cache" / "orcar"
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / f"{args.dataset_name.replace('/', '__')}_{args.split}.json"
    target.write_text(Path(args.samples).read_text(encoding="utf-8"), encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()
