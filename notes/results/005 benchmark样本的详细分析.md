## 2. Benchmark 全量样本级分析

这里需要特别区分三类统计：

1. **全量样本级统计**：来自 benchmark JSONL 和 gold patch，例如 issue 长度、图片数、URL 数、复现代码、运行错误、gold 文件数、hunk 数、patch 行数。这些才是 benchmark 任务本身的复杂度。
2. **可运行候选子集统计**：有些数据集原始全量大于本地已构建 `repo_structures` 和候选文件的数量。例如 OmniGIRL 原始全量为 959 条，但当前本地 MM-IR 已准备候选和结构的是 631 条。
3. **仓库级搜索空间统计**：来自 `repo_structures`，例如整个仓库有多少文件、函数、代码行。它说明检索背景有多大，但不能直接等同于样本难度。

因此，这里以 **SWE-bench Multimodal dev 全量 102 条** 和 **OmniGIRL 原始全量 959 条 / 当前可运行候选 631 条** 为主。之前的 60 条只是我们为了跑 baseline 方便抽取的实验子集，不应作为 benchmark 全量画像。

### 2.1 SWE-bench Multimodal dev 全量 102

数据来源：`/home/like/locCode/MM-IR/data/swebench_multimodal-full-candidates/samples.jsonl`。该目录 summary 显示数据集为 `SWE-bench/SWE-bench_Multimodal` 的 `dev` split，`source_rows=102`，`candidate_rows=102`。

| 统计项 | 数值 |
|---|---:|
| 样本数 | 102 |
| 仓库分布 | Automattic/wp-calypso 37；Chart.js 24；p5.js 16；marked 14；react-pdf 11 |
| 平均 gold 文件数 | 4.0 |
| 中位 gold 文件数 | 2.0 |
| 最大 gold 文件数 | 36 |
| 平均 hunk 数 | 9.4 |
| 中位 hunk 数 | 4.5 |
| 最大 hunk 数 | 128 |
| 平均 patch 行数 | 131.7 |
| 中位 patch 行数 | 35.0 |
| 最大 patch 行数 | 2904 |
| 平均 issue 长度 | 3688.3 字符 |
| 中位 issue 长度 | 3505.0 字符 |
| 所有样本均有图片 | 102/102 |
| 所有样本均有 URL | 102/102 |
| 有复现代码/步骤 | 75/102 |
| 有运行错误或 stack 线索 | 44/102 |
| 图片数 | 平均 3.0；中位 1；最大 73 |
| URL 数 | 平均 2.3；中位 2；最大 9 |
| 代码块数 | 平均 0.6；中位 0；最大 5 |
| 样本复杂度分布 | 中等 20；困难 43；极难 39 |

SWE-bench Multimodal dev 全量的核心特点是：**所有样本都有图片和 URL，gold 修改经常分散，patch 跨度明显大于普通单文件定位任务**。平均每个样本 4.0 个 gold 文件、9.4 个 hunk，说明它经常不是“找一个文件”就结束，而是要定位一组参与同一机制的文件。

从仓库类型看，可以把 SWE-bench Multimodal 粗分为几类：

| 仓库 | 数量 | 主要定位机制 |
|---|---:|---|
| Automattic/wp-calypso | 37 | UI 流程、状态管理、路由、权限、表单、Redux selector/action |
| chartjs/Chart.js | 24 | canvas/chart 渲染、scale、layout、clip、tooltip、element draw |
| processing/p5.js | 16 | WebGL/canvas、图形渲染、颜色、alpha、纹理、字体 |
| markedjs/marked | 14 | Markdown 解析、tokenizer、renderer、格式化边界 |
| diegomura/react-pdf | 11 | PDF layout/render、字体、分页、样式布局 |

这比单纯关键词分类更合理：SWE-bench Multimodal 的视觉证据通常和渲染/UI 状态相关，但真实修改可能落在 route、selector、render pipeline 或 parser。也就是说，视觉证据常常是“症状”，不一定是“代码位置”。

代表困难/极难样本：

