# 60 样本 Baseline 结果汇总

生成时间：2026-07-08。

本文档只汇总 60 样本实验结果，独立于 full-candidates 结果。数值重新读取自各 baseline 的 `eval/metrics_3level.md` 与 `eval_strict/metrics_3level.md`。

## 统计口径说明

- `SWE-bench Multimodal 60`：5 个 baseline 均评估 60 条样本。
- `OmniGIRL unified60`：统一 60 样本口径，5 个 baseline 均评估 60 条样本，推荐作为 OmniGIRL 60 横向比较主表。
- `OmniGIRL 60 legacy/non-unified`：历史口径，LocAgent / GraphLocator / BM25-MMIR 为 48 条，CoSIL 为 60 条，GALA JS/TS 为 17 条；只适合保留记录，不宜和 unified60 混用。

排序指标分为两个版本：

- 宽松 `Acc@K`：top-K 中命中任意一个 gold location 即算成功。
- 严格 `Acc@K`：top-K 必须覆盖该层级所有 gold locations 才算成功，和 LocAgent-style full-coverage 口径一致。
- `MRR@15`、`MAP@15`、`Empty` 在宽松和严格评估文件中含义保持一致。
- 集合指标采用 `eval/metrics_3level.md` 的完整预测集合 `Set Metrics @All`。

## 汇总范围

| 数据集 | 方法 | 说明 |
|---|---|---|
| SWE-bench Multimodal 60 | LocAgent / CoSIL / GALA / GraphLocator / BM25-MMIR | 统一 60 样本 |
| OmniGIRL unified60 | LocAgent / CoSIL / GALA / GraphLocator / BM25-MMIR | 统一 60 样本 |
| OmniGIRL 60 legacy/non-unified | LocAgent / CoSIL / GALA JS/TS / GraphLocator / BM25-MMIR | 历史非统一评估样本数 |

## SWE-bench Multimodal 60

### 宽松排序指标（hit-any Acc@K）

| 方法 | 评估样本数 | File Acc@1 | File Acc@3 | File Acc@5 | File Acc@8 | File Acc@10 | File Acc@15 | Module Acc@1 | Module Acc@3 | Module Acc@5 | Module Acc@8 | Module Acc@10 | Module Acc@15 | Function Acc@1 | Function Acc@3 | Function Acc@5 | Function Acc@8 | Function Acc@10 | Function Acc@15 | File MRR@15 | Module MRR@15 | Function MRR@15 | File MAP@15 | Module MAP@15 | Function MAP@15 | 空预测率 File/Module/Function |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 60 | 35.00 | 51.67 | 55.00 | 58.33 | 60.00 | 61.67 | 18.33 | 30.00 | 35.00 | 41.67 | 43.33 | 48.33 | 10.00 | 18.33 | 20.00 | 25.00 | 25.00 | 28.33 | 44.40 | 25.21 | 14.98 | 27.04 | 18.65 | 10.30 | 3.33 / 3.33 / 3.33 |
| CoSIL | 60 | 26.67 | 45.00 | 50.00 | 50.00 | 50.00 | 50.00 | 21.67 | 30.00 | 36.67 | 38.33 | 38.33 | 38.33 | 3.33 | 8.33 | 11.67 | 15.00 | 18.33 | 23.33 | 35.33 | 27.29 | 7.52 | 17.07 | 13.38 | 4.44 | 3.33 / 10.00 / 10.00 |
| GALA | 60 | 35.00 | 60.00 | 61.67 | 61.67 | 61.67 | 61.67 | 8.33 | 16.67 | 21.67 | 21.67 | 21.67 | 21.67 | 3.33 | 8.33 | 10.00 | 10.00 | 11.67 | 13.33 | 46.81 | 13.39 | 6.19 | 25.73 | 9.46 | 5.14 | 0.00 / 0.00 / 13.33 |
| GraphLocator | 60 | 21.67 | 26.67 | 28.33 | 28.33 | 28.33 | 30.00 | 10.00 | 20.00 | 21.67 | 21.67 | 21.67 | 21.67 | 6.67 | 11.67 | 11.67 | 13.33 | 13.33 | 13.33 | 24.18 | 14.86 | 9.40 | 10.97 | 9.18 | 4.62 | 0.00 / 10.00 / 10.00 |
| BM25-MMIR | 60 | 25.00 | 43.33 | 48.33 | 58.33 | 60.00 | 66.67 | 15.00 | 33.33 | 40.00 | 51.67 | 60.00 | 65.00 | 11.67 | 20.00 | 28.33 | 36.67 | 38.33 | 43.33 | 36.36 | 27.96 | 19.41 | 22.30 | 21.20 | 11.15 | 0.00 / 0.00 / 0.00 |

