# Strict 三层定位指标汇总

生成时间：2026-07-04。

本文件汇总新增的 `eval_strict/metrics_3level.*` 结果。这里的 `Acc@K` 已改为 LocAgent-style strict full-coverage 口径：只有 top-K 预测覆盖该层级所有 gold locations，才记为成功。

注意：`MRR@15` 和 `MAP@15` 保持原有排序指标含义，仍用于观察第一个命中和多 gold 排序质量；本次严格化只改变 `Acc@K` 的成功判定。

## 生成的严格评估脚本

| 项目 | strict 评估脚本 |
|---|---|
| LocAgent | `/home/like/locCode/LocAgent/newtest/scripts/eval_3level_localization_strict.py` |
| CoSIL | `/home/like/locCode/CoSIL/newtest/scripts/eval_3level_localization_strict.py` |
| GraphLocator | `/home/like/locCode/GraphLocator/newtest/scripts/eval_3level_localization_strict.py` |
| GALA | `/home/like/locCode/GALA/mytest/scripts/eval_gala_localization_strict.py` |
| MM-IR | `/home/like/locCode/MM-IR/mmir/evaluation/eval_3level_strict.py` |

## SWE-bench Multimodal 60

| 方法 | 评估样本数 | File Acc@1 | File Acc@3 | File Acc@5 | File Acc@8 | File Acc@10 | File Acc@15 | File MRR@15 | Module Acc@1 | Module Acc@3 | Module Acc@5 | Module Acc@8 | Module Acc@10 | Module Acc@15 | Module MRR@15 | Function Acc@1 | Function Acc@3 | Function Acc@5 | Function Acc@8 | Function Acc@10 | Function Acc@15 | Function MRR@15 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 60 | 16.67 | 18.33 | 21.67 | 21.67 | 21.67 | 21.67 | 43.62 | 10.00 | 16.67 | 18.33 | 25.00 | 28.33 | 28.33 | 25.33 | 3.33 | 10.00 | 11.67 | 11.67 | 13.33 | 13.33 | 14.97 |
| CoSIL | 60 | 6.67 | 11.67 | 13.33 | 13.33 | 13.33 | 13.33 | 35.33 | 1.67 | 5.00 | 6.67 | 6.67 | 6.67 | 6.67 | 27.29 | 1.67 | 1.67 | 1.67 | 5.00 | 6.67 | 6.67 | 7.52 |
| GALA | 60 | 6.67 | 16.67 | 20.00 | 20.00 | 20.00 | 20.00 | 46.81 | 3.33 | 6.67 | 8.33 | 8.33 | 8.33 | 8.33 | 9.64 | 3.33 | 5.00 | 5.00 | 5.00 | 6.67 | 6.67 | 5.02 |
| GraphLocator | 60 | 6.67 | 6.67 | 6.67 | 6.67 | 6.67 | 8.33 | 24.18 | 3.33 | 8.33 | 10.00 | 10.00 | 10.00 | 10.00 | 14.86 | 1.67 | 3.33 | 3.33 | 3.33 | 3.33 | 3.33 | 9.40 |
| BM25-MMIR | 60 | 6.67 | 13.33 | 18.33 | 23.33 | 26.67 | 30.00 | 36.36 | 6.67 | 18.33 | 20.00 | 26.67 | 31.67 | 43.33 | 27.96 | 3.33 | 6.67 | 11.67 | 15.00 | 15.00 | 15.00 | 19.41 |

## OmniGIRL 60

| 方法 | 评估样本数 | File Acc@1 | File Acc@3 | File Acc@5 | File Acc@8 | File Acc@10 | File Acc@15 | File MRR@15 | Module Acc@1 | Module Acc@3 | Module Acc@5 | Module Acc@8 | Module Acc@10 | Module Acc@15 | Module MRR@15 | Function Acc@1 | Function Acc@3 | Function Acc@5 | Function Acc@8 | Function Acc@10 | Function Acc@15 | Function MRR@15 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 48 | 14.58 | 31.25 | 35.42 | 41.67 | 45.83 | 50.00 | 27.75 | 10.42 | 22.92 | 22.92 | 27.08 | 29.17 | 29.17 | 20.02 | 0.00 | 4.17 | 4.17 | 4.17 | 6.25 | 6.25 | 2.56 |
| CoSIL | 60 | 26.67 | 36.67 | 38.33 | 38.33 | 38.33 | 38.33 | 33.47 | 6.67 | 15.00 | 18.33 | 28.33 | 28.33 | 28.33 | 18.25 | 0.00 | 0.00 | 0.00 | 1.67 | 1.67 | 1.67 | 0.93 |
| GALA JS/TS | 17 | 23.53 | 35.29 | 41.18 | 41.18 | 41.18 | 41.18 | 33.82 | 0.00 | 17.65 | 17.65 | 17.65 | 17.65 | 17.65 | 7.84 | 0.00 | 0.00 | 5.88 | 5.88 | 5.88 | 5.88 | 1.47 |
| GraphLocator | 48 | 12.50 | 14.58 | 16.67 | 20.83 | 20.83 | 22.92 | 15.83 | 6.25 | 8.33 | 8.33 | 8.33 | 8.33 | 8.33 | 7.29 | 0.00 | 4.17 | 6.25 | 6.25 | 6.25 | 6.25 | 5.73 |
| BM25-MMIR | 48 | 4.17 | 12.50 | 20.83 | 29.17 | 35.42 | 41.67 | 15.28 | 2.08 | 4.17 | 8.33 | 10.42 | 12.50 | 18.75 | 7.32 | 4.17 | 6.25 | 6.25 | 14.58 | 16.67 | 16.67 | 9.95 |

