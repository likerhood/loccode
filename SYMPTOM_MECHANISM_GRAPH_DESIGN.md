# 面向多语言多模态 Issue 定位的“症状-机制-代码”局部机制图方案

本文档记录一个新的定位范式：先用 MM-IR 建立候选池，再把多模态证据转化为可执行诊断动作，最后围绕候选和证据构建小型局部机制图。它不是 GraphLocator 式的全仓库 skeleton graph，也不是简单把 OCR 文本拼进 prompt，而是让每条证据触发具体、可验证、可剪枝的搜索动作。

## 1. 相关工作给我们的启发

SweRank 把 issue localization 明确建模为代码排序任务，用 retrieve-and-rerank 找到相关函数，并通过 SweLoc 的一致性过滤和 hard-negative mining 提高训练数据质量。这个视角提醒我们：定位首先是排序问题，尤其是函数级排序，而不是纯生成问题。参考：<https://arxiv.org/html/2505.07849v2>。

CoSIL 强调 LLM 上下文窗口无法容纳完整仓库，因此需要动态构建代码图并剪枝搜索空间。这个结论直接对应我们在 GraphLocator 上看到的慢和崩溃问题：全量图太重，局部动态图更合理。参考：<https://arxiv.org/html/2503.22424v1>。

GALA 已经把截图构造成 Image UI Graph，并和代码图做跨模态对齐。它证明“视觉图 + 代码图”是有价值的，但我们本地结果也说明，仅做视觉-代码结构对齐仍容易停在表层 UI 文件，函数级闭环不稳定。参考：<https://arxiv.org/html/2604.08089v1>。

ARISE 强调 statement-level def-use 和 data-flow slicing，因为结构图只能说明相关，不能说明值如何传播到错误点。这对 `Cannot read property 'ID' of null` 这类样本尤其关键。参考：<https://arxiv.org/html/2605.03117v1>。

代码 RAG 方向也在从单一检索走向 sparse/dense/graph/hybrid/agent 检索组合。我们的 MM-IR 候选池可以作为第一阶段召回，但后续需要机制化 rerank。参考：<https://arxiv.org/html/2510.04905v1>。

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

### 2.4 证据来源分布与诊断动作映射

这里把 issue 中可用的信息拆成“证据来源”，再映射到后续的诊断动作。这个统计使用的是启发式规则：URL 来自结构字段和正文链接；图片分为显式 `image_urls` 字段和 Markdown/图片链接痕迹；复现代码/步骤由 `Steps to reproduce`、`expected/actual`、代码块、行内代码等模式识别；错误日志由 `error/exception/traceback/typeerror/cannot read/null/undefined/failed` 等模式识别；配置文本由 `webpack/babel/tailwind/package.json/tsconfig/plugin/loader/config` 等词识别。因此它不是人工标注标签，而是为了说明“每类证据在 benchmark 中是否足够常见，能不能设计成稳定动作”。

| 证据来源 | 是否必须 | 例子 | 对应诊断动作 | SWE dev 102 | OmniGIRL 原始 959 | OmniGIRL 候选 631 |
|---|---|---|---|---:|---:|---:|
| Issue 文本 | 必须 | `rightmost point clipped`、`subscriber redirect loop` | 基础 query、候选召回、概念归因 | 102/102 (100.0%) | 959/959 (100.0%) | 631/631 (100.0%) |
| 复现代码/步骤 | 常见 | `for (await of ...)`、`Steps to reproduce`、代码块 | `parser_context_search`、`repro_context_search` | 97/102 (95.1%) | 936/959 (97.6%) | 628/631 (99.5%) |
| 错误日志/失败语义 | 常见 | `Cannot read property 'ID' of null`、`TypeError`、`failed` | `dataflow_backward_trace`、异常点反向切片 | 48/102 (47.1%) | 510/959 (53.2%) | 404/631 (64.0%) |
| 显式图片字段 | 可选 | `image_urls` 中的截图链接 | OCR/视觉结构抽取入口 | 102/102 (100.0%) | 19/959 (2.0%) | 48/631 (7.6%) |
| 图片链接/Markdown 图片痕迹 | 可选 | `![](...)`、`<img ...>`、`user-images` | OCR/截图下载候选入口 | 102/102 (100.0%) | 70/959 (7.3%) | 70/631 (11.1%) |
| 视觉语义线索 | 可选 | clipped、layout、color、button、chart、render | `visual_mechanism_probe` | 102/102 (100.0%) | 296/959 (30.9%) | 270/631 (42.8%) |
| URL / 外部页面 | 可选 | CodePen、Babel REPL、GitHub、docs | `external_repro_parser`、route/API anchor search | 102/102 (100.0%) | 632/959 (65.9%) | 631/631 (100.0%) |
| 配置/构建文本 | 可选 | webpack、tailwind、babel config、package.json | `config_dependency_search` | 39/102 (38.2%) | 579/959 (60.4%) | 452/631 (71.6%) |
| 路由/路径片段 | 可选 | `/jetpack/connect/plans`、`/api/foo`、文件路径 | route search、path/symbol anchor search | 102/102 (100.0%) | 820/959 (85.5%) | 631/631 (100.0%) |

