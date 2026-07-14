# Clean15 样本图片与 URL 证据类型、失败模式和多模态定位处理方案

本文专门分析一个问题：**图片和 URL 作为多模态输入，到底包含什么定位信息，为什么现有 baseline 经常没有用好，以及我们应该如何把它们变成可检索、可验证、可进入 Agent 搜索闭环的证据。**

分析对象使用 Clean15 口径：只保留 `gold file/module/function` 数量都在 `1..15` 之间的样本。这样可以排除“gold 本身超过 Acc@15 容量”以及 “module/function 无法映射”带来的评估口径干扰。

数据来源：

- `LocAgent/newtest/swebench_multimodal-full-dev/data/samples.jsonl`
- `LocAgent/newtest/swebench_multimodal-60/data/samples.jsonl`
- `MM-IR/data/omnigirl-full-candidates/samples.jsonl`
- `LocAgent/newtest/omnigirl-unified60/data/samples.jsonl`
- `collected_results/qwen8b_mimo_compare_20260711_212220/.../metrics_clean15/.../per_instance_metrics_3level.csv`

统计说明：

- `图片类型` 是基于 repo、issue 文本、文件语言和样本字段做的规则分类，没有逐张人工看图。
- `URL 类型` 是基于 URL host/path 分类。
- `URL 角色` 是进一步判断 URL 对定位的作用，例如是否直接指向 gold 文件。
- baseline 分组指标使用 `eval_strict_clean15/per_instance_metrics_3level.csv` 的 `REC@All`，不是 Acc@K。这里更适合看“某类证据下 baseline 至少召回了多少 gold”。

## 1. Clean15 样本的图片和 URL 总体分布

### 1.1 模态组合

| 数据集 | Clean15 样本数 | 图片+网页URL | 仅图片 | 仅网页URL | 纯文本 |
|---|---:|---:|---:|---:|---:|
| SWE-bench Multimodal dev | 92 | 73 | 19 | 0 | 0 |
| SWE-bench Multimodal 60 | 55 | 43 | 12 | 0 | 0 |
| OmniGIRL full-candidates | 445 | 24 | 8 | 413 | 0 |
| OmniGIRL unified60 | 40 | 9 | 3 | 20 | 8 |

结论：

1. **SWE-bench Multimodal 基本是“图片主导”的 benchmark。** Clean15 的 92 条里，全部有图片，其中 73 条同时有网页 URL。
2. **OmniGIRL full-candidates 基本是“URL 主导”的 benchmark。** Clean15 的 445 条里，413 条只有网页 URL，真正含图片的只有 32 条。
3. 所以两个 benchmark 的多模态难点不是同一种：SWE 更像视觉症状定位，Omni 更像网页/issue/代码链接证据定位。

### 1.2 URL 内容类型

| 数据集 | 外部网页/其他 | 复现/演示页面 | 外部文档/API | GitHub issue/PR | GitHub 代码文件 | GitHub 仓库/其他 | commit/compare | 截断/无效 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SWE dev Clean15 | 49 | 41 | 29 | 24 | 15 | 8 | 0 | 2 |
| SWE60 Clean15 | 33 | 22 | 13 | 13 | 12 | 6 | 0 | 0 |
| Omni full Clean15 | 284 | 124 | 104 | 118 | 138 | 206 | 10 | 0 |
| Omni60 Clean15 | 16 | 6 | 7 | 4 | 14 | 12 | 2 | 0 |

这里要区分“URL 类型”和“URL 对定位的角色”：

- `GitHub 代码文件 URL`：可能直接指向 gold 文件，也可能只是 issue 里引用的相关文件。
- `GitHub issue/PR`：通常包含历史讨论、设计原因、旧补丁或 reviewer 线索。
- `复现/演示页面`：例如 localhost 页面、CodePen、demo、产品页面路径，通常能告诉我们 UI route 或复现路径。
- `外部文档/API`：提供 API、浏览器能力、协议或业务概念，不能直接等价到代码文件。
- `外部网页/其他`：信息强度不稳定，可能是产品页面，也可能只是上下文网页。

### 1.3 URL 对定位的角色

| 数据集 | 直接指向 gold 文件 | 指向相关代码但非 gold 文件 | 历史讨论/补丁线索 | 概念/API语义线索 | 复现行为线索 | 弱网页线索 | 无URL |
|---|---:|---:|---:|---:|---:|---:|---:|
| SWE dev Clean15 | 8 | 4 | 12 | 17 | 24 | 8 | 19 |
| SWE60 Clean15 | 5 | 3 | 7 | 8 | 16 | 4 | 12 |
| Omni full Clean15 | 62 | 36 | 79 | 70 | 72 | 118 | 8 |
| Omni60 Clean15 | 5 | 4 | 4 | 6 | 3 | 7 | 11 |

关键点：**URL 不是天然等于定位答案。**

在 SWE dev Clean15 中，只有 8/92 个样本的 URL 能直接解析到 gold 文件；Omni full Clean15 中是 62/445。更多 URL 是“复现行为、历史讨论、文档/API、相关但非 gold 的代码文件”。这些 URL 如果直接塞给 LLM，让 LLM 自己理解，常见结果是：

