"""Multi-language defaults for LocAgent repository search tools."""

from __future__ import annotations

from fnmatch import fnmatch
from pathlib import PurePosixPath


SOURCE_EXTENSIONS = (
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".mjs",
    ".cjs",
    ".java",
    ".kt",
    ".go",
    ".rs",
    ".c",
    ".cc",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".php",
    ".rb",
    ".scala",
    ".swift",
    ".vue",
    ".svelte",
    ".css",
    ".scss",
    ".less",
    ".html",
)

JS_TS_EXTENSIONS = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte")
PYTHON_EXTENSIONS = (".py",)

EXCLUDED_DIR_PARTS = {
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


def normalize_repo_path(path: str) -> str:
    return str(path or "").strip().replace("\\", "/").lstrip("./")


def is_excluded_path(path: str) -> bool:
    parts = set(PurePosixPath(normalize_repo_path(path)).parts)
    return bool(parts & EXCLUDED_DIR_PARTS)


def is_source_file(path: str) -> bool:
    normalized = normalize_repo_path(path).lower()
    return normalized.endswith(SOURCE_EXTENSIONS) and not is_excluded_path(normalized)


def infer_language_family(file_paths: list[str]) -> str:
    counts = {"js_ts": 0, "python": 0, "other": 0}
    for path in file_paths:
        normalized = normalize_repo_path(path).lower()
        if is_excluded_path(normalized):
            continue
        if normalized.endswith(JS_TS_EXTENSIONS):
            counts["js_ts"] += 1
        elif normalized.endswith(PYTHON_EXTENSIONS):
            counts["python"] += 1
        elif normalized.endswith(SOURCE_EXTENSIONS):
            counts["other"] += 1
    if counts["js_ts"] >= max(counts["python"], counts["other"], 1):
        return "js_ts"
    if counts["python"] >= max(counts["js_ts"], counts["other"], 1):
        return "python"
    if sum(counts.values()):
        return "mixed"
    return "unknown"


def default_search_pattern(file_paths: list[str]) -> str:
    family = infer_language_family(file_paths)
    if family == "python":
        return "**/*.py"
    if family == "js_ts":
        return "**/*"
    return "**/*"


def select_source_files(file_paths: list[str], pattern: str | None = None) -> list[str]:
    normalized_files = [normalize_repo_path(path) for path in file_paths if normalize_repo_path(path)]
    source_files = [path for path in normalized_files if is_source_file(path)]
    candidates = source_files or [path for path in normalized_files if not is_excluded_path(path)]
    if not pattern or pattern == "**/*":
        return candidates
    def matches(path: str) -> bool:
        if fnmatch(path, pattern):
            return True
        if "/**/*" in pattern:
            return fnmatch(path, pattern.replace("/**/*", "/*"))
        return False

    matched = [path for path in candidates if matches(path)]
    return matched or candidates
