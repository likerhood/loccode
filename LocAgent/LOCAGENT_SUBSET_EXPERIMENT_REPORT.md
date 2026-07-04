# 原生 LocAgent 在不同子集上的测试结果与分析汇报

## 1. 汇报目的

我们前面做了三类递进实验，目标是观察 **原生 LocAgent** 在不同 benchmark 场景下的代码定位能力：

1. 单语言、单模态：SWE-bench Lite 小子集。
2. 多语言、多模态：OmniGIRL small-60。
3. 多语言、弱多模态/链接模态：Multi-SWE-bench small-60。

整体结论很清楚：

```text
原生 LocAgent 在 Python/SWE-bench 风格任务上表现较强；
遇到多语言、多模态、非 Python 仓库后，性能明显下降；
在 Multi-SWE small-60 上，严格 file/module/function 指标均为 0。
```

这不是简单的模型能力问题，而是由数据模态、语言覆盖、代码图构建、检索工具、输出解析和评测 GT 共同导致的系统性问题。

## 2. 实验设置概览

| 实验 | 数据集 | 样本数 | 语言 | 模态 | 主要目的 |
|---|---|---:|---|---|---|
| SWE-bench Lite 小子集 | `czlll/SWE-bench_Lite` | 10 | Python | 文本 issue | 验证原生 LocAgent 在熟悉场景下的定位能力 |
| OmniGIRL small-60 | `Deep-Software-Analytics/OmniGIRL` | 60 | Python / Java / JS / TS | 文本 + 图片链接 + 网址 | 测试多语言、多模态 issue 场景 |
| Multi-SWE small-60 | `ByteDance-Seed/Multi-SWE-bench` 派生本地 JSONL | 60 | C / C++ / Go / Java / JS / Rust / TS | issue 文本 + 图片/网址链接 | 测试更广语言覆盖下的原生 LocAgent 泛化能力 |

运行模型主要为：

```text
openai/qwen-7B
```

运行模式主要为：

```text
--localize --merge --num_samples 1 --repo_cache_mode shared
```

## 3. SWE-bench Lite 小子集：单语言单模态 baseline

### 3.1 数据特点

SWE-bench Lite 是 LocAgent 原始实验最接近的场景：

- 主要是 Python 仓库。
- issue 以文本为主。
- benchmark 与原 LocAgent 评测代码兼容。
- GT 中有较稳定的 file/module/function 信息。
- 代码图、BM25、实体抽取和输出解析都更贴合 Python。

当前工作区中保留的可复现实验产物主要是 10 条小子集：

- `test/swebenchlite-10/results_10_test2/location/merged_loc_outputs_mrr.jsonl`
- `test/swebenchlite-10/results_10/location/merged_loc_outputs_mrr.jsonl`

注意：这是 10 条小样本结果，样本数较少，不能视为完整 SWE-bench Lite 性能。

### 3.2 定位指标

之前使用 `evaluation.eval_metric.evaluate_results` 得到的 10 条子集结果如下：

| Level | Acc@1 | Acc@3 | Acc@5 | Acc@10 | NDCG@1 | NDCG@3 | NDCG@5 | NDCG@10 | P@1 | P@3 | P@5 | P@10 | Recall@1 | Recall@3 | Recall@5 | Recall@10 | MAP@1 | MAP@3 | MAP@5 | MAP@10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| file | 1.0000 | 1.0000 | 1.0000 | - | 1.0000 | 1.0000 | 1.0000 | - | 1.0000 | 0.3333 | 0.2000 | - | 1.0000 | 1.0000 | 1.0000 | - | 1.0000 | 0.3333 | 0.2000 | - |
| module | - | - | 0.7000 | 0.7000 | - | - | 0.4503 | 0.4503 | - | - | 0.1600 | 0.0800 | - | - | 0.7500 | 0.7500 | - | - | 0.0720 | 0.0360 |
| function | - | - | 0.4000 | 0.5000 | - | - | 0.3336 | 0.3652 | - | - | 0.1400 | 0.0800 | - | - | 0.5167 | 0.6167 | - | - | 0.0710 | 0.0368 |

### 3.3 结果解释

这个结果说明原生 LocAgent 在 **Python + 文本 issue + SWE-bench 风格 GT** 下是有效的。

原因包括：

1. Python AST/entity 抽取更成熟。
2. 原始工具说明、搜索策略和输出解析更贴合 Python。
3. SWE-bench Lite 的 patch/GT 与 `evaluation/eval_metric.py` 直接兼容。
4. 文件级定位更容易，函数级定位更难，但仍有一定命中。

这组实验可以作为后续多语言/多模态实验的正向 baseline。