1. LLM 被 URL 里的非 gold 文件误导。
2. LLM 只把 URL 当普通文本，不会打开、解析、抽取路径和行号。
3. Agent 搜索时没有把 URL 转换成 route、symbol、API、component 等可执行查询。

### 1.4 OmniGIRL full-candidates Clean15 的 URL 内容差异

上一节只给了总体分类。OmniGIRL full-candidates Clean15 需要单独展开，因为它和 SWE-bench Multimodal 的模态结构完全不同：**445 条 Clean15 样本中，413 条是仅网页 URL，只有 32 条包含图片。** 因此 Omni 的核心不是“视觉理解”，而是“URL 证据解析和跨语言代码链接”。

#### 1.4.1 URL host 分布

Omni full Clean15 的 URL host Top 30 如下：

| URL host | 出现次数 | 主要含义 |
|---|---:|---|
| `github.com` | 452 | issue、PR、代码 blob、仓库主页、commit/compare |
| `prettier.io` | 144 | Prettier playground / formatter 复现 |
| `mypy.readthedocs.io` | 47 | mypy 类型系统文档 |
| `play.tailwindcss.com` | 37 | Tailwind playground 复现 |
| `stackoverflow.com` | 34 | API 行为、用法讨论 |
| `gitter.im` | 28 | 项目讨论上下文 |
| `issuehunt.io` | 23 | issue bounty 页面，通常是弱线索 |
| `mypy-play.net` | 22 | mypy playground 复现 |
| `gist.github.com` | 20 | 最小复现代码、片段 |
| `babeljs.io` | 17 | Babel REPL / 文档 |
| `babel.dev` | 10 | Babel REPL |
| `docs.python.org` | 8 | Python 标准库文档 |
| `www.w3.org` | 6 | Web 标准/API |
| `codesandbox.io` | 5 | 前端复现工程 |
| `mypy.rtfd.io` | 5 | mypy 文档镜像 |
| `tools.ietf.org` | 4 | RFC/协议文档 |
| `day.js.org` | 4 | Day.js 文档 |
| `runkit.com` | 4 | JS 运行复现 |
| `redis.io` | 4 | Redis 行为/命令文档 |
| `docs.scipy.org` | 4 | SciPy 文档 |
| `www.statsmodels.org` | 4 | statsmodels 文档 |
| `tailwindcss.com` | 4 | Tailwind 文档 |
| `registry.yarnpkg.com` | 4 | npm/yarn 包信息 |
| `www.typescriptlang.org` | 3 | TypeScript 文档/playground |
| `en.wikipedia.org` | 3 | 概念解释 |
| `avatars0.githubusercontent.com` | 3 | 头像/徽章类图片，定位价值弱 |
| `avatars3.githubusercontent.com` | 3 | 头像/徽章类图片，定位价值弱 |
| `developers.google.com` | 3 | API 文档 |
| `nodejs.org` | 2 | Node.js API 文档 |
| `jsfiddle.net` | 2 | 前端复现 |

这里可以看到三个明显的 URL 族群：

1. **GitHub 族群**：代码 blob、issue、PR、commit。它和定位最直接，但也最容易误导，因为引用的代码文件不一定是 gold 文件。
2. **Playground / REPL 族群**：Prettier、Babel、Tailwind、mypy-play、CodeSandbox、RunKit、JSFiddle。它们提供最小复现，但需要把输入代码、配置、版本参数解析出来。
3. **文档/API 族群**：mypy、Python docs、W3C、TypeScript、Node、Redis、SciPy、statsmodels。这类 URL 不直接定位文件，而是给出 API 语义，需要进一步搜索仓库里的 API usage。

#### 1.4.2 URL 角色和语言的关系

Omni full Clean15 的语言分布：

| 主语言 | 样本数 |
|---|---:|
| JavaScript | 187 |
| Python | 174 |
| TypeScript | 42 |
| Java | 41 |
| C | 1 |

URL 角色按语言拆开后，差异很明显：

| 主语言 | 弱网页线索 | 复现行为线索 | 概念/API语义线索 | 历史讨论/补丁线索 | 指向相关代码但非 gold | 直接指向 gold | 无URL |
|---|---:|---:|---:|---:|---:|---:|---:|
| JavaScript | 56 | 54 | 24 | 23 | 18 | 9 | 3 |
| Python | 50 | 0 | 43 | 39 | 14 | 25 | 3 |
| TypeScript | 6 | 17 | 2 | 9 | 1 | 7 | 0 |
| Java | 6 | 1 | 1 | 8 | 3 | 20 | 2 |
| C | 0 | 0 | 0 | 0 | 0 | 1 | 0 |

这说明 Omni 的 URL 处理必须走 language router：

- **JavaScript/TypeScript**：大量 URL 是 playground/repl，重点是解析复现输入、formatter/transpiler 配置、route 或 framework 选项。
- **Python**：大量 URL 是文档/API、GitHub issue/PR、代码链接，重点是 API usage、type checker rule、stats/model 参数、datetime/parser 行为。
- **Java**：大量 URL 直接指向代码文件，特别是 AssertJ/Gson/Netty 这类库，重点是 blob path、类名、方法名和测试邻域。

