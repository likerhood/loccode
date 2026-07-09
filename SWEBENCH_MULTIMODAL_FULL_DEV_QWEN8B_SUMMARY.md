# SWE-bench Multimodal Full Dev Qwen3-VL-8B Baseline Summary

Generated: 2026-07-09

This document summarizes the completed `qwen3-vl-8b` baseline run on the full SWE-bench Multimodal `dev` split. The evaluated set contains 102 instances.

## Experiment Scope

| Item | Value |
|---|---|
| Benchmark | SWE-bench Multimodal |
| Split | dev |
| Samples | 102 |
| Model for LLM/VLM baselines | `openai/qwen3-vl-8b` / `qwen3-vl-8b` |
| Main run log | `baseline_run_logs/swebench_multimodal_full_dev_parallel_20260708_182346/` |
| Canonical samples | `LocAgent/newtest/swebench_multimodal-full-dev/data/samples.jsonl` |
| Canonical structures | `LocAgent/newtest/swebench_multimodal-full-dev/repo_structures/` |

Dataset profile from the run:

| Repository | Count |
|---|---:|
| Automattic/wp-calypso | 37 |
| chartjs/Chart.js | 24 |
| diegomura/react-pdf | 11 |
| markedjs/marked | 14 |
| processing/p5.js | 16 |

The prepared full-dev set contains 301 images and 138 web URLs.

## Result Paths

| Baseline | Result Directory |
|---|---|
| LocAgent | `LocAgent/newtest/swebench_multimodal-full-dev/results/openai_qwen3-vl-8b/` |
| CoSIL | `CoSIL/newtest/swebench_multimodal-full-dev/results/openai_qwen3-vl-8b/` |
| GraphLocator | `GraphLocator/newtest/swebench_multimodal-full-dev/results/openai_qwen3-vl-8b/` |
| GALA | `GALA/mytest/swebench_multimodal-full-dev/results/qwen3-vl-8b/` |
| BM25-MMIR | `MM-IR/results/swebench_multimodal-full-candidates/bm25-mmir/` |

Notes:

- BM25-MMIR is a non-LLM retrieval baseline. Its directory name is `swebench_multimodal-full-candidates`, but the evaluated sample count is also 102.
- GALA file-level metrics use the `final` stage. Module and function metrics are derived from GALA staged candidates and `repo_structures`.
- CoSIL completed 102 rows and normalized 102 non-empty file-level outputs in this run.

## Metric Definition

Two Acc@K standards are reported:

- Relaxed Acc@K: hit-any standard. A sample is correct if at least one gold location at that level appears in top-K.
- Strict Acc@K: LocAgent-style full-coverage standard. A sample is correct only if top-K covers all gold locations at that level.

`MRR@15`, `MAP@15`, and `Empty` are also included. Set metrics are reported as:

- `SL`: full-coverage success for the evaluated prediction set.
- `REC`: average recall.
- `PRE`: average precision.
- `F1`: average F1.

All values below are percentages.

## Relaxed Ranking Metrics

### File Level

| Baseline | N | Acc@1 | Acc@3 | Acc@5 | Acc@10 | Acc@15 | MRR@15 | MAP@15 | Empty |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 102 | 26.47 | 31.37 | 38.24 | 41.18 | 41.18 | 30.78 | 18.83 | 4.90 |
| CoSIL | 102 | 31.37 | 43.14 | 44.12 | 44.12 | 44.12 | 37.01 | 22.27 | 0.00 |
| GraphLocator | 102 | 20.59 | 25.49 | 28.43 | 29.41 | 29.41 | 23.56 | 11.53 | 0.00 |
| GALA | 102 | 36.27 | 57.84 | 61.76 | 61.76 | 61.76 | 47.40 | 30.00 | 0.00 |
| BM25-MMIR | 102 | 26.47 | 41.18 | 46.08 | 58.82 | 65.69 | 36.07 | 21.89 | 0.00 |

### Module Level

| Baseline | N | Acc@1 | Acc@3 | Acc@5 | Acc@10 | Acc@15 | MRR@15 | MAP@15 | Empty |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 102 | 9.80 | 18.63 | 23.53 | 31.37 | 34.31 | 16.21 | 11.70 | 4.90 |
| CoSIL | 102 | 23.53 | 31.37 | 33.33 | 33.33 | 33.33 | 27.45 | 18.35 | 1.96 |
| GraphLocator | 102 | 14.71 | 22.55 | 23.53 | 23.53 | 24.51 | 18.46 | 11.60 | 10.78 |
| GALA | 102 | 9.80 | 20.59 | 22.55 | 23.53 | 23.53 | 14.98 | 10.88 | 0.98 |
| BM25-MMIR | 102 | 13.73 | 30.39 | 37.25 | 50.00 | 56.86 | 25.16 | 19.03 | 0.00 |