### 严格排序指标（full-coverage Acc@K）

| 方法 | 评估样本数 | File Acc@1 | File Acc@3 | File Acc@5 | File Acc@8 | File Acc@10 | File Acc@15 | Module Acc@1 | Module Acc@3 | Module Acc@5 | Module Acc@8 | Module Acc@10 | Module Acc@15 | Function Acc@1 | Function Acc@3 | Function Acc@5 | Function Acc@8 | Function Acc@10 | Function Acc@15 | File MRR@15 | Module MRR@15 | Function MRR@15 | File MAP@15 | Module MAP@15 | Function MAP@15 | 空预测率 File/Module/Function |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 60 | 16.67 | 18.33 | 21.67 | 21.67 | 21.67 | 21.67 | 10.00 | 16.67 | 18.33 | 25.00 | 28.33 | 28.33 | 3.33 | 10.00 | 11.67 | 11.67 | 13.33 | 13.33 | 43.62 | 25.33 | 14.97 | 27.20 | 19.01 | 9.83 | 3.33 / 3.33 / 3.33 |
| CoSIL | 60 | 6.67 | 11.67 | 13.33 | 13.33 | 13.33 | 13.33 | 1.67 | 5.00 | 6.67 | 6.67 | 6.67 | 6.67 | 1.67 | 1.67 | 1.67 | 5.00 | 6.67 | 6.67 | 35.33 | 27.29 | 7.52 | 17.07 | 13.38 | 4.44 | 3.33 / 10.00 / 10.00 |
| GALA | 60 | 6.67 | 16.67 | 20.00 | 20.00 | 20.00 | 20.00 | 3.33 | 6.67 | 8.33 | 8.33 | 8.33 | 8.33 | 3.33 | 5.00 | 5.00 | 5.00 | 6.67 | 6.67 | 46.81 | 9.64 | 5.02 | 25.73 | 7.53 | 4.53 | 0.00 / 41.67 / 45.00 |
| GraphLocator | 60 | 6.67 | 6.67 | 6.67 | 6.67 | 6.67 | 8.33 | 3.33 | 8.33 | 10.00 | 10.00 | 10.00 | 10.00 | 1.67 | 3.33 | 3.33 | 3.33 | 3.33 | 3.33 | 24.18 | 14.86 | 9.40 | 10.97 | 9.18 | 4.62 | 0.00 / 10.00 / 10.00 |
| BM25-MMIR | 60 | 6.67 | 13.33 | 18.33 | 23.33 | 26.67 | 30.00 | 6.67 | 18.33 | 20.00 | 26.67 | 31.67 | 43.33 | 3.33 | 6.67 | 11.67 | 15.00 | 15.00 | 15.00 | 36.36 | 27.96 | 19.41 | 22.30 | 21.20 | 11.15 | 0.00 / 0.00 / 0.00 |

### 集合指标（Set Metrics @All）