如果把这些 URL 都当作普通文本，Agent 会丢掉最关键的结构信息。例如 `prettier.io/playground/#...` 里真正重要的是 `parser`、`printWidth`、输入代码片段、版本和格式化输出差异；`mypy.readthedocs.io` 真正重要的是类型系统规则；`github.com/.../blob/...#L130` 真正重要的是 repo/path/line/symbol。

#### 1.4.3 URL 类型和语言的关系

| 主语言 | 外部网页/其他 | 复现/演示页面 | 外部文档/API | GitHub issue/PR | GitHub 代码文件 | GitHub 仓库/其他 | commit/compare |
|---|---:|---:|---:|---:|---:|---:|---:|
| JavaScript | 177 | 95 | 35 | 33 | 36 | 79 | 2 |
| Python | 78 | 0 | 64 | 56 | 50 | 105 | 7 |
| TypeScript | 11 | 27 | 4 | 13 | 13 | 14 | 0 |
| Java | 17 | 2 | 1 | 16 | 35 | 8 | 1 |
| C | 1 | 0 | 0 | 0 | 4 | 0 | 0 |

这个表揭示了一个关键问题：**同样叫 URL，实际定位价值完全不同。**

- JavaScript 的 URL 常常是可运行复现入口，但需要解析 URL hash 内的代码和配置。
- Python 的 URL 常常是文档、issue、GitHub 讨论，需要抽取 API/行为规则。
- Java 的 URL 常常是直接代码指针，需要抽取类、方法、行号和邻近测试。

因此 Omni full 的 URL 处理不能只有“打开网页”这一步，而应该有不同 resolver：

| URL 族群 | resolver | 产物 |
|---|---|---|
| GitHub blob | `GitHubBlobResolver` | repo、path、line range、symbol、是否与 gold 文件重合 |
| GitHub issue/PR | `GitHubDiscussionResolver` | 文件提及、旧补丁、review comment、commit diff、关键词 |
| Playground/REPL | `PlaygroundResolver` | 输入代码、配置、版本、parser/framework、复现 API |
| 文档/API | `DocsResolver` | API 名、参数、行为规则、异常条件 |
| 外部弱网页 | `WeakURLResolver` | title、可见关键词、降权处理 |

#### 1.4.4 Omni full Clean15 的图片内容分布

Omni full Clean15 虽然主要是 URL benchmark，但仍有 32 条包含图片：

| 图片内容类型 | 样本数 | 典型来源 |
|---|---:|---|
| Web UI页面截图 | 26 | Prettier playground、Tailwind playground、statsmodels 输出截图、Netty/WebSocket 行为截图 |
| 未明确图片类型 | 6 | IssueHunt 头像/徽章、无法稳定判定的外部图片 |
| 无图片 | 413 | 仅 URL |

典型图片样本：

| 样本 | 语言 | 图片类型 | URL 角色 | 说明 |
|---|---|---|---|---|
| `prettier__prettier-11884` | JavaScript | Web UI页面截图 | 复现行为线索 | Prettier playground 展示 TypeScript generics 格式化异常 |
| `prettier__prettier-12177` | JavaScript | Web UI页面截图 | 复现行为线索 | Playground 展示 `switch case` 注释格式差异 |
| `prettier__prettier-14262` | JavaScript | Web UI页面截图 | 历史讨论/补丁线索 | Playground + TypeScript PR，涉及 JSDoc/intellisense |
| `tailwindlabs__tailwindcss-10214` | JavaScript | Web UI页面截图 | 弱网页线索 | Tailwind playground 展示 prefix/modifier/arbitrary variant 问题 |
| `tailwindlabs__tailwindcss-4260` | JavaScript | Web UI页面截图 | 概念/API语义线索 | Tailwind important modifier 行为 |
| `statsmodels__statsmodels-7757` | Python | Web UI页面截图 | 直接指向 gold 文件 | OrderedModel 缺失值行为，URL 指向 `ordinal_model.py#L130` |
| `netty__netty-13114` | Java | Web UI页面截图 | 无URL | WebSocket status code 行为截图 |
| `iamkun__dayjs-1101` | JavaScript | Web UI页面截图 | 无URL | timezone/UTC 行为截图 |

Omni 图片和 SWE 图片的差异：

- SWE 图片更像产品 UI、图表、PDF、Canvas 输出，视觉本身是主要症状。
- Omni 图片多数是 playground 或输出截图，**图片往往是 URL 复现的一部分**，不是独立视觉场景。
- 因此 Omni 的图片处理应该优先绑定 URL：先解析 playground URL，再用图片确认输出差异。

#### 1.4.5 Omni URL 的具体定位价值和风险

Omni full Clean15 中，直接指向 gold 文件的样本有 62 条，例如：

| 样本 | 语言 | URL 指向 |
|---|---|---|
| `assertj__assertj-2200` | Java | `ShouldBeEqual.java#L44` |
| `assertj__assertj-2685` | Java | `Strings.java#L528-L531` |
| `babel__babel-15489` | TypeScript | `babel-plugin-transform-typescript/src/index.ts#L594` |
| `dateutil__dateutil-247` | Python | `dateutil/parser.py#L67` |
| `google__gson-2153` | Java | `Gson.java#L434` |
| `statsmodels__statsmodels-7757` | Python | `ordinal_model.py#L130` |

