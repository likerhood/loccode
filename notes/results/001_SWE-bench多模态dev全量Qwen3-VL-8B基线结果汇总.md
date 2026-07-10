# SWE-bench 多模态 dev 全量 Qwen3-VL-8B 基线结果汇总

生成时间：2026-07-09

本文档汇总已经完成的 `qwen3-vl-8b` 基线实验结果。实验数据为 SWE-bench Multimodal `dev` 全量 split，共 102 条样本。

## 1. 实验范围

| 项目 | 内容 |
|---|---|
| 基准 | SWE-bench Multimodal |
| 数据划分 | dev |
| 样本数 | 102 |
| LLM/VLM 基线模型 | `openai/qwen3-vl-8b` / `qwen3-vl-8b` |
| 主运行日志 | `baseline_run_logs/swebench_multimodal_full_dev_parallel_20260708_182346/` |
| 规范化样本文件 | `LocAgent/newtest/swebench_multimodal-full-dev/data/samples.jsonl` |
| 规范化仓库结构 | `LocAgent/newtest/swebench_multimodal-full-dev/repo_structures/` |

本次运行中的仓库分布如下：

| 仓库 | 数量 |
|---|---:|
| Automattic/wp-calypso | 37 |
| chartjs/Chart.js | 24 |
| diegomura/react-pdf | 11 |
| markedjs/marked | 14 |
| processing/p5.js | 16 |

该 dev 全量数据集共包含 301 张图片和 138 个网页链接。

## 2. 结果路径

| 基线 | 结果目录 |
|---|---|
| LocAgent | `LocAgent/newtest/swebench_multimodal-full-dev/results/openai_qwen3-vl-8b/` |
| CoSIL | `CoSIL/newtest/swebench_multimodal-full-dev/results/openai_qwen3-vl-8b/` |
| GraphLocator | `GraphLocator/newtest/swebench_multimodal-full-dev/results/openai_qwen3-vl-8b/` |
| GALA | `GALA/mytest/swebench_multimodal-full-dev/results/qwen3-vl-8b/` |
| BM25-MMIR | `MM-IR/results/swebench_multimodal-full-candidates/bm25-mmir/` |

说明：

- BM25-MMIR 是非大模型检索基线。它的目录名为 `swebench_multimodal-full-candidates`，但评估样本数同样是 102。
- GALA 文件级指标采用 `final` 阶段；模块级和函数级指标由 GALA 分阶段候选与 `repo_structures` 派生。
- CoSIL 在本次 dev 全量运行中完成 102 行输出，并规范化得到 102 条非空文件级预测。

## 3. 指标口径

本文同时报告两套 Acc@K 口径：

- 宽松 Acc@K：任意命中标准。前 K 个预测中命中该层级任意一个标准答案位置即算成功。
- 严格 Acc@K：LocAgent 风格全覆盖标准。前 K 个预测必须覆盖该层级全部标准答案位置才算成功。

同时报告 `MRR@15`、`MAP@15` 和 `Empty`。集合指标含义如下：

- `SL`：预测集合是否覆盖该层级全部标准答案位置。
- `REC`：平均召回率。
- `PRE`：平均精度。
- `F1`：平均 F1。

以下所有数值均为百分比。

## 4. 宽松排序指标

### 文件级

| 基线 | N | Acc@1 | Acc@3 | Acc@5 | Acc@10 | Acc@15 | MRR@15 | MAP@15 | Empty |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 102 | 26.47 | 31.37 | 38.24 | 41.18 | 41.18 | 30.78 | 18.83 | 4.90 |
| CoSIL | 102 | 31.37 | 43.14 | 44.12 | 44.12 | 44.12 | 37.01 | 22.27 | 0.00 |
| GraphLocator | 102 | 20.59 | 25.49 | 28.43 | 29.41 | 29.41 | 23.56 | 11.53 | 0.00 |
| GALA | 102 | 36.27 | 57.84 | 61.76 | 61.76 | 61.76 | 47.40 | 30.00 | 0.00 |
| BM25-MMIR | 102 | 26.47 | 41.18 | 46.08 | 58.82 | 65.69 | 36.07 | 21.89 | 0.00 |

### 模块级

| 基线 | N | Acc@1 | Acc@3 | Acc@5 | Acc@10 | Acc@15 | MRR@15 | MAP@15 | Empty |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 102 | 9.80 | 18.63 | 23.53 | 31.37 | 34.31 | 16.21 | 11.70 | 4.90 |
| CoSIL | 102 | 23.53 | 31.37 | 33.33 | 33.33 | 33.33 | 27.45 | 18.35 | 1.96 |
| GraphLocator | 102 | 14.71 | 22.55 | 23.53 | 23.53 | 24.51 | 18.46 | 11.60 | 10.78 |
| GALA | 102 | 9.80 | 20.59 | 22.55 | 23.53 | 23.53 | 14.98 | 10.88 | 0.98 |
| BM25-MMIR | 102 | 13.73 | 30.39 | 37.25 | 50.00 | 56.86 | 25.16 | 19.03 | 0.00 |