| 样本 | 仓库 | Gold 文件 | Hunk | Patch 行 | 图片 | URL | Issue 长度 | 复杂度 |
|---|---|---:|---:|---:|---:|---:|---:|---|
| Automattic__wp-calypso-34597 | wp-calypso | 15 | 48 | 271 | 6 | 1 | 6507 | 极难 |
| processing__p5.js-5917 | p5.js | 9 | 13 | 95 | 5 | 7 | 8452 | 极难 |
| processing__p5.js-5915 | p5.js | 6 | 14 | 56 | 3 | 6 | 6303 | 极难 |
| processing__p5.js-4147 | p5.js | 12 | 28 | 684 | 2 | 2 | 4679 | 极难 |
| diegomura__react-pdf-433 | react-pdf | 5 | 8 | 936 | 4 | 6 | 4353 | 极难 |
| chartjs__Chart.js-8650 | Chart.js | 6 | 10 | 46 | 73 | 1 | 3520 | 极难 |


#### 搜索空间背景

`MM-IR/data/swebench_multimodal-full-candidates/repo_structures` 中有 102 个结构文件。由于该 dev split 只覆盖 5 个仓库，仓库搜索空间在每个仓库内高度重复：wp-calypso 和 Chart.js 类样本会反复面对同一大型前端仓库。这里的仓库规模不是 benchmark 样本复杂度本身，但会直接影响检索和函数级 rerank 的难度。

### 2.2 OmniGIRL 原始全量 959

数据来源：`/home/like/locCode/OmniGIRL/omnigirl/harness/benchmark/OmniGIRL.json` 和 `/home/like/locCode/MM-IR/data/omnigirl-full-candidates/source_omnigirl_full.jsonl`。二者均为 959 条。

| 统计项 | 数值 |
|---|---:|
| 原始样本数 | 959 |
| 语言分布 | Python 374；JavaScript 270；TypeScript 210；Java 105 |
| 仓库数量 | 15 个主要仓库 |
| Top 仓库 | mypy 189；prettier 119；tailwindcss 100；dayjs 93；babel 79；statsmodels 76；webpack 58；netty 54 |
| 平均 gold 文件数 | 2.2 |
| 中位 gold 文件数 | 1 |
| 最大 gold 文件数 | 131 |
| 平均 hunk 数 | 5.0 |
| 中位 hunk 数 | 2 |
| 最大 hunk 数 | 136 |
| 平均 patch 行数 | 46.3 |
| 中位 patch 行数 | 16 |
| 最大 patch 行数 | 1657 |
| 平均 issue 长度 | 1885.4 字符 |
| 中位 issue 长度 | 1375 字符 |
| 显式 `image_urls` 字段 | 19/959 |
| 图片链接/Markdown 图片痕迹 | 70/959 |
| 有 URL | 631/959 |
| 有复现代码/步骤 | 794/959 |
| 有运行错误或 stack 线索 | 308/959 |
| 图片数 | 平均 0.1；中位 0；最大 8 |
| URL 数 | 平均 1.3；中位 1；最大 20 |
| 代码块数 | 平均 1.9；中位 2；最大 12 |
| 样本复杂度分布 | 简单 173；中等 425；困难 289；极难 72 |

OmniGIRL 和 SWE-bench Multimodal 的差异很明显：OmniGIRL 并不是每条都有图片，但复现代码和外部链接非常多，语言更多、仓库更多。它更像“多语言 issue + 复现代码 + URL”的定位任务，而不是纯视觉 UI 定位任务。

语言和仓库分布很重要：

| 语言 | 数量 | 常见机制 |
|---|---:|---|
| Python | 374 | 类型检查、运行错误、库 API 行为、测试失败、数据处理 |
| JavaScript | 270 | parser/formatter、日期时间、构建工具、前端库行为 |
| TypeScript | 210 | 类型/配置/构建、Tailwind/webpack/prettier 等工具链 |
| Java | 105 | Netty/Gson/AssertJ 等库 API、异常和协议行为 |

代表困难/极难样本：

| 样本 | 仓库 | Gold 文件 | Hunk | Patch 行 | 图片 | URL | Issue 长度 | 复杂度 |
|---|---|---:|---:|---:|---:|---:|---:|---|
| tqdm__tqdm-834 | tqdm | 13 | 21 | 86 | 1 | 5 | 2241 | 极难 |
| python__mypy-12762 | mypy | 5 | 15 | 186 | 0 | 3 | 7071 | 极难 |
| webpack__webpack-18319 | webpack | 7 | 23 | 148 | 0 | 4 | 2248 | 极难 |
| webpack__webpack-14784 | webpack | 8 | 17 | 166 | 0 | 3 | 2383 | 极难 |
| tailwindlabs__tailwindcss-4335 | tailwindcss | 5 | 10 | 59 | 0 | 5 | 4373 | 极难 |
| statsmodels__statsmodels-8648 | statsmodels | 7 | 27 | 210 | 0 | 5 | 3923 | 极难 |

