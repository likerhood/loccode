# SWE-bench Multimodal 全量 Clean15 下 Mimo-v2.5 与 BM25 基线结果汇总

生成时间：2026-07-12。

本文档汇总 `SWE-bench Multimodal full-dev` 在 `clean15` 口径下的三层定位结果。这里的 `clean15` 指：保留三层 gold 数量均不超过 15 的样本，用于避免 `Acc@15` 在理论上无法覆盖 gold 的样本直接参与排序指标比较。

## 统计口径

- 原始样本数：102
- Clean15 保留样本数：92
- Clean15 剔除样本数：10
- 评估层级：File / Module / Function
- LLM 模型：`mimo-v2.5`
- 检索基线：`bm25-mmir`

参与本表的结果：

| 方法 | 结果来源 | 说明 |
|---|---|---|
| LocAgent | `unpacked_results/.../LocAgent/.../results/mimo-v2.5` | 服务器 Mimo-v2.5 全量结果解压后复评估 |
| CoSIL | `unpacked_results/.../CoSIL/.../results/mimo-v2.5` | 服务器 Mimo-v2.5 全量结果解压后复评估 |
| GraphLocator | `unpacked_results/.../GraphLocator/.../results/mimo-v2.5` | 服务器 Mimo-v2.5 全量结果解压后复评估 |
| GALA | `unpacked_results/.../GALA/.../results/mimo-v2.5` | 服务器 Mimo-v2.5 全量结果解压后复评估 |
| BM25-MMIR | `MM-IR/results/swebench_multimodal-full-candidates/bm25-mmir` | 本地已有 BM25 全量结果，按同一 Clean15 样本复评估 |

指标解释沿用 `003_两个60样本子集Qwen3-VL-8B基线结果汇总.md`：

- 宽松 `Acc@K`：前 K 个预测只要命中任意一个 gold 即算成功。
- 严格 `Acc@K`：前 K 个预测必须覆盖该层级所有 gold 才算成功。
- `MRR@15`：第一个命中位置越靠前越高。
- `MAP@15`：多个 gold 的整体排序质量。
- `Empty`：该层级没有预测的样本比例。
- 集合指标 `@All`：不截断预测集合，直接评估完整预测集合的 SL / REC / PRE / F1。

## 1. 文件级结果

文件级是最稳定的比较层级。Clean15 后，LocAgent 在严格覆盖和排序质量上最好；GALA 的宽松命中也很强；BM25 的宽松 Acc@15 较高，但严格覆盖和精度明显偏低，说明它能把相关文件召回到候选里，但噪声较多。

### 1.1 文件级宽松 Acc

| 方法 | Acc@1 | Acc@5 | Acc@10 | Acc@15 | MRR@15 | MAP@15 | Empty |
|---|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 66.30 | 82.61 | 83.70 | 84.78 | 73.24 | 53.02 | 0.00 |
| CoSIL | 51.09 | 69.57 | 69.57 | 69.57 | 58.79 | 37.07 | 0.00 |
| GraphLocator | 16.30 | 31.52 | 35.87 | 38.04 | 22.73 | 12.45 | 0.00 |
| GALA | 43.48 | 80.43 | 80.43 | 80.43 | 58.62 | 41.43 | 3.26 |
| BM25-MMIR | 25.00 | 45.65 | 57.61 | 65.22 | 35.09 | 21.32 | 0.00 |

### 1.2 文件级严格 Acc

| 方法 | Acc@1 | Acc@5 | Acc@10 | Acc@15 | MRR@15 | MAP@15 | Empty |
|---|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 25.00 | 41.30 | 42.39 | 42.39 | 73.24 | 53.02 | 0.00 |
| CoSIL | 15.22 | 26.09 | 26.09 | 26.09 | 58.79 | 37.07 | 0.00 |
| GraphLocator | 4.35 | 8.70 | 9.78 | 11.96 | 22.73 | 12.45 | 0.00 |
| GALA | 13.04 | 39.13 | 39.13 | 39.13 | 58.62 | 41.43 | 3.26 |
| BM25-MMIR | 5.43 | 17.39 | 27.17 | 30.43 | 35.09 | 21.32 | 0.00 |

### 1.3 文件级集合指标 @All

| 方法 | SL | REC | PRE | F1 |
|---|---:|---:|---:|---:|
| LocAgent | 42.39 | 59.77 | 46.98 | 46.38 |
| CoSIL | 26.09 | 43.35 | 23.99 | 27.68 |
| GraphLocator | 11.96 | 21.88 | 7.86 | 8.26 |
| GALA | 39.13 | 57.26 | 27.72 | 33.25 |
| BM25-MMIR | 30.43 | 45.41 | 6.81 | 11.11 |

## 2. Module 级结果

Module 级比较显示：LocAgent 和 GALA 的上限最高，BM25 的严格 Acc@15 也达到 40.22，但 BM25 的精度只有 5.81，说明它主要依靠扩大候选集合提升覆盖率。CoSIL 的 module 级精度相对较好，但完整覆盖率较低。

