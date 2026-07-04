# MM-IR Implementation Plan

## 1. Motivation

LocAgent is an agent-based localizer. To show that the multimodal information
itself is useful, MM-IR provides a non-agent retrieval baseline. It uses issue
text, screenshots, and web URLs to retrieve code locations at file, module, and
function levels.

This baseline answers:

- How strong is multimodal retrieval without agentic reasoning?
- How much does OCR from screenshots help over issue text alone?
- How much do code-specific embeddings help over BM25?

## 2. Inputs

Each benchmark sample should be normalized to:

```json
{
  "instance_id": "...",
  "repo": "owner/name",
  "base_commit": "...",
  "problem_statement": "...",
  "image_urls": ["..."],
  "web_urls": ["..."],
  "patch": "gold patch, eval only",
  "files": ["gold files, eval only"]
}
```

The localization pipeline must not use `patch` or `files` for prediction.

## 3. Evidence Extraction

### 3.1 Text Evidence

Use the issue title/body/problem statement directly.

Extract high-value lexical signals:

- stack trace file paths
- function/class-like identifiers
- route strings
- error strings
- quoted UI strings
- package/module names

### 3.2 OCR Evidence

Run OCR over benchmark screenshots and add the extracted text to the retrieval
query. OCR is the key multimodal component for the first version.

Useful screenshot signals often include:

- visible UI labels
- buttons
- browser URL bar path
- console errors
- screenshots of rendered error messages

### 3.3 Web Evidence

For each web URL, extract lightweight page text:

- title
- headings
- alt text
- short visible paragraphs
- GitHub issue/PR title when available

The first version should cache fetched text and tolerate network failures.

## 4. Code Document Schema

All retrievers should use the same document schema:

```json
{
  "doc_id": "file::path/to/file.js",
  "level": "file | module | function",
  "file": "path/to/file.js",
  "symbol": "ClassName.methodName",
  "text": "path, names, comments, string literals, code snippet",
  "metadata": {
    "start_line": 12,
    "end_line": 40,
    "language": "javascript"
  }
}
```

Documents are built from `repo_structures` when available. For robustness, a
fallback source-code scanner can be added later.

## 5. BM25 Baseline, First Implementation Target

### 5.1 Variants

Implement these BM25 variants first:

| Variant | Query |
|---|---|
| BM25-text | issue text only |
| BM25-text+OCR | issue text + OCR text |
| BM25-text+OCR+Web | issue text + OCR text + web text |
| BM25-full | all above + symbol/path/string-literal boosts |

### 5.2 Retrieval Levels

Recommended first pass:

1. Rank file documents globally.
2. Take top-N files.
3. Rank module/function documents only within top-N files.

This avoids noisy full-repo function search.

### 5.3 Scoring

Use BM25 as the base score. Add deterministic boosts:

```text
score = bm25
      + path_match_boost
      + symbol_match_boost
      + string_literal_boost
      + ocr_exact_phrase_boost
```

Use stable default cutoffs:

```text
top_files = 15
candidate_file_pool = 50
top_modules = 15
top_functions = 15
```

### 5.4 Output

Write:

```text
results/<benchmark>/<method>/loc_results.json
results/<benchmark>/<method>/eval/metrics_3level.md
```

`loc_results.json` should use:

```json
{
  "instance_id": {
    "found_files": [],
    "found_modules": [],
    "found_functions": []
  }
}
```

## 6. Dense Embedding Baselines

After BM25 is working, add retriever backends with the same document schema.

### 6.1 E5-base-v2

General-purpose text embedding baseline. Use query/document prefixes if the
model expects them:

```text
query: ...
passage: ...
```

Best used for issue/OCR/web text to code-document semantic retrieval.

### 6.2 Jina-Code-v2

Code-oriented embedding baseline with long-context support. Good candidate for
file-level and function-level code documents.

### 6.3 Codesage-large-v2

Code embedding baseline. Keep it behind the same `DenseRetriever` interface so
it can be enabled if the local model is available.

### 6.4 CodeRankEmbed

Code retrieval bi-encoder baseline. Use it as another dense backend and compare
against BM25 and E5.

## 7. Fusion

All retriever outputs should be fused with Reciprocal Rank Fusion:

```text
RRF(d) = sum_i 1 / (k + rank_i(d))
```

Recommended `k=60`.

Planned fusion variants:

- BM25 only
- BM25 + OCR BM25
- BM25 + dense
- BM25 + OCR + dense
- BM25 + OCR + dense + symbol boosts

## 8. Evaluation

Use the same three-level metrics already used by LocAgent/GALA/CoSIL:

- File Acc@k / MRR / MAP
- Module Acc@k / MRR / MAP
- Function Acc@k / MRR / MAP
- Set metrics @10 and @15

This makes MM-IR directly comparable to agent-based baselines.

## 9. Implementation Phases

### Phase 1: BM25 MVP

- Benchmark readers for SWE-bench Multimodal and OmniGIRL.
- Corpus builder from `repo_structures`.
- OCR text cache interface, initially optional.
- BM25 retriever.
- File -> module/function reranking.
- Three-level output.

### Phase 2: Multimodal Evidence

- OCR pipeline.
- Web text extraction.
- Evidence cache.
- BM25 ablations.

### Phase 3: Dense Retrieval

- E5 backend.
- Jina-Code-v2 backend.
- Codesage backend.
- CodeRankEmbed backend.
- FAISS or NumPy index cache.

### Phase 4: Fusion and Reporting

- RRF fusion.
- Per-evidence ablation tables.
- Dataset-level reports for both benchmarks.

## 10. Expected Use in Comparison Table

MM-IR should be reported as an Embedding/IR-based baseline:

```text
Embedding-Based | BM25-MMIR             | none
Embedding-Based | E5-base-v2-MMIR       | e5-base-v2
Embedding-Based | Jina-Code-v2-MMIR     | jina-embeddings-v2-base-code
Embedding-Based | CodeRankEmbed-MMIR    | CodeRankEmbed
```

The `Loc-Model` column can be `None/BM25` for lexical BM25, and the model name
for dense embedding variants.
