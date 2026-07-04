"""File-level language helpers for mixed-language repositories."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rdfs.dependency_graph.models.language import Language


@dataclass(frozen=True)
class LanguageSpec:
    language: Language
    extensions: tuple[str, ...]


LANGUAGE_SPECS: tuple[LanguageSpec, ...] = (
    LanguageSpec(Language.CSharp, (".cs", ".csx")),
    LanguageSpec(Language.Python, (".py", ".pyi")),
    LanguageSpec(Language.Java, (".java",)),
    LanguageSpec(Language.JavaScript, (".js", ".jsx", ".mjs", ".cjs")),
    LanguageSpec(Language.TypeScript, (".ts", ".tsx", ".mts", ".cts", ".ets")),
    LanguageSpec(Language.Kotlin, (".kt", ".kts")),
    LanguageSpec(Language.PHP, (".php",)),
    LanguageSpec(Language.Ruby, (".rb",)),
    LanguageSpec(Language.C, (".c", ".h")),
    LanguageSpec(Language.CPP, (".cpp", ".hpp", ".cc", ".hh", ".cxx", ".hxx")),
    LanguageSpec(Language.Go, (".go",)),
    LanguageSpec(Language.Swift, (".swift",)),
    LanguageSpec(Language.Rust, (".rs",)),
    LanguageSpec(Language.Lua, (".lua",)),
    LanguageSpec(Language.Bash, (".sh", ".bash")),
    LanguageSpec(Language.R, (".r", ".R")),
)

EXTENSION_LANGUAGE_MAP: dict[str, Language] = {
    extension: spec.language
    for spec in LANGUAGE_SPECS
    for extension in spec.extensions
}


def normalize_language(language: Language | str | None) -> Language | None:
    if language is None:
        return None
    if isinstance(language, Language):
        if language == Language.ArkTS:
            return Language.TypeScript
        return language
    value = str(language)
    if value == Language.ArkTS.value:
        return Language.TypeScript
    return Language(value)


def is_auto_language(language: Language | str | None) -> bool:
    language = normalize_language(language)
    return language in {Language.Auto, Language.Mixed}


def language_from_path(file_path: str | Path) -> Language | None:
    path = Path(file_path)
    suffix = path.suffix
    if suffix == ".ets":
        return Language.TypeScript
    return EXTENSION_LANGUAGE_MAP.get(suffix)


def extensions_for_language(language: Language | str | None) -> tuple[str, ...]:
    language = normalize_language(language)
    if language in {Language.Auto, Language.Mixed, None}:
        return supported_extensions()
    return tuple(
        extension
        for spec in LANGUAGE_SPECS
        if spec.language == language
        for extension in spec.extensions
    )


def supported_extensions() -> tuple[str, ...]:
    extensions = []
    seen = set()
    for spec in LANGUAGE_SPECS:
        for extension in spec.extensions:
            if extension not in seen:
                seen.add(extension)
                extensions.append(extension)
    return tuple(extensions)