这个分布说明两个 benchmark 的证据结构并不一样：

- **SWE-bench Multimodal dev 是强多模态定位集**：102 条全部有图片和 URL，视觉语义线索也基本全覆盖。因此，视觉机制探针、外部页面解析、URL/route anchor 都应该是一等动作。
- **OmniGIRL 原始 959 更像多语言 issue 定位集**：只有少量样本有真实图片字段，但复现代码/步骤、URL、配置/构建文本、错误失败语义非常常见。因此，不能把方法讲成“必须有图片才能工作”，而应该讲成“多源证据驱动”：有图时走视觉机制探针；没有图时走复现上下文、错误反向切片、配置依赖和符号搜索。
- **OmniGIRL 候选 631 有明显筛选偏置**：当前本地候选集 631 条全部有 URL，配置/构建文本和错误失败语义比例也更高，所以它更适合验证 URL/配置/错误驱动的诊断动作，但不能代表原始 959 的完整分布。

把这些证据进一步压成动作覆盖率，可以得到：

| 诊断动作 | 触发条件 | SWE dev 102 | OmniGIRL 原始 959 | OmniGIRL 候选 631 |
|---|---|---:|---:|---:|
| Anchor Binding Search | URL、路径片段、配置词、字符串锚点 | 102/102 (100.0%) | 852/959 (88.8%) | 631/631 (100.0%) |
| State/Dataflow Trace | 错误日志、null/undefined、失败语义 | 48/102 (47.1%) | 510/959 (53.2%) | 404/631 (64.0%) |
| Visual Mechanism Probe | 显式图片、图片痕迹、视觉语义 | 102/102 (100.0%) | 296/959 (30.9%) | 270/631 (42.8%) |
| Repro/Config Context Search | 复现代码/步骤或配置/构建文本 | 97/102 (95.1%) | 941/959 (98.1%) | 629/631 (99.7%) |

因此，局部机制图不应被设计成“图片/OCR 专用图”。更稳的设计是：

```text
EvidenceExtractor
  -> Issue 文本证据：所有样本都有，负责基础召回和症状概念化
  -> 复现代码证据：触发 parser/API/config 上下文搜索
  -> 错误日志证据：触发 dataflow backward trace
  -> 图片/OCR/视觉证据：触发 visual mechanism probe
  -> URL 证据：触发 external repro parser 和 route/API anchor search
  -> 配置文本证据：触发 config dependency search
```

这样即使某个样本只有 issue 文本和代码块，也仍然可以形成闭环：`Issue text -> ConceptNode -> Repro/Config action -> Symbol/String/Config index -> Local mechanism graph -> CodeNode ranking`。图片和 URL 是增强证据，不是方法成立的前提。

### 2.5 60 子集的位置

之前文档中的 `SWE-bench Multimodal 60` 和 `OmniGIRL 48/60` 是我们为了快速跑 LocAgent、CoSIL、GraphLocator、GALA、MM-IR 而准备的实验子集。它们可以用于 baseline 对比和案例分析，但不能代表全量 benchmark 画像。

正确表述应为：

- 全量数据集画像：SWE-bench Multimodal dev 102；OmniGIRL 原始 959；OmniGIRL 当前可运行候选 631。
- 实验子集结果：SWE 60；OmniGIRL 48/60 或 GALA JS/TS 子集。
- 方法动机和复杂度分析应优先引用全量画像，baseline 指标分析可以引用实验子集。

## 3. 复杂度分类建议

参考 SweRank 将 issue localization 视作代码排序任务，我们对每个样本设计一个定位复杂度分数。这里必须以样本级因素为主，仓库规模只作为搜索空间修正项：

```text
C_gold_spread      gold 文件数量，衡量修改目标是否分散
C_patch_span       hunk 数和 patch 行数，衡量补丁跨度
C_issue_length     issue 文本长度，衡量描述和噪声负担
C_modality         图片、URL、stack、复现代码、视觉症状数量
C_mechanism_gap    表层症状与真实修改点之间是否跨机制
C_search_space     仓库候选文件/函数规模，只作为检索背景惩罚
```

建议分层：

| 分层 | 判断依据 |
|---|---|
| 简单 | 仓库小，gold 单文件，issue 有明显 API/函数名，表层词和修改点接近 |
| 中等 | 仓库中等或大，但 gold 集中；需要解析复现代码、错误文本或外部 URL |
| 困难 | 多模态证据明显，表层视觉位置和真实根因不同；需要 route/dataflow/render 机制追踪 |
| 极难 | 大仓库、多文件 patch、多 hunk、多模态证据、多机制交叉；需要多轮诊断和剪枝 |