### Function Level

| Baseline | N | Acc@1 | Acc@3 | Acc@5 | Acc@10 | Acc@15 | MRR@15 | MAP@15 | Empty |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 102 | 2.94 | 10.78 | 12.75 | 18.63 | 19.61 | 7.30 | 4.17 | 4.90 |
| CoSIL | 102 | 5.88 | 9.80 | 13.73 | 15.69 | 16.67 | 8.90 | 5.06 | 1.96 |
| GraphLocator | 102 | 5.88 | 10.78 | 12.75 | 13.73 | 14.71 | 8.66 | 5.06 | 11.76 |
| GALA | 102 | 5.88 | 8.82 | 11.76 | 11.76 | 12.75 | 7.74 | 5.57 | 10.78 |
| BM25-MMIR | 102 | 11.76 | 21.57 | 26.47 | 35.29 | 39.22 | 18.88 | 10.51 | 0.00 |

## Strict Ranking Metrics

### File Level

| Baseline | N | Acc@1 | Acc@3 | Acc@5 | Acc@10 | Acc@15 | MRR@15 | MAP@15 | Empty |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 102 | 9.80 | 13.73 | 15.69 | 17.65 | 18.63 | 30.78 | 18.83 | 4.90 |
| CoSIL | 102 | 10.78 | 15.69 | 18.63 | 18.63 | 18.63 | 37.01 | 22.27 | 0.00 |
| GraphLocator | 102 | 5.88 | 6.86 | 6.86 | 6.86 | 6.86 | 23.56 | 11.53 | 0.00 |
| GALA | 102 | 10.78 | 19.61 | 25.49 | 25.49 | 25.49 | 47.40 | 30.00 | 0.00 |
| BM25-MMIR | 102 | 6.86 | 12.75 | 17.65 | 27.45 | 31.37 | 36.07 | 21.89 | 0.00 |

### Module Level

| Baseline | N | Acc@1 | Acc@3 | Acc@5 | Acc@10 | Acc@15 | MRR@15 | MAP@15 | Empty |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 102 | 3.92 | 8.82 | 12.75 | 17.65 | 19.61 | 16.21 | 11.70 | 4.90 |
| CoSIL | 102 | 8.82 | 14.71 | 15.69 | 15.69 | 15.69 | 27.45 | 18.35 | 1.96 |
| GraphLocator | 102 | 4.90 | 8.82 | 8.82 | 8.82 | 8.82 | 18.46 | 11.60 | 10.78 |
| GALA | 102 | 3.92 | 8.82 | 10.78 | 11.76 | 11.76 | 14.98 | 10.88 | 0.98 |
| BM25-MMIR | 102 | 4.90 | 16.67 | 18.63 | 26.47 | 36.27 | 25.16 | 19.03 | 0.00 |

### Function Level

| Baseline | N | Acc@1 | Acc@3 | Acc@5 | Acc@10 | Acc@15 | MRR@15 | MAP@15 | Empty |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 102 | 0.00 | 4.90 | 5.88 | 6.86 | 6.86 | 7.30 | 4.17 | 4.90 |
| CoSIL | 102 | 2.94 | 2.94 | 3.92 | 4.90 | 4.90 | 8.90 | 5.06 | 1.96 |
| GraphLocator | 102 | 1.96 | 3.92 | 3.92 | 3.92 | 3.92 | 8.66 | 5.06 | 11.76 |
| GALA | 102 | 2.94 | 4.90 | 5.88 | 6.86 | 7.84 | 7.74 | 5.57 | 10.78 |
| BM25-MMIR | 102 | 2.94 | 5.88 | 8.82 | 10.78 | 11.76 | 18.88 | 10.51 | 0.00 |

## Set Metrics @All

### Relaxed

| Baseline | File SL | File REC | File PRE | File F1 | Module SL | Module REC | Module PRE | Module F1 | Function SL | Function REC | Function PRE | Function F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 18.63 | 24.94 | 15.87 | 14.30 | 23.53 | 29.79 | 7.39 | 9.75 | 7.84 | 13.93 | 2.58 | 3.49 |
| CoSIL | 18.63 | 27.59 | 17.34 | 18.59 | 15.69 | 22.21 | 18.33 | 17.51 | 4.90 | 8.71 | 3.00 | 3.45 |
| GraphLocator | 6.86 | 14.25 | 19.18 | 13.24 | 8.82 | 15.19 | 14.03 | 13.21 | 3.92 | 8.18 | 3.03 | 3.79 |
| GALA | 25.49 | 39.55 | 21.24 | 23.99 | 11.76 | 17.15 | 8.63 | 10.11 | 7.84 | 9.75 | 3.39 | 3.97 |
| BM25-MMIR | 31.37 | 45.69 | 7.39 | 11.38 | 36.27 | 44.36 | 5.69 | 9.57 | 11.76 | 20.07 | 3.99 | 5.70 |

