#!/usr/bin/env python3
"""Generate benchmark sample distribution stats, SVG charts, and a Chinese report.

The script is intentionally dependency-free. It uses the same lightweight
entity extraction helpers as LocAgent evaluation, then writes:

  notes/main/tupian/generated/benchmark_sample_distribution_stats.json
  notes/main/tupian/generated/*.svg
  notes/results/006_benchmark样本URL图片语言和Gold分布分析.md
"""

from __future__ import annotations

import json
import math
import re
import statistics
import sys
import importlib.util
from collections import Counter, defaultdict
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parents[2]
LOCAGENT_ROOT = ROOT_DIR / "LocAgent"
EXTRACTOR_PATH = LOCAGENT_ROOT / "muladapter/entities/extractor.py"
spec = importlib.util.spec_from_file_location("locagent_entity_extractor", EXTRACTOR_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Cannot load entity extractor: {EXTRACTOR_PATH}")
extractor = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = extractor
spec.loader.exec_module(extractor)

CodeEntity = extractor.CodeEntity
entities_overlapping_lines = extractor.entities_overlapping_lines
extract_entities_from_structure = extractor.extract_entities_from_structure
extract_entities_from_structure_file = extractor.extract_entities_from_structure_file


PATCH_HEADER_RE = re.compile(r"^\+\+\+ b/(.+)$")
DIFF_HEADER_RE = re.compile(r"^diff --git a/(.*?) b/(.*?)$")
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
URL_RE = re.compile(r"https?://[^\s)>\"]+")


@dataclass(frozen=True)
class DatasetConfig:
    key: str
    title: str
    samples: Path
    structures: Path | None = None
    note: str = ""


DATASETS = [
    DatasetConfig(
        key="swe_full_dev",
        title="SWE-bench Multimodal dev 全量",
        samples=ROOT_DIR / "LocAgent/newtest/swebench_multimodal-full-dev/data/samples.jsonl",
        structures=ROOT_DIR / "LocAgent/newtest/swebench_multimodal-full-dev/repo_structures",
        note="当前本地准备好的 SWE-bench Multimodal dev 全量口径，样本数通常为 102。",
    ),
    DatasetConfig(
        key="swe60",
        title="SWE-bench Multimodal 60 子集",
        samples=ROOT_DIR / "LocAgent/newtest/swebench_multimodal-60/data/samples.jsonl",
        structures=ROOT_DIR / "LocAgent/newtest/swebench_multimodal-60/repo_structures",
        note="统一 60 样本子集，用于多 baseline 横向比较。",
    ),
    DatasetConfig(
        key="omni_full_candidates",
        title="OmniGIRL full-candidates",
        samples=ROOT_DIR / "MM-IR/data/omnigirl-full-candidates/samples.jsonl",
        structures=ROOT_DIR / "MM-IR/data/omnigirl-full-candidates/repo_structures",
        note="当前可运行候选全集口径，不是原始 959 全量；本地通常为 631。",
    ),
    DatasetConfig(
        key="omni60",
        title="OmniGIRL unified60 子集",
        samples=ROOT_DIR / "LocAgent/newtest/omnigirl-unified60/data/samples.jsonl",
        structures=ROOT_DIR / "LocAgent/newtest/omnigirl-unified60/repo_structures",
        note="统一 60 样本子集，用于多 baseline 横向比较。",
    ),
    DatasetConfig(
        key="omni_raw_source",
        title="OmniGIRL 原始源数据",
        samples=ROOT_DIR / "MM-IR/data/omnigirl-full-candidates/source_omnigirl_full.jsonl",
        structures=None,
        note="原始源数据只能稳定统计图片、URL、语言、文件、hunk 等 patch 级特征；module/function 需要 repo_structures，因此这里不做实体级 gold。",
    ),
]


EXT_LANGUAGE = {
    ".py": "Python",
    ".pyi": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript/JSX",
    ".ts": "TypeScript",
    ".tsx": "TypeScript/TSX",
    ".java": "Java",
    ".kt": "Kotlin",
    ".scala": "Scala",
    ".go": "Go",
    ".rs": "Rust",
    ".c": "C",
    ".h": "C/C++",
    ".cc": "C++",
    ".cpp": "C++",
    ".hpp": "C++",
    ".cs": "C#",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".less": "Less",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".xml": "XML",
    ".md": "Markdown",
    ".rst": "reStructuredText",
    ".toml": "TOML",
    ".ini": "INI",
    ".sh": "Shell",
    ".bat": "Batch",
}


def normalize(path: Any) -> str:
    text = str(path or "").strip().replace("\\", "/")
    if text.startswith(("a/", "b/")):
        text = text[2:]
    return text.lstrip("./")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def ordered_unique(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def list_field(row: dict[str, Any], *names: str) -> list[str]:
    values: list[str] = []
    for name in names:
        value = row.get(name)
        if not value:
            continue
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except Exception:
                parsed = None
            if isinstance(parsed, dict):
                for item in parsed.values():
                    if isinstance(item, list):
                        values.extend(str(x) for x in item if x)
                    elif item:
                        values.append(str(item))
                continue
            if isinstance(parsed, list):
                values.extend(str(x) for x in parsed if x)
                continue
            values.append(value)
            continue
        if isinstance(value, list):
            values.extend(str(x) for x in value if x)
            continue
        if isinstance(value, dict):
            for item in value.values():
                if isinstance(item, list):
                    values.extend(str(x) for x in item if x)
                elif item:
                    values.append(str(item))
    return ordered_unique(values)


def first_list_field(row: dict[str, Any], *names: str) -> list[str]:
    for name in names:
        values = list_field(row, name)
        if values:
            return values
    return []


def patch_files(patch: str) -> list[str]:
    files: list[str] = []
    for line in str(patch or "").splitlines():
        match = DIFF_HEADER_RE.match(line)
        if match:
            files.append(normalize(match.group(2)))
            continue
        match = PATCH_HEADER_RE.match(line)
        if match:
            files.append(normalize(match.group(1)))
    return ordered_unique(files)


def sample_files(row: dict[str, Any]) -> list[str]:
    values = row.get("files")
    if isinstance(values, list):
        files = [normalize(x) for x in values if normalize(x)]
    else:
        files = []
    if not files:
        files = patch_files(row.get("patch", ""))
    return ordered_unique(files)


def parse_changed_old_lines(patch: str) -> dict[str, set[int]]:
    current_file = ""
    old_line = 0
    changed: dict[str, set[int]] = {}
    for line in str(patch or "").splitlines():
        file_match = PATCH_HEADER_RE.match(line)
        if file_match:
            current_file = normalize(file_match.group(1))
            changed.setdefault(current_file, set())
            continue
        hunk_match = HUNK_RE.match(line)
        if hunk_match:
            old_line = int(hunk_match.group(1))
            continue
        if not current_file or line.startswith(("diff --git", "--- ")):
            continue
        if line.startswith("-") and not line.startswith("---"):
            changed[current_file].add(max(1, old_line))
            old_line += 1
        elif line.startswith("+") and not line.startswith("+++"):
            changed[current_file].add(max(1, old_line))
        else:
            old_line += 1
    return changed


def patch_hunk_count(row: dict[str, Any]) -> int:
    value = row.get("num_hunks")
    if isinstance(value, int):
        return value
    hunks = row.get("hunks")
    if isinstance(hunks, list):
        return len(hunks)
    return sum(1 for line in str(row.get("patch", "")).splitlines() if HUNK_RE.match(line))


def patch_changed_line_count(patch: str) -> int:
    total = 0
    for line in str(patch or "").splitlines():
        if line.startswith(("+++", "---", "diff --git")):
            continue
        if line.startswith(("+", "-")):
            total += 1
    return total


def language_for_file(path: str) -> str:
    suffix = Path(path).suffix.lower()
    return EXT_LANGUAGE.get(suffix, suffix[1:].upper() if suffix else "Unknown")


def dominant_language(row: dict[str, Any], files: list[str]) -> str:
    counter = Counter(language_for_file(path) for path in files)
    if not counter and row.get("language"):
        return str(row["language"])
    if not counter:
        return "Unknown"
    return counter.most_common(1)[0][0]


def entity_id(entity: CodeEntity) -> str:
    return f"{entity.file}::{entity.qualified_name}"


def module_id(entity: CodeEntity) -> str:
    if entity.kind == "class":
        return f"{entity.file}::{entity.qualified_name}"
    if "." in entity.qualified_name:
        return f"{entity.file}::{entity.qualified_name.rsplit('.', 1)[0]}"
    return entity.file


def compute_gold_entities(instance_id: str, patch: str, structures: Path | None) -> tuple[int | None, int | None]:
    if not structures:
        return None, None
    structure_path = structures / f"{instance_id}.json"
    if not structure_path.exists():
        return None, None
    try:
        payload = json.loads(structure_path.read_text(encoding="utf-8", errors="ignore"))
        structure = payload.get("structure", payload)
    except Exception:
        return None, None
    changed_lines = parse_changed_old_lines(patch)
    gt_modules: set[str] = set()
    gt_functions: set[str] = set()
    for file_path, lines in changed_lines.items():
        file_node = structure_file_node(structure, file_path)
        if not file_node:
            continue
        try:
            entities = extract_entities_from_structure_file(file_path, file_node)
        except Exception:
            continue
        overlaps = entities_overlapping_lines(entities, lines)
        for entity in overlaps:
            if entity.kind == "class":
                gt_modules.add(module_id(entity))
            elif entity.kind in {"function", "method"}:
                gt_functions.add(entity_id(entity))
                gt_modules.add(module_id(entity))
    return len(gt_modules), len(gt_functions)


def structure_file_node(structure: dict[str, Any], file_path: str) -> dict[str, Any] | None:
    """Return one file node from a nested repo_structure tree.

    The evaluation helper can expand a whole repository, but for benchmark
    profiling we only need files touched by the gold patch. This keeps the
    full-candidates analysis fast.
    """
    parts = [part for part in normalize(file_path).split("/") if part]
    node: Any = structure
    for part in parts:
        if not isinstance(node, dict) or part not in node:
            node = None
            break
        node = node[part]
    if isinstance(node, dict) and "text" in node:
        return node

    target = normalize(file_path)
    found: dict[str, Any] | None = None

    def walk(current: Any, prefix: str = "") -> None:
        nonlocal found
        if found is not None or not isinstance(current, dict):
            return
        if "text" in current and normalize(prefix) == target:
            found = current
            return
        for name, child in current.items():
            if name in {"text", "classes", "functions"}:
                continue
            next_prefix = f"{prefix}/{name}" if prefix else str(name)
            walk(child, next_prefix)

    walk(structure)
    return found


def bucket_count(value: int | None, buckets: list[tuple[str, int | None, int | None]]) -> str:
    if value is None:
        return "不可统计"
    for label, low, high in buckets:
        if low is not None and value < low:
            continue
        if high is not None and value > high:
            continue
        return label
    return str(value)


COUNT_BUCKETS = [
    ("0", 0, 0),
    ("1", 1, 1),
    ("2", 2, 2),
    ("3", 3, 3),
    ("4-5", 4, 5),
    ("6-10", 6, 10),
    ("11-15", 11, 15),
    ("16-30", 16, 30),
    (">30", 31, None),
]

SMALL_BUCKETS = [
    ("0", 0, 0),
    ("1", 1, 1),
    ("2", 2, 2),
    ("3", 3, 3),
    ("4-5", 4, 5),
    (">5", 6, None),
]

FILE_BUCKETS = [
    ("1", 1, 1),
    ("2", 2, 2),
    ("3", 3, 3),
    ("4-5", 4, 5),
    ("6-10", 6, 10),
    ("11-15", 11, 15),
    (">15", 16, None),
]


def image_count(row: dict[str, Any]) -> int:
    if isinstance(row.get("num_images"), int):
        return int(row["num_images"])
    return len(first_list_field(row, "image_urls", "images", "image", "image_assets"))


def web_url_count(row: dict[str, Any]) -> int:
    if isinstance(row.get("num_websites"), int):
        return int(row["num_websites"])
    structured = list_field(row, "web_urls", "website_links", "website links", "urls")
    if structured:
        return len(structured)
    image_urls = set(first_list_field(row, "image_urls", "images", "image", "image_assets"))
    text = str(row.get("problem_statement", "")) + "\n" + str(row.get("hints_text", ""))
    return len([url for url in ordered_unique(URL_RE.findall(text)) if url not in image_urls])


def all_url_count(row: dict[str, Any], images: int, web_urls: int) -> int:
    text_urls = URL_RE.findall(str(row.get("problem_statement", "")) + "\n" + str(row.get("hints_text", "")))
    image_urls = first_list_field(row, "image_urls", "images", "image", "image_assets")
    web_values = list_field(row, "web_urls", "website_links", "website links", "urls")
    return len(ordered_unique(text_urls + image_urls + web_values)) or (images + web_urls)


def modality_label(images: int, web_urls: int) -> str:
    if images and web_urls:
        return "图片+网页URL"
    if images:
        return "仅图片"
    if web_urls:
        return "仅网页URL"
    return "纯文本"


def summarize_values(values: list[int]) -> dict[str, float | int]:
    if not values:
        return {"avg": 0, "median": 0, "p75": 0, "p90": 0, "max": 0}
    ordered = sorted(values)
    def percentile(p: float) -> float:
        if len(ordered) == 1:
            return float(ordered[0])
        index = (len(ordered) - 1) * p
        lo = math.floor(index)
        hi = math.ceil(index)
        if lo == hi:
            return float(ordered[lo])
        return float(ordered[lo] + (ordered[hi] - ordered[lo]) * (index - lo))
    return {
        "avg": round(sum(values) / len(values), 2),
        "median": round(statistics.median(values), 2),
        "p75": round(percentile(0.75), 2),
        "p90": round(percentile(0.90), 2),
        "max": max(values),
    }


def analyze_dataset(config: DatasetConfig) -> dict[str, Any]:
    rows = load_jsonl(config.samples)
    per_sample: list[dict[str, Any]] = []
    for row in rows:
        instance_id = str(row.get("instance_id", ""))
        files = sample_files(row)
        images = image_count(row)
        web_urls = web_url_count(row)
        language = dominant_language(row, files)
        file_languages = Counter(language_for_file(path) for path in files)
        module_count, function_count = compute_gold_entities(instance_id, row.get("patch", ""), config.structures)
        per_sample.append(
            {
                "instance_id": instance_id,
                "repo": row.get("repo", ""),
                "language": language,
                "file_languages": dict(file_languages),
                "image_count": images,
                "web_url_count": web_urls,
                "all_url_count": all_url_count(row, images, web_urls),
                "modality": modality_label(images, web_urls),
                "gold_file_count": len(files),
                "hunk_count": patch_hunk_count(row),
                "patch_changed_lines": patch_changed_line_count(row.get("patch", "")),
                "gold_module_count": module_count,
                "gold_function_count": function_count,
            }
        )
    return aggregate_dataset(config, per_sample)


def distribution(samples: list[dict[str, Any]], field: str, buckets: list[tuple[str, int | None, int | None]]) -> dict[str, int]:
    counter = Counter(bucket_count(sample.get(field), buckets) for sample in samples)
    return {label: counter.get(label, 0) for label, _, _ in buckets if counter.get(label, 0)}


def aggregate_dataset(config: DatasetConfig, samples: list[dict[str, Any]]) -> dict[str, Any]:
    numeric_fields = [
        "image_count",
        "web_url_count",
        "all_url_count",
        "gold_file_count",
        "hunk_count",
        "patch_changed_lines",
    ]
    entity_fields = ["gold_module_count", "gold_function_count"]
    summary = {field: summarize_values([int(s[field]) for s in samples if s.get(field) is not None]) for field in numeric_fields}
    summary.update({field: summarize_values([int(s[field]) for s in samples if s.get(field) is not None]) for field in entity_fields})
    language_counter = Counter(str(s["language"]) for s in samples)
    file_language_counter: Counter[str] = Counter()
    for sample in samples:
        file_language_counter.update(sample["file_languages"])
    modality_counter = Counter(str(s["modality"]) for s in samples)
    module_available = sum(1 for s in samples if s.get("gold_module_count") is not None)
    function_available = sum(1 for s in samples if s.get("gold_function_count") is not None)
    return {
        "key": config.key,
        "title": config.title,
        "note": config.note,
        "samples_path": str(config.samples.relative_to(ROOT_DIR)) if config.samples.exists() else str(config.samples),
        "structures_path": str(config.structures.relative_to(ROOT_DIR)) if config.structures and config.structures.exists() else "",
        "sample_count": len(samples),
        "entity_coverage": {
            "module_samples": module_available,
            "function_samples": function_available,
        },
        "summary": summary,
        "distributions": {
            "images": distribution(samples, "image_count", SMALL_BUCKETS),
            "web_urls": distribution(samples, "web_url_count", SMALL_BUCKETS),
            "all_urls": distribution(samples, "all_url_count", COUNT_BUCKETS),
            "files": distribution(samples, "gold_file_count", FILE_BUCKETS),
            "hunks": distribution(samples, "hunk_count", COUNT_BUCKETS),
            "modules": distribution(samples, "gold_module_count", COUNT_BUCKETS),
            "functions": distribution(samples, "gold_function_count", COUNT_BUCKETS),
        },
        "languages": dict(language_counter.most_common()),
        "file_languages": dict(file_language_counter.most_common()),
        "modalities": dict(modality_counter.most_common()),
        "cross": {
            "modality_by_language": cross_count(samples, "language", "modality", top_left=8),
            "file_bucket_by_modality": cross_bucket_count(samples, "gold_file_count", FILE_BUCKETS, "modality"),
            "function_bucket_by_file_bucket": cross_two_buckets(samples, "gold_file_count", FILE_BUCKETS, "gold_function_count", COUNT_BUCKETS),
        },
        "top_examples": {
            "most_images": top_samples(samples, "image_count", 8),
            "most_web_urls": top_samples(samples, "web_url_count", 8),
            "most_files": top_samples(samples, "gold_file_count", 8),
            "most_functions": top_samples(samples, "gold_function_count", 8),
            "most_hunks": top_samples(samples, "hunk_count", 8),
        },
        "per_sample": samples,
    }


def cross_count(samples: list[dict[str, Any]], left: str, right: str, top_left: int = 8) -> dict[str, dict[str, int]]:
    left_order = [name for name, _ in Counter(str(s[left]) for s in samples).most_common(top_left)]
    out: dict[str, dict[str, int]] = {}
    for left_value in left_order:
        counter = Counter(str(s[right]) for s in samples if str(s[left]) == left_value)
        out[left_value] = dict(counter.most_common())
    return out


def cross_bucket_count(
    samples: list[dict[str, Any]],
    value_field: str,
    buckets: list[tuple[str, int | None, int | None]],
    group_field: str,
) -> dict[str, dict[str, int]]:
    out: dict[str, Counter[str]] = defaultdict(Counter)
    for sample in samples:
        out[str(sample[group_field])][bucket_count(sample.get(value_field), buckets)] += 1
    return {group: {label: counts.get(label, 0) for label, _, _ in buckets if counts.get(label, 0)} for group, counts in out.items()}


def cross_two_buckets(
    samples: list[dict[str, Any]],
    left_field: str,
    left_buckets: list[tuple[str, int | None, int | None]],
    right_field: str,
    right_buckets: list[tuple[str, int | None, int | None]],
) -> dict[str, dict[str, int]]:
    out: dict[str, Counter[str]] = defaultdict(Counter)
    for sample in samples:
        left = bucket_count(sample.get(left_field), left_buckets)
        right = bucket_count(sample.get(right_field), right_buckets)
        out[left][right] += 1
    return {left: {label: counts.get(label, 0) for label, _, _ in right_buckets if counts.get(label, 0)} for left, counts in out.items()}


def top_samples(samples: list[dict[str, Any]], field: str, n: int) -> list[dict[str, Any]]:
    valid = [s for s in samples if s.get(field) is not None]
    valid.sort(key=lambda item: (int(item.get(field) or 0), str(item.get("instance_id", ""))), reverse=True)
    return [
        {
            "instance_id": s["instance_id"],
            "repo": s["repo"],
            "value": s.get(field),
            "images": s.get("image_count"),
            "web_urls": s.get("web_url_count"),
            "files": s.get("gold_file_count"),
            "modules": s.get("gold_module_count"),
            "functions": s.get("gold_function_count"),
            "hunks": s.get("hunk_count"),
            "language": s.get("language"),
        }
        for s in valid[:n]
    ]


def svg_bar_chart(path: Path, title: str, values: dict[str, int], color: str = "#3b82f6") -> None:
    labels = list(values)
    nums = [values[label] for label in labels]
    width = max(900, 96 * max(1, len(labels)))
    height = 480
    margin_left, margin_right, margin_top, margin_bottom = 80, 40, 80, 135
    chart_w = width - margin_left - margin_right
    chart_h = height - margin_top - margin_bottom
    max_value = max(nums) if nums else 1
    bar_gap = 12
    bar_w = (chart_w - bar_gap * (len(labels) - 1)) / max(1, len(labels))
    parts = [svg_header(width, height), f'<text x="{width/2}" y="34" text-anchor="middle" class="title">{escape(title)}</text>']
    parts.append(axis_group(margin_left, margin_top, chart_w, chart_h, max_value))
    for i, (label, num) in enumerate(zip(labels, nums)):
        x = margin_left + i * (bar_w + bar_gap)
        h = 0 if max_value == 0 else chart_h * num / max_value
        y = margin_top + chart_h - h
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" rx="3" fill="{color}"/>')
        parts.append(f'<text x="{x + bar_w/2:.1f}" y="{y - 8:.1f}" text-anchor="middle" class="value">{num}</text>')
        parts.extend(label_tspans(label, x + bar_w / 2, margin_top + chart_h + 24, anchor="middle", max_chars=13))
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def svg_grouped_bar_chart(path: Path, title: str, series: dict[str, dict[str, int]], colors: list[str] | None = None) -> None:
    colors = colors or ["#2563eb", "#16a34a", "#f97316", "#9333ea"]
    labels = []
    for values in series.values():
        for label in values:
            if label not in labels:
                labels.append(label)
    names = list(series)
    width = max(980, 110 * max(1, len(labels)))
    height = 520
    ml, mr, mt, mb = 90, 50, 80, 150
    cw, ch = width - ml - mr, height - mt - mb
    max_value = max([series[name].get(label, 0) for name in names for label in labels] or [1])
    group_gap = 18
    group_w = (cw - group_gap * (len(labels) - 1)) / max(1, len(labels))
    bar_w = group_w / max(1, len(names))
    parts = [svg_header(width, height), f'<text x="{width/2}" y="34" text-anchor="middle" class="title">{escape(title)}</text>']
    parts.append(axis_group(ml, mt, cw, ch, max_value))
    for li, label in enumerate(labels):
        gx = ml + li * (group_w + group_gap)
        for si, name in enumerate(names):
            num = series[name].get(label, 0)
            h = ch * num / max_value if max_value else 0
            x = gx + si * bar_w
            y = mt + ch - h
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(1, bar_w-3):.1f}" height="{h:.1f}" rx="2" fill="{colors[si % len(colors)]}"/>')
        parts.extend(label_tspans(label, gx + group_w / 2, mt + ch + 24, anchor="middle", max_chars=12))
    legend_x = ml
    for si, name in enumerate(names):
        x = legend_x + si * 185
        parts.append(f'<rect x="{x}" y="{height - 42}" width="14" height="14" fill="{colors[si % len(colors)]}"/>')
        parts.append(f'<text x="{x + 20}" y="{height - 30}" class="label">{escape(name)}</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def svg_horizontal_grouped_chart(path: Path, title: str, series: dict[str, dict[str, float]], colors: list[str] | None = None) -> None:
    colors = colors or ["#2563eb", "#16a34a", "#f97316", "#9333ea"]
    labels: list[str] = []
    for values in series.values():
        for label in values:
            if label not in labels:
                labels.append(label)
    names = list(series)
    width = 1320
    row_h = 92
    height = 105 + row_h * max(1, len(labels)) + 70
    ml, mr, mt, mb = 330, 70, 80, 55
    cw = width - ml - mr
    max_value = max([series[name].get(label, 0) for name in names for label in labels] or [1])
    max_value = max(1, max_value)
    bar_h = 18
    parts = [svg_header(width, height), f'<text x="{width/2}" y="36" text-anchor="middle" class="title">{escape(title)}</text>']
    for i in range(5):
        x = ml + cw * i / 4
        value = max_value * i / 4
        parts.append(f'<line x1="{x:.1f}" y1="{mt}" x2="{x:.1f}" y2="{height-mb}" class="grid"/>')
        parts.append(f'<text x="{x:.1f}" y="{height-mb+25}" text-anchor="middle" class="label">{value:.1f}</text>')
    for li, label in enumerate(labels):
        group_y = mt + li * row_h
        parts.extend(label_tspans(label, ml - 18, group_y + 30, anchor="end", max_chars=18))
        for si, name in enumerate(names):
            value = float(series[name].get(label, 0))
            y = group_y + si * (bar_h + 6)
            w = cw * value / max_value
            parts.append(f'<rect x="{ml}" y="{y:.1f}" width="{w:.1f}" height="{bar_h}" rx="3" fill="{colors[si % len(colors)]}"/>')
            parts.append(f'<text x="{ml + w + 8:.1f}" y="{y + 14:.1f}" class="value">{value:.2f}</text>')
    legend_x = ml
    for si, name in enumerate(names):
        x = legend_x + si * 190
        parts.append(f'<rect x="{x}" y="{height - 32}" width="14" height="14" fill="{colors[si % len(colors)]}"/>')
        parts.append(f'<text x="{x + 20}" y="{height - 20}" class="label">{escape(name)}</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def label_tspans(text: str, x: float, y: float, anchor: str = "middle", max_chars: int = 12) -> list[str]:
    lines = wrap_label(str(text), max_chars=max_chars)
    return [
        f'<text x="{x:.1f}" y="{y + i * 16:.1f}" text-anchor="{anchor}" class="label">{escape(line)}</text>'
        for i, line in enumerate(lines)
    ]


def wrap_label(text: str, max_chars: int = 12) -> list[str]:
    text = str(text)
    if len(text) <= max_chars:
        return [text]
    separators = [" ", "-", "_", "/"]
    chunks: list[str] = []
    current = ""
    for char in text:
        current += char
        if len(current) >= max_chars and char in separators:
            chunks.append(current.rstrip(" -_/"))
            current = ""
    if current:
        chunks.append(current)
    if len(chunks) == 1 and len(chunks[0]) > max_chars:
        return [chunks[0][i : i + max_chars] for i in range(0, len(chunks[0]), max_chars)]
    return chunks[:3]


def svg_header(width: int, height: int) -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<style>
  .title {{ font: 700 22px Arial, "Noto Sans CJK SC", sans-serif; fill: #111827; }}
  .label {{ font: 13px Arial, "Noto Sans CJK SC", sans-serif; fill: #374151; }}
  .value {{ font: 12px Arial, "Noto Sans CJK SC", sans-serif; fill: #111827; }}
  .axis {{ stroke: #9ca3af; stroke-width: 1; }}
  .grid {{ stroke: #e5e7eb; stroke-width: 1; }}
</style>
<rect width="100%" height="100%" fill="#ffffff"/>'''


def axis_group(x: int, y: int, w: int, h: int, max_value: int) -> str:
    parts = [f'<line x1="{x}" y1="{y+h}" x2="{x+w}" y2="{y+h}" class="axis"/>', f'<line x1="{x}" y1="{y}" x2="{x}" y2="{y+h}" class="axis"/>']
    steps = 4
    for i in range(1, steps + 1):
        yy = y + h - h * i / steps
        value = round(max_value * i / steps)
        parts.append(f'<line x1="{x}" y1="{yy:.1f}" x2="{x+w}" y2="{yy:.1f}" class="grid"/>')
        parts.append(f'<text x="{x-10}" y="{yy+4:.1f}" text-anchor="end" class="label">{value}</text>')
    return "\n".join(parts)


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        out.append("| " + " | ".join(str(x) for x in row) + " |")
    return "\n".join(out)


def fmt_summary(summary: dict[str, Any], field: str) -> str:
    item = summary.get(field, {})
    return f"{item.get('avg', 0)} / {item.get('median', 0)} / {item.get('p90', 0)} / {item.get('max', 0)}"


def summary_metric_rows(all_stats: list[dict[str, Any]], metrics: list[tuple[str, str]]) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for stats in all_stats:
        for label, field in metrics:
            item = stats["summary"].get(field, {})
            rows.append(
                [
                    stats["title"],
                    label,
                    item.get("avg", 0),
                    item.get("median", 0),
                    item.get("p90", 0),
                    item.get("max", 0),
                ]
            )
    return rows


def write_charts(all_stats: list[dict[str, Any]], out_dir: Path) -> dict[str, dict[str, str]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    chart_paths: dict[str, dict[str, str]] = {}
    for stats in all_stats:
        key = stats["key"]
        chart_paths[key] = {}
        charts = [
            ("images", "图片数分布", stats["distributions"]["images"], "#2563eb"),
            ("web_urls", "网页 URL 数分布", stats["distributions"]["web_urls"], "#16a34a"),
            ("files", "Gold 文件数分布", stats["distributions"]["files"], "#f97316"),
            ("hunks", "Hunk 数分布", stats["distributions"]["hunks"], "#9333ea"),
        ]
        if stats["distributions"]["modules"] or stats["distributions"]["functions"]:
            grouped = {
                "Gold File": stats["distributions"]["files"],
                "Gold Module": stats["distributions"]["modules"],
                "Gold Function": stats["distributions"]["functions"],
            }
            path = out_dir / f"{key}_gold_file_module_function.svg"
            svg_grouped_bar_chart(path, f"{stats['title']}：三层 Gold 数量分布", grouped)
            chart_paths[key]["gold"] = path.name
        for name, title, values, color in charts:
            path = out_dir / f"{key}_{name}.svg"
            svg_bar_chart(path, f"{stats['title']}：{title}", values, color)
            chart_paths[key][name] = path.name
        top_languages = dict(list(stats["languages"].items())[:12])
        if top_languages:
            path = out_dir / f"{key}_languages.svg"
            svg_bar_chart(path, f"{stats['title']}：主修改文件类型/语言 Top 12", top_languages, "#0ea5e9")
            chart_paths[key]["languages"] = path.name
        if stats["modalities"]:
            path = out_dir / f"{key}_modalities.svg"
            svg_bar_chart(path, f"{stats['title']}：模态组合分布", stats["modalities"], "#14b8a6")
            chart_paths[key]["modalities"] = path.name
    overview = {
        "图片均值": {s["title"]: float(s["summary"]["image_count"]["avg"]) for s in all_stats},
        "网页URL均值": {s["title"]: float(s["summary"]["web_url_count"]["avg"]) for s in all_stats},
        "Gold文件均值": {s["title"]: float(s["summary"]["gold_file_count"]["avg"]) for s in all_stats},
    }
    path = out_dir / "overview_avg_images_urls_files.svg"
    svg_horizontal_grouped_chart(path, "各 benchmark 图片、网页 URL、Gold 文件均值对比", overview)
    chart_paths["overview"] = {"avg": path.name}
    return chart_paths


def write_report(all_stats: list[dict[str, Any]], chart_paths: dict[str, dict[str, str]], report_path: Path, image_dir: Path) -> None:
    rel_image_dir = Path("../main/tupian/generated")
    lines: list[str] = [
        "# Benchmark 样本 URL、图片、语言与 Gold 分布分析",
        "",
        "本文档由 `notes/main/tupian/benchmark_sample_distribution.py` 自动生成。统计目标是把 benchmark 样本本身讲清楚：每个集合里有多少图片、多少外部 URL、主要语言是什么、gold patch 通常改几个文件，以及这些真实修改能映射到多少 module/function。",
        "",
        "先把几个容易误解的口径说清楚：",
        "",
        "- **P90**：第 90 百分位数。把所有样本按某个数值从小到大排序，90% 的样本不超过这个值。例如 `Gold文件 P90=8`，意思是约 90% 样本真实修改文件数不超过 8 个。",
        "- **网页 URL**：优先统计样本结构化字段里的 `web_urls`、`website_links`、`website links`、`urls`，这些通常是 issue 里额外引用的网页、playground、commit、文档链接等；只有结构化字段为空时，才从问题文本中兜底抽取 `http(s)` 链接。图片链接单独算入图片数，不重复算作网页 URL。",
        "- **主修改文件类型/语言**：这里不是 GitHub 仓库语言，而是 gold patch 实际改到的文件扩展名推断出的主文件类型。比如 `Markdown`、`MDX`、`JSON`、`SCSS` 表示真实补丁改到了 `.md`、`.mdx`、`.json`、`.scss` 文件，这在前端仓库、文档、配置或快照修改里是正常现象。",
        "- **模态组合**：`图片+网页URL` 表示同一个样本同时有图片证据和非图片网页 URL；`仅图片` 表示有图片但没有结构化网页 URL；`仅网页URL` 表示没有图片但有网页 URL；`纯文本` 表示两者都没有。",
        "- **Gold Module / Gold Function**：与三层评估口径一致，是把 gold patch 的真实修改行映射到 `repo_structures` 抽取出的代码实体后得到的数量。它不是从文件数直接推出来的；如果 patch 改的是 import、配置、顶层常量、JSON、快照或结构抽取不到的区域，那么 module/function 数可能为 0。",
        "",
        f"![总体均值对比]({rel_image_dir / chart_paths['overview']['avg']})",
        "",
        "## 1. 总览表",
        "",
    ]
    lines.append("为了避免横向表太宽，下面把每个统计量拆成一行。`均值/中位数/P90/最大值` 分别回答“平均水平、典型样本、偏难样本、极端长尾样本”。")
    lines.append("")
    lines.append(markdown_table(["数据集", "样本数"], [[s["title"], s["sample_count"]] for s in all_stats]))
    lines.append("")
    lines.append("### 1.1 模态证据分布概览")
    lines.append("")
    lines.append(markdown_table(["数据集", "指标", "均值", "中位数", "P90", "最大值"], summary_metric_rows(all_stats, [("图片数", "image_count"), ("网页URL数", "web_url_count")])))
    lines.append("")
    lines.append("### 1.2 Gold patch 难度分布概览")
    lines.append("")
    lines.append(markdown_table(["数据集", "指标", "均值", "中位数", "P90", "最大值"], summary_metric_rows(all_stats, [("Gold文件数", "gold_file_count"), ("Hunk数", "hunk_count"), ("Gold Module数", "gold_module_count"), ("Gold Function数", "gold_function_count")])))
    lines += [
        "",
        "从总览看，SWE-bench Multimodal 更偏多图、多 URL、多文件、多 hunk；OmniGIRL unified60 最像小补丁集合，几乎都是单文件小改动。OmniGIRL full-candidates 的样本数更大，整体仍偏少文件，但 function 数存在明显长尾。",
        "",
        "### 1.3 口径校验：为什么会有“仅图片”和 Markdown/MDX",
        "",
        "这份报告的模态组合不是互斥地看 benchmark 名字，而是逐条样本检查证据字段：",
        "",
        "- 如果样本有 `image_urls`，但没有非图片网页 URL，就归为 `仅图片`。",
        "- 如果样本没有图片，但有 `web_urls` 或 `website links`，就归为 `仅网页URL`。",
        "- 如果两类都有，才归为 `图片+网页URL`。",
        "",
        "因此，`图片+网页URL` 和 `仅图片` 同时存在是正常现象，表示不同样本携带的证据类型不同，不是统计相加错误。",
        "",
        "以 OmniGIRL full-candidates 为例，修正后的模态组合是：",
        "",
    ]
    omni_full = next((s for s in all_stats if s["key"] == "omni_full_candidates"), None)
    if omni_full:
        lines.append(markdown_table(["模态", "样本数"], [[k, v] for k, v in omni_full["modalities"].items()]))
        only_image_examples = [s for s in omni_full["per_sample"] if s.get("modality") == "仅图片"][:8]
        if only_image_examples:
            lines += [
                "",
                "其中 `仅图片` 的样本示例：",
                "",
                markdown_table(
                    ["样本", "仓库", "图片数", "网页URL数", "Gold文件数", "主修改文件类型/语言"],
                    [
                        [
                            s["instance_id"],
                            s["repo"],
                            s["image_count"],
                            s["web_url_count"],
                            s["gold_file_count"],
                            s["language"],
                        ]
                        for s in only_image_examples
                    ],
                ),
            ]
    lines += [
        "",
        "`Markdown`、`MDX`、`JSON`、`SCSS` 这些语言/文件类型也不是仓库名，而是 gold patch 实际改到的文件类型。例如前端仓库经常会改 `.mdx` 文档、`.json` 配置、`.scss` 样式或 `.md` 说明文件；这些样本在 file-level 仍然是正常代码仓库样本，只是这次真实补丁的主要修改目标不是 `.js/.py/.java` 文件。",
        "",
        "## 2. 各数据集详细分布",
        "",
    ]
    for stats in all_stats:
        key = stats["key"]
        lines += [
            f"### 2.{all_stats.index(stats)+1} {stats['title']}",
            "",
            stats["note"],
            "",
            f"- 样本文件：`{stats['samples_path']}`",
        ]
        if stats.get("structures_path"):
            lines.append(f"- 结构文件：`{stats['structures_path']}`")
            lines.append(f"- module/function 可统计样本数：{stats['entity_coverage']['module_samples']} / {stats['sample_count']}")
        else:
            lines.append("- 结构文件：无，因此 module/function gold 不做实体映射统计。")
        lines.append("")
        if "modalities" in chart_paths[key]:
            lines.append(f"![{stats['title']} 模态组合]({rel_image_dir / chart_paths[key]['modalities']})")
        lines.append("")
        if "images" in chart_paths[key]:
            lines.append(f"![{stats['title']} 图片数分布]({rel_image_dir / chart_paths[key]['images']})")
        if "web_urls" in chart_paths[key]:
            lines.append(f"![{stats['title']} URL数分布]({rel_image_dir / chart_paths[key]['web_urls']})")
        if "languages" in chart_paths[key]:
            lines.append(f"![{stats['title']} 语言分布]({rel_image_dir / chart_paths[key]['languages']})")
        if "gold" in chart_paths[key]:
            lines.append(f"![{stats['title']} 三层Gold分布]({rel_image_dir / chart_paths[key]['gold']})")
        else:
            lines.append(f"![{stats['title']} Gold文件分布]({rel_image_dir / chart_paths[key]['files']})")
        lines.append("")
        lines.append("关键分布表：")
        lines.append("")
        lines.append(markdown_table(["分布项", "桶", "样本数"], flatten_distribution_rows(stats["distributions"], ["images", "web_urls", "files", "hunks", "modules", "functions"])))
        lines.append("")
        lines.append("模态组合：")
        lines.append("")
        lines.append(markdown_table(["模态", "样本数"], [[k, v] for k, v in stats["modalities"].items()]))
        lines.append("")
        lines.append("主修改文件类型/语言 Top：")
        lines.append("")
        lines.append(markdown_table(["语言", "样本数"], [[k, v] for k, v in list(stats["languages"].items())[:12]]))
        lines.append("")
        if stats["cross"]["modality_by_language"]:
            lines.append("主修改文件类型/语言与模态组合交叉分布 Top：")
            lines.append("")
            cross_rows = []
            for lang, counts in stats["cross"]["modality_by_language"].items():
                cross_rows.append([lang, counts.get("纯文本", 0), counts.get("仅图片", 0), counts.get("仅网页URL", 0), counts.get("图片+网页URL", 0)])
            lines.append(markdown_table(["语言", "纯文本", "仅图片", "仅网页URL", "图片+网页URL"], cross_rows))
            lines.append("")
        lines.append("长尾样本示例：")
        lines.append("")
        lines.append(markdown_table(["维度", "样本", "repo", "值", "图片", "URL", "文件", "module", "function", "hunk", "语言"], top_example_rows(stats)))
        lines.append("")
    lines += [
        "## 3. 读数方式和结论",
        "",
        "1. **图片数分布**看的是每个 issue/sample 显式携带的 `image_urls` 或等价字段。图片越多，模型需要从视觉证据中提取 bug 线索的概率越高。",
        "2. **网页 URL 数分布**看的是非图片网页链接。脚本会合并 `web_urls`、`website_links`、`website links`、`urls` 等字段并去重；如果这些字段都为空，才从问题描述中兜底抽取网页 URL。",
        "3. **主修改文件类型/语言分布**看的是 gold patch 实际修改的文件类型，不是仓库整体语言。因此 JavaScript 仓库里出现 Markdown、MDX、JSON、SCSS 并不矛盾，它只是说明该样本真实补丁主要改到了这些文件。",
        "4. **Gold 文件数**是实际 patch 涉及的文件数。它能反映 file-level 定位难度，但不能直接代表 function-level 难度。",
        "5. **Gold Module/Function 数**是修改行和结构实体重叠后的实体数量。一个文件可以对应多个函数，也可能完全不映射到函数。",
        "6. **Hunk 数**表示 patch 中分散修改块数量。文件数少但 hunk 多，通常说明修改在同一文件里分布很散，函数级定位仍然可能很难。",
        "",
        "总体上，SWE-bench Multimodal 的样本更强调多模态和多位置修改：图片、URL、hunk 和 gold 文件数都更高。OmniGIRL full-candidates 更大、更偏少文件，但语言和仓库更分散，function 数有长尾。OmniGIRL unified60 则是更小、更干净的统一子集，适合快速对比 baseline，但不能代表 OmniGIRL full-candidates 的长尾复杂度。",
        "",
        "## 4. 如何重新生成",
        "",
        "```bash",
        "cd /home/like/locCode",
        "python3 notes/main/tupian/benchmark_sample_distribution.py",
        "```",
        "",
        "生成物：",
        "",
        "- `notes/main/tupian/generated/benchmark_sample_distribution_stats.json`：所有原始统计和交叉分布。",
        "- `notes/main/tupian/generated/*.svg`：柱状图。",
        "- `notes/results/006_benchmark样本URL图片语言和Gold分布分析.md`：本文档。",
        "",
    ]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")


def flatten_distribution_rows(distributions: dict[str, dict[str, int]], names: list[str]) -> list[list[Any]]:
    zh = {
        "images": "图片数",
        "web_urls": "网页URL数",
        "files": "Gold文件数",
        "hunks": "Hunk数",
        "modules": "Gold Module数",
        "functions": "Gold Function数",
    }
    rows = []
    for name in names:
        values = distributions.get(name) or {}
        if not values:
            continue
        for bucket, count in values.items():
            rows.append([zh.get(name, name), bucket, count])
    return rows


def top_example_rows(stats: dict[str, Any]) -> list[list[Any]]:
    labels = {
        "most_images": "图片最多",
        "most_web_urls": "URL最多",
        "most_files": "文件最多",
        "most_functions": "函数最多",
        "most_hunks": "hunk最多",
    }
    rows = []
    for key, label in labels.items():
        examples = stats["top_examples"].get(key, [])
        if not examples:
            continue
        sample = examples[0]
        rows.append(
            [
                label,
                sample["instance_id"],
                sample["repo"],
                sample["value"],
                sample["images"],
                sample["web_urls"],
                sample["files"],
                sample["modules"],
                sample["functions"],
                sample["hunks"],
                sample["language"],
            ]
        )
    return rows


def main() -> None:
    generated = SCRIPT_DIR / "generated"
    generated.mkdir(parents=True, exist_ok=True)
    stats = [analyze_dataset(config) for config in DATASETS if config.samples.exists()]
    stats_path = generated / "benchmark_sample_distribution_stats.json"
    compact_stats = []
    for item in stats:
        without_samples = dict(item)
        without_samples["per_sample"] = item["per_sample"]
        compact_stats.append(without_samples)
    stats_path.write_text(json.dumps(compact_stats, ensure_ascii=False, indent=2), encoding="utf-8")
    chart_paths = write_charts(stats, generated)
    write_report(
        stats,
        chart_paths,
        ROOT_DIR / "notes/results/006_benchmark样本URL图片语言和Gold分布分析.md",
        generated,
    )
    print(f"Wrote {stats_path}")
    print(f"Wrote {ROOT_DIR / 'notes/results/006_benchmark样本URL图片语言和Gold分布分析.md'}")
    print(f"Wrote SVG charts under {generated}")


if __name__ == "__main__":
    main()