这些样本理论上应该容易，但现有 Agent 仍可能失败，原因通常是：

1. 没有解析 GitHub blob URL，只把整段 URL 当字符串。
2. 没有把 line number 映射到函数/类。
3. 没有检查当前 benchmark 的 `base_commit`，URL 的 branch/commit 可能和本地 checkout 不完全一致。
4. 没有围绕该 symbol 扩展测试、调用者、同类实现。

同时，指向相关但非 gold 文件的样本有 36 条，例如：

| 样本 | 语言 | URL 特点 | 风险 |
|---|---|---|---|
| `babel__babel-15225` | TypeScript | Babel REPL + parser fixture URL | fixture 是复现，不一定是修复点 |
| `dateutil__dateutil-517` | Python | `parser.py#L605` | 相关解析逻辑，但 gold 可能在邻近 helper |
| `netty__netty-8471` | Java | 多个 codec/test URL | 多个相关文件，容易锚定错测试或旧实现 |
| `prettier__prettier-11685` | JavaScript | `type-parameters.js#L54-L64` + playground | 代码链接相关但最终修复可能在 printer 其它层 |
| `prettier__prettier-12302` | JavaScript | CONTRIBUTING + playground redirect | CONTRIBUTING 是噪声，playground 才是复现 |

这类 URL 必须降权，并且要求 verifier 做反证检查：**候选文件是否同时解释 issue 文本、URL 复现、图片输出差异和 gold 语言上下文。**

### 1.5 图片内容类型

| 数据集 | Web UI页面截图 | 图表/Canvas截图 | 图形/动画/Canvas截图 | PDF/排版截图 | Markdown/文本渲染截图 | 未明确图片 | 无图片 |
|---|---:|---:|---:|---:|---:|---:|---:|
| SWE dev Clean15 | 37 | 24 | 14 | 10 | 7 | 0 | 0 |
| SWE60 Clean15 | 20 | 16 | 9 | 6 | 4 | 0 | 0 |
| Omni full Clean15 | 18 | 0 | 0 | 0 | 0 | 14 | 413 |
| Omni60 Clean15 | 6 | 0 | 0 | 0 | 0 | 6 | 28 |

SWE 的图片可以再分成五类定位信号：

1. **Web UI 页面截图**：按钮、表单、banner、toast、页面路径、产品术语、组件布局。
2. **图表/Canvas 渲染截图**：坐标轴、legend、tooltip、scale、dataset、颜色、交互状态。
3. **图形/动画/Canvas 截图**：渲染函数、绘图状态、几何行为、浏览器 canvas API。
4. **PDF/排版截图**：换行、分页、字体、布局、Yoga/Flexbox、文本测量。
5. **Markdown/文本渲染截图**：parser、renderer、HTML 输出、tokenizer、escape 规则。

这些图片不是“泛泛视觉信息”。它们对应不同的代码搜索入口：

| 图片类型 | 应抽取的证据 | 应转成的代码查询 |
|---|---|---|
| Web UI 页面 | 页面标题、按钮文案、表单字段、route、状态提示、组件层级 | route、component、selector、action、store/state、i18n key |
| 图表/Canvas | axis、scale、legend、tooltip、dataset、颜色、交互位置 | scale/controller/element/plugin/layout/interaction 文件 |
| 图形/动画 | shape、坐标、stroke/fill、frame、event、pixel mismatch | drawing API、renderer、geometry、event handler |
| PDF/排版 | page break、line break、font、margin、wrap、flex | layout engine、text measurement、font resolver |
| Markdown 渲染 | HTML 片段、token、escape、link/image/code block | tokenizer、parser、renderer、extension rule |

## 2. 现有 baseline 在不同证据类型下的表现

下面的表使用 `REC@All`，单位是百分比。`zero_file` 表示该证据类型下 file recall 为 0 的样本数。

### 2.1 SWE dev Clean15：按 URL 角色看 File REC@All

| URL 角色 | 样本数 | LocAgent | CoSIL | GraphLocator | GALA | BM25-MMIR |
|---|---:|---:|---:|---:|---:|---:|
| 直接指向 gold 文件 | 8 | 23.96 | 29.17 | 28.12 | 57.29 | 46.87 |
| 指向相关代码但非 gold 文件 | 4 | 0.00 | 8.33 | 0.00 | 0.00 | 19.17 |
| 历史讨论/补丁线索 | 12 | 13.43 | 13.80 | 11.76 | 19.99 | 21.02 |
| 概念/API语义线索 | 17 | 17.06 | 30.59 | 17.65 | 38.82 | 30.20 |
| 复现行为线索 | 24 | 41.46 | 39.51 | 12.15 | 55.49 | 54.93 |
| 弱网页线索 | 8 | 30.95 | 45.54 | 24.70 | 51.19 | 66.37 |
| 无URL | 19 | 28.82 | 16.84 | 14.04 | 32.13 | 58.47 |

直接结论：