### 2.3 OmniGIRL 当前可运行候选 631

本地 `MM-IR/data/omnigirl-full-candidates/summary.json` 显示：原始 `source_rows=959`，但当前 `candidate_rows=631`，并且 `repo_structures` 目录中有 631 个结构文件。因此，当前可直接运行 MM-IR、三层评估和局部机制图原型的是这 631 条。

| 统计项 | 数值 |
|---|---:|
| 可运行候选样本数 | 631 |
| 语言分布 | JavaScript 207；Python 202；TypeScript 172；Java 50 |
| 仓库分布 | mypy 114；prettier 114；tailwindcss 90；babel 58；webpack 51；dayjs 42；statsmodels 34；netty 28 |
| 平均 gold 文件数 | 2.1 |
| 中位 gold 文件数 | 1 |
| 最大 gold 文件数 | 27 |
| 平均 hunk 数 | 4.8 |
| 中位 hunk 数 | 2 |
| 最大 hunk 数 | 54 |
| 平均 patch 行数 | 44.8 |
| 中位 patch 行数 | 16 |
| 最大 patch 行数 | 746 |
| 平均 issue 长度 | 2223.7 字符 |
| 中位 issue 长度 | 1580 字符 |
| 显式 `image_urls` 字段 | 48/631 |
| 图片链接/Markdown 图片痕迹 | 70/631 |
| 有 URL | 631/631 |
| 有复现代码/步骤 | 547/631 |
| 有运行错误或 stack 线索 | 212/631 |
| 样本复杂度分布 | 简单 86；中等 275；困难 207；极难 63 |

注意：这 631 条不是 OmniGIRL 原始全量，而是当前本地可直接参与 MM-IR 候选构建和定位评估的子集。它比原始 959 更偏向有 URL 和有可构建结构的样本，因此用于方法验证是合理的，但写论文或专利时必须说明筛选口径。

## 3. Gold Patch、Hunk 与三层 Gold 分布补充分析

这一节专门解释 `gold patch`、`hunk`、`gold file/module/function` 的统计口径。前面的统计更多是 benchmark 总体画像；这里进一步回答一个更具体的问题：**大多数样本的真实修改文件数是不是在 10 到 15 个以内？如果文件数不多，module/function 数是否一定更多？**

### 3.1 先理解 hunk 是什么

`gold patch` 是真实修复补丁，也就是 benchmark 给出的标准答案。它通常长这样：

```diff
diff --git a/src/a.py b/src/a.py
--- a/src/a.py
+++ b/src/a.py
@@ -30,7 +30,9 @@ def foo():
-    old_value = 1
+    new_value = 2
```

这里的 `@@ -30,7 +30,9 @@` 就是一个 **hunk**。可以把 hunk 理解为“同一个文件里一段连续的修改上下文”。一个文件可以有多个 hunk；一个样本也可以同时修改多个文件。比如：

- `gold file = 2`：真实补丁改了 2 个文件。
- `hunk = 5`：这 2 个文件里一共有 5 段分散修改。
- `patch changed lines = 37`：补丁里真正新增/删除的行数大约是 37 行，不包括普通上下文行。

所以 hunk 数比文件数更细：一个样本只改 1 个文件，但如果在这个文件中改了 8 个相隔很远的位置，那么它就是 `gold file=1, hunk=8`。这类样本对函数定位仍然可能很难，因为不同 hunk 可能落在不同函数里。

### 3.2 文件、模块、函数 gold 的计算口径

这里的统计和三层评估保持一致：

- **Gold File**：真实 patch 涉及的文件数，主要来自样本 `files` 字段和 patch 文件头。
- **Gold Module**：真实修改行落入的类、父级模块或文件级模块。
- **Gold Function**：真实修改行落入的函数或方法。

需要特别注意：**module/function 不是直接从 patch 文件数量推出来的，而是把 patch 修改行映射到 `repo_structures` 里的代码实体后得到的。**

因此会出现三种情况：