| 方法 | File SL | File REC | File PRE | File F1 | Module SL | Module REC | Module PRE | Module F1 | Function SL | Function REC | Function PRE | Function F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 23.33 | 35.93 | 12.76 | 13.25 | 31.67 | 41.62 | 8.36 | 10.60 | 13.33 | 22.29 | 2.90 | 4.02 |
| CoSIL | 13.33 | 24.44 | 15.47 | 15.42 | 6.67 | 18.04 | 16.71 | 14.92 | 6.67 | 12.15 | 2.85 | 3.87 |
| GALA | 20.00 | 35.19 | 18.28 | 20.37 | 10.00 | 15.14 | 7.68 | 9.40 | 6.67 | 9.50 | 3.77 | 4.84 |
| GraphLocator | 8.33 | 13.75 | 20.08 | 13.62 | 10.00 | 13.47 | 12.14 | 11.45 | 3.33 | 6.62 | 5.13 | 4.89 |
| BM25-MMIR | 30.00 | 46.02 | 8.78 | 12.97 | 43.33 | 51.19 | 6.92 | 11.36 | 15.00 | 22.72 | 4.62 | 6.26 |

## OmniGIRL unified60

### 宽松排序指标（hit-any Acc@K）

| 方法 | 评估样本数 | File Acc@1 | File Acc@3 | File Acc@5 | File Acc@8 | File Acc@10 | File Acc@15 | Module Acc@1 | Module Acc@3 | Module Acc@5 | Module Acc@8 | Module Acc@10 | Module Acc@15 | Function Acc@1 | Function Acc@3 | Function Acc@5 | Function Acc@8 | Function Acc@10 | Function Acc@15 | File MRR@15 | Module MRR@15 | Function MRR@15 | File MAP@15 | Module MAP@15 | Function MAP@15 | 空预测率 File/Module/Function |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 60 | 25.00 | 35.00 | 40.00 | 48.33 | 48.33 | 48.33 | 15.00 | 26.67 | 35.00 | 38.33 | 40.00 | 40.00 | 5.00 | 11.67 | 15.00 | 16.67 | 18.33 | 18.33 | 32.06 | 23.15 | 8.62 | 31.18 | 21.74 | 6.68 | 0.00 / 0.00 / 0.00 |
| CoSIL | 60 | 31.67 | 38.33 | 40.00 | 40.00 | 40.00 | 40.00 | 10.00 | 26.67 | 28.33 | 33.33 | 33.33 | 33.33 | 0.00 | 1.67 | 3.33 | 5.00 | 5.00 | 5.00 | 35.14 | 18.07 | 1.21 | 34.40 | 16.99 | 0.85 | 5.00 / 6.67 / 6.67 |
| GALA | 60 | 6.67 | 18.33 | 23.33 | 23.33 | 23.33 | 23.33 | 1.67 | 5.00 | 6.67 | 6.67 | 6.67 | 6.67 | 0.00 | 0.00 | 1.67 | 5.00 | 5.00 | 5.00 | 12.83 | 3.47 | 0.75 | 12.28 | 3.47 | 0.83 | 43.33 / 48.33 / 48.33 |
| GraphLocator | 60 | 18.33 | 26.67 | 30.00 | 31.67 | 31.67 | 33.33 | 6.67 | 11.67 | 11.67 | 11.67 | 11.67 | 11.67 | 6.67 | 11.67 | 11.67 | 11.67 | 11.67 | 11.67 | 23.36 | 9.17 | 8.89 | 22.81 | 9.17 | 7.78 | 0.00 / 20.00 / 20.00 |
| BM25-MMIR | 60 | 10.00 | 23.33 | 33.33 | 46.67 | 46.67 | 48.33 | 6.67 | 13.33 | 21.67 | 23.33 | 23.33 | 26.67 | 8.33 | 15.00 | 16.67 | 18.33 | 21.67 | 23.33 | 20.09 | 12.57 | 12.16 | 19.14 | 11.87 | 11.35 | 0.00 / 0.00 / 0.00 |

### 严格排序指标（full-coverage Acc@K）

