from __future__ import annotations

import re
from typing import Any, Iterator

from mmir.schema import CodeEntity


def normalize_path(path: Any) -> str:
    text = str(path or "").strip().replace("\\", "/").lstrip("./")
    if text.startswith(("a/", "b/")):
        text = text[2:]
    return text


def language_from_path(file_path: str) -> str:
    lower = file_path.lower()
    if lower.endswith((".ts", ".tsx", ".mts", ".cts")):
        return "typescript"
    if lower.endswith((".js", ".jsx", ".mjs", ".cjs")):
        return "javascript"
    if lower.endswith(".py"):
        return "python"
    if lower.endswith(".java"):
        return "java"
    return ""


CODE_SUFFIXES = {
    ".c",
    ".cc",
    ".cfg",
    ".cjs",
    ".cpp",
    ".cs",
    ".css",
    ".go",
    ".h",
    ".hpp",
    ".html",
    ".ini",
    ".java",
    ".js",
    ".json",
    ".jsx",
    ".kt",
    ".kts",
    ".less",
    ".mjs",
    ".mts",
    ".php",
    ".py",
    ".rb",
    ".rs",
    ".scala",
    ".scss",
    ".svelte",
    ".swift",
    ".toml",
    ".ts",
    ".tsx",
    ".vue",
    ".yaml",
    ".yml",
}

DOC_NAMES = {
    "changelog",
    "code_of_conduct",
    "contributing",
    "license",
    "readme",
    "security",
}


def is_indexable_code_path(file_path: str) -> bool:
    normalized = normalize_path(file_path)
    lower = normalized.lower()
    name = lower.rsplit("/", 1)[-1]
    stem = name.rsplit(".", 1)[0]
    if lower.endswith((".md", ".mdx", ".rst", ".txt")):
        return False
    if stem in DOC_NAMES:
        return False
    if "issue_template" in lower or lower.startswith(("docs/", "doc/", "documentation/")):
        return False
    return any(lower.endswith(suffix) for suffix in CODE_SUFFIXES)


def _brace_end_line(lines: list[str], start_line: int) -> int:
    balance = 0
    opened = False
    for idx in range(max(start_line - 1, 0), len(lines)):
        line = re.sub(r"//.*$", "", lines[idx])
        balance += line.count("{")
        opened = opened or "{" in line
        balance -= line.count("}")
        if opened and balance <= 0:
            return idx + 1
    return start_line


def _python_end_line(lines: list[str], start_line: int) -> int:
    if start_line < 1 or start_line > len(lines):
        return start_line
    base = len(lines[start_line - 1]) - len(lines[start_line - 1].lstrip())
    end = start_line
    for idx in range(start_line, len(lines)):
        text = lines[idx]
        if not text.strip():
            end = idx + 1
            continue
        indent = len(text) - len(text.lstrip())
        if indent <= base and re.match(r"\s*(def|class)\s+", text):
            break
        if indent <= base and not text.lstrip().startswith(("#", "@")):
            break
        end = idx + 1
    return max(end, start_line)


def _line_from_item(item: dict[str, Any], default: int = 1) -> int:
    try:
        return max(1, int(item.get("start_line") or default))
    except (TypeError, ValueError):
        return default


def _end_from_item(item: dict[str, Any], lines: list[str], start: int, language: str) -> int:
    try:
        end = int(item.get("end_line") or 0)
    except (TypeError, ValueError):
        end = 0
    if end and end >= start:
        return end
    return _python_end_line(lines, start) if language == "python" else _brace_end_line(lines, start)


def _clean_name(value: Any) -> str:
    return str(value or "").strip().strip("`'\"")