1. **GALA 在“直接指向 gold 文件”的 URL 上收益最大**，File REC@All 达到 57.29，且 zero-file 为 0。这说明当代码链接非常明确时，代码图/检索对齐能吃到一部分红利。
2. **“指向相关代码但非 gold 文件”是最危险的 URL 类型。** LocAgent、GraphLocator、GALA 在这 4 个样本上 File REC@All 都是 0。这类 URL 会诱导模型在相关但错误的文件附近搜索。
3. **历史讨论/PR URL 没有被充分利用。** 它们本应提供旧补丁、review 意图、被改文件、旧实现位置，但所有方法都偏低。
4. **复现行为 URL 对 BM25/GALA 更友好。** 因为 URL 路径和 issue 文本里常出现 route、页面名、产品关键词，能被 lexical retrieval 捕捉。

### 2.2 SWE dev Clean15：按图片类型看 File REC@All

| 图片类型 | 样本数 | LocAgent | CoSIL | GraphLocator | GALA | BM25-MMIR |
|---|---:|---:|---:|---:|---:|---:|
| Web UI页面截图 | 37 | 15.12 | 18.92 | 10.95 | 28.39 | 31.02 |
| 图表/Canvas渲染截图 | 24 | 32.12 | 34.76 | 15.87 | 43.08 | 57.40 |
| 图形/动画/Canvas截图 | 14 | 51.39 | 29.56 | 27.58 | 59.92 | 79.56 |
| PDF/排版渲染截图 | 10 | 7.50 | 14.50 | 9.17 | 21.17 | 10.50 |
| Markdown/文本渲染截图 | 7 | 44.05 | 70.24 | 22.62 | 82.14 | 61.90 |

直接结论：

1. **Web UI 截图是最大弱点。** 37 个样本中，LocAgent、CoSIL、GraphLocator 都低于 20，GALA/BM25 也只有 28-31。UI 截图需要 route/component/state 的映射，不是简单文本检索。
2. **PDF/排版截图是第二个弱点。** 这类错误通常发生在 layout engine 或 text measurement 的深层逻辑，图片描述很难直接变成文件名。
3. **图形/Canvas 和 Markdown 相对更适合检索。** 因为 issue 文本通常包含 API 名、渲染规则、token 名、scale 名，BM25/GALA 能命中更多。
4. GraphLocator 在大多数图片类型上偏低，说明它的“因果链”如果初始语义种子不准，图扩展无法补救。

### 2.3 Omni60 Clean15：URL 类型下的差异

Omni60 Clean15 只有 40 条，样本较少，但可看出趋势：

| URL 角色 | 样本数 | LocAgent File REC | CoSIL File REC | GraphLocator File REC | GALA File REC | BM25 File REC |
|---|---:|---:|---:|---:|---:|---:|
| 直接指向 gold 文件 | 5 | 80.00 | 80.00 | 60.00 | 20.00 | 60.00 |
| 指向相关代码但非 gold 文件 | 4 | 50.00 | 25.00 | 0.00 | 33.33 | 8.33 |
| 历史讨论/补丁线索 | 4 | 50.00 | 25.00 | 50.00 | 25.00 | 50.00 |
| 概念/API语义线索 | 6 | 83.33 | 50.00 | 16.67 | 25.00 | 25.00 |
| 复现行为线索 | 3 | 0.00 | 0.00 | 0.00 | 33.33 | 0.00 |
| 弱网页线索 | 7 | 71.43 | 85.71 | 28.57 | 0.00 | 42.86 |
| 无URL | 11 | 60.61 | 51.52 | 45.45 | 0.00 | 72.73 |

Omni 的 URL 证据更偏代码/网页/文档，不像 SWE 那样视觉强。这里 LocAgent 和 CoSIL 对直接代码 URL 更容易受益，但 GraphLocator/GALA 不稳定。原因通常不是“有没有 URL”，而是 URL 被转化成什么搜索动作。

## 3. 失败样本：图片和 URL 为什么没有帮上忙

### 3.1 `Automattic__wp-calypso-21409`

证据特征：

- 模态：图片 + URL
- URL 角色：指向相关代码但非 gold 文件
- 图片类型：Web UI 页面截图
- gold：10 个文件、10 个函数
- URL 示例：`client/state/current-user/selectors.js#L157`

各方法 File REC@All：

| LocAgent | CoSIL | GraphLocator | GALA | BM25-MMIR |
|---:|---:|---:|---:|---:|
| 0.0 | 0.0 | 0.0 | 0.0 | 10.0 |

问题不是“没有 URL”，而是 URL 指向 `current-user/selectors.js`，它是身份/用户状态相关文件，但 gold 主要在 Store/WooCommerce 流程。这个 URL 是**上游概念线索**，不是答案文件。

现有 baseline 的典型错误：

- 把 URL 当成强定位锚点，围绕 selector/state 搜索。
- 没有把“email verification / country unsupported / store signup flow”拆成业务流程链。
- 没有从截图中抽取“页面阶段、按钮、流程状态、提示文本”，因此无法把证据转成 `store onboarding / dashboard / settings` 等组件检索。

应该做：

1. URL 进入证据图时标注为 `related_code_pointer`，权重低于 `direct_gold_candidate`。
2. 对 URL 文件做邻域扩展：`current-user` 只作为 identity dependency，继续向 `store signup flow`、`woocommerce dashboard` 扩展。
3. 图片抽取 UI 文本和流程状态，生成 route/component 查询。

### 3.2 `Automattic__wp-calypso-21648`

证据特征：