### 2.1 Module 级宽松 Acc

| 方法 | Acc@1 | Acc@5 | Acc@10 | Acc@15 | MRR@15 | MAP@15 | Empty |
|---|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 20.65 | 43.48 | 52.17 | 65.22 | 31.18 | 24.71 | 0.00 |
| CoSIL | 23.91 | 50.00 | 53.26 | 53.26 | 34.48 | 24.43 | 1.09 |
| GraphLocator | 8.70 | 21.74 | 23.91 | 23.91 | 13.99 | 10.28 | 9.78 |
| GALA | 28.26 | 61.96 | 64.13 | 64.13 | 40.51 | 31.20 | 4.35 |
| BM25-MMIR | 14.13 | 38.04 | 53.26 | 60.87 | 26.48 | 20.56 | 0.00 |

### 2.2 Module 级严格 Acc

| 方法 | Acc@1 | Acc@5 | Acc@10 | Acc@15 | MRR@15 | MAP@15 | Empty |
|---|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 9.78 | 23.91 | 33.70 | 43.48 | 31.18 | 24.71 | 0.00 |
| CoSIL | 9.78 | 23.91 | 25.00 | 25.00 | 34.48 | 24.43 | 1.09 |
| GraphLocator | 4.35 | 11.96 | 13.04 | 13.04 | 13.99 | 10.28 | 9.78 |
| GALA | 14.13 | 34.78 | 34.78 | 34.78 | 40.51 | 31.20 | 4.35 |
| BM25-MMIR | 5.43 | 20.65 | 29.35 | 40.22 | 26.48 | 20.56 | 0.00 |

### 2.3 Module 级集合指标 @All

| 方法 | SL | REC | PRE | F1 |
|---|---:|---:|---:|---:|
| LocAgent | 55.43 | 67.79 | 12.37 | 17.40 |
| CoSIL | 25.00 | 37.19 | 19.44 | 22.60 |
| GraphLocator | 13.04 | 17.43 | 8.14 | 9.47 |
| GALA | 34.78 | 48.21 | 22.17 | 27.18 |
| BM25-MMIR | 40.22 | 48.51 | 5.81 | 10.06 |

## 3. Function 级结果

Function 级是最难的层级。LocAgent 在严格覆盖和集合召回上最高；BM25 的宽松 Acc@15 接近 GALA，但严格覆盖只到 13.04，说明很多命中只是碰到部分函数；CoSIL 和 GraphLocator 的函数级表现明显偏弱。

### 3.1 Function 级宽松 Acc

| 方法 | Acc@1 | Acc@5 | Acc@10 | Acc@15 | MRR@15 | MAP@15 | Empty |
|---|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 11.96 | 33.70 | 44.57 | 50.00 | 22.66 | 14.76 | 0.00 |
| CoSIL | 4.35 | 16.30 | 26.09 | 30.43 | 10.83 | 6.96 | 1.09 |
| GraphLocator | 4.35 | 10.87 | 13.04 | 14.13 | 6.96 | 3.59 | 9.78 |
| GALA | 6.52 | 19.57 | 31.52 | 38.04 | 12.70 | 7.30 | 4.35 |
| BM25-MMIR | 13.04 | 28.26 | 36.96 | 39.13 | 20.35 | 11.63 | 0.00 |

### 3.2 Function 级严格 Acc

| 方法 | Acc@1 | Acc@5 | Acc@10 | Acc@15 | MRR@15 | MAP@15 | Empty |
|---|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 3.26 | 14.13 | 18.48 | 21.74 | 22.66 | 14.76 | 0.00 |
| CoSIL | 1.09 | 5.43 | 7.61 | 10.87 | 10.83 | 6.96 | 1.09 |
| GraphLocator | 1.09 | 3.26 | 3.26 | 3.26 | 6.96 | 3.59 | 9.78 |
| GALA | 1.09 | 5.43 | 10.87 | 13.04 | 12.70 | 7.30 | 4.35 |
| BM25-MMIR | 3.26 | 9.78 | 11.96 | 13.04 | 20.35 | 11.63 | 0.00 |

### 3.3 Function 级集合指标 @All

| 方法 | SL | REC | PRE | F1 |
|---|---:|---:|---:|---:|
| LocAgent | 31.52 | 52.38 | 7.89 | 12.40 |
| CoSIL | 10.87 | 18.89 | 4.63 | 6.48 |
| GraphLocator | 3.26 | 7.18 | 2.61 | 3.22 |
| GALA | 13.04 | 22.70 | 4.85 | 7.05 |
| BM25-MMIR | 13.04 | 22.08 | 3.98 | 6.09 |

## 4. 横向结论

### 4.1 LocAgent 是 clean15 后最强的综合方法

LocAgent 在文件级、模块级和函数级的严格 Acc@15 都是最高或并列最高：