def _regex_entities(file_path: str, lines: list[str], language: str) -> list[CodeEntity]:
    if language == "python":
        patterns = [
            ("class", re.compile(r"^\s*class\s+([A-Za-z_]\w*)\b")),
            ("function", re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)\s*\(")),
        ]
    elif language in {"javascript", "typescript"}:
        patterns = [
            ("class", re.compile(r"\bclass\s+([A-Za-z_$][\w$]*)")),
            ("function", re.compile(r"\bfunction\s+([A-Za-z_$][\w$]*)\s*\(")),
            ("function", re.compile(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>")),
            ("function", re.compile(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?function\b")),
            ("method", re.compile(r"^\s*(?:async\s+)?([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{")),
            ("method", re.compile(r"\.prototype\.([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?function\b")),
        ]
    elif language == "java":
        patterns = [
            ("class", re.compile(r"\bclass\s+([A-Za-z_]\w*)\b")),
            ("function", re.compile(r"^\s*(?:public|private|protected)?\s*(?:static\s+)?[A-Za-z_<>\[\], ?]+\s+([A-Za-z_]\w*)\s*\([^;{}]*\)\s*(?:throws\s+[^{]+)?\{")),
        ]
    else:
        patterns = [
            ("class", re.compile(r"\b(?:class|struct|interface)\s+([A-Za-z_]\w*)\b")),
            ("function", re.compile(r"^\s*(?:func|fn)\s+([A-Za-z_]\w*)\s*\(")),
            ("function", re.compile(r"^\s*[A-Za-z_][\w:<>\s*&]*\s+([A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{")),
        ]
    entities: list[CodeEntity] = []
    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith(("//", "*", "#")):
            continue
        for kind, pattern in patterns:
            match = pattern.search(line)
            if not match:
                continue
            name = match.group(1)
            if name in {"if", "for", "while", "switch", "catch", "function"}:
                continue
            end = _python_end_line(lines, idx) if language == "python" else _brace_end_line(lines, idx)
            entities.append(CodeEntity(file_path, kind, name, name, idx, end, language))
            break
    return entities


def iter_structure_files(structure: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    def walk(node: dict[str, Any], prefix: str = ""):
        for name, content in node.items():
            path = f"{prefix}/{name}" if prefix else name
            if isinstance(content, dict) and "text" in content:
                yield normalize_path(path), content
            elif isinstance(content, dict):
                yield from walk(content, path)

    yield from walk(structure)


def extract_entities_from_structure_file(file_path: str, file_node: dict[str, Any]) -> list[CodeEntity]:
    text = file_node.get("text") or ""
    lines = text.splitlines() if isinstance(text, str) else [str(line) for line in text]
    language = language_from_path(file_path)
    entities: list[CodeEntity] = []
    for cls in file_node.get("classes") or []:
        if not isinstance(cls, dict):
            continue
        name = _clean_name(cls.get("name"))
        if not name:
            continue
        start = _line_from_item(cls)
        end = _end_from_item(cls, lines, start, language)
        entities.append(CodeEntity(file_path, "class", name, name, start, end, language))
        for method in cls.get("methods") or []:
            if not isinstance(method, dict):
                continue
            method_name = _clean_name(method.get("name"))
            if not method_name:
                continue
            m_start = _line_from_item(method, start)
            m_end = _end_from_item(method, lines, m_start, language)
            entities.append(CodeEntity(file_path, "method", method_name, f"{name}.{method_name}", m_start, m_end, language))
    for fn in file_node.get("functions") or []:
        if not isinstance(fn, dict):
            continue
        name = _clean_name(fn.get("name"))
        if not name:
            continue
        start = _line_from_item(fn)
        end = _end_from_item(fn, lines, start, language)
        entities.append(CodeEntity(file_path, "function", name, name, start, end, language))
    existing = {(e.kind, e.name, e.start_line) for e in entities}
    for entity in _regex_entities(file_path, lines, language):
        key = (entity.kind, entity.name, entity.start_line)
        if key not in existing:
            existing.add(key)
            entities.append(entity)
    classes = [entity for entity in entities if entity.kind == "class"]
    qualified: list[CodeEntity] = []
    for entity in entities:
        if entity.kind == "method" and "." not in entity.qualified_name:
            parents = [cls for cls in classes if cls.start_line < entity.start_line <= cls.end_line]
            if parents:
                parent = sorted(parents, key=lambda cls: (cls.end_line - cls.start_line, -cls.start_line))[0]
                entity = CodeEntity(entity.file, entity.kind, entity.name, f"{parent.qualified_name}.{entity.name}", entity.start_line, entity.end_line, entity.language)
        qualified.append(entity)
    return sorted(qualified, key=lambda item: (item.start_line, item.kind, item.name))


def extract_entities_from_structure(structure: dict[str, Any]) -> dict[str, list[CodeEntity]]:
    return {
        file_path: extract_entities_from_structure_file(file_path, file_node)
        for file_path, file_node in iter_structure_files(structure)
    }


def entities_overlapping_lines(entities: list[CodeEntity], lines: set[int]) -> list[CodeEntity]:
    return [
        entity
        for entity in entities
        if any(entity.start_line <= line <= entity.end_line for line in lines)
    ] if lines else []