- URL 角色：复现行为线索
- URL 示例：`/store/settings/email/{DOMAIN}`
- 图片类型：Web UI 页面截图
- gold：7 个文件、8 个函数
- 所有 baseline File REC@All 都是 0。

这里 URL 很有价值，但它不是代码 URL，而是产品 route。现有方法没有把 route 转成代码搜索：

- `/store/settings/email/{DOMAIN}` 应该映射到 route registry、page container、email settings component、store settings reducer/action。
- 如果只把这个 URL 当普通字符串，搜索命中会非常稀疏。

应该做：

1. 对 URL path 做 route decomposition：`store -> settings -> email -> domain`。
2. 在仓库中搜索 route 定义、页面入口、导航配置、component 文件。
3. 把截图中的 placeholder、From-Name、entity decode 等文本 OCR 出来，和 route 候选做交叉验证。

### 3.3 `Automattic__wp-calypso-23915`

证据特征：

- URL 角色：概念/API语义线索
- URL 示例：`wordpress.com/read/...`
- 图片类型：Web UI 页面截图
- gold：1 个文件、1 个函数
- 所有 baseline File REC@All 都是 0。

这个样本看起来简单：Clean15 后只有 1 个 gold 文件和 1 个函数，但 baseline 全失败。原因是 URL 是产品页面，不是源码路径；问题是 Reader 中自己文章的 Edit link 错误。

现有 baseline 容易搜索到 reader 页面、feed、post 相关通用文件，但定位不到“我的文章 / Jetpack sites / Edit link”这一具体条件。

应该做：

1. URL 解析出 route：`read / feeds / posts` 与 `read/list/...`。
2. 结合文本抽取状态约束：`own posts`、`Jetpack sites`、`Edit link`。
3. 在代码里优先找生成 edit URL 的 selector/helper，而不是泛 reader UI 文件。

### 3.4 `Automattic__wp-calypso-33948`

证据特征：

- URL 角色：历史讨论/外部 API 线索
- URL 示例：`localForage`, `indexeddb`, Apache license article
- 图片类型：Web UI 页面截图
- gold：10 个文件、10 个函数
- LocAgent/CoSIL/GraphLocator/GALA 全 0，BM25 只召回 20% file。

这里 URL 是 API/机制线索，不是 UI route。它提示问题和 browser storage、IndexedDB/localForage、license/package behavior 有关。现有 baseline 的问题是：

- 没有把外部 API 文档转换成“仓库内使用 localForage/IndexedDB 的调用点”。
- 没有做 package/API usage graph。
- 图片对定位帮助有限，因为真正 bug 在 storage 机制层。

应该做：

1. URL classifier 标注为 `external_api_evidence`。
2. 建立 API usage index：`localForage`、`indexedDB`、`storage`、`driver`、`license`。
3. 从 API usage 节点扩展到调用文件、wrapper、初始化配置、测试文件。

### 3.5 `diegomura/react-pdf` 和 PDF/排版截图类失败

SWE dev Clean15 里 PDF/排版截图 10 条。各方法 File REC@All：

| LocAgent | CoSIL | GraphLocator | GALA | BM25-MMIR |
|---:|---:|---:|---:|---:|
| 7.50 | 14.50 | 9.17 | 21.17 | 10.50 |

这类样本对所有 baseline 都难。原因是图片显示的是“结果渲染异常”，例如换行、分页、边距、字体、布局错位，但 gold 往往在布局引擎、文本测量、font resolver、Yoga/Flexbox 抽象层。

现有 baseline 的问题：

- 图片 caption 通常只能得到“text wraps incorrectly / page layout wrong”，不能映射到具体函数。
- 文本检索会命中很多 renderer/layout 文件，但很难区分真正负责的算法模块。
- 图结构如果只围绕候选文件扩展，初始候选不准时会继续扩错。

应该做：

1. 对 PDF 截图做 layout-specific vision extraction：换行位置、页边距、overflow、font weight、baseline、page break。
2. 将视觉症状映射到 layout taxonomy：`line breaking`、`page wrapping`、`text measurement`、`font fallback`、`flex layout`。
3. 再用 taxonomy 触发 repo 内专项搜索，而不是让 LLM 自由搜索。

## 4. 为什么现有 baseline 没有处理好图片和 URL

### 4.1 LocAgent

LocAgent 的优势是能调用工具、读文件、搜索仓库。但在多模态证据上有三个不足：

1. 图片和 URL 通常以原始文本形式进入上下文，没有被结构化成 `route / API / symbol / visual symptom`。
2. 搜索动作主要依赖 LLM 自己生成 query，容易被 issue 中最显眼但不准确的词带偏。
3. 对 UI route、GitHub blob URL、外部 API URL 没有独立工具链，无法先做证据归一化再搜索。

表现上，SWE Web UI 页面截图类只有 15.12 File REC@All，PDF/排版截图只有 7.50。

### 4.2 CoSIL

CoSIL 更依赖 LLM 的一次性或少轮推理，适合文本线索明确、文件名/函数名容易出现的场景。它的问题是：

1. 对 URL 没有“打开、解析、判断是否直接指向 gold”的过程。
2. 对图片没有稳定的视觉证据抽取和再检索。
3. 当 URL 是历史 PR 或相关但非 gold 代码时，容易当成普通语义提示，不会显式控制误导风险。

