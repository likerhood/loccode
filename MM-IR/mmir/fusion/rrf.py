from __future__ import annotations

from collections import defaultdict

from mmir.schema import ScoredDocument


def reciprocal_rank_fusion(rankings: list[list[ScoredDocument]], *, k: int = 60, limit: int = 15) -> list[ScoredDocument]:
    scores: dict[str, float] = defaultdict(float)
    docs = {}
    best_rank: dict[str, int] = {}
    for ranking in rankings:
        for item in ranking:
            doc_id = item.document.doc_id
            docs[doc_id] = item.document
            best_rank[doc_id] = min(best_rank.get(doc_id, item.rank), item.rank)
            scores[doc_id] += 1.0 / (k + item.rank)
    ordered = sorted(scores, key=lambda doc_id: (-scores[doc_id], best_rank.get(doc_id, 10**9), doc_id))
    return [
        ScoredDocument(document=docs[doc_id], score=scores[doc_id], rank=rank)
        for rank, doc_id in enumerate(ordered[:limit], start=1)
    ]