### Strict

| Baseline | File SL | File REC | File PRE | File F1 | Module SL | Module REC | Module PRE | Module F1 | Function SL | Function REC | Function PRE | Function F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 18.63 | 24.94 | 15.87 | 14.30 | 23.53 | 29.79 | 7.39 | 9.75 | 7.84 | 13.93 | 2.58 | 3.49 |
| CoSIL | 18.63 | 27.59 | 17.34 | 18.59 | 15.69 | 22.21 | 18.33 | 17.51 | 4.90 | 8.71 | 3.00 | 3.45 |
| GraphLocator | 6.86 | 14.25 | 19.18 | 13.24 | 8.82 | 15.19 | 14.03 | 13.21 | 3.92 | 8.18 | 3.03 | 3.79 |
| GALA | 25.49 | 39.55 | 21.24 | 23.99 | 11.76 | 17.15 | 8.63 | 10.11 | 7.84 | 9.75 | 3.39 | 3.97 |
| BM25-MMIR | 31.37 | 45.69 | 7.39 | 11.38 | 36.27 | 44.36 | 5.69 | 9.57 | 11.76 | 20.07 | 3.99 | 5.70 |

The Set Metrics tables are identical under relaxed and strict files because `SL/REC/PRE/F1` are computed from the evaluated prediction sets directly; the strict/relaxed distinction mainly changes Acc@K.

## Main Observations

1. File-level ranking is strongest for GALA and BM25-MMIR. GALA has the best relaxed File Acc@1, MRR@15, and MAP@15, while BM25-MMIR reaches the highest File Acc@15 under both relaxed and strict standards.
2. BM25-MMIR dominates module/function recall-oriented ranking at larger K. It has the highest relaxed and strict Module Acc@15 and Function Acc@15, but its precision is low in set metrics because it returns broader candidate sets.
3. GALA gives the strongest file-level set F1 among the LLM baselines. Its File F1@All is 23.99, higher than LocAgent, CoSIL, and GraphLocator.
4. CoSIL is competitive at file/module level, especially File MRR@15 and Module F1@All. It also produced no empty file-level predictions in this full-dev run.
5. LocAgent has moderate file-level performance but lower function-level strict accuracy. It still has useful module-level strict SL@All at 23.53.
6. GraphLocator trails on this full-dev setting and has the highest function-level empty rate among the LLM baselines.

## Interpretation

The full-dev result reinforces the pattern seen in the 60-sample experiments:

- Visual/code graph alignment helps GALA at file-level ranking and file-level set quality.
- Sparse lexical retrieval remains a very strong high-K recall baseline, especially when the benchmark gold patches span multiple files/modules/functions.
- Function-level localization is still the hardest layer. Even the best strict Function Acc@15 here is 11.76, which suggests that future reranking needs mechanism-level evidence, not only visual or lexical anchors.
- Strict Acc@K is much lower than relaxed Acc@K because many SWE-bench Multimodal issues modify multiple gold locations. Full-coverage success is therefore a more demanding and more realistic metric for patch-oriented localization.

## Source Metric Files

| Baseline | Relaxed Metrics | Strict Metrics |
|---|---|---|
| LocAgent | `LocAgent/newtest/swebench_multimodal-full-dev/results/openai_qwen3-vl-8b/eval/metrics_3level.md` | `LocAgent/newtest/swebench_multimodal-full-dev/results/openai_qwen3-vl-8b/eval_strict/metrics_3level.md` |
| CoSIL | `CoSIL/newtest/swebench_multimodal-full-dev/results/openai_qwen3-vl-8b/eval/metrics_3level.md` | `CoSIL/newtest/swebench_multimodal-full-dev/results/openai_qwen3-vl-8b/eval_strict/metrics_3level.md` |
| GraphLocator | `GraphLocator/newtest/swebench_multimodal-full-dev/results/openai_qwen3-vl-8b/eval/metrics_3level.md` | `GraphLocator/newtest/swebench_multimodal-full-dev/results/openai_qwen3-vl-8b/eval_strict/metrics_3level.md` |
| GALA | `GALA/mytest/swebench_multimodal-full-dev/results/qwen3-vl-8b/eval/metrics_3level.md` | `GALA/mytest/swebench_multimodal-full-dev/results/qwen3-vl-8b/eval_strict/metrics_3level.md` |
| BM25-MMIR | `MM-IR/results/swebench_multimodal-full-candidates/bm25-mmir/eval/metrics_3level.md` | `MM-IR/results/swebench_multimodal-full-candidates/bm25-mmir/eval_strict/metrics_3level.md` |