### 函数级

| 基线 | N | Acc@1 | Acc@3 | Acc@5 | Acc@10 | Acc@15 | MRR@15 | MAP@15 | Empty |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 102 | 2.94 | 10.78 | 12.75 | 18.63 | 19.61 | 7.30 | 4.17 | 4.90 |
| CoSIL | 102 | 5.88 | 9.80 | 13.73 | 15.69 | 16.67 | 8.90 | 5.06 | 1.96 |
| GraphLocator | 102 | 5.88 | 10.78 | 12.75 | 13.73 | 14.71 | 8.66 | 5.06 | 11.76 |
| GALA | 102 | 5.88 | 8.82 | 11.76 | 11.76 | 12.75 | 7.74 | 5.57 | 10.78 |
| BM25-MMIR | 102 | 11.76 | 21.57 | 26.47 | 35.29 | 39.22 | 18.88 | 10.51 | 0.00 |

## 5. 严格排序指标

### 文件级

| 基线 | N | Acc@1 | Acc@3 | Acc@5 | Acc@10 | Acc@15 | MRR@15 | MAP@15 | Empty |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 102 | 9.80 | 13.73 | 15.69 | 17.65 | 18.63 | 30.78 | 18.83 | 4.90 |
| CoSIL | 102 | 10.78 | 15.69 | 18.63 | 18.63 | 18.63 | 37.01 | 22.27 | 0.00 |
| GraphLocator | 102 | 5.88 | 6.86 | 6.86 | 6.86 | 6.86 | 23.56 | 11.53 | 0.00 |
| GALA | 102 | 10.78 | 19.61 | 25.49 | 25.49 | 25.49 | 47.40 | 30.00 | 0.00 |
| BM25-MMIR | 102 | 6.86 | 12.75 | 17.65 | 27.45 | 31.37 | 36.07 | 21.89 | 0.00 |

### 模块级

| 基线 | N | Acc@1 | Acc@3 | Acc@5 | Acc@10 | Acc@15 | MRR@15 | MAP@15 | Empty |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 102 | 3.92 | 8.82 | 12.75 | 17.65 | 19.61 | 16.21 | 11.70 | 4.90 |
| CoSIL | 102 | 8.82 | 14.71 | 15.69 | 15.69 | 15.69 | 27.45 | 18.35 | 1.96 |
| GraphLocator | 102 | 4.90 | 8.82 | 8.82 | 8.82 | 8.82 | 18.46 | 11.60 | 10.78 |
| GALA | 102 | 3.92 | 8.82 | 10.78 | 11.76 | 11.76 | 14.98 | 10.88 | 0.98 |
| BM25-MMIR | 102 | 4.90 | 16.67 | 18.63 | 26.47 | 36.27 | 25.16 | 19.03 | 0.00 |

### 函数级

| 基线 | N | Acc@1 | Acc@3 | Acc@5 | Acc@10 | Acc@15 | MRR@15 | MAP@15 | Empty |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 102 | 0.00 | 4.90 | 5.88 | 6.86 | 6.86 | 7.30 | 4.17 | 4.90 |
| CoSIL | 102 | 2.94 | 2.94 | 3.92 | 4.90 | 4.90 | 8.90 | 5.06 | 1.96 |
| GraphLocator | 102 | 1.96 | 3.92 | 3.92 | 3.92 | 3.92 | 8.66 | 5.06 | 11.76 |
| GALA | 102 | 2.94 | 4.90 | 5.88 | 6.86 | 7.84 | 7.74 | 5.57 | 10.78 |
| BM25-MMIR | 102 | 2.94 | 5.88 | 8.82 | 10.78 | 11.76 | 18.88 | 10.51 | 0.00 |

## 6. 集合指标 @All

### 宽松

| 基线 | 文件 SL | 文件 REC | 文件 PRE | 文件 F1 | 模块 SL | 模块 REC | 模块 PRE | 模块 F1 | 函数 SL | 函数 REC | 函数 PRE | 函数 F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 18.63 | 24.94 | 15.87 | 14.30 | 23.53 | 29.79 | 7.39 | 9.75 | 7.84 | 13.93 | 2.58 | 3.49 |
| CoSIL | 18.63 | 27.59 | 17.34 | 18.59 | 15.69 | 22.21 | 18.33 | 17.51 | 4.90 | 8.71 | 3.00 | 3.45 |
| GraphLocator | 6.86 | 14.25 | 19.18 | 13.24 | 8.82 | 15.19 | 14.03 | 13.21 | 3.92 | 8.18 | 3.03 | 3.79 |
| GALA | 25.49 | 39.55 | 21.24 | 23.99 | 11.76 | 17.15 | 8.63 | 10.11 | 7.84 | 9.75 | 3.39 | 3.97 |
| BM25-MMIR | 31.37 | 45.69 | 7.39 | 11.38 | 36.27 | 44.36 | 5.69 | 9.57 | 11.76 | 20.07 | 3.99 | 5.70 |

