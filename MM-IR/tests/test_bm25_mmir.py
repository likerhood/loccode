from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from mmir.evaluation.eval_3level import evaluate
from mmir.pipeline import run_location
from mmir.retrievers.bm25 import BM25Retriever
from mmir.retrievers.dense import DenseRetriever
from mmir.schema import Document


class BM25MMIRTest(unittest.TestCase):
    def test_bm25_ranks_matching_document(self) -> None:
        docs = [
            Document("file::a.py", "file", "a.py", "unrelated text"),
            Document("file::b.py", "file", "b.py", "contact form selectedSite ID null crash"),
        ]
        retriever = BM25Retriever()
        retriever.build_index(docs)
        hits = retriever.search("selectedSite null contact form", 1)
        self.assertEqual(hits[0].document.file, "b.py")

    def test_dense_retriever_ranks_matching_document_with_fake_embedder(self) -> None:
        class FakeEmbedder:
            def encode(self, texts: list[str], *, batch_size: int, is_query: bool) -> np.ndarray:
                vectors = []
                for text in texts:
                    lower = text.lower()
                    vectors.append([
                        1.0 if "selectedsite" in lower else 0.0,
                        1.0 if "contact" in lower else 0.0,
                        1.0 if "stripe" in lower else 0.0,
                    ])
                return np.asarray(vectors, dtype=np.float32)

        docs = [
            Document("file::stripe.js", "file", "stripe.js", "stripe payment connection"),
            Document("file::contact.js", "file", "contact.js", "selectedSite contact form crash"),
        ]
        retriever = DenseRetriever(method="e5-mmir", embedder=FakeEmbedder())
        retriever.build_index(docs)
        hits = retriever.search("selectedSite contact", 2)
        self.assertEqual(hits[0].document.file, "contact.js")

    def test_pipeline_and_evaluator_emit_three_levels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            samples = root / "samples.jsonl"
            structure_dir = root / "structures"
            output_dir = root / "out"
            structure_dir.mkdir()
            instance_id = "demo__repo-1"
            patch = "\n".join(
                [
                    "diff --git a/src/contact.js b/src/contact.js",
                    "--- a/src/contact.js",
                    "+++ b/src/contact.js",
                    "@@ -2,4 +2,4 @@",
                    "-export function renderContactForm(selectedSite) {",
                    "+export function renderContactForm(selectedSite = {}) {",
                    "   return selectedSite.ID;",
                    " }",
                ]
            )
            samples.write_text(
                json.dumps(
                    {
                        "instance_id": instance_id,
                        "repo": "demo/repo",
                        "base_commit": "abc",
                        "problem_statement": "Contact form crashes when selectedSite ID is null.",
                        "patch": patch,
                        "files": ["src/contact.js"],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            structure = {
                "structure": {
                    "src": {
                        "contact.js": {
                            "text": "const x = 1;\nexport function renderContactForm(selectedSite) {\n  return selectedSite.ID;\n}\n",
                            "functions": [{"name": "renderContactForm", "start_line": 2, "end_line": 4}],
                        }
                    }
                }
            }
            (structure_dir / f"{instance_id}.json").write_text(json.dumps(structure), encoding="utf-8")
            results = run_location(samples_path=samples, structure_dir=structure_dir, output_dir=output_dir)
            row = results[instance_id]
            self.assertEqual(row["found_files"][0], "src/contact.js")
            self.assertTrue(row["found_functions"])

            metrics = evaluate(samples, output_dir / "loc_results.json", structure_dir, output_dir / "eval")
            self.assertEqual(metrics["evaluated"], 1)
            self.assertTrue((output_dir / "eval" / "metrics_3level.md").exists())


if __name__ == "__main__":
    unittest.main()