它在 `直接指向 gold 文件` 的 SWE 样本上 function recall 较高，但在历史讨论、PDF、Web UI 上偏弱。

### 4.3 GraphLocator

GraphLocator 的因果链思路适合从问题现象扩展到相关代码实体，但多模态下的关键瓶颈是初始证据节点质量：

1. 如果图片没有变成结构化视觉症状，因果链起点就是模糊文本。
2. 如果 URL 是 route/API/PR，GraphLocator 没有把它拆成图节点类型。
3. 相关但非 gold 的代码 URL 会成为错误强锚点，导致图扩展围绕错误区域。

SWE Clean15 中，GraphLocator 在 Web UI、图表、PDF 三类图片上的 File REC@All 分别只有 10.95、15.87、9.17，说明图结构没有弥补证据抽取不足。

### 4.4 GALA

GALA 在多个分组里相对较强，尤其是：

- 直接指向 gold 文件 URL：File REC@All 57.29
- Markdown/文本渲染截图：File REC@All 82.14
- 图形/动画 Canvas 截图：File REC@All 59.92

但它的问题是：

1. 对 Web UI 截图仍然不够，File REC@All 只有 28.39。
2. 对 PDF/排版仍然弱，只有 21.17。
3. 如果 URL 指向相关但非 gold 文件，File REC@All 也是 0，说明缺少 URL 置信度和反误导机制。

### 4.5 BM25-MMIR

BM25 的优势是可解释、稳定、不会被 LLM 空响应影响。它在图形/Canvas、Markdown、复现 URL 上表现较好，因为关键词和文件名/API 名更直接。

不足也很明确：

1. 它不理解图片，只吃文本中的词。
2. 对 PDF/排版这类“视觉症状到算法模块”的跨层映射很弱。
3. 对外部 URL 不会打开解析，只能用 URL 字符串本身做弱匹配。

## 5. 应该如何处理图片和 URL：证据类型驱动的 Agent 流程

我建议不要把图片和 URL 直接塞进 prompt，然后期待 LLM 自己理解。更可控的做法是：**先把多模态输入变成结构化证据，再让 Agent 基于证据图搜索。**

### 5.1 第一层：证据归一化

输入样本后，先生成 `Evidence Card`：

```json
{
  "visual_evidence": [
    {
      "type": "web_ui_screenshot",
      "ocr_text": ["From name", "Email settings", "Save"],
      "ui_entities": ["settings page", "email form", "placeholder"],
      "symptoms": ["HTML entity not decoded in placeholder"]
    }
  ],
  "url_evidence": [
    {
      "type": "reproduction_route",
      "url": "http://calypso.localhost:3000/store/settings/email/{DOMAIN}",
      "route_tokens": ["store", "settings", "email", "domain"],
      "repo_query": ["store settings email", "email settings page", "from name placeholder"]
    }
  ],
  "text_evidence": {
    "bug_action": "undecoded entity appears in From-Name placeholder",
    "domain_terms": ["store", "settings", "email", "entity decode"]
  }
}
```

这一步的目标不是定位，而是把不同模态翻译成统一的代码检索语言。

### 5.2 第二层：URL 专用处理

URL 至少要分 7 类处理：

| URL 角色 | 处理方式 | 风险控制 |
|---|---|---|
| 直接指向 gold 候选文件 | 解析 repo/path/line，加入高权重候选 | 仍需验证是否只是上下文引用 |
| 指向相关代码但非 gold 文件 | 加入中低权重候选，并扩展邻域 | 防止把它当最终答案 |
| GitHub issue/PR | 抽取提到的文件、函数、review comment、commit diff | 旧 PR 可能不是当前 patch |
| 复现 route | route tokenization，搜索 route registry/component/page container | URL 字符串本身不一定出现在代码里 |
| 外部文档/API | 抽取 API/概念名，搜索仓库 usage | 文档域名不能直接定位文件 |
| demo/playground | 抽取最小复现代码、参数、API 调用 | demo 代码可能和仓库封装层不一致 |
| 无效/截断 URL | 降权，只保留可见 token | 不应强行打开 |

### 5.3 第三层：图片专用处理

图片也不能只做一句 caption。建议根据类型走不同 extractor：

| 图片类型 | 视觉 extractor | 输出 |
|---|---|---|
| Web UI | OCR + layout + component vocabulary | 文案、按钮、route、页面区域、状态提示 |
| 图表/Canvas | chart grammar parser | scale、axis、legend、tooltip、dataset、颜色 |
| 图形/动画 | geometry/state extractor | shape、坐标、event、render state |
| PDF/排版 | layout symptom extractor | page break、line wrap、font、margin、overflow |
| Markdown | rendered HTML/text diff extractor | token、HTML tag、escape/link/code block |

图片 extractor 输出后，不直接给最终答案，而是生成 repo query 和候选约束。

### 5.4 第四层：证据图检索

建议构建一个轻量证据图：

```text
Issue text
  -> domain terms
  -> visual symptoms
  -> URL route/API/file pointer
  -> repo entities
  -> files/functions/modules
  -> tests/examples
```

图节点类型：