这个复杂度比单纯“改了几个文件”更适合多模态定位，因为很多样本只改 1 个文件，但定位难点在于症状到机制的距离很远，例如 Babel parser context 或 p5.js WebGL alpha blending。

## 4. Baseline 失败案例与机制图建模

### 4.1 Jetpack Connect 显示错误页面

样本：`Automattic__wp-calypso-21492`

真实修改：

- `client/jetpack-connect/authorize.js`
- `client/jetpack-connect/utils.js`

现象：

- URL 是 `/jetpack/connect/plans`
- 截图显示 `Connect a self-hosted WordPress`
- 预期 subscriber 连接后回到 wp-admin

Baseline 问题：

- GALA 找到 `site-url-input.jsx`、`plans.jsx`，因为视觉上最像截图。
- GraphLocator 找到 `client/jetpack-connect/main.jsx`、example components、reducer，命中 Jetpack Connect 表层区域，但没有追到 auth redirect。
- MM-IR 能召回 `authorize.js`，但函数级容易被 `renderTermsOfServiceLink` 之类视觉文本函数吸走。

机制图应这样构建：

```text
EvidenceNode(URL_PATH: /jetpack/connect/plans)
EvidenceNode(TEXT: subscriber)
EvidenceNode(FLOW: approve connection -> redirect loop)
ConceptNode(AUTH_REDIRECT)
ConceptNode(ROLE_SCOPE)
ActionNode(route_auth_redirect_search)
CodeNode(authorize.js::redirect)
CodeNode(utils.js::getRoleFromScope)

URL_PATH --triggers_action--> route_auth_redirect_search
subscriber --explains_symptom--> ROLE_SCOPE
ROLE_SCOPE --flows_to--> AUTH_REDIRECT
AUTH_REDIRECT --matches_code--> authorize.js::redirect
ROLE_SCOPE --matches_code--> utils.js::getRoleFromScope
```

关键是给 `site-url-input.jsx` 一个 surface-only penalty：它解释截图内容，但不能解释 subscriber redirect loop。

### 4.2 Help Contact Form 空主站点崩溃

样本：`Automattic__wp-calypso-21769`

真实修改：

- `client/me/help/help-contact-form/index.jsx`
- `client/state/help/selectors.js`

现象：

- console 报 `Cannot read property 'ID' of null`
- Contact form 页面一直 loading
- 用户没有 primary site / selected site

Baseline 问题：

- GALA 能找到 `help-contact-form/index.jsx`，但 selector 层不稳定。
- GraphLocator 偏到 `jetpack-onboarding/steps/contact-form.jsx`，被 contact-form 名称误导。
- MM-IR 找到 help/contact 周边，但状态 selector 不一定靠前。

机制图：

```text
EvidenceNode(RUNTIME_ERROR: Cannot read property 'ID' of null)
EvidenceNode(UI_TEXT: Loading contact form)
ConceptNode(NULL_STATE)
ActionNode(null_state_backward_slice)
FlowNode(PROP: selectedSite)
CodeNode(help-contact-form/index.jsx::render)
CodeNode(state/help/selectors.js::getHelpSelectedSite)

RUNTIME_ERROR --triggers_action--> null_state_backward_slice
NULL_STATE --flows_to--> selectedSite
selectedSite --reads_state--> getHelpSelectedSite
selectedSite --used_by--> render
```

这里需要 dataflow/backward slice，而不是只做文件名或 UI 文本检索。

### 4.3 p5.js WebGL alpha blending

样本：`processing__p5.js-5855`

症状：

- `blendMode(MULTIPLY)`
- WebGL text transparent texture alpha ignored
- glyph 显示成实心矩形

Baseline 问题：

- CoSIL 找到 `p5.RendererGL.js`、`p5.Font.js`。
- MM-IR 能召回 `src/webgl/material.js`、`src/typography/loading_displaying.js`、`src/image/pixels.js`。
- 但函数级缺少 `alpha -> blend/material/shader/texture` 的机制路径。

机制图：

```text
EvidenceNode(VISUAL_ANOMALY: opaque glyph rectangles)
EvidenceNode(REPRO_CODE: blendMode(MULTIPLY), text(), WEBGL)
ConceptNode(ALPHA_BLEND)
ConceptNode(TEXTURE_GLYPH)
ActionNode(visual_render_mechanism_probe)
CodeNode(src/webgl/material.js::*)
CodeNode(src/webgl/p5.RendererGL.js::*)
CodeNode(shader/material/texture functions)

VISUAL_ANOMALY --explains_symptom--> ALPHA_BLEND
REPRO_CODE --mentions--> blendMode
ALPHA_BLEND --triggers_action--> visual_render_mechanism_probe
visual_render_mechanism_probe --expands_to--> material/shader/texture pipeline
```