| 方法 | 评估样本数 | File Acc@1 | File Acc@3 | File Acc@5 | File Acc@8 | File Acc@10 | File Acc@15 | Module Acc@1 | Module Acc@3 | Module Acc@5 | Module Acc@8 | Module Acc@10 | Module Acc@15 | Function Acc@1 | Function Acc@3 | Function Acc@5 | Function Acc@8 | Function Acc@10 | Function Acc@15 | File MRR@15 | Module MRR@15 | Function MRR@15 | File MAP@15 | Module MAP@15 | Function MAP@15 | 空预测率 File/Module/Function |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 60 | 23.33 | 31.67 | 36.67 | 46.67 | 46.67 | 46.67 | 15.00 | 23.33 | 26.67 | 26.67 | 28.33 | 31.67 | 1.67 | 5.00 | 10.00 | 10.00 | 11.67 | 11.67 | 32.06 | 23.15 | 8.62 | 31.18 | 21.74 | 6.68 | 0.00 / 0.00 / 0.00 |
| CoSIL | 60 | 30.00 | 36.67 | 38.33 | 38.33 | 38.33 | 38.33 | 5.00 | 16.67 | 23.33 | 31.67 | 31.67 | 31.67 | 0.00 | 1.67 | 1.67 | 1.67 | 1.67 | 1.67 | 35.14 | 18.07 | 1.21 | 34.40 | 16.99 | 0.85 | 5.00 / 6.67 / 6.67 |
| GALA | 60 | 6.67 | 16.67 | 20.00 | 20.00 | 20.00 | 20.00 | 1.67 | 5.00 | 6.67 | 6.67 | 6.67 | 6.67 | 0.00 | 0.00 | 1.67 | 3.33 | 5.00 | 5.00 | 12.83 | 3.47 | 0.75 | 12.28 | 3.47 | 0.83 | 43.33 / 48.33 / 48.33 |
| GraphLocator | 60 | 16.67 | 25.00 | 28.33 | 30.00 | 30.00 | 31.67 | 6.67 | 11.67 | 11.67 | 11.67 | 11.67 | 11.67 | 1.67 | 10.00 | 10.00 | 10.00 | 10.00 | 10.00 | 23.36 | 9.17 | 8.89 | 22.81 | 9.17 | 7.78 | 0.00 / 20.00 / 20.00 |
| BM25-MMIR | 60 | 8.33 | 20.00 | 30.00 | 40.00 | 41.67 | 43.33 | 6.67 | 11.67 | 18.33 | 18.33 | 18.33 | 21.67 | 5.00 | 10.00 | 11.67 | 16.67 | 20.00 | 21.67 | 20.09 | 12.57 | 12.16 | 19.14 | 11.87 | 11.35 | 0.00 / 0.00 / 0.00 |

### 集合指标（Set Metrics @All）

| 方法 | File SL | File REC | File PRE | File F1 | Module SL | Module REC | Module PRE | Module F1 | Function SL | Function REC | Function PRE | Function F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 46.67 | 47.78 | 4.91 | 8.71 | 40.00 | 41.67 | 3.53 | 5.86 | 18.33 | 22.04 | 0.82 | 1.53 |
| CoSIL | 38.33 | 39.44 | 11.36 | 16.72 | 31.67 | 32.38 | 10.47 | 14.84 | 1.67 | 3.06 | 0.78 | 1.07 |
| GALA | 20.00 | 21.39 | 4.75 | 7.67 | 6.67 | 6.67 | 1.72 | 2.72 | 5.00 | 5.00 | 0.47 | 0.86 |
| GraphLocator | 31.67 | 32.78 | 17.76 | 20.45 | 11.67 | 11.67 | 5.83 | 7.42 | 10.00 | 10.83 | 1.48 | 2.55 |
| BM25-MMIR | 43.33 | 45.56 | 3.44 | 6.34 | 21.67 | 24.17 | 2.24 | 3.80 | 21.67 | 22.22 | 2.62 | 4.44 |

## OmniGIRL 60 legacy/non-unified