1. 一个文件里改了多个函数：`function 数 > file 数`。
2. 一个文件只改了一个函数：`function 数 = file 数`。
3. 修改落在 import、配置、常量、测试数据、快照或顶层非函数区域：`function 数 < file 数`，甚至 function 为 0。

这里表格里的 `0` 很容易误解。它**不是说这个样本没有修改文件，也不是说 gold patch 为空**；它只表示：这个样本的真实修改行，在当前 `repo_structures` 抽取出的 class/function 范围里没有找到可对应的 module/function 实体。换句话说，file-level 仍然有标准答案，但 module/function-level 在当前实体映射口径下为空。

常见原因包括：

- patch 改的是 `import`、顶层常量、配置项、测试数据、快照文件、JSON/YAML/Markdown、样式文件等非函数区域；
- patch 改的是文件顶部或文件底部的模块级代码，没有落入任何函数或类；
- 语言或语法结构比较特殊，当前结构抽取器没有识别出对应函数；
- repo structure 缺失、结构文件不完整，或者函数起止行范围不准，导致真实修改行无法和实体重叠。

所以 `function 数 = 0` 的含义更准确地说是：**函数级 gold 在当前评估结构里不可映射**，而不是“这个样本不需要改代码”。

所以“文件数 10 到 15 个以内”并不等于“函数数也一定 10 到 15 个以内”。对于大文件或多 hunk 样本，function 数可能明显更多。

### 3.3 SWE-bench Multimodal dev 全量 102 的 Gold 分布

数据来源：`MM-IR/data/swebench_multimodal-full-candidates/samples.jsonl` 和对应 `repo_structures`。

| 指标 | 平均 | 中位数 | P75 | P90 | 最大值 |
|---|---:|---:|---:|---:|---:|
| Gold 文件数 | 3.87 | 2 | 5 | 8 | 36 |
| Hunk 数 | 9.35 | 4.5 | 10 | 22 | 128 |
| Patch 变更行数 | 131.68 | 35 | 95 | 271 | 2904 |
| Gold module 数 | 2.67 | 2 | 3 | 4 | 43 |
| Gold function 数 | 5.46 | 3 | 5 | 9 | 121 |

文件数分布：

| Gold 文件数区间 | 样本数 |
|---|---:|
| 1 | 38 |
| 2 | 21 |
| 3 | 12 |
| 4-5 | 9 |
| 6-10 | 16 |
| 11-15 | 3 |
| >15 | 3 |

module/function 分布：

| 区间 | Module 样本数 | Function 样本数 |
|---|---:|---:|
| 0 | 5 | 5 |
| 1 | 43 | 25 |
| 2 | 27 | 18 |
| 3 | 10 | 15 |
| 4-5 | 10 | 15 |
| 6-10 | 4 | 16 |
| 11-15 | 1 | 4 |
| 16-30 | 1 | 2 |
| >30 | 1 | 2 |

结论很明确：**SWE-bench Multimodal dev 全量中，96/102 个样本的 gold 文件数不超过 10，99/102 个样本不超过 15。** 也就是说，从文件数量看，大多数样本确实在 10 到 15 个文件以内。但函数级别有明显长尾：有 43/102 个样本的 `function 数 > file 数`，说明不少样本虽然文件不多，但每个文件里修改了多个函数。

文件数最多的样本：

| 样本 | Gold 文件 | Gold module | Gold function | Hunk | Patch 行 |
|---|---:|---:|---:|---:|---:|
| diegomura__react-pdf-1285 | 36 | 43 | 121 | 128 | 2904 |
| Automattic__wp-calypso-25160 | 24 | 21 | 50 | 103 | 1821 |
| Automattic__wp-calypso-26816 | 20 | 2 | 2 | 22 | 341 |
| Automattic__wp-calypso-34597 | 15 | 11 | 22 | 48 | 271 |
| Automattic__wp-calypso-27090 | 13 | 3 | 6 | 24 | 30 |

这里可以看到一个关键现象：**文件数和函数数不是线性关系。** `Automattic__wp-calypso-26816` 有 20 个文件，但只映射到 2 个函数；而 `processing__p5.js-4147` 只有 12 个文件，却有 26 个函数。原因通常是 patch 是否落在可识别函数内部，以及单文件内有多少个分散 hunk。

### 3.4 OmniGIRL 原始全量 959 与可运行候选 631 的 Gold 分布