这个样本说明视觉证据应该转成渲染机制，而不是只转成 `text/WebGL` 搜索词。

### 4.4 Chart.js 右侧点被裁剪

样本：`chartjs__Chart.js-8650`

症状：

- rightmost data point clipped
- tooltip works
- line chart, no plugin

Baseline 问题：

- GALA/MM-IR 都能找到 `controller.line.js`、`element.point.js`、`helpers.canvas.js`、`core.layouts.js` 等文件。
- 但函数级需要区分“tooltip 正常说明数据模型正常，渲染边界/clip 有问题”。

机制图：

```text
EvidenceNode(VISUAL_ANOMALY: rightmost point clipped)
EvidenceNode(TEXT: tooltip displayed fine)
ConceptNode(LAYOUT_CLIP)
ConceptNode(CHART_AREA_BOUNDS)
ActionNode(visual_layout_boundary_probe)
CodeNode(controller.line.js::*)
CodeNode(core.layouts.js::*)
CodeNode(helpers.canvas.js::*)
CodeNode(element.point.js::*)

VISUAL_ANOMALY --explains_symptom--> LAYOUT_CLIP
tooltip works --rules_out--> data_model_error
LAYOUT_CLIP --triggers_action--> visual_layout_boundary_probe
visual_layout_boundary_probe --searches--> clip/chartArea/padding/pointRadius
```

这里的关键动作是“反证”：tooltip 正常可以降低数据解析函数分数，提高绘制边界函数分数。

### 4.5 Babel await identifier parser crash

样本：`babel__babel-15134`

症状：

- `for( await of [1, 2, 3] )`
- Babel crash
- Node 可以执行
- 外部 Babel REPL URL

Baseline 问题：

- 普通检索容易搜 `await`，但 `await` 在 Babel 仓库里太常见。
- Graph 方法如果只看 import/call，也不知道关键上下文是 `ForInOfHead`。

机制图：

```text
EvidenceNode(REPRO_CODE: for (await of ...))
EvidenceNode(WEB_URL: Babel REPL)
ConceptNode(PARSER_CONTEXT)
ConceptNode(IDENTIFIER_VS_KEYWORD)
ActionNode(parser_context_search)
CodeNode(parser/expression/statement/lval/tokenizer functions)

REPRO_CODE --extracts--> token await
REPRO_CODE --extracts--> ForInOfHead
PARSER_CONTEXT --triggers_action--> parser_context_search
parser_context_search --searches--> parseFor / checkReservedWord / parseIdentifier
```

这个例子说明外部 URL 不是为了泄露 patch，而是为了提取复现代码和 parser context。

## 5. 四类诊断动作

### 5.1 表层锚点绑定动作

适用证据：

- URL path
- OCR 文本
- i18n 文案
- error message
- API 名称

动作：

```text
route_search
string_literal_search
i18n_key_search
public_api_entry_search
parser_token_search
```

作用：把多模态文本证据绑定到可能的入口点，而不是让 LLM 自由猜关键词。

### 5.2 状态/数据流回溯动作

适用证据：

- null/undefined
- Cannot read property
- stack trace
- state/prop 异常
- selector/reducer 相关问题

动作：

```text
property_access_search
backward_state_slice
selector_reducer_expansion
def_use_slice
```

作用：从报错点回溯变量来源，解决“表面组件正确但根因在状态 selector”的问题。

### 5.3 视觉机制探针动作

适用证据：

- 截图裁剪
- 颜色/透明度异常
- 布局错位
- canvas/WebGL/chart/pdf 渲染异常

动作：

```text
visual_anomaly_classifier
domain_concept_expand
render_pipeline_search
layout_boundary_probe
shader_material_probe
```

作用：把视觉症状映射到渲染机制词，如 alpha、blend、clip、chartArea、padding、scale、texture、shader。

### 5.4 外部复现/配置解析动作

适用证据：

- CodePen URL
- Babel REPL URL
- 文档 URL
- package/config/build 描述
- 网页 reproduction

动作：

```text
url_type_classifier
safe_web_fetch
repro_code_extract
config_option_extract
leakage_guard
```

作用：从外部链接提取复现代码、API、配置项；禁止读取 PR/commit diff 里的 patch 泄露内容。

## 6. 局部机制图构建算法

### 6.1 输入

```text
issue text
multimodal compact context
image urls / OCR / visual descriptions
web urls
MM-IR topK files/modules/functions
repo_structures for candidate files
```

### 6.2 节点