## 4. OmniGIRL small-60：多语言多模态场景

### 4.1 数据构成

OmniGIRL small-60 从 `Deep-Software-Analytics/OmniGIRL` test split 中筛选 60 条：

| Language | Count |
|---|---:|
| Python | 15 |
| Java | 15 |
| TypeScript | 15 |
| JavaScript | 15 |

模态分布：

| Modality | Count |
|---|---:|
| text_only | 15 |
| website_only | 26 |
| image_only | 12 |
| image_and_website | 7 |

也就是说：

- 45 / 60 个样本含图片或网址线索，占 75.0%。
- 带图片样本 19 个。
- 带网址样本 33 个。
- 同时带图片和网址 7 个。

### 4.2 运行产物

主要产物：

- `test/OmniGIRL_small60/results_small_60/location/merged_loc_outputs_mrr.jsonl`
- `test/OmniGIRL_small60/eval_small_60/metrics.md`
- `test/OmniGIRL_small60/eval_small_60/metrics.json`
- `test/OmniGIRL_small60/test60/run_result_analysis.md`

OmniGIRL 没有原生 `edit_functions`，因此我们写了 `evaluation/omnigirl_eval` 适配评测：

- file GT 从 patch 修改文件抽取。
- module/function GT 从 patch + base commit + tree-sitter enclosing entity 抽取。
- prediction 使用 `combined = found_* + raw_output_loc`，因为 Java/JS/TS 的 `found_*` 很多为空，但 raw output 中仍有可用路径。

### 4.3 Strict 指标

| Level | Evaluated | Acc@1 | Acc@3 | Acc@5 | Acc@10 | Recall@5 | Recall@10 | NDCG@5 | NDCG@10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| file | 60 | 0.2833 | 0.3500 | 0.3667 | - | 0.3778 | - | 0.3360 | - |
| module | 53 | 0.1132 | 0.1698 | 0.1698 | 0.1887 | 0.1745 | 0.1981 | 0.1462 | 0.1542 |
| function | 53 | 0.0566 | 0.0943 | 0.0943 | 0.1132 | 0.0943 | 0.1132 | 0.0755 | 0.0809 |

### 4.4 Relaxed 指标

| Level | Evaluated | Acc@1 | Acc@3 | Acc@5 | Acc@10 | Recall@5 | Recall@10 | NDCG@5 | NDCG@10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| file | 60 | 0.2833 | 0.3500 | 0.3667 | - | 0.3778 | - | 0.3360 | - |
| module | 53 | 0.1132 | 0.1698 | 0.1698 | 0.1887 | 0.1745 | 0.1981 | 0.1462 | 0.1542 |
| function | 53 | 0.1132 | 0.1509 | 0.1509 | 0.1698 | 0.1536 | 0.1725 | 0.1315 | 0.1358 |

Relaxed 对 function 有提升，原因是模型经常输出函数 basename，例如 `read`，而 GT 是 `FlowControlHandler.read`。同文件下 basename 匹配可以捞回一部分结果。

### 4.5 按语言结果

File Acc@5：

| Language | File Acc@5 |
|---|---:|
| Python | 0.6667 |
| Java | 0.5333 |
| JavaScript | 0.2667 |
| TypeScript | 0.0000 |

Function Acc@10 relaxed：

| Language | Function Acc@10 Relaxed |
|---|---:|
| Java | 0.4000 |
| Python | 0.2000 |
| JavaScript | 0.0000 |
| TypeScript | 0.0000 |

### 4.6 结果解释

OmniGIRL 的结果比 SWE-bench Lite 低很多，但不是完全失效：

1. Python 仍然明显强于其他语言。
2. Java 文件级结果较好，但函数级需要 relaxed 才明显提升。
3. JS/TS 较弱，尤其 TypeScript 在 file Acc@5 上为 0。
4. 原生 LocAgent 没有真正处理图片，只是看到 issue 文本中的 URL。
5. `found_*` 对非 Python 解析不足，因此必须结合 `raw_output_loc` 才能得到合理评测。

这说明原生 LocAgent 有一定跨语言迁移能力，但需要多语言解析、路径规范化、函数名 relaxed matching 和真正的模态预处理。

## 5. Multi-SWE small-60：更广多语言场景

### 5.1 数据构成

Multi-SWE small-60 来自 `ByteDance-Seed/Multi-SWE-bench`，为了避免 Hugging Face 远程加载 40 个 JSONL 文件超时，我们构建成本地：

- `test/mutilswe_small/samples.jsonl`

语言分布：

| Language | Count |
|---|---:|
| C | 9 |
| C++ | 9 |
| Go | 9 |
| Java | 9 |
| JavaScript | 8 |
| Rust | 8 |
| TypeScript | 8 |

