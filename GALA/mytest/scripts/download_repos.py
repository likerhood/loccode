#!/usr/bin/env python3
"""Clone repositories for GALA mytest datasets."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from mytest_utils import maybe_prefixed_github_url


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", required=True)
    parser.add_argument("--repo-dir", required=True)
    parser.add_argument("--github-mirror-prefix", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with open(args.samples, encoding="utf-8") as infile:
        data = json.load(infile)
    if not isinstance(data, dict):
        raise ValueError("samples must be a dict JSON")

    repos = sorted({str(doc.get("repo") or "") for doc in data.values() if isinstance(doc, dict) and doc.get("repo")})
    repo_dir = Path(args.repo_dir)
    repo_dir.mkdir(parents=True, exist_ok=True)
    for repo in repos:
        owner = repo.split("/", 1)[0]
        target = repo_dir / owner
        if target.is_dir():
            print(f"Repository exists, skip: {target}")
            continue
        url = maybe_prefixed_github_url(repo, args.github_mirror_prefix)
        print(f"Cloning {repo} -> {target}")
        subprocess.run(["git", "clone", url, str(target)], check=True)
    print(f"Repositories ready: {len(repos)}")


if __name__ == "__main__":
    main()