- `VisualSymptom`: `button missing`, `axis overlap`, `PDF line wrap`
- `Route`: `/store/settings/email`
- `API`: `localForage`, `indexedDB`, `Chart scale`, `PDF layout`
- `CodePointer`: `client/state/current-user/selectors.js#L157`
- `Component`: `EmailSettings`, `ReaderPost`, `ChartScale`
- `File`
- `Function`
- `Test`

边类型：

- `mentions`
- `renders`
- `routes_to`
- `imports`
- `calls`
- `configures`
- `tests`
- `same_domain`

这样做的核心价值是：**URL 和图片不再只是 prompt 文本，而是可控的搜索种子。**

### 5.5 第五层：反误导 verifier

多模态证据经常有“相关但非答案”的风险，所以需要 verifier：

1. 如果 URL 指向代码文件，检查该文件是否真的解释 issue 中的视觉/行为症状。
2. 如果候选文件只匹配 URL，不匹配图片/文本症状，降权。
3. 如果候选文件只匹配图片 OCR，不在相关 route/API 邻域，降权。
4. 如果候选文件和测试/patch 语言不一致，降权。
5. 对 top candidates 生成“证据覆盖表”：每个文件由哪些 text/image/url 证据支持。

最终输出不应该只是文件列表，而应该是：

| 文件 | 支持证据 | 反证/风险 | 是否进入 topK |
|---|---|---|---|
| `client/my-sites/.../email-settings.jsx` | route + OCR + store email terms | 无 | 是 |
| `client/state/current-user/selectors.js` | URL code pointer | 与 store email symptom 弱相关 | 降权 |

## 6. 对当前 benchmark 的具体处理建议

### 6.1 SWE-bench Multimodal Clean15

优先级最高的处理对象是：

1. Web UI 页面截图：37/92，现有 baseline 普遍弱。
2. PDF/排版截图：10/92，所有 baseline 都弱。
3. 指向相关代码但非 gold 文件的 URL：4/92，容易强误导。
4. 历史 PR/issue URL：12/92，潜在价值大，但现有方法没有充分解析。

建议实现顺序：

1. 先做 URL classifier + GitHub blob/PR parser。
2. 再做 Web UI OCR + route/component query 生成。
3. 再做 PDF/layout taxonomy。
4. 最后加证据图 rerank。

这样能覆盖 SWE 中最大且最弱的几类。

### 6.2 OmniGIRL Clean15

Omni 更需要 URL 处理：

1. Omni full Clean15 中 413/445 是仅网页 URL。
2. GitHub 代码文件 URL 有 138 个，issue/PR 有 118 个，外部文档/API 有 104 个。
3. 语言分布更跨语言：JavaScript 187、Python 174、TypeScript 42、Java 41。

建议：

1. 对 GitHub URL 做强解析：repo/path/line/PR diff/comment。
2. 对文档/API URL 做跨语言 API usage search，例如 Python/Java/JS 中同一个 API 名的不同封装。
3. 对每种语言建立 language router，避免用 JS 的 route/component 逻辑处理 Java/Python。

## 7. 可落地的改造方案

### 7.1 最小可行版本

先实现一个 `evidence_preprocessor.py`：

输入：

- `samples.jsonl`
- `repo_structures`

输出：

- `evidence_cards.jsonl`
- 每个样本的 `text_queries`、`url_queries`、`visual_queries`
- URL role、image type、risk flags

每个 baseline 先不大改，只把 evidence card 追加到 prompt 或检索 query。

### 7.2 中等版本

增加 `evidence_retriever.py`：

1. GitHub blob URL 解析到文件候选。
2. route URL 搜索 route registry 和 component。
3. API/doc URL 搜索 usage。
4. visual query 搜索 OCR text、component text、domain API。

输出一个候选文件池，再交给 LocAgent/GALA/GraphLocator/CoSIL。

### 7.3 完整版本

实现 `EvidenceGraph-Agent`：

1. 证据归一化。
2. 多路召回。
3. 证据图扩展。
4. LLM agent 只在图上做受控搜索。
5. verifier 输出证据覆盖和反证。
6. 最终按 file/module/function 三层 rerank。

## 8. 核心结论

1. **SWE Clean15 是图片主导，Omni Clean15 是 URL 主导。** 不能用同一种“多模态 prompt”处理。
2. **图片和 URL 的价值不是直接给答案，而是提供搜索入口。** 必须转成 route、API、component、symbol、visual symptom。
3. **现有 baseline 最大问题是证据未结构化。** 它们多数把图片/URL 当文本上下文，缺少 URL parser、visual extractor、route/API linker。
4. **URL 会误导。** 特别是“相关代码但非 gold 文件”的 URL，需要低权重和反证机制。
5. **Web UI 和 PDF/layout 是最应该优先改的失败类型。** 它们占比不低，而且现有方法普遍召回差。
6. **多语言场景下，URL/API 证据必须进入 language router。** Omni 里 JavaScript、Python、Java、TypeScript 并存，同一个 URL 类型在不同语言仓库里的代码入口完全不同。

一句话概括改进方向：

> 不要让 Agent 直接“看图和看 URL 后猜文件”，而要先把图片和 URL 变成可检索、可链接、可验证的证据图节点，再让 Agent 在证据图和仓库图之间做受控搜索。