链接模态分布：

| Modality | Count |
|---|---:|
| website_only | 17 |
| image_and_website | 37 |
| image_only | 6 |

统计：

- 图片链接样本：43
- 网页链接样本：54
- 图片 URL：96
- 网页 URL：149
- 修改文件总数：146
- patch hunk header：166

注意：Multi-SWE 不是原生强多模态 benchmark。这里的图片/网址是从 issue 文本中抽取的弱模态链接，不等价于 SWE-bench Multimodal 那种视觉任务。

### 5.2 运行与评测产物

主要产物：

- `test/mutilswe_small/results_small_60/location/merged_loc_outputs_mrr.jsonl`
- `test/mutilswe_small/results_small_60/analysis/run_result_analysis.md`
- `test/mutilswe_small/results_small_60/analysis/metrics.json`
- `test/mutilswe_small/results_small_60/analysis/per_instance_file_metrics.csv`

评测口径：

- file GT：gold patch 修改文件。
- module/function GT：从 patch hunk header 抽取 `file:entity` proxy。
- 这里的 module/function 是 proxy，不是严格 AST gold，因为 Multi-SWE 没有官方 `edit_functions`。

### 5.3 指标结果

| Level | Acc@1 | Acc@3 | Acc@5 | Acc@10 | NDCG@5 | NDCG@10 | Recall@5 | Recall@10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| file | 0.0000 | 0.0000 | 0.0000 | - | 0.0000 | - | 0.0000 | - |
| module/proxy | - | - | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| function/proxy | - | - | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

运行状态：

| Item | Count |
|---|---:|
| 样本数 | 60 |
| merged 输出 | 60 |
| 有 file prediction | 14 |
| 无 file prediction | 46 |
| module/function proxy GT 覆盖 | 37 |

### 5.4 结果为什么为 0

核心原因是 **预测文件语言完全跑偏**。

GT 文件扩展名主要是：

| GT extension | Count |
|---|---:|
| `.hpp` | 31 |
| `.rs` | 19 |
| `.cpp` | 13 |
| `.h` | 13 |
| `.js` | 11 |
| `.java` | 10 |
| `.go` | 9 |
| `.c` | 8 |
| `.ts` | 5 |

但解析出来的预测文件扩展名是：

| Pred extension | Count |
|---|---:|
| `.py` | 32 |

典型例子：

| Instance | Language | GT | Prediction |
|---|---|---|---|
| `ponylang__ponyc-2504` | C | `src/libponyc/expr/call.c` | `lib/gbenchmark/mingw.py` |
| `jqlang__jq-2157` | C | `src/builtin.c` | `scripts/gen_utf8_tables.py` |
| `fmtlib__fmt-2394` | C++ | `include/fmt/color.h` | `support/rst2md.py`, `support/docopt.py` |
| `nushell__nushell-10405` | Rust | `crates/nu-parser/src/parser.rs` | `crates/nu_plugin_python/nu_plugin_python_example.py` |

也就是说，原生 LocAgent 在多语言仓库中经常定位到 Python helper/build/doc 脚本，而不是目标语言代码。

此外日志中还有大量 BM25 top-k 越界：

```json
{
  "value_error_lines": 82,
  "generic_error_lines": 59,
  "traceback_lines": 281,
  "bm25_topk_out_of_bounds": 247
}
```

这说明检索候选数量小于请求的 top-k，导致工具调用失败，进一步降低定位质量。

### 5.5 结果解释

Multi-SWE small-60 是对原生 LocAgent 最严苛的一组：

1. 完全没有 Python 样本。
2. 覆盖 C/C++/Go/Java/JS/Rust/TS。
3. 仓库中存在大量 Python 辅助脚本，容易误导 Python-oriented 检索。
4. 工具说明中 `file_path_or_pattern` 默认是 `**/*.py`。
5. 原生图结构、实体抽取和输出解析没有为这些语言充分适配。
6. 图片/网址没有被 OCR、caption 或网页摘要处理。

因此 0 分不是偶然，而是暴露出原生 LocAgent 的适用边界。

## 6. 横向对比

