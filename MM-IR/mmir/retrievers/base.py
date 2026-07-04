from __future__ import annotations

from abc import ABC, abstractmethod

from mmir.schema import Document, ScoredDocument


class Retriever(ABC):
    name: str

    @abstractmethod
    def build_index(self, docs: list[Document]) -> None:
        raise NotImplementedError

    @abstractmethod
    def search(self, query: str, top_k: int) -> list[ScoredDocument]:
        raise NotImplementedError
