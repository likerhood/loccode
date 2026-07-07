#!/usr/bin/env python3
"""Ensure GraphLocator's bundled tree-sitter language library exists.

The original project keeps prebuilt language libraries under
``rdfs/dependency_graph/lib/``. Those binaries are intentionally not tracked in
this repository, so server clones need a reproducible way to recreate them.

This script first tries to reuse the ``tree_sitter_languages`` wheel's
``languages.so``. If that is unavailable or incompatible, it can build a
minimal library from upstream grammar repositories.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "rdfs" / "dependency_graph" / "lib"

MINIMAL_REPOS = [
    ("python", "https://github.com/tree-sitter/tree-sitter-python", "0dee05ef958ba2eae88d1e65f24b33cad70d4367", "."),
    ("javascript", "https://github.com/tree-sitter/tree-sitter-javascript", "a92640f158c208ca3be28b560b838b2bd60e8eac", "."),
    ("typescript", "https://github.com/tree-sitter/tree-sitter-typescript", "e45cb3225bf47a04da827e4575b9791523d953fd", "typescript"),
    ("tsx", "https://github.com/tree-sitter/tree-sitter-typescript", "e45cb3225bf47a04da827e4575b9791523d953fd", "tsx"),
    ("java", "https://github.com/tree-sitter/tree-sitter-java", "953abfc8bb3eb2f578e1f461edba4a9885f974b8", "."),
    ("c_sharp", "https://github.com/tree-sitter/tree-sitter-c-sharp", "31a64b28292aac6adf44071e449fa03fb80eaf4e", "."),
    ("html", "https://github.com/tree-sitter/tree-sitter-html", "e4d834eb4918df01dcad5c27d1b15d56e3bd94cd", "."),
    ("css", "https://github.com/tree-sitter/tree-sitter-css", "f6be52c3d1cdb1c5e4dd7d8bce0a57497f55d6af", "."),
    ("json", "https://github.com/tree-sitter/tree-sitter-json", "94f5c527b2965465956c2000ed6134dd24daf2a7", "."),
]

VALIDATION_LANGUAGES = ("python", "javascript", "typescript", "java")


def target_lib_path() -> Path:
    if sys.platform.startswith("linux"):
        return LIB_DIR / "languages-linux-x86_64.so"
    if sys.platform == "darwin":
        machine = platform.machine()
        if machine == "arm64":
            return LIB_DIR / "languages-darwin-arm64.dylib"
        if machine == "x86_64":
            return LIB_DIR / "languages-darwin-x86_64.dylib"
    raise RuntimeError(f"Unsupported platform for GraphLocator tree-sitter lib: {sys.platform}/{platform.machine()}")


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print("+ " + " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True)


def validate_library(path: Path, *, verbose: bool = True) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False
    try:
        from tree_sitter import Language

        for language in VALIDATION_LANGUAGES:
            Language(str(path), language)
        if verbose:
            print(f"[tree-sitter] validated {path}", flush=True)
        return True
    except Exception as exc:
        if verbose:
            print(f"[tree-sitter] validation failed for {path}: {type(exc).__name__}: {exc}", flush=True)
        return False


def find_tree_sitter_languages_lib() -> Path | None:
    spec = importlib.util.find_spec("tree_sitter_languages")
    if spec is None or not spec.origin:
        return None
    package_dir = Path(spec.origin).resolve().parent
    candidates = [
        package_dir / "languages.so",
        package_dir / "languages.dylib",
    ]
    candidates.extend(package_dir.glob("*.so"))
    candidates.extend(package_dir.glob("*.dylib"))
    for candidate in candidates:
        if candidate.exists() and "languages" in candidate.name:
            return candidate
    return None


def copy_from_package(target: Path) -> bool:
    source = find_tree_sitter_languages_lib()
    if source is None:
        print("[tree-sitter] tree_sitter_languages package library not found", flush=True)
        return False
    print(f"[tree-sitter] copying package library {source} -> {target}", flush=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return validate_library(target)


def rewrite_github_url(url: str) -> str:
    prefix = os.environ.get("TREE_SITTER_GITHUB_PREFIX") or os.environ.get("GITHUB_URL_PREFIX", "")
    if not prefix:
        return url
    if not url.startswith("https://github.com/"):
        return url
    suffix = url.removeprefix("https://github.com/")
    return f"{prefix.rstrip('/')}/{suffix}"


def ensure_repo(cache_dir: Path, name: str, url: str, commit: str) -> Path:
    repo_dir = cache_dir / name
    clone_url = rewrite_github_url(url)
    if not repo_dir.exists():
        run(["git", "clone", "--depth", "1", clone_url, str(repo_dir)])
    try:
        run(["git", "-C", str(repo_dir), "fetch", "--depth", "1", "origin", commit])
        run(["git", "-C", str(repo_dir), "checkout", commit])
    except subprocess.CalledProcessError:
        print(f"[tree-sitter] shallow fetch failed for {name}; retrying full fetch", flush=True)
        run(["git", "-C", str(repo_dir), "fetch", "origin", commit])
        run(["git", "-C", str(repo_dir), "checkout", commit])
    return repo_dir


def build_library(target: Path, cache_dir: Path) -> bool:
    from tree_sitter import Language

    cache_dir.mkdir(parents=True, exist_ok=True)
    grammar_paths: list[str] = []
    repo_cache: dict[tuple[str, str], Path] = {}
    for name, url, commit, subdir in MINIMAL_REPOS:
        key = (url, commit)
        if key not in repo_cache:
            repo_cache[key] = ensure_repo(cache_dir, url.rstrip("/").rsplit("/", 1)[-1], url, commit)
        grammar_path = repo_cache[key] / subdir
        if not grammar_path.exists():
            raise FileNotFoundError(f"Missing grammar path for {name}: {grammar_path}")
        grammar_paths.append(str(grammar_path))

    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_target = target.with_suffix(target.suffix + ".tmp")
    if tmp_target.exists():
        tmp_target.unlink()
    print(f"[tree-sitter] building {target} from {len(grammar_paths)} grammars", flush=True)
    Language.build_library(str(tmp_target), grammar_paths)
    tmp_target.replace(target)
    return validate_library(target)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--no-package", action="store_true", help="skip tree_sitter_languages package reuse")
    parser.add_argument("--no-build", action="store_true", help="do not build from grammar repos")
    parser.add_argument("--cache-dir", default=os.environ.get("TREE_SITTER_GRAMMAR_CACHE", ""))
    args = parser.parse_args()

    target = target_lib_path()
    if target.exists() and not args.force and validate_library(target):
        return
    if target.exists() and args.force:
        target.unlink()

    if not args.no_package and copy_from_package(target):
        return

    if args.no_build:
        raise SystemExit(f"GraphLocator tree-sitter library is missing or invalid: {target}")

    cache_dir = Path(args.cache_dir) if args.cache_dir else REPO_ROOT / ".cache" / "tree_sitter_grammars"
    if build_library(target, cache_dir):
        return
    raise SystemExit(f"Failed to prepare GraphLocator tree-sitter library: {target}")


if __name__ == "__main__":
    main()
