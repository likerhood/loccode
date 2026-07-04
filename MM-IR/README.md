# MM-IR

Multimodal information-retrieval baselines for localization on
SWE-bench Multimodal and OmniGIRL.

The goal of this project is to provide non-agent baselines that use the
multimodal evidence available in the benchmarks without iterative LLM tool use.
The first implementation is `BM25-MMIR`. Dense embedding baselines are wired
through a shared retriever interface and can be added without changing the
benchmark reader, evidence builder, output writer, or evaluator.

## Baseline Family

| Method | Type | Query Sources | Code Index | Notes |
|---|---|---|---|---|
| BM25-MMIR | Lexical IR | issue text, OCR text, web text | file/module/function documents | Implemented |
| E5-MMIR | Dense text embedding | issue text, OCR text, web text | same documents | Implemented backend, requires dense deps |
| Jina-Code-v2-MMIR | Dense code embedding | issue text, OCR text, web text | same documents | Implemented backend, requires dense deps |
| CodeSage-large-v2-MMIR | Dense code embedding | issue text, OCR text, web text | same documents | Implemented backend, requires dense deps |
| CodeRankEmbed-MMIR | Dense code embedding | issue text, OCR text, web text | same documents | Implemented backend, requires dense deps |

## Design Principles

- No agent loop.
- No LLM reasoning for localization decisions.
- Multimodal evidence is extracted deterministically where possible:
  OCR for images, lightweight text extraction for web URLs.
- All retrievers share one document schema and one output schema.
- Output is directly compatible with the existing three-level localization
  evaluator:

```json
{
  "instance_id": "...",
  "found_files": ["path/to/file.js"],
  "found_modules": ["path/to/file.js::ClassName"],
  "found_functions": ["path/to/file.js::ClassName.methodName"]
}
```

## Layout

```text
MM-IR/
  mmir/
    benchmark/       # SWE-bench Multimodal / OmniGIRL readers
    evidence/        # issue text, OCR, web text extraction
    indexing/        # repo_structures -> file/module/function docs
    retrievers/      # BM25, E5, Jina-Code, Codesage, CodeRankEmbed
    fusion/          # RRF and weighted score fusion
    output/          # loc_results.json and three-level output helpers
  scripts/
    run_mmir_swebench_multimodal_60.sh
    run_mmir_omnigirl_60.sh
  docs/
    implementation_plan.md
```

See [docs/implementation_plan.md](docs/implementation_plan.md) for the detailed
roadmap.

## Run BM25-MMIR

Smoke test two samples:

```bash
cd /home/like/locCode/MM-IR
LIMIT=2 PYTHON_BIN=/home/like/miniconda3/envs/locagent/bin/python \
  bash scripts/run_mmir_swebench_multimodal_60.sh

LIMIT=2 PYTHON_BIN=/home/like/miniconda3/envs/locagent/bin/python \
  bash scripts/run_mmir_omnigirl_60.sh
```

Full runs:

```bash
cd /home/like/locCode/MM-IR
PYTHON_BIN=/home/like/miniconda3/envs/locagent/bin/python \
  bash scripts/run_mmir_swebench_multimodal_60.sh

PYTHON_BIN=/home/like/miniconda3/envs/locagent/bin/python \
  bash scripts/run_mmir_omnigirl_60.sh
```

## Run Dense MMIR

Dense methods use the same pipeline and evaluator as BM25. Install optional
dense dependencies in the environment you run from:

```bash
cd /home/like/locCode/MM-IR
/home/like/miniconda3/envs/locagent/bin/python -m pip install -r requirements-dense.txt
```

Supported method names:

```text
e5-mmir                  -> intfloat/e5-base-v2
jina-code-v2-mmir        -> jinaai/jina-embeddings-v2-base-code
codesage-large-v2-mmir   -> codesage/codesage-large-v2
coderankembed-mmir       -> nomic-ai/CodeRankEmbed
```

Run E5 on SWE-bench Multimodal:

```bash
cd /home/like/locCode/MM-IR
METHOD=e5-mmir DENSE_BATCH_SIZE=16 DENSE_DEVICE=cuda \
  PYTHON_BIN=/home/like/miniconda3/envs/locagent/bin/python \
  bash scripts/run_mmir_swebench_multimodal_60.sh
```

Override a model with a local path or another Hugging Face id:

```bash
METHOD=jina-code-v2-mmir DENSE_MODEL=/path/to/local/model \
  PYTHON_BIN=/home/like/miniconda3/envs/locagent/bin/python \
  bash scripts/run_mmir_omnigirl_60.sh
```

Default output locations:

```text
results/swebench_multimodal-60/bm25-mmir/loc_results.json
results/swebench_multimodal-60/bm25-mmir/eval/metrics_3level.md
results/omnigirl-60/bm25-mmir/loc_results.json
results/omnigirl-60/bm25-mmir/eval/metrics_3level.md
```

## Tests

```bash
cd /home/like/locCode/MM-IR
PYTHONPATH=/home/like/locCode/MM-IR \
  /home/like/miniconda3/envs/locagent/bin/python -m unittest discover -s tests
```