这一组是历史结果，评估样本数不统一；保留用于复核旧表，不建议和 `OmniGIRL unified60` 直接横向比较。

### 宽松排序指标（hit-any Acc@K）

| 方法 | 评估样本数 | File Acc@1 | File Acc@3 | File Acc@5 | File Acc@8 | File Acc@10 | File Acc@15 | Module Acc@1 | Module Acc@3 | Module Acc@5 | Module Acc@8 | Module Acc@10 | Module Acc@15 | Function Acc@1 | Function Acc@3 | Function Acc@5 | Function Acc@8 | Function Acc@10 | Function Acc@15 | File MRR@15 | Module MRR@15 | Function MRR@15 | File MAP@15 | Module MAP@15 | Function MAP@15 | 空预测率 File/Module/Function |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 48 | 20.83 | 35.42 | 39.58 | 45.83 | 47.92 | 47.92 | 10.42 | 22.92 | 29.17 | 35.42 | 37.50 | 43.75 | 2.08 | 6.25 | 8.33 | 8.33 | 12.50 | 14.58 | 28.77 | 19.10 | 4.83 | 28.41 | 17.83 | 3.41 | 0.00 / 0.00 / 0.00 |
| CoSIL | 60 | 28.33 | 38.33 | 40.00 | 40.00 | 40.00 | 40.00 | 13.33 | 23.33 | 23.33 | 30.00 | 30.00 | 30.00 | 0.00 | 0.00 | 1.67 | 5.00 | 5.00 | 5.00 | 33.47 | 18.25 | 0.93 | 32.73 | 16.68 | 0.57 | 6.67 / 8.33 / 8.33 |
| GALA JS/TS | 17 | 23.53 | 47.06 | 52.94 | 52.94 | 52.94 | 52.94 | 0.00 | 17.65 | 17.65 | 17.65 | 17.65 | 17.65 | 0.00 | 0.00 | 5.88 | 5.88 | 5.88 | 5.88 | 33.82 | 7.84 | 1.47 | 31.05 | 7.84 | 1.47 | 0.00 / 0.00 / 0.00 |
| GraphLocator | 48 | 12.50 | 16.67 | 18.75 | 22.92 | 22.92 | 25.00 | 6.25 | 8.33 | 8.33 | 8.33 | 8.33 | 8.33 | 4.17 | 6.25 | 8.33 | 8.33 | 8.33 | 8.33 | 15.83 | 7.29 | 5.73 | 15.49 | 7.29 | 4.69 | 0.00 / 22.92 / 25.00 |
| BM25-MMIR | 48 | 6.25 | 16.67 | 25.00 | 35.42 | 41.67 | 47.92 | 2.08 | 8.33 | 14.58 | 16.67 | 18.75 | 25.00 | 6.25 | 12.50 | 12.50 | 16.67 | 18.75 | 20.83 | 15.28 | 7.32 | 9.95 | 13.89 | 6.27 | 8.76 | 0.00 / 0.00 / 0.00 |

### 严格排序指标（full-coverage Acc@K）