OmniGIRL 原始全量 959 可以可靠统计文件和 hunk；module/function 需要本地 `repo_structures`，因此三层统计使用当前可运行候选 631。

原始全量 959 的文件和 hunk 分布：

| 指标 | 平均 | 中位数 | P75 | P90 | 最大值 |
|---|---:|---:|---:|---:|---:|
| Gold 文件数 | 2.21 | 1 | 2 | 4 | 131 |
| Hunk 数 | 5.02 | 2 | 5 | 11 | 136 |
| Patch 变更行数 | 46.33 | 16 | 42 | 105 | 1657 |

| Gold 文件数区间 | 样本数 |
|---|---:|
| 1 | 601 |
| 2 | 162 |
| 3 | 73 |
| 4-5 | 64 |
| 6-10 | 42 |
| 11-15 | 9 |
| >15 | 8 |

OmniGIRL 原始全量中，951/959 个样本的 gold 文件数不超过 15。它比 SWE-bench Multimodal 更偏单文件或少文件修改，但也有极端长尾，例如 `iamkun__dayjs-793` 修改了 131 个文件。

当前可运行候选 631 的三层分布：

| 指标 | 平均 | 中位数 | P75 | P90 | 最大值 |
|---|---:|---:|---:|---:|---:|
| Gold 文件数 | 2.05 | 1 | 2 | 4 | 27 |
| Hunk 数 | 4.82 | 2 | 5 | 11 | 54 |
| Patch 变更行数 | 44.80 | 16 | 46 | 97 | 746 |
| Gold module 数 | 1.91 | 1 | 2 | 4 | 23 |
| Gold function 数 | 3.96 | 1 | 4 | 9 | 100 |

文件数分布：

| Gold 文件数区间 | 样本数 |
|---|---:|
| 1 | 395 |
| 2 | 106 |
| 3 | 52 |
| 4-5 | 45 |
| 6-10 | 23 |
| 11-15 | 4 |
| >15 | 6 |

module/function 分布：

| 区间 | Module 样本数 | Function 样本数 |
|---|---:|---:|
| 0 | 146 | 159 |
| 1 | 218 | 160 |
| 2 | 132 | 92 |
| 3 | 51 | 57 |
| 4-5 | 41 | 62 |
| 6-10 | 35 | 55 |
| 11-15 | 4 | 22 |
| 16-30 | 4 | 11 |
| >30 | 0 | 13 |

这张表里的 `0` 行要按上面的口径理解：这些样本并不是没有真实修改，而是它们的真实修改没有被映射成 module/function gold。比如一个样本只修改配置、快照、顶层常量或 import，那么 file-level 可以正常计算，但 function-level 就可能是 0。对于 OmniGIRL 候选集，`0` 的数量偏高，也提示我们在解释 module/function 统计时要同时考虑结构抽取覆盖率，不能把它简单理解为“没有函数需要修改”。

这里有两个非常重要的结论：

1. **OmniGIRL 候选 631 里 625/631 个样本的 gold 文件数不超过 15。** 也就是说，绝大多数样本在 file-level 上并不夸张。
2. **但 function 数仍然有长尾。** 258/631 个样本的 `function 数 > file 数`，说明少文件修改仍可能对应多个函数级目标。

典型长尾样本：

| 样本 | Gold 文件 | Gold module | Gold function | 说明 |
|---|---:|---:|---:|---|
| webpack__webpack-15579 | 16 | 16 | 100 | 少量文件内密集覆盖大量函数 |
| webpack__webpack-17249 | 17 | 12 | 81 | 构建工具链大型补丁 |
| webpack__webpack-17946 | 18 | 7 | 79 | 多 hunk、多函数修改 |
| iamkun__dayjs-1459 | 27 | 7 | 9 | 文件多，但函数数量不同比例膨胀 |
| google__gson-2397 | 16 | 9 | 11 | 文件数和函数数接近 |

### 3.5 两个统一 60 子集的 Gold 分布

两个 60 子集是我们当前主要用于 baseline 横向比较的统一实验集，因此需要单独看。

#### SWE-bench Multimodal 60

