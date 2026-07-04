from __future__ import annotations

import math
import re
from collections import Counter

from mmir.retrievers.base import Retriever
from mmir.schema import Document, ScoredDocument


TOKEN_RE = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*|\d+")


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for raw in TOKEN_RE.findall(text or ""):
        token = raw.lower()
        tokens.append(token)
        split = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", raw).replace("_", " ").replace("-", " ")
        for part in split.split():
            part = part.lower()
            if part and part != token:
                tokens.append(part)
    return tokens


class BM25Retriever(Retriever):
    name = "bm25-mmir"

    def __init__(self, *, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.docs: list[Document] = []
        self.doc_tokens: list[list[str]] = []
        self.term_freqs: list[Counter[str]] = []
        self.doc_freq: Counter[str] = Counter()
        self.avgdl = 0.0

    def build_index(self, docs: list[Document]) -> None:
        self.docs = docs
        self.doc_tokens = [tokenize(doc.text) for doc in docs]
        self.term_freqs = [Counter(tokens) for tokens in self.doc_tokens]
        self.doc_freq = Counter()
        for tokens in self.doc_tokens:
            self.doc_freq.update(set(tokens))
        self.avgdl = sum(len(tokens) for tokens in self.doc_tokens) / max(1, len(self.doc_tokens))

    def _idf(self, term: str) -> float:
        n_docs = len(self.docs)
        df = self.doc_freq.get(term, 0)
        return math.log(1 + (n_docs - df + 0.5) / (df + 0.5))

    def search(self, query: str, top_k: int) -> list[ScoredDocument]:
        query_terms = tokenize(query)
        if not query_terms or not self.docs:
            return []
        query_counts = Counter(query_terms)
        scored: list[tuple[float, int, Document]] = []
        for idx, (doc, tf) in enumerate(zip(self.docs, self.term_freqs)):
            dl = len(self.doc_tokens[idx])
            score = 0.0
            for term, qf in query_counts.items():
                freq = tf.get(term, 0)
                if not freq:
                    continue
                denom = freq + self.k1 * (1 - self.b + self.b * dl / max(self.avgdl, 1e-9))
                score += self._idf(term) * (freq * (self.k1 + 1) / denom) * min(qf, 3)
            if score > 0:
                scored.append((score, idx, doc))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [
            ScoredDocument(document=doc, score=score, rank=rank)
            for rank, (score, _, doc) in enumerate(scored[:top_k], start=1)
        ]