### 严格

| 基线 | 文件 SL | 文件 REC | 文件 PRE | 文件 F1 | 模块 SL | 模块 REC | 模块 PRE | 模块 F1 | 函数 SL | 函数 REC | 函数 PRE | 函数 F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 18.63 | 24.94 | 15.87 | 14.30 | 23.53 | 29.79 | 7.39 | 9.75 | 7.84 | 13.93 | 2.58 | 3.49 |
| CoSIL | 18.63 | 27.59 | 17.34 | 18.59 | 15.69 | 22.21 | 18.33 | 17.51 | 4.90 | 8.71 | 3.00 | 3.45 |
| GraphLocator | 6.86 | 14.25 | 19.18 | 13.24 | 8.82 | 15.19 | 14.03 | 13.21 | 3.92 | 8.18 | 3.03 | 3.79 |
| GALA | 25.49 | 39.55 | 21.24 | 23.99 | 11.76 | 17.15 | 8.63 | 10.11 | 7.84 | 9.75 | 3.39 | 3.97 |
| BM25-MMIR | 31.37 | 45.69 | 7.39 | 11.38 | 36.27 | 44.36 | 5.69 | 9.57 | 11.76 | 20.07 | 3.99 | 5.70 |

集合指标表在宽松版和严格版中一致，因为 `SL / REC / PRE / F1` 直接基于预测集合计算；宽松与严格的主要差异体现在 Acc@K。

## 7. 主要观察

1. 文件级排序最强的是 GALA 和 BM25-MMIR。GALA 在宽松文件级 Acc@1、MRR@15 和 MAP@15 上最高；BM25-MMIR 在宽松和严格文件级 Acc@15 上最高。
2. BM25-MMIR 在较大 K 下的模块级和函数级召回优势明显。它拥有最高的宽松/严格模块级 Acc@15 和函数级 Acc@15，但集合指标中的精度偏低，说明候选集合更宽。
3. GALA 在大模型基线中拥有最强的文件级集合 F1。其文件级 F1@All 为 23.99，高于 LocAgent、CoSIL 和 GraphLocator。
4. CoSIL 在文件级和模块级上较有竞争力，尤其是文件级 MRR@15 与模块级 F1@All；同时本次 dev 全量运行没有文件级空预测。
5. LocAgent 文件级表现中等，但函数级严格准确率偏低；不过它的模块级严格 SL@All 达到 23.53，仍有一定机制范围覆盖能力。
6. GraphLocator 在该 dev 全量设置下整体落后，并且在大模型基线中函数级空预测率最高。

## 8. 结果解释

dev 全量结果进一步印证了 60 样本实验中观察到的趋势：

- 视觉图和代码图对齐能明显帮助 GALA 的文件级排序和文件级集合质量。
- 稀疏词法检索仍然是很强的高 K 召回基线，尤其适合标准答案补丁跨多个文件、模块或函数的样本。
- 函数级定位仍然最难。这里最好的严格函数级 Acc@15 也只有 11.76，说明后续重排序不能只依赖视觉或词法锚点，还需要机制级证据。
- 严格 Acc@K 明显低于宽松 Acc@K，因为 SWE-bench Multimodal 中很多问题会修改多个标准答案位置。全覆盖成功率更苛刻，但也更贴近面向补丁的定位真实需求。

## 9. 源指标文件

| 基线 | 宽松指标 | 严格指标 |
|---|---|---|
| LocAgent | `LocAgent/newtest/swebench_multimodal-full-dev/results/openai_qwen3-vl-8b/eval/metrics_3level.md` | `LocAgent/newtest/swebench_multimodal-full-dev/results/openai_qwen3-vl-8b/eval_strict/metrics_3level.md` |
| CoSIL | `CoSIL/newtest/swebench_multimodal-full-dev/results/openai_qwen3-vl-8b/eval/metrics_3level.md` | `CoSIL/newtest/swebench_multimodal-full-dev/results/openai_qwen3-vl-8b/eval_strict/metrics_3level.md` |
| GraphLocator | `GraphLocator/newtest/swebench_multimodal-full-dev/results/openai_qwen3-vl-8b/eval/metrics_3level.md` | `GraphLocator/newtest/swebench_multimodal-full-dev/results/openai_qwen3-vl-8b/eval_strict/metrics_3level.md` |
| GALA | `GALA/mytest/swebench_multimodal-full-dev/results/qwen3-vl-8b/eval/metrics_3level.md` | `GALA/mytest/swebench_multimodal-full-dev/results/qwen3-vl-8b/eval_strict/metrics_3level.md` |
| BM25-MMIR | `MM-IR/results/swebench_multimodal-full-candidates/bm25-mmir/eval/metrics_3level.md` | `MM-IR/results/swebench_multimodal-full-candidates/bm25-mmir/eval_strict/metrics_3level.md` |