```text
EvidenceNode:
  OCR_TEXT / URL_PATH / RUNTIME_ERROR / VISUAL_ANOMALY / REPRO_CODE / WEB_URL

ConceptNode:
  AUTH_REDIRECT / NULL_STATE / ALPHA_BLEND / LAYOUT_CLIP / PARSER_CONTEXT / BUILD_CONFIG

CodeNode:
  FILE / MODULE / FUNCTION / LINE

FlowNode:
  VARIABLE / PROP / STATE_SELECTOR / CONFIG_OPTION

ActionNode:
  route_search / string_search / backward_slice / visual_probe / parser_context_search
```

### 6.3 边

```text
mentions
matches_literal
triggers_action
explains_symptom
routes_to
reads_state
writes_state
flows_to
renders
clips
configures
calls
imports
rules_out
```

### 6.4 构建步骤

```text
1. 用 MM-IR 召回 topK 文件、模块、函数。
2. 从 issue 和多模态上下文抽取 EvidenceNode。
3. 用规则/轻量分类器把 EvidenceNode 映射到 ConceptNode。
4. ConceptNode 触发 1-2 个诊断动作，不允许无限工具调用。
5. 每个动作只在 MM-IR candidate_file_pool 内局部展开。
6. 生成 CodeNode / FlowNode / ActionNode 和边。
7. 根据证据覆盖率、机制路径完整度、MM-IR 排名、局部切片支持度打分。
8. 输出 file/module/function/line 和 evidence chain。
```

## 7. 剪枝策略

### 7.1 预算剪枝

```text
candidate_file_pool = 30~50
candidate_symbols = 80~120
max_actions_per_issue = 3
max_hop = 2
dataflow_slice 只对 top10 函数执行
每个动作最多新增 20 个节点
```

### 7.2 收益剪枝

若某动作没有新增以下任何信息，则停止：

- 新的 gold-like 文件候选
- 新的函数候选
- 新的机制边
- 新的反证边
- 提高 top candidate 分数

### 7.3 表层误导惩罚

如果一个候选只解释截图文本，但不能解释问题机制，降权。

例子：

```text
site-url-input.jsx:
  matches screenshot text: high
  explains subscriber redirect loop: low
  => surface_only_penalty

authorize.js::redirect:
  matches screenshot text: low
  explains auth redirect mechanism: high
  => boost
```

### 7.4 反证剪枝

如果证据说明某机制不太可能，降低相关候选。

例子：

```text
Chart.js tooltip works:
  data parsing likely correct
  rendering boundary likely wrong
  => lower parser/data model candidates
  => boost clip/layout/draw candidates
```

## 8. 为什么可能比现有 baseline 更好

| 方法 | 主要问题 | 新方案对应修复 |
|---|---|---|
| MM-IR | 召回强，但函数级缺少机制解释 | 用机制图 rerank，区分表层匹配和根因解释 |
| LocAgent | 工具调用自由，容易漂移、空输出、格式错 | 诊断动作模板化，输出 schema 校验 |
| CoSIL | 动态图有效，但多模态证据不是中心 | 多模态证据直接触发 route/dataflow/render/parser 动作 |
| GraphLocator | 预构建全仓库图，慢且脆弱 | 只对 MM-IR 候选局部建机制图 |
| GALA | 视觉-代码对齐容易停在表层 UI 文件 | 视觉症状先转成机制概念，再追代码实体 |

## 9. 输出格式建议

最终定位不应只返回文件，而应返回：

```json
{
  "file": "client/jetpack-connect/authorize.js",
  "module": "client/jetpack-connect/authorize.js::JetpackAuthorize",
  "function": "client/jetpack-connect/authorize.js::JetpackAuthorize.redirect",
  "line": 165,
  "evidence_chain": [
    "URL_PATH:/jetpack/connect/plans",
    "TEXT:subscriber",
    "CONCEPT:AUTH_REDIRECT",
    "ACTION:route_auth_redirect_search",
    "CODE:redirect() uses redirectAfterAuth and scope"
  ],
  "confidence": 0.82
}
```

同时 resolver 校验：

- 文件存在
- module/function 在 repo_structures 或本地 parser 中存在
- line 落在函数范围内
- evidence_chain 至少包含一个多模态证据和一个代码证据

## 10. 下一步实验设计

建议先做一个轻量原型，不直接上大模型：

1. 复用 MM-IR 的 BM25 候选池。
2. 为四类诊断动作写规则工具：
   - route/string/API search
   - null-state backward search
   - visual mechanism keyword expansion
   - external repro parser
3. 对 10 个代表样本手工或半自动生成局部机制图。
4. 比较：
   - MM-IR 原始排序
   - MM-IR + 机制图 rerank
   - MM-IR + 机制图 + schema resolver
5. 重点看 function Acc@10 / MRR@15 是否提升。

如果这个小实验成立，再接入 LLM 作为：

- evidence classifier
- mechanism classifier
- candidate explanation scorer

而不是让 LLM 自由决定搜什么。