| 方法 | 评估样本数 | File Acc@1 | File Acc@3 | File Acc@5 | File Acc@8 | File Acc@10 | File Acc@15 | Module Acc@1 | Module Acc@3 | Module Acc@5 | Module Acc@8 | Module Acc@10 | Module Acc@15 | Function Acc@1 | Function Acc@3 | Function Acc@5 | Function Acc@8 | Function Acc@10 | Function Acc@15 | File MRR@15 | Module MRR@15 | Function MRR@15 | File MAP@15 | Module MAP@15 | Function MAP@15 | 空预测率 File/Module/Function |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 48 | 14.58 | 31.25 | 35.42 | 41.67 | 45.83 | 50.00 | 10.42 | 22.92 | 22.92 | 27.08 | 29.17 | 29.17 | 0.00 | 4.17 | 4.17 | 4.17 | 6.25 | 6.25 | 27.75 | 20.02 | 2.56 | 26.41 | 18.58 | 2.09 | 0.00 / 0.00 / 0.00 |
| CoSIL | 60 | 26.67 | 36.67 | 38.33 | 38.33 | 38.33 | 38.33 | 6.67 | 15.00 | 18.33 | 28.33 | 28.33 | 28.33 | 0.00 | 0.00 | 0.00 | 1.67 | 1.67 | 1.67 | 33.47 | 18.25 | 0.93 | 32.73 | 16.68 | 0.57 | 6.67 / 8.33 / 8.33 |
| GALA JS/TS | 17 | 23.53 | 35.29 | 41.18 | 41.18 | 41.18 | 41.18 | 0.00 | 17.65 | 17.65 | 17.65 | 17.65 | 17.65 | 0.00 | 0.00 | 5.88 | 5.88 | 5.88 | 5.88 | 33.82 | 7.84 | 1.47 | 31.05 | 7.84 | 1.47 | 0.00 / 0.00 / 0.00 |
| GraphLocator | 48 | 12.50 | 14.58 | 16.67 | 20.83 | 20.83 | 22.92 | 6.25 | 8.33 | 8.33 | 8.33 | 8.33 | 8.33 | 0.00 | 4.17 | 6.25 | 6.25 | 6.25 | 6.25 | 15.83 | 7.29 | 5.73 | 15.49 | 7.29 | 4.69 | 0.00 / 22.92 / 25.00 |
| BM25-MMIR | 48 | 4.17 | 12.50 | 20.83 | 29.17 | 35.42 | 41.67 | 2.08 | 4.17 | 8.33 | 10.42 | 12.50 | 18.75 | 4.17 | 6.25 | 6.25 | 14.58 | 16.67 | 16.67 | 15.28 | 7.32 | 9.95 | 13.89 | 6.27 | 8.76 | 0.00 / 0.00 / 0.00 |

### 集合指标（Set Metrics @All）

| 方法 | File SL | File REC | File PRE | File F1 | Module SL | Module REC | Module PRE | Module F1 | Function SL | Function REC | Function PRE | Function F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 52.08 | 52.08 | 5.14 | 9.19 | 41.67 | 43.96 | 3.25 | 5.74 | 14.58 | 18.06 | 0.78 | 1.44 |
| CoSIL | 38.33 | 39.44 | 11.14 | 16.44 | 28.33 | 29.05 | 8.85 | 12.53 | 1.67 | 3.06 | 0.74 | 1.02 |
| GALA JS/TS | 41.18 | 46.08 | 11.37 | 17.86 | 17.65 | 17.65 | 4.61 | 7.25 | 5.88 | 5.88 | 0.53 | 0.98 |
| GraphLocator | 22.92 | 24.31 | 13.09 | 14.31 | 8.33 | 8.33 | 6.25 | 6.94 | 6.25 | 7.29 | 1.15 | 1.94 |
| BM25-MMIR | 41.67 | 44.44 | 3.47 | 6.36 | 18.75 | 21.88 | 2.25 | 3.72 | 16.67 | 18.06 | 2.48 | 4.07 |

## 结果文件索引