| 指标 | 平均 | 中位数 | P75 | P90 | 最大值 |
|---|---:|---:|---:|---:|---:|
| Gold 文件数 | 4.48 | 2 | 6 | 8 | 36 |
| Hunk 数 | 11.15 | 5 | 11 | 22 | 128 |
| Patch 变更行数 | 177.22 | 37 | 95 | 341 | 2904 |
| Gold module 数 | 3.28 | 1 | 3 | 6 | 43 |
| Gold function 数 | 7.13 | 3 | 6 | 12 | 121 |

| Gold 文件数区间 | 样本数 |
|---|---:|
| 1 | 22 |
| 2 | 10 |
| 3 | 7 |
| 4-5 | 5 |
| 6-10 | 11 |
| 11-15 | 2 |
| >15 | 3 |

SWE60 中 55/60 个样本文件数不超过 10，57/60 个样本文件数不超过 15。只有 3 个样本落在 10-15 文件区间：

| 样本 | Gold 文件 | Gold module | Gold function |
|---|---:|---:|---:|
| Automattic__wp-calypso-33948 | 10 | 3 | 10 |
| Automattic__wp-calypso-34597 | 15 | 11 | 22 |
| processing__p5.js-4147 | 12 | 8 | 26 |

这 3 个样本的平均 function 数是 19.33，最大 26。也就是说，**当文件数达到 10-15 时，函数级目标很可能比文件数更多**，尤其是前端/UI 或渲染类仓库里的分散修改。

#### OmniGIRL unified60

| 指标 | 平均 | 中位数 | P75 | P90 | 最大值 |
|---|---:|---:|---:|---:|---:|
| Gold 文件数 | 1.13 | 1 | 1 | 1 | 3 |
| Hunk 数 | 1.58 | 1 | 2 | 2 | 8 |
| Patch 变更行数 | 9.98 | 4 | 9 | 28 | 105 |
| Gold module 数 | 1.00 | 1 | 1 | 2 | 10 |
| Gold function 数 | 1.12 | 1 | 2 | 2 | 9 |

| Gold 文件数区间 | 样本数 |
|---|---:|
| 1 | 54 |
| 2 | 4 |
| 3 | 2 |
| 4-5 | 0 |
| 6-10 | 0 |
| 11-15 | 0 |
| >15 | 0 |

Omni60 与 SWE60 很不一样：它几乎都是单文件小补丁，100% 样本不超过 3 个文件。这里 function 数不一定比文件数更多：

| 关系 | 样本数 |
|---|---:|
| function 数 > file 数 | 17 |
| function 数 = file 数 | 20 |
| function 数 < file 数 | 23 |

出现 `function 数 < file 数` 的主要原因是修改落在非函数区域，例如配置、顶层常量、测试数据、import、类型定义或结构解析不到的区域。这不是评估错误，而是实体级评估的自然结果。

### 3.6 结论：文件数大多不高，但函数级定位仍然更难

综合看，两个 benchmark 的 gold patch 文件数量确实大多在 10 到 15 个以内：

| 数据集 | 样本数 | Gold 文件 <= 10 | Gold 文件 <= 15 |
|---|---:|---:|---:|
| SWE-bench Multimodal dev 102 | 102 | 96 | 99 |
| SWE-bench Multimodal 60 | 60 | 55 | 57 |
| OmniGIRL 原始 959 | 959 | 942 | 951 |
| OmniGIRL 可运行 631 | 631 | 621 | 625 |
| OmniGIRL unified60 | 60 | 60 | 60 |

但这不代表 module/function 定位一定简单。原因有三点：

1. **一个文件可以包含多个真实修改函数。** SWE60 中有 27/60 个样本 function 数大于 file 数；Omni 候选 631 中有 258/631 个样本 function 数大于 file 数。
2. **hunk 数体现修改分散程度。** 文件数只有 1-2 个时，如果 hunk 很多，函数级定位仍可能覆盖多个实体。
3. **非函数修改会造成 function gold 为 0。** 这类样本不能简单理解为“函数定位失败”，而是 gold patch 本身不落在函数实体里。

因此，写结果分析时建议使用下面这句话作为核心口径：

> 从 file-level 看，两个 benchmark 的 gold patch 大多数都在 10-15 个文件以内，OmniGIRL 更偏单文件小补丁；但 module/function-level 的目标数量由真实修改行和 repo structure 共同决定。一个文件可能映射到多个函数，也可能完全不映射到函数。因此函数级定位不是 file-level 的简单缩小版，而是更依赖代码结构和 hunk 分布的实体级定位任务。