| 实验 | 样本 | 语言 | 模态 | File Acc@5 | Module Acc@10 | Function Acc@10 | 主要结论 |
|---|---:|---|---|---:|---:|---:|---|
| SWE-bench Lite 小子集 | 10 | Python | 文本 | 1.0000 | 0.7000 | 0.5000 | 原生 LocAgent 在熟悉 Python/SWE 场景有效 |
| OmniGIRL small-60 strict | 60 | Python/Java/JS/TS | 文本+图片链接+网址 | 0.3667 | 0.1887 | 0.1132 | 多语言后明显下降，但仍有部分跨语言能力 |
| OmniGIRL small-60 relaxed | 60 | Python/Java/JS/TS | 文本+图片链接+网址 | 0.3667 | 0.1887 | 0.1698 | relaxed function matching 能捞回部分 Java/Python 样本 |
| Multi-SWE small-60 | 60 | C/C++/Go/Java/JS/Rust/TS | issue 链接模态 | 0.0000 | 0.0000 | 0.0000 | 原生 LocAgent 在广多语言场景基本失效 |

趋势非常明显：

```text
Python 单语言文本任务
    > 多语言混合任务
        > 更广多语言、非 Python 主导任务
```

性能下降的核心原因不是模型完全不会推理，而是工具链和数据处理没有跟上：

- 代码图偏 Python。
- 搜索默认偏 Python。
- BM25 对多语言仓库候选处理不稳。
- 输出解析偏 Python/SWE-bench 格式。
- 图片/网址没有真正转化为可检索语义。

## 7. 可以考虑的研究点

### 7.1 多语言代码图与实体抽取

需要引入 tree-sitter 多语言 AST，至少覆盖：

- Python
- Java
- JavaScript
- TypeScript
- Go
- Rust
- C
- C++

目标是统一抽象：

```text
file / module / class / function / method / component / struct / enum / macro
```

这样才能让 `found_modules` 和 `found_entities` 在非 Python 上真正有意义。

### 7.2 语言感知搜索

当前工具默认 `**/*.py` 对多语言任务非常危险。应该根据样本语言和仓库文件扩展名动态设置搜索范围。

例如：

| Language | Search patterns |
|---|---|
| C | `**/*.c`, `**/*.h` |
| C++ | `**/*.cpp`, `**/*.cc`, `**/*.hpp`, `**/*.h` |
| Go | `**/*.go` |
| Java | `**/*.java` |
| JavaScript | `**/*.js`, `**/*.jsx` |
| TypeScript | `**/*.ts`, `**/*.tsx` |
| Rust | `**/*.rs` |

### 7.3 修复 BM25 top-k 越界

Multi-SWE 结果中大量出现：

```text
ValueError: kth(=-9) out of bounds (1)
```

应在 BM25 检索前加入：

```python
k = min(k, len(candidates))
```

这是一个低成本、高收益的稳定性修复。

### 7.4 多模态信息真正进入定位流程

当前图片/网址只是链接字符串，不是真正多模态。需要增加：

1. 图片下载与缓存。
2. OCR。
3. 图片 caption。
4. 网页标题和摘要抓取。
5. 将 OCR/caption/URL summary 合并进 issue prompt。
6. 做 ablation：
   - text only
   - text + URL summary
   - text + OCR
   - text + caption
   - full multimodal

这样才能证明“多模态”对定位有实际贡献。

### 7.5 输出解析与评测适配

OmniGIRL 说明 raw output 中有很多有用信息，但 `found_*` 对非 Python 解析失败。后续应增强：

- 非 Python 路径抽取。
- class/function/method 规范化。
- relaxed matching。
- raw output fallback。
- module/function/entity 多语言 GT。

### 7.6 构建更系统的 800 条 benchmark

我们已经规划了一个 800 条左右的多语言多模态定位 benchmark：

- 250 SWE-bench Multimodal
- 180 OmniGIRL
- 270 Multi-SWE-bench
- 60 SWE-bench Lite/Verified/Multilingual
- 40 自采 GitHub issue

对应文档：

- `MULTIMODAL_MULTILINGUAL_BENCHMARK_PLAN.md`

这个 benchmark 可以用来系统体现改进版 LocAgent 的优势。

## 8. 当前阶段结论

当前实验可以形成一个清晰叙事：

1. 原生 LocAgent 在 SWE-bench Lite 小子集上表现好，说明基础 agent/search/merge/eval 管线是有效的。
2. 到 OmniGIRL small-60，性能下降但仍有信号，说明原生 LocAgent 有部分跨语言迁移能力。
3. 到 Multi-SWE small-60，指标为 0，说明广多语言场景暴露出工具链边界。
4. 图片/网址目前没有被真正消费，所以现阶段不能声称原生 LocAgent 具备多模态定位能力。
5. 后续创新应集中在多语言代码图、语言感知检索、多模态预处理、BM25 稳定性、输出解析和统一评测上。

一句话总结：

```text
原生 LocAgent 证明了 Python SWE-style code localization 的有效性；
我们的实验进一步证明，要走向多语言多模态，需要系统性改造检索、图结构、模态输入和评测适配。
```