## 11. 一句话创新表述

现有多模态定位方法多把截图、网页、OCR 转换为额外文本上下文，或把视觉图与代码图做静态对齐；本方案将多模态证据转换为可执行诊断动作，并在检索候选范围内按需构建局部机制图，从而实现从症状、机制到代码实体的可验证闭环定位。





对，我觉得现在应该把方案再“收紧”。不能再说一个听起来很宏大的“异构多层图”，而要变成：

> **MM-IR 负责召回，诊断动作负责追因，局部机制图负责闭环验证。**

也就是说，我们不是为了建图而建图，而是为了回答一个具体问题：

> 这个多模态症状，到底应该触发哪一种代码诊断动作？

我查了一下相关工作，也结合我们本地跑出来的失败样本，比较清楚地看到：CoSIL 强调动态构建调用图和 pruning，避免上下文爆炸；GALA 强调 Image UI Graph 和代码图对齐；ARISE 强调 statement-level def-use 和 data-flow slicing；RAG 方向也强调 sparse/dense/graph/hybrid/agent-style retrieval 的组合。参考：CoSIL [arXiv](https://arxiv.org/html/2503.22424v1)、GALA [arXiv](https://arxiv.org/html/2604.08089v1)、ARISE [arXiv](https://arxiv.org/html/2605.03117v1)、RAG survey [arXiv](https://arxiv.org/html/2510.04905v1)。

**核心判断**
现在最有新意的点不是“我也做一个图”，而是：

> **把多模态内容变成可执行诊断动作，而不是变成一段自然语言 prompt。**

这句话可以继续往下落地为四类动作。

---

**动作一：表层锚点绑定**

这个动作解决的问题是：issue、截图、URL、OCR、报错文本里经常有精确锚点，但 baseline 不知道怎么用。

输入证据：

- URL：`/jetpack/connect/plans`
- OCR 文本：`Terms of Service`
- 错误文本：`Cannot read property 'ID' of null`
- API 调用：`blendMode(MULTIPLY)`
- UI 文案：`Contact Us`, `Loading contact form`

动作不是“把这些词拼进 prompt”，而是生成专门搜索：

```text
url_path         -> route_search / controller_search
ocr_text         -> string_literal_search / i18n_key_search
runtime_error    -> property_access_search / stack_trace_search
api_call         -> public_api_entry_search
component_text   -> jsx_text / translation_search
```

比如 `Automattic__wp-calypso-21492`：

- GALA 找到 `site-url-input.jsx`，因为截图显示 site entry form。
- MM-IR 也容易召回 `site-url-input.jsx`、`plans.jsx`。
- 但真实修复在 `authorize.js::redirect()` 和 `utils.js::getRoleFromScope()`。

所以这个动作应该把 `/jetpack/connect/plans` 和 `subscriber / redirect / scope` 绑定成：

```text
route evidence: /jetpack/connect/plans
role evidence: subscriber
flow evidence: approve connection -> redirect
diagnostic action: route_auth_redirect_search
```

这一步会强制搜索：

```text
authorize
redirectAfterAuth
scope
role
subscriber
wp-admin
```

而不是只搜索截图里的 `site entry` 或 `Terms of Service`。

这就是对 GALA 的改进：GALA 的视觉图会被 site-entry 表象吸走；我们要把表象证据转成“认证重定向机制”的搜索动作。

---

**动作二：状态/数据流追踪**

这个动作解决的问题是：很多 bug 的表面报错不是根因，根因在状态来源。

典型样本：`Automattic__wp-calypso-21769`

真实修复：

- `client/me/help/help-contact-form/index.jsx`
- `client/state/help/selectors.js`

报错：

```text
Cannot read property 'ID' of null
```

baseline 常见失败：

- LocAgent/GraphLocator 容易找 help 页面或 contact component。
- GALA 可以找 `help-contact-form/index.jsx`，但未必能稳定找到 `state/help/selectors.js`。
- MM-IR 能召回一些 help/contact 文件，但 selector 不一定排得靠前。

这里的诊断动作应该是：

```text
runtime_error: Cannot read property 'ID' of null
property: ID
object: selectedSite / site
diagnostic action: null_state_backward_slice
```

工具序列：

```text
1. property_access_search(".ID")
2. find variables before .ID, e.g. selectedSite.ID
3. backward_state_slice(selectedSite)
4. search selectors/actions/reducers that define selectedSite
5. rank functions that can return null or missing fallback
```

局部机制图不是全仓库图，而是：

```text
runtime_error(ID of null)
  -> property_access(selectedSite.ID)
  -> component HelpContactForm.render
  -> prop selectedSite
  -> selector getHelpSelectedSite
  -> fallback missing when primary site is null
```

这比 GraphLocator 的 `HasMember / UsedBy / ImportedBy` 更有针对性。GraphLocator 的图能告诉你文件和函数有什么结构关系，但不一定回答：

> 这个 null 是从哪里流过来的？

ARISE 也正是强调 data-flow slicing 应该是一等工具，因为结构图缺少 statement-level def-use 关系。

---

**动作三：视觉机制探针**

这个动作解决视觉问题：截图不是为了找到“看起来像的 UI 文件”，而是为了识别视觉异常背后的渲染机制。

典型样本一：`processing__p5.js-5855`

症状：

```text
WebGL text + MULTIPLY blend mode
transparent texture alpha ignored
text appears as solid rectangles
```

baseline 现象：

- MM-IR 能召回 `src/webgl/material.js`、`src/typography/loading_displaying.js`、`src/image/pixels.js`。
- CoSIL 找到 `src/webgl/p5.RendererGL.js`、`src/typography/p5.Font.js`。
- 但函数级定位仍容易散。

这里不应该只搜 `text`，而应该把视觉症状映射到机制词：

```text
alpha ignored       -> alpha channel / premultiplied alpha
solid rectangle     -> texture sampling / fragment shader
MULTIPLY            -> blend mode / blend function
WebGL text          -> texture glyph / material / renderer
```

诊断动作：

```text
visual_render_mechanism_probe
```

工具序列：

```text
1. visual_anomaly_classifier(image, issue)
2. concept_expand(alpha ignored -> blendFunc, shader, material, texture)
3. api_entry_search("blendMode", "text", "WEBGL")
4. local_call_slice from public APIs
5. shader/material/render function ranking
```

局部机制图：

```text
visual_anomaly: opaque glyph rectangles
  -> concept: alpha ignored in multiply blending
  -> API: blendMode(MULTIPLY)
  -> API: text()
  -> render pipeline: RendererGL / material / texture / shader
  -> candidate function
```

典型样本二：`chartjs__Chart.js-8650`

症状：

```text
rightmost data point clipped
tooltip works
line chart, no plugin
```

这里应该映射到：

```text
clipped point -> clip rectangle / chartArea / layout padding
tooltip works -> data model correct, rendering bounds wrong
right edge -> x scale / canvas boundary / point radius
```

诊断动作：

```text
visual_layout_boundary_probe
```

工具序列：

```text
1. detect visual anomaly: boundary clipping
2. concept_expand(clip, chartArea, padding, pointRadius, scale bounds)
3. search within MM-IR top files: controller.line, core.layouts, core.scale, helpers.canvas, element.point
4. inspect functions modifying clip/bounds/layout/draw range
5. rerank by mechanism path
```

这一步能解释为什么 MM-IR 文件级效果还不错，但函数级仍不够：它召回了相关文件，但没有把“右边界裁剪”转成 `clip/chartArea/layout bounds` 这条机制链。

---

**动作四：外部复现/配置证据解析**

多模态 benchmark 里很多 issue 有 URL：

- 图片 URL
- CodePen URL
- Babel REPL URL
- docs URL
- GitHub PR/commit URL

这些不能一股脑抓进来。要区分是否泄露 patch。

动作：

```text
external_repro_evidence_parse
```

规则：

```text
image URL       -> OCR / visual anomaly extraction
CodePen/Repl    -> extract repro code, API calls, options
docs URL        -> extract API/config names
GitHub PR diff  -> forbid reading patch content, only keep issue-visible metadata
font/assets URL -> keep as resource type, usually不作为代码定位主证据
```

比如 `babel__babel-15134`：

issue 里有 Babel REPL 链接，核心症状是：

```text
await as identifier in for-in/of head
```

动作不应该只搜 `await`，而应该生成 parser 机制：

```text
syntax token: await
context: ForInOfHead
mechanism: parser/tokenizer/lval/checkReservedWord
```

搜索动作：

```text
parser_token_context_search("await", "ForInOfHead")
```

这比普通 BM25 搜 `await` 更强，因为普通检索会找很多 await 相关文件，但不知道 `for-of head` 是 parser context。

---

**局部机制图怎么构建**

这里的图不是 GraphLocator 那种全仓库 skeleton。它是每个 issue 的小型“案情关系网”。

节点类型：

```text
EvidenceNode:
  OCR_TEXT / URL_PATH / RUNTIME_ERROR / VISUAL_ANOMALY / REPRO_CODE / WEB_URL

ConceptNode:
  AUTH_REDIRECT / NULL_STATE / ALPHA_BLEND / LAYOUT_CLIP / PARSER_CONTEXT / BUILD_CONFIG

CodeNode:
  FILE / MODULE / FUNCTION / LINE

FlowNode:
  VARIABLE / PROP / STATE_SELECTOR / CONFIG_OPTION

ActionNode:
  route_search / string_search / backward_slice / visual_probe / parser_context_search
```

边类型：

```text
mentions
matches_literal
triggers_action
explains_symptom
routes_to
reads_state
writes_state
flows_to
renders
clips
configures
calls
imports
```

一个样本只建几十到几百个节点，不建整个仓库。

大致算法：

```text
1. MM-IR 召回 topK files/functions/strings
2. 抽取多模态证据表
3. 将证据映射到 3-4 类诊断动作
4. 执行动作，生成局部机制图
5. 对候选代码实体打分
6. 剪枝低收益路径
7. 输出 file/module/function/line + evidence chain
```

打分可以设计成：

```text
Score(code_entity) =
  0.30 * MMIR_rank_score
+ 0.25 * evidence_anchor_score
+ 0.25 * mechanism_path_score
+ 0.15 * dataflow_or_route_support
+ 0.05 * multimodal_support
- cost_penalty
- surface_only_penalty
```

这里最关键的是 `surface_only_penalty`。

例如 `site-url-input.jsx` 在 21492 里：

- OCR/text 匹配高
- 视觉相似高
- 但不能解释 subscriber approve 后 redirect loop

所以应该被降权。

`authorize.js::redirect()`：

- OCR 匹配低
- 但能解释 auth role、scope、redirectAfterAuth、wp-admin

所以应该被升权。

这就是从“视觉表象匹配”升级为“症状机制解释”。

---

**剪枝策略怎么做**

不能任由 agent 扩展，否则就变成 GraphLocator/LocAgent 那种慢、漂、上下文爆炸。

我建议三层剪枝。

第一层：证据收益剪枝。

```text
如果一个动作没有新增 code entity、没有新增机制边、没有提高 top candidate 分数，就停止该动作。
```

第二层：机制一致性剪枝。

比如 21492 是 auth redirect 问题，如果候选文件只解释 site entry form，但不解释 redirect/auth/scope，就保留为 context，不继续扩展。

第三层：预算剪枝。

```text
每个 issue:
- MM-IR topK files: 30
- 初始 symbol: 80
- 每个诊断动作最多扩展 2 hop
- dataflow slice 只对 top 10 function 执行
- 每轮最多新增 20 个节点
```

这样新方法不会像 GraphLocator 那样全仓库建图，也不会像 LocAgent 那样工具调用一旦漂了就一路偏。

---

**和已有 baseline 的差异**

1. 相比 MM-IR

MM-IR 强在召回，但弱在“为什么”。它能把 `authorize.js` 拉进候选，但不知道为什么 `redirect()` 比 `site-url-input.jsx::renderTermsOfServiceLink` 更像根因。

新方法用 MM-IR 做候选池，然后用机制图重排。

2. 相比 LocAgent

LocAgent 是 agent 自由搜索，容易出现：

- 搜索词漂移
- tool call 格式错
- finish 空结果
- file-only 输出
- 查到自身工具代码

新方法把搜索动作模板化，LLM 不再随便决定工具，而是只在结构化候选里做判断。

3. 相比 CoSIL

CoSIL 的动态调用图和 pruning 很值得借鉴，但主要面向文本 issue 和代码调用图。新方法把多模态证据变成动作入口：

- URL 触发 route/action
- 截图触发 visual mechanism
- console error 触发 state/dataflow
- external repro 触发 parser/config/API mechanism

4. 相比 GraphLocator

GraphLocator 预构建代码结构图，再搜索结构节点。新方法先用 MM-IR 缩小范围，再按症状构建局部机制图。

所以它不会一上来就解析全仓库，也不会被混合语言和奇怪目录拖死。

5. 相比 GALA

GALA 已经有 Image UI Graph 和 function-level alignment，这是强 baseline。但它仍然容易把视觉元素对齐到“表面 UI 文件”。

新方法更强调：

```text
视觉元素 -> 症状类型 -> 程序机制 -> 代码实体
```

而不是：

```text
视觉元素 -> 相似代码节点
```

这就是创新点。

---

**我建议最终框架名字**

可以叫：

**MIRAGE-Loc：Multimodal Issue Reasoning with Actionable Graph Evidence**

中文可以叫：

**基于可执行证据图的多模态缺陷定位方法**

或者更像专利一点：

**一种面向多语言多模态软件仓库的症状驱动式局部机制图缺陷定位方法**

关键技术特征：

1. 基于 MM-IR 的候选召回。
2. 多模态证据表构建。
3. 证据到诊断动作的规则化映射。
4. 按需构建局部机制图。
5. 基于机制路径的候选重排。
6. 三层定位输出校验。

最重要的一句话是：

> 现有方法把多模态信息变成“额外上下文”，本方法把多模态信息变成“可执行诊断动作”；现有方法构建代码结构图，本方法围绕症状构建局部机制图。

这个点比“加 OCR”“加多语言 parser”“建更大的图”更有专利味，也更符合你这几天实验里观察到的真实失败模式。
