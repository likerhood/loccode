from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

from mmir.benchmark.samples import load_samples
from mmir.evidence.builder import build_evidence
from mmir.indexing.document_builder import build_documents
from mmir.output.writer import write_json
from mmir.retrievers.bm25 import BM25Retriever
from mmir.retrievers.dense import DenseRetriever
from mmir.schema import Document, Sample, ScoredDocument


def _dedupe_hits(hits: Iterable[ScoredDocument], key_name: str) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for hit in hits:
        doc = hit.document
        value = doc.file if key_name == "file" else str(doc.metadata.get(key_name) or doc.symbol or doc.file)
        if not value or value in seen:
            continue
        seen.add(value)
        row = {
            "id": value,
            "file": doc.file,
            "score": hit.score,
            "rank": hit.rank,
            "symbol": doc.symbol,
            "start_line": doc.start_line,
            "end_line": doc.end_line,
            "metadata": doc.metadata,
        }
        out.append(row)
    return out


def _search(
    docs: list[Document],
    query: str,
    top_k: int,
    *,
    method: str,
    dense_model: str | None = None,
    dense_batch_size: int = 16,
    dense_device: str | None = None,
) -> list[ScoredDocument]:
    if method == "bm25-mmir":
        retriever = BM25Retriever()
    else:
        retriever = DenseRetriever(
            method=method,
            model_name=dense_model,
            batch_size=dense_batch_size,
            device=dense_device,
        )
    retriever.build_index(docs)
    return retriever.search(query, top_k)


def locate_sample(
    sample: Sample,
    *,
    structure_dir: str | Path,
    ocr_cache: str | Path | None = None,
    web_cache: str | Path | None = None,
    top_files: int = 15,
    candidate_file_pool: int = 40,
    top_modules: int = 15,
    top_functions: int = 15,
    method: str = "bm25-mmir",
    dense_model: str | None = None,
    dense_batch_size: int = 16,
    dense_device: str | None = None,
) -> dict:
    docs, _ = build_documents(sample, structure_dir)
    evidence = build_evidence(sample, ocr_cache=ocr_cache, web_cache=web_cache)
    query = evidence.query_text

    file_docs = [doc for doc in docs if doc.level == "file"]
    file_hits = _search(
        file_docs,
        query,
        max(top_files, candidate_file_pool),
        method=method,
        dense_model=dense_model,
        dense_batch_size=dense_batch_size,
        dense_device=dense_device,
    )
    candidate_files = {hit.document.file for hit in file_hits[:candidate_file_pool]}

    module_docs = [doc for doc in docs if doc.level == "module" and doc.file in candidate_files]
    function_docs = [doc for doc in docs if doc.level == "function" and doc.file in candidate_files]
    module_hits = _search(
        module_docs,
        query,
        top_modules,
        method=method,
        dense_model=dense_model,
        dense_batch_size=dense_batch_size,
        dense_device=dense_device,
    )
    function_hits = _search(
        function_docs,
        query,
        top_functions,
        method=method,
        dense_model=dense_model,
        dense_batch_size=dense_batch_size,
        dense_device=dense_device,
    )

    file_rows = _dedupe_hits(file_hits, "file")[:top_files]
    module_rows = _dedupe_hits(module_hits, "module_id")[:top_modules]
    function_rows = _dedupe_hits(function_hits, "entity_id")[:top_functions]

    return {
        "instance_id": sample.instance_id,
        "repo": sample.repo,
        "method": method,
        "dense_model": dense_model or "",
        "found_files": [row["id"] for row in file_rows],
        "found_modules": [row["id"] for row in module_rows],
        "found_functions": [row["id"] for row in function_rows],
        "ranked_files": file_rows,
        "ranked_modules": module_rows,
        "ranked_functions": function_rows,
        "evidence": asdict(evidence),
    }


def run_location(
    *,
    samples_path: str | Path,
    structure_dir: str | Path,
    output_dir: str | Path,
    ocr_cache: str | Path | None = None,
    web_cache: str | Path | None = None,
    limit: int | None = None,
    top_files: int = 15,
    candidate_file_pool: int = 40,
    top_modules: int = 15,
    top_functions: int = 15,
    method: str = "bm25-mmir",
    dense_model: str | None = None,
    dense_batch_size: int = 16,
    dense_device: str | None = None,
) -> dict[str, dict]:
    samples = load_samples(samples_path)
    if limit:
        samples = samples[:limit]
    dense_fail_fast = os.environ.get("MMIR_DENSE_FAIL_FAST", "1").strip().lower() not in {"0", "false", "no", "off"}
    if method != "bm25-mmir":
        # Load once before the loop so missing dense dependencies fail loudly
        # instead of producing one empty prediction row per sample.
        DenseRetriever(
            method=method,
            model_name=dense_model,
            batch_size=dense_batch_size,
            device=dense_device,
        )

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, dict] = {}
    debug_path = out_dir / "retrieval_debug.jsonl"
    with debug_path.open("w", encoding="utf-8") as debug_file:
        for idx, sample in enumerate(samples, start=1):
            print(f"[MM-IR] locating {idx}/{len(samples)} {sample.instance_id}", flush=True)
            try:
                row = locate_sample(
                    sample,
                    structure_dir=structure_dir,
                    ocr_cache=ocr_cache,
                    web_cache=web_cache,
                    top_files=top_files,
                    candidate_file_pool=candidate_file_pool,
                    top_modules=top_modules,
                    top_functions=top_functions,
                    method=method,
                    dense_model=dense_model,
                    dense_batch_size=dense_batch_size,
                    dense_device=dense_device,
                )
            except Exception as exc:
                if method != "bm25-mmir" and dense_fail_fast:
                    raise RuntimeError(
                        f"Dense MM-IR failed on {sample.instance_id}. "
                        "Stop to avoid writing empty dense retrieval rows."
                    ) from exc
                row = {
                    "instance_id": sample.instance_id,
                    "repo": sample.repo,
                    "method": method,
                    "dense_model": dense_model or "",
                    "error": str(exc),
                    "found_files": [],
                    "found_modules": [],
                    "found_functions": [],
                    "ranked_files": [],
                    "ranked_modules": [],
                    "ranked_functions": [],
                }
            results[sample.instance_id] = row
            debug_file.write(json.dumps(row, ensure_ascii=False) + "\n")

    write_json(out_dir / "loc_results.json", results)
    write_json(
        out_dir / "run_config.json",
        {
            "method": method,
            "dense_model": dense_model or "",
            "dense_batch_size": dense_batch_size,
            "dense_device": dense_device or "",
            "samples_path": str(samples_path),
            "structure_dir": str(structure_dir),
            "ocr_cache": str(ocr_cache) if ocr_cache else "",
            "web_cache": str(web_cache) if web_cache else "",
            "limit": limit,
            "top_files": top_files,
            "candidate_file_pool": candidate_file_pool,
            "top_modules": top_modules,
            "top_functions": top_functions,
        },
    )
    return results
