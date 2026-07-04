from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Sample:
    instance_id: str
    repo: str
    base_commit: str
    problem_statement: str
    patch: str = ""
    files: list[str] = field(default_factory=list)
    image_urls: list[str] = field(default_factory=list)
    web_urls: list[str] = field(default_factory=list)

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "Sample":
        web_urls = row.get("web_urls") or row.get("website_links") or []
        return cls(
            instance_id=str(row.get("instance_id") or row.get("id") or ""),
            repo=str(row.get("repo") or row.get("repository") or ""),
            base_commit=str(row.get("base_commit") or row.get("commit") or ""),
            problem_statement=str(row.get("problem_statement") or row.get("issue") or ""),
            patch=str(row.get("patch") or row.get("gold_patch") or ""),
            files=[str(item) for item in row.get("files") or []],
            image_urls=[str(item) for item in row.get("image_urls") or []],
            web_urls=[str(item) for item in web_urls or []],
        )


@dataclass(frozen=True)
class Evidence:
    issue_text: str
    ocr_text: str = ""
    web_text: str = ""
    symbols: list[str] = field(default_factory=list)

    @property
    def query_text(self) -> str:
        parts = [self.issue_text, self.ocr_text, self.web_text, " ".join(self.symbols)]
        return "\n".join(part for part in parts if part.strip())


@dataclass(frozen=True)
class CodeEntity:
    file: str
    kind: str
    name: str
    qualified_name: str
    start_line: int
    end_line: int
    language: str = ""


@dataclass(frozen=True)
class Document:
    doc_id: str
    level: str
    file: str
    text: str
    symbol: str = ""
    start_line: int = 0
    end_line: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ScoredDocument:
    document: Document
    score: float
    rank: int