## Full candidates

| 方法 | 评估样本数 | File Acc@1 | File Acc@3 | File Acc@5 | File Acc@8 | File Acc@10 | File Acc@15 | File MRR@15 | Module Acc@1 | Module Acc@3 | Module Acc@5 | Module Acc@8 | Module Acc@10 | Module Acc@15 | Module MRR@15 | Function Acc@1 | Function Acc@3 | Function Acc@5 | Function Acc@8 | Function Acc@10 | Function Acc@15 | Function MRR@15 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| BM25-MMIR / SWE-bench Multimodal | 102 | 6.86 | 12.75 | 17.65 | 21.57 | 27.45 | 31.37 | 36.07 | 4.90 | 16.67 | 18.63 | 22.55 | 26.47 | 36.27 | 25.16 | 2.94 | 5.88 | 8.82 | 10.78 | 10.78 | 11.76 | 18.88 |
| BM25-MMIR / OmniGIRL | 631 | 6.66 | 15.85 | 21.08 | 26.15 | 29.48 | 34.07 | 23.83 | 1.43 | 5.55 | 8.56 | 11.73 | 13.63 | 20.76 | 14.62 | 1.58 | 3.49 | 4.75 | 6.34 | 7.92 | 9.51 | 11.10 |

## 结果文件索引

| 数据集 | 方法 | strict 指标文件 |
|---|---|---|
| SWE-bench Multimodal 60 | LocAgent | `/home/like/locCode/LocAgent/newtest/swebench_multimodal-60/results/openai_qwen3-vl-8b/eval_strict/metrics_3level.json` |
| SWE-bench Multimodal 60 | CoSIL | `/home/like/locCode/CoSIL/newtest/swebench_multimodal-60/results/openai_qwen3-vl-8b/eval_strict/metrics_3level.json` |
| SWE-bench Multimodal 60 | GALA | `/home/like/locCode/GALA/mytest/swebench-multimodal-60/results/qwen3-vl-8b/eval_strict/metrics_3level.json` |
| SWE-bench Multimodal 60 | GraphLocator | `/home/like/locCode/GraphLocator/newtest/swebench_multimodal-60/results/openai_qwen3-vl-8b/eval_strict/metrics_3level.json` |
| SWE-bench Multimodal 60 | BM25-MMIR | `/home/like/locCode/MM-IR/results/swebench_multimodal-60/bm25-mmir/eval_strict/metrics_3level.json` |
| OmniGIRL 60 | LocAgent | `/home/like/locCode/LocAgent/newtest/omnigirl-60/results/openai_qwen3-vl-8b/eval_strict/metrics_3level.json` |
| OmniGIRL 60 | CoSIL | `/home/like/locCode/CoSIL/newtest/omnigirl-60/results/openai_qwen3-vl-8b/eval_strict/metrics_3level.json` |
| OmniGIRL 60 | GALA JS/TS | `/home/like/locCode/GALA/mytest/omnigirl-js-ts-multimodal-60/results/qwen3-vl-8b/eval_strict/metrics_3level.json` |
| OmniGIRL 60 | GraphLocator | `/home/like/locCode/GraphLocator/newtest/omnigirl-60/results/openai_qwen3-vl-8b/eval_strict/metrics_3level.json` |
| OmniGIRL 60 | BM25-MMIR | `/home/like/locCode/MM-IR/results/omnigirl-60/bm25-mmir/eval_strict/metrics_3level.json` |
| Full candidates | BM25-MMIR / SWE-bench Multimodal | `/home/like/locCode/MM-IR/results/swebench_multimodal-full-candidates/bm25-mmir/eval_strict/metrics_3level.json` |
| Full candidates | BM25-MMIR / OmniGIRL | `/home/like/locCode/MM-IR/results/omnigirl-full-candidates/bm25-mmir/eval_strict/metrics_3level.json` |

## 主要观察

1. 严格 Acc@K 明显低于原来的 hit-any Acc@K，这是预期结果；多文件、多函数 gold 的样本必须全部覆盖才算成功。
2. 在 SWE-bench Multimodal 60 上，BM25-MMIR 的严格 File/Module/Function Acc@15 分别为 30.00 / 43.33 / 15.00，说明强检索在严格函数覆盖下也会大幅下降。
3. LocAgent 在 SWE-bench Multimodal 60 上严格 File/Module/Function Acc@15 分别为 21.67 / 28.33 / 13.33，和 `SL@15` 对齐。
4. GALA 的严格文件级 Acc@15 与文件级 `SL@15` 对齐，说明此前 hit-any 文件指标高估了多文件 patch 的完整覆盖能力。
5. OmniGIRL 的严格函数级指标整体更低，进一步说明多语言样本中 exact function 覆盖是当前所有 baseline 的弱点。
