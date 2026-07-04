import json
import os
import tempfile
import unittest
from pathlib import Path

from muladapter.adapter import detect_language, enrich_problem_statement, export_for_graphlocator, scan_repo


class MulAdapterTest(unittest.TestCase):
    def make_repo(self, root: Path) -> None:
        (root / "src").mkdir()
        (root / "src" / "App.tsx").write_text("export default function App() { return <Button />; }\nconst Button = () => 1;\n", encoding="utf-8")
        (root / "src" / "Main.java").write_text("public class Main { public void run() {} }\n", encoding="utf-8")
        (root / "src" / "mod.py").write_text("class Handler:\n    pass\n\ndef handle():\n    return 1\n", encoding="utf-8")

    def test_detect_language(self):
        self.assertEqual(detect_language("x.tsx"), "typescript")
        self.assertEqual(detect_language("x.java"), "java")

    def test_enrich_problem_statement(self):
        os.environ.pop("MULADAPTER_MODE", None)
        enriched = enrich_problem_statement({"problem_statement": "see https://example.com/a.png and https://example.com"})
        self.assertIn("Attached Images:", enriched["problem_statement"])
        self.assertIn("Related URLs:", enriched["problem_statement"])

    def test_codev_compact_enrichment_uses_fallbacks_without_network(self):
        with tempfile.TemporaryDirectory() as td:
            old_env = dict(os.environ)
            try:
                os.environ["MULADAPTER_MODE"] = "codev_compact"
                os.environ["MULADAPTER_CACHE_FILE"] = str(Path(td) / "cache.json")
                os.environ.pop("MULADAPTER_BASE_URL", None)
                os.environ.pop("MULADAPTER_MODEL", None)
                enriched = enrich_problem_statement({
                    "problem_statement": "Broken chart https://example.com/chart.png see https://github.com/org/repo/commit/abc123"
                })
                self.assertIn("[Multimodal Context - Compact]", enriched["problem_statement"])
                self.assertIn("Visual processing failed", enriched["problem_statement"])
                self.assertIn("Skipped detailed fetch", enriched["problem_statement"])
            finally:
                os.environ.clear()
                os.environ.update(old_env)

    def test_scan_and_export_two_samples(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            self.make_repo(repo)
            parsed = scan_repo(repo)
            self.assertGreaterEqual(len(parsed["files"]), 3)
            samples = [{"instance_id": "demo__1", "problem_statement": "one"}, {"instance_id": "demo__2", "problem_statement": "two"}]
            out = Path(td) / "out"
            export_for_graphlocator(parsed, samples, out)
            data = json.loads((out / "repo_skeleton" / "demo__1.json").read_text())
            self.assertEqual(data["adapter_schema"], "graphlocator-muladapter-v1")
            self.assertGreaterEqual(len(data["nodes"]), 3)


if __name__ == "__main__":
    unittest.main()