| 层级 | LocAgent 严格 Acc@15 | 最接近方法 |
|---|---:|---|
| File | 42.39 | GALA 39.13 |
| Module | 43.48 | BM25-MMIR 40.22 |
| Function | 21.74 | GALA / BM25-MMIR 13.04 |

这说明在 gold 数量被限制到 15 以内后，LocAgent 的 agent 搜索和候选重排仍然最适合全覆盖式定位。

### 4.2 GALA 在文件级和模块级排序较强，但函数级不足

GALA 的文件级宽松 Acc@15 为 80.43，接近 LocAgent 的 84.78；模块级宽松 Acc@15 为 64.13，也接近 LocAgent 的 65.22。它的问题主要出现在函数级：严格 Acc@15 只有 13.04，说明它能找到相关文件和模块，但进一步落到具体函数时覆盖不足。

### 4.3 BM25-MMIR 有较强召回，但噪声很高

BM25-MMIR 的文件级宽松 Acc@15 为 65.22，模块级宽松 Acc@15 为 60.87，函数级宽松 Acc@15 为 39.13。它说明纯文本检索仍然能捕捉大量相关候选。

但集合指标显示它的精度很低：

| 层级 | BM25 REC@All | BM25 PRE@All | BM25 F1@All |
|---|---:|---:|---:|
| File | 45.41 | 6.81 | 11.11 |
| Module | 48.51 | 5.81 | 10.06 |
| Function | 22.08 | 3.98 | 6.09 |

这说明 BM25 适合作为召回器，但不适合作为最终定位器。更合理的用法是作为候选生成阶段，然后交给 LLM、图结构或 reranker 精排。

### 4.4 CoSIL 文件级可用，函数级偏弱

CoSIL 文件级宽松 Acc@15 为 69.57，严格 Acc@15 为 26.09；但函数级严格 Acc@15 只有 10.87。它在 clean15 后没有出现大量空预测，说明运行结果是可用的，但实体级定位能力不足。

### 4.5 GraphLocator 在该口径下整体偏弱

GraphLocator 的文件级严格 Acc@15 为 11.96，模块级为 13.04，函数级为 3.26，并且 module/function 空预测率为 9.78。它在这个实验中的主要问题不是 clean15 样本不公平，而是跨仓库、多语言、多模态情况下图缓存、实体映射和因果链搜索容易断开。

## 5. 后续使用建议

后续写实验分析时，建议将本表作为 `SWE-bench Multimodal full-dev clean15` 的主结果表：

1. 如果讨论最终定位质量，优先看严格 `Acc@15` 和 `SL@All`。
2. 如果讨论召回能力，优先看宽松 `Acc@15` 和 `REC@All`。
3. 如果讨论候选噪声，必须同时看 `PRE@All` 和 `F1@All`。
4. BM25-MMIR 不应和 agent 方法直接当作最终定位器比较；它更适合作为第一阶段召回基线。
5. Clean15 后仍然保留 92/102 条样本，覆盖大多数 SWE-bench Multimodal full-dev 问题，因此这个口径比原始全集更适合分析 `Acc@15`。

## 6. 结果文件位置

Clean15 子集文件：

```text
unpacked_results/swefull_results_mimov2.5/swebench_multimodal_full_dev_mimo-v2.5_20260712_152753/repo/clean_subsets/swebench_multimodal-full-dev.clean15.samples.jsonl
unpacked_results/swefull_results_mimov2.5/swebench_multimodal_full_dev_mimo-v2.5_20260712_152753/repo/clean_subsets/swebench_multimodal-full-dev.clean15.manifest.json
```

Mimo-v2.5 clean15 指标：

```text
unpacked_results/swefull_results_mimov2.5/swebench_multimodal_full_dev_mimo-v2.5_20260712_152753/repo/LocAgent/newtest/swebench_multimodal-full-dev/results/mimo-v2.5/eval_strict_clean15/metrics_3level.md
unpacked_results/swefull_results_mimov2.5/swebench_multimodal_full_dev_mimo-v2.5_20260712_152753/repo/CoSIL/newtest/swebench_multimodal-full-dev/results/mimo-v2.5/eval_strict_clean15/metrics_3level.md
unpacked_results/swefull_results_mimov2.5/swebench_multimodal_full_dev_mimo-v2.5_20260712_152753/repo/GraphLocator/newtest/swebench_multimodal-full-dev/results/mimo-v2.5/eval_strict_clean15/metrics_3level.md
unpacked_results/swefull_results_mimov2.5/swebench_multimodal_full_dev_mimo-v2.5_20260712_152753/repo/GALA/mytest/swebench_multimodal-full-dev/results/mimo-v2.5/eval_strict_clean15/metrics_3level.md
```

BM25-MMIR clean15 指标：

```text
MM-IR/results/swebench_multimodal-full-candidates/bm25-mmir/eval_strict_clean15/metrics_3level.md
MM-IR/results/swebench_multimodal-full-candidates/bm25-mmir/eval_clean15/metrics_3level.md
```