| 方法 | 数据集 | 宽松指标 | 严格指标 |
|---|---|---|---|
| LocAgent | SWE-bench Multimodal 60 | `LocAgent/newtest/swebench_multimodal-60/results/openai_qwen3-vl-8b/eval/metrics_3level.md` | `LocAgent/newtest/swebench_multimodal-60/results/openai_qwen3-vl-8b/eval_strict/metrics_3level.md` |
| CoSIL | SWE-bench Multimodal 60 | `CoSIL/newtest/swebench_multimodal-60/results/openai_qwen3-vl-8b/eval/metrics_3level.md` | `CoSIL/newtest/swebench_multimodal-60/results/openai_qwen3-vl-8b/eval_strict/metrics_3level.md` |
| GALA | SWE-bench Multimodal 60 | `GALA/mytest/swebench-multimodal-60/results/qwen3-vl-8b/eval/metrics_3level.md` | `GALA/mytest/swebench-multimodal-60/results/qwen3-vl-8b/eval_strict/metrics_3level.md` |
| GraphLocator | SWE-bench Multimodal 60 | `GraphLocator/newtest/swebench_multimodal-60/results/openai_qwen3-vl-8b/eval/metrics_3level.md` | `GraphLocator/newtest/swebench_multimodal-60/results/openai_qwen3-vl-8b/eval_strict/metrics_3level.md` |
| BM25-MMIR | SWE-bench Multimodal 60 | `MM-IR/results/swebench_multimodal-60/bm25-mmir/eval/metrics_3level.md` | `MM-IR/results/swebench_multimodal-60/bm25-mmir/eval_strict/metrics_3level.md` |
| LocAgent | OmniGIRL unified60 | `LocAgent/newtest/omnigirl-unified60/results/openai_qwen3-vl-8b/eval/metrics_3level.md` | `LocAgent/newtest/omnigirl-unified60/results/openai_qwen3-vl-8b/eval_strict/metrics_3level.md` |
| CoSIL | OmniGIRL unified60 | `CoSIL/newtest/omnigirl-unified60/results/openai_qwen3-vl-8b/eval/metrics_3level.md` | `CoSIL/newtest/omnigirl-unified60/results/openai_qwen3-vl-8b/eval_strict/metrics_3level.md` |
| GALA | OmniGIRL unified60 | `GALA/mytest/omnigirl-unified60/results/qwen3-vl-8b/eval/metrics_3level.md` | `GALA/mytest/omnigirl-unified60/results/qwen3-vl-8b/eval_strict/metrics_3level.md` |
| GraphLocator | OmniGIRL unified60 | `GraphLocator/newtest/omnigirl-unified60/results/openai_qwen3-vl-8b/eval/metrics_3level.md` | `GraphLocator/newtest/omnigirl-unified60/results/openai_qwen3-vl-8b/eval_strict/metrics_3level.md` |
| BM25-MMIR | OmniGIRL unified60 | `MM-IR/results/omnigirl-unified60/bm25-mmir/eval/metrics_3level.md` | `MM-IR/results/omnigirl-unified60/bm25-mmir/eval_strict/metrics_3level.md` |
| LocAgent | OmniGIRL 60 legacy/non-unified | `LocAgent/newtest/omnigirl-60/results/openai_qwen3-vl-8b/eval/metrics_3level.md` | `LocAgent/newtest/omnigirl-60/results/openai_qwen3-vl-8b/eval_strict/metrics_3level.md` |
| CoSIL | OmniGIRL 60 legacy/non-unified | `CoSIL/newtest/omnigirl-60/results/openai_qwen3-vl-8b/eval/metrics_3level.md` | `CoSIL/newtest/omnigirl-60/results/openai_qwen3-vl-8b/eval_strict/metrics_3level.md` |
| GALA JS/TS | OmniGIRL 60 legacy/non-unified | `GALA/mytest/omnigirl-js-ts-multimodal-60/results/qwen3-vl-8b/eval/metrics_3level.md` | `GALA/mytest/omnigirl-js-ts-multimodal-60/results/qwen3-vl-8b/eval_strict/metrics_3level.md` |
| GraphLocator | OmniGIRL 60 legacy/non-unified | `GraphLocator/newtest/omnigirl-60/results/openai_qwen3-vl-8b/eval/metrics_3level.md` | `GraphLocator/newtest/omnigirl-60/results/openai_qwen3-vl-8b/eval_strict/metrics_3level.md` |
| BM25-MMIR | OmniGIRL 60 legacy/non-unified | `MM-IR/results/omnigirl-60/bm25-mmir/eval/metrics_3level.md` | `MM-IR/results/omnigirl-60/bm25-mmir/eval_strict/metrics_3level.md` |
