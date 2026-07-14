# SWE 与 Omni 全集 URL 证据内容及定位关系分析

本文专门分析 SWE-bench Multimodal dev 全量、OmniGIRL full-candidates 以及 OmniGIRL 原始 959 条数据中的 URL 证据。重点不是简单统计“有几个 URL”，而是回答三个问题：

1. URL 具体是什么内容。
2. URL 和真实修改位置，也就是 gold file/module/function，有什么关系。
3. 现有 baseline 为什么没有充分利用 URL，后续框架应该如何改。

## 1. 数据口径

本文使用的主要数据源如下：

| 数据集 | 样本数 | 数据文件 |
|---|---:|---|
| SWE-bench Multimodal dev 全量 | 102 | `LocAgent/newtest/swebench_multimodal-full-dev/data/samples.jsonl` |
| OmniGIRL full-candidates | 631 | `MM-IR/data/omnigirl-full-candidates/samples.jsonl` |
| OmniGIRL 原始源数据 | 959 | `OmniGIRL/omnigirl/harness/benchmark/OmniGIRL.json` |

这里的 URL 主要来自样本字段 `web_urls`、`website links`、`urls`，以及 problem statement 中解析出的网页链接。图片链接单独作为 image evidence，不作为普通网页 URL 统计；但原始数据里仍存在少量头像、附件、图片 URL 被混在网页链接里的情况，因此后文会单独标注。

## 2. URL 内容总览

### 2.1 SWE-bench Multimodal dev 全量

SWE 全量 102 个样本中，65 个样本带有 URL，共 138 条 URL。

| URL 数 | 样本数 |
|---:|---:|
| 0 | 37 |
| 1 | 32 |
| 2 | 15 |
| 3 | 7 |
| 4 | 8 |
| 7 | 1 |
| 8 | 2 |

URL 类型分布：

| 类型 | URL 数 | 涉及样本数 | 说明 |
|---|---:|---:|---|
| 文档/规范链接 | 32 | 17 | 例如 Chart.js 文档、Marked/CommonMark 规范、React-PDF 文档 |
| 复现/Playground 链接 | 25 | 21 | 例如 CodePen、JSFiddle、CodeSandbox、p5 editor |
| 产品/站点/本地复现 URL | 23 | 19 | 例如 WordPress 页面、Calypso 本地路由 |
| 其他外链 | 17 | 12 | 外部博客、说明页、非标准网页 |
| GitHub 代码/文件引用 | 11 | 9 | `github.com/.../blob/...`，常带文件路径或行号 |
| GitHub issue 链接 | 9 | 4 | 相关 issue 或讨论 |
| GitHub PR 链接 | 5 | 5 | 相关 PR，有泄露 patch 风险 |
| GitHub commit 链接 | 2 | 1 | 相关提交，有泄露 patch 风险 |
| 讨论/问答/社交链接 | 3 | 2 | Twitter、讨论页面等 |
| 图片/附件残留链接 | 4 | 4 | 本应归入图片证据或附件证据 |

Top 域名：

| 域名 | URL 数 | 主要含义 |
|---|---:|---|
| github.com | 34 | issue、PR、代码文件、提交、项目链接 |
| wordpress.com | 19 | WordPress/Calypso 产品页面或复现页面 |
| marked.js.org | 13 | Marked 文档 |
| codepen.io | 9 | 前端复现 demo |
| chartjs.org | 8 | Chart.js 文档和样例 |
| jsfiddle.net | 6 | 前端复现 demo |
| react-pdf.org | 6 | React-PDF 文档 |
| editor.p5js.org | 6 | p5.js 在线复现 |
| spec.commonmark.org | 5 | Markdown 规范 |
| codesandbox.io | 3 | 前端复现 demo |

SWE 的 URL 很典型：它们多半是 UI/文档/复现证据，不一定直接告诉你应该改哪个文件。比如 Chart.js 的文档 URL 往往说明某个视觉或配置行为异常；p5.js 的 editor 链接说明渲染或 WebGL 现象；WordPress URL 说明页面路由和用户操作流程。

### 2.2 OmniGIRL full-candidates

OmniGIRL full-candidates 631 个样本中，615 个样本带有 URL，共 1346 条普通网页 URL。

| URL 数 | 样本数 |
|---:|---:|
| 0 | 16 |
| 1 | 295 |
| 2 | 148 |
| 3 | 79 |
| 4 | 50 |
| 5 | 17 |
| 6-10 | 20 |
| 11-15 | 5 |
| 21 | 1 |

URL 类型分布：

| 类型 | URL 数 | 涉及样本数 | 说明 |
|---|---:|---:|---|
| 文档/规范链接 | 357 | 228 | Prettier、mypy、Babel、Python、TypeScript、dayjs 文档 |
| GitHub 其他 | 228 | 169 | 仓库页、目录页、release、讨论入口等 |
| GitHub 代码/文件引用 | 180 | 132 | 直接文件路径、行号或源码引用 |
| 讨论/问答/社交链接 | 124 | 66 | StackOverflow、Gitter、IssueHunt 等 |
| 复现/Playground 链接 | 120 | 101 | Tailwind playground、mypy-play、Babel REPL、Gist 等 |
| 其他外链 | 113 | 92 | 博客、说明页、第三方资源 |
| GitHub issue 链接 | 99 | 85 | issue 本身或相关 issue |
| GitHub PR 链接 | 63 | 55 | PR 讨论，有泄露答案风险 |
| Gist/代码片段 | 27 | 26 | 最小复现代码片段 |
| GitHub commit 链接 | 18 | 16 | 提交链接，有泄露答案风险 |
| 图片/附件残留链接 | 14 | 5 | 头像、附件、图片链接混入 |

Top 域名：

| 域名 | URL 数 | 主要含义 |
|---|---:|---|
| github.com | 588 | issue、源码、PR、commit、讨论 |
| prettier.io | 190 | Prettier 文档、playground 或输出片段 |
| play.tailwindcss.com | 75 | Tailwind 在线复现 |
| mypy.readthedocs.io | 50 | mypy 文档 |
| stackoverflow.com | 41 | 外部问答证据 |
| issuehunt.io | 41 | 旧 issue 镜像或 bounty 页面 |
| gitter.im | 34 | 社区讨论 |
| babeljs.io | 32 | Babel 文档或 REPL |
| gist.github.com | 27 | 复现代码片段 |
| mypy-play.net | 24 | mypy 在线复现 |

OmniGIRL 的 URL 密度远高于 SWE。它的 URL 更多是“开发者报告时附带的上下文证据”：源码链接、文档链接、playground、StackOverflow、Gist、历史 issue/PR。这些 URL 对定位有明显价值，但价值形式不一样：有些是直接文件路径，有些只是语义约束，有些是最小复现输入。

### 2.3 OmniGIRL 原始 959

OmniGIRL 原始 959 条中，627 个样本带 URL，共 1391 条 URL。

| URL 数 | 样本数 |
|---:|---:|
| 0 | 332 |
| 1 | 298 |
| 2 | 152 |
| 3 | 83 |
| 4 | 48 |
| 5 | 19 |
| 6-10 | 20 |
| 11-15 | 5 |
| 20-21 | 2 |

原始 959 与 full-candidates 631 的 URL 结构基本一致。差异主要来自候选集筛选：full-candidates 更偏可准备、可评估、可运行的样本；原始数据里有更多没有 URL、图片附件混杂、结构不可用或仓库准备失败的样本。

## 3. URL 和 Gold 位置的关系

URL 和 gold 之间不是单一关系。可以分成五类。

### 3.1 直接文件线索

这是最强的一类。URL 本身包含 GitHub blob 文件路径，甚至有 `#Lxx` 行号。

统计结果：

| 数据集 | GitHub blob 直接命中 gold 文件样本 | URL 文本包含 gold 文件名样本 |
|---|---:|---:|
| SWE-bench Multimodal dev 全量 | 5 | 7 |
| OmniGIRL full-candidates | 76 | 81 |
| OmniGIRL 原始 959 | 76 | 81 |

示例：

| 样本 | URL 线索 | Gold 文件 |
|---|---|---|
| `Automattic__wp-calypso-26008` | `client/lib/post-normalizer/rule-content-detect-polls.js` | `client/lib/post-normalizer/index.js`, `rule-content-detect-polls.js` |
| `Automattic__wp-calypso-26286` | `client/blocks/app-banner/index.jsx#L149` | `client/blocks/app-banner/index.jsx`, `utils.js` |
| `markedjs__marked-1889` | `src/Lexer.js#L123` | `src/Lexer.js`, `src/Renderer.js` |
| `assertj__assertj-2200` | `ShouldBeEqual.java#L44` | `Descriptable.java`, `ShouldBeEqual.java` |
| `babel__babel-15757` | `packages/babel-generator/src/index.ts#L74` | `packages/babel-generator/src/index.ts` |

这类 URL 不应该只作为 prompt 文本。更合理的做法是把它解析成结构化 hint：

```text
url_type = github_blob
repo = babel/babel
path = packages/babel-generator/src/index.ts
line = 74
relation = direct_file_hint
confidence = high
```

但是即使 URL 直接命中文件，也不能简单把它当成 gold。原因是一个 issue 可能同时需要改相邻文件、调用者、测试、配置文件；URL 可能只是复现位置、文档位置、旧实现位置，不一定是最终 patch 位置。因此它应该是高置信候选，而不是硬编码答案。

### 3.2 相邻文件或同模块线索

很多 URL 没有直接命中 gold 文件，但会指向同目录、同 package、同组件、同 API。比如文档提到 `bar border radius`，gold 可能落在 `docs/charts/bar.md`、`docs/configuration/elements.md` 或 Chart.js 控制器逻辑；WordPress 路由 URL 可能映射到某个页面组件和用户状态逻辑；p5.js editor 链接可能指向 WebGL 渲染路径。

这类关系需要“URL -> 概念 -> 仓库符号”的映射，而不是字符串匹配。

### 3.3 复现输入线索

Playground、Gist、CodePen、JSFiddle、CodeSandbox、mypy-play、Babel REPL、Tailwind playground 通常给出最小复现。

它们的重要性在于：

- 能提取触发 bug 的 API、语法、配置、输入代码。
- 能说明 expected/actual behavior。
- 能把自然语言 issue 转成更稳定的 query。

但它们通常不会直接出现 gold 文件名。例如 Tailwind playground 的 URL 可能只包含 CSS 类、配置片段或压缩后的状态；Babel REPL 可能只有一段 TypeScript/JavaScript 代码；mypy-play 可能只有类型检查复现代码。它们对 file-level 是间接线索，对 function-level 更间接。

### 3.4 文档/规范线索

文档和规范链接常见于 Marked、Chart.js、Prettier、Babel、mypy、Python、TypeScript 等项目。它们通常说明“正确行为应该是什么”，例如：

- Markdown/CommonMark 规范说明 tokenization/rendering 应该如何处理。
- Prettier 文档或 playground 输出说明格式化规则。
- mypy/Python 文档说明类型语义。
- Chart.js 文档说明某个配置选项和视觉效果。

这类 URL 对定位的帮助不是文件路径，而是概念约束。它需要把“规范概念”映射到仓库内实现该概念的模块，例如 parser、printer、renderer、resolver、validator、layout、controller。

### 3.5 历史讨论、PR、commit 线索

GitHub issue、PR、commit、讨论链接很复杂：

- issue/讨论可能包含用户复现、维护者分析、相关文件名。
- PR/commit 可能直接包含答案，有数据泄露风险。
- 旧 PR 可能是相似修复，不一定是当前 gold。

当前 muladapter 对 commit/PR/patch/diff 类 URL 有跳过详细抓取的逻辑，这是合理的防泄露策略。但问题是跳过之后，系统往往只保留 URL 字符串，没有进一步解析“这是 issue 讨论、PR、commit、目录、源码文件还是 release 页面”。因此安全性有了，信息利用不足。

## 4. URL 分组下的定位表现

下面不是完整排名表，而是用 URL 分组观察 baseline 是否真的吃到了 URL 证据。指标使用 clean15 复评估结果；`SL@15` 表示 top-15 严格覆盖成功率，`REC@All` 表示全预测集合召回。

### 4.1 SWE 全量：LocAgent / GALA / BM25

#### LocAgent，SWE full-dev，mimo-v2.5，clean15

| 分组 | 样本数 | File SL@15 | File REC@All | Function SL@15 | Function REC@All |
|---|---:|---:|---:|---:|---:|
| 无 URL | 34 | 32.4 | 54.4 | 20.6 | 45.9 |
| 有 URL | 58 | 48.3 | 62.9 | 22.4 | 56.2 |
| 含 GitHub | 16 | 18.8 | 45.0 | 12.5 | 54.4 |
| 无 GitHub | 76 | 47.4 | 62.9 | 23.7 | 51.9 |
| 含 Playground | 18 | 55.6 | 65.5 | 11.1 | 52.7 |
| 无 Playground | 74 | 39.2 | 58.4 | 24.3 | 52.3 |
| URL 含 gold 文件名 | 7 | 28.6 | 62.1 | 14.3 | 62.1 |
| 无显式 gold 文件名 | 85 | 43.5 | 59.6 | 22.4 | 51.6 |

解释：

- 有 URL 的样本 file-level 明显更好，说明 URL 至少提供了一些有用上下文。
- 但含 GitHub 链接的样本 File SL@15 反而低。这不是“GitHub URL 没用”，而是这组样本通常更难：多文件、历史讨论、PR/commit、跨模块关联更多。
- Playground 样本 File SL@15 高，但 Function SL@15 低，说明复现链接能帮助定位到大方向，却很难精确落到函数。
- URL 明确包含 gold 文件名的样本只有 7 个，样本数太少，且很多 gold 是多文件闭包。单个 URL 命中文件不等于 top-15 覆盖全部 gold。

#### GALA，SWE full-dev，mimo-v2.5，clean15

| 分组 | 样本数 | File SL@15 | File REC@All | Function SL@15 | Function REC@All |
|---|---:|---:|---:|---:|---:|
| 无 URL | 34 | 29.4 | 48.5 | 14.7 | 24.4 |
| 有 URL | 58 | 44.8 | 62.4 | 12.1 | 21.7 |
| 含 GitHub | 16 | 25.0 | 53.7 | 12.5 | 26.9 |
| 无 GitHub | 76 | 42.1 | 58.0 | 13.2 | 21.8 |
| 含 Playground | 18 | 61.1 | 76.9 | 11.1 | 12.6 |
| 无 Playground | 74 | 33.8 | 52.5 | 13.5 | 25.1 |
| URL 含 gold 文件名 | 7 | 28.6 | 71.7 | 14.3 | 42.4 |
| 无显式 gold 文件名 | 85 | 40.0 | 56.1 | 12.9 | 21.1 |

解释：

- GALA 在 Playground 组的 file-level 表现更好，说明图像/上下文对 UI 和前端问题有帮助。
- Function-level 仍然低，说明“视觉/网页现象 -> 代码函数”之间缺少结构化桥接。
- URL 含 gold 文件名时 Function REC@All 提升明显，但严格成功率不高。这同样说明 URL 能给候选，但不能自动完成多文件、多函数闭包。

#### BM25-MMIR，SWE full-dev，clean15

| 分组 | 样本数 | File SL@15 | File REC@All | Function SL@15 | Function REC@All |
|---|---:|---:|---:|---:|---:|
| 无 URL | 34 | 29.4 | 44.7 | 11.8 | 25.3 |
| 有 URL | 58 | 31.0 | 45.8 | 13.8 | 20.2 |
| 含 GitHub | 16 | 12.5 | 36.5 | 25.0 | 32.8 |
| 无 GitHub | 76 | 34.2 | 47.3 | 10.5 | 19.8 |
| 含 Playground | 18 | 44.4 | 62.0 | 0.0 | 11.7 |
| 无 Playground | 74 | 27.0 | 41.4 | 16.2 | 24.6 |
| URL 含 gold 文件名 | 7 | 14.3 | 50.2 | 42.9 | 48.7 |
| 无显式 gold 文件名 | 85 | 31.8 | 45.0 | 10.6 | 19.9 |

解释：

- BM25 对 URL 文本非常敏感。如果 URL 里出现文件名、API 名、函数名，召回会受益。
- 但 BM25 不理解 URL 类型，也不会打开 URL。因此 Playground 对 file-level 有帮助，但 Function SL@15 为 0，说明它只学到了一些粗粒度 token，无法把复现代码映射到函数实体。

### 4.2 Omni full-candidates：LocAgent / CoSIL

#### LocAgent，Omni full-candidates，qwen 结果

| 分组 | 样本数 | File SL@15 | File REC@All | Function SL@15 | Function REC@All |
|---|---:|---:|---:|---:|---:|
| 无 URL | 16 | 18.8 | 42.7 | 0.0 | 7.0 |
| 有 URL | 615 | 27.3 | 33.2 | 3.9 | 9.5 |
| 含 GitHub | 366 | 31.4 | 37.1 | 4.1 | 9.6 |
| 无 GitHub | 265 | 21.1 | 28.5 | 3.4 | 9.1 |
| 含 Playground | 101 | 25.7 | 31.6 | 5.9 | 11.4 |
| 无 Playground | 530 | 27.4 | 33.8 | 3.4 | 9.0 |
| URL 含 gold 文件名 | 81 | 70.4 | 80.8 | 11.1 | 24.0 |
| 无显式 gold 文件名 | 550 | 20.7 | 26.5 | 2.7 | 7.2 |

#### CoSIL，Omni full-candidates，qwen 结果

| 分组 | 样本数 | File SL@15 | File REC@All | Function SL@15 | Function REC@All |
|---|---:|---:|---:|---:|---:|
| 无 URL | 16 | 43.8 | 58.8 | 0.0 | 9.1 |
| 有 URL | 615 | 34.3 | 40.2 | 4.4 | 7.8 |
| 含 GitHub | 366 | 41.5 | 48.1 | 3.8 | 7.6 |
| 无 GitHub | 265 | 24.9 | 30.4 | 4.9 | 8.2 |
| 含 Playground | 101 | 23.8 | 27.2 | 5.0 | 6.3 |
| 无 Playground | 530 | 36.6 | 43.2 | 4.2 | 8.1 |
| URL 含 gold 文件名 | 81 | 76.5 | 87.0 | 13.6 | 21.6 |
| 无显式 gold 文件名 | 550 | 28.4 | 33.8 | 2.9 | 5.8 |

解释：

- Omni 中 URL 显式包含 gold 文件名的 81 个样本，file-level 指标大幅提升。这说明 URL 文件路径是强证据。
- 但 function-level 仍然低。原因是文件路径最多解决“在哪个文件”，无法直接解决“文件中的哪个函数、哪个方法、哪个闭包链”。
- Playground 组没有明显提升，甚至 CoSIL file-level 更低。说明复现 URL 如果不被打开、解码、执行或转成 API/符号线索，对 LLM/检索系统帮助有限。

## 5. URL 丰富但仍然失败的代表样本

### 5.1 SWE 样本

| 样本 | URL 类型 | Gold 文件数 | 现象 |
|---|---|---:|---|
| `processing__p5.js-5917` | GitHub issue、图片附件、p5 editor 复现 | 9 | URL 很多，但 WebGL/material 相关修改分散，file-level 召回不足 |
| `processing__p5.js-3769` | GitHub 代码引用、外链、复现 | 6 | 能召回部分文件，但 function 召回很低，说明复现现象没有映射到具体渲染函数 |
| `chartjs__Chart.js-9678` | 文档/规范链接 | 5 | 文档说明配置/视觉行为，但需要映射到 docs、controller、element 多处 |
| `Automattic__wp-calypso-21635` | PR、GitHub、产品路由 | 3 | `calypso.localhost` 路由本身不包含文件名，需要 route-to-component 映射 |
| `diegomura__react-pdf-1541` | CodeSandbox、文档 | 1 | 复现 URL 指向布局问题，但 gold 在 `resolveDimensions.js`，需要 layout pipeline 知识 |

这些样本的共同点是：URL 很有价值，但它们提供的是“现象、路由、输入、规范”，不是直接答案。现有 baseline 基本没有把 URL 转成结构化检索动作。

### 5.2 Omni 样本

| 样本 | URL 类型 | Gold 文件数 | 现象 |
|---|---|---:|---|
| `iamkun__dayjs-858` | PR、issue、头像/附件残留 | 2 | URL 多但噪声大，头像和讨论链接会稀释有效信号 |
| `prettier__prettier-16347` | 文档、外链 | 1 | 需要把格式化现象映射到 document utils，而不是只检索文档词 |
| `python__mypy-15042` | Python 文档、GitHub 文件、PR | 3 | 文档说明类型语义，但定位需要 subtypes/messages 等内部模块知识 |
| `prettier__prettier-15826` | PR、源码、文档 | 4 | URL 能给文件和语义，但多文件闭包仍然难覆盖 |
| `webpack__webpack-15801` | Gist、issue、GitHub | 3 | Gist 是最小复现代码，但需要解析依赖图和 JSON exports 逻辑 |

Omni 的失败更偏跨语言和跨框架：Python 类型系统、Java assertion API、JS/TS parser/printer、Webpack dependency graph、Tailwind CSS compiler。URL 经常提供“外部语义”，但 baseline 需要把外部语义接回仓库内部的语言结构。

## 6. 各 baseline 当前如何处理 URL

### 6.1 LocAgent

准备脚本会抽取 `web_urls`，并在 problem statement 后追加：

```text
Related URLs:
- ...
```

muladapter 的 `codev_compact` 模式会尝试生成 `[Web Evidence]`，包括网页 title、description、headings、正文摘要。但它有几个限制：

- commit、PR、compare、patch、diff 等 URL 会被跳过详细抓取，以避免答案泄露；
- 网页抓取失败时只保留 URL 字符串；
- 即使抓取成功，也只是附加到 prompt，不会变成 agent 的专门搜索动作；
- 没有把 GitHub blob URL 解析成 path/line 结构化 hint；
- 没有把 playground URL 解码成复现代码和 API token；
- 没有 route-to-component、doc-to-symbol、API-to-module 映射工具。

所以 LocAgent 能从 URL 中获益，但主要是 LLM 自己读 prompt 和普通搜索的收益，不是 URL-aware agent 策略的收益。

### 6.2 CoSIL

CoSIL 也会接受增强后的 problem statement，并可能带上 `Related URLs` 或 `[Web Evidence]`。但 CoSIL 的核心仍是文件级 LLM 定位和结构信息，它没有独立的 URL 解析、网页证据图或外部复现执行链。

这导致两类问题：

- 直接源码 URL 有帮助，但多文件闭包仍然容易漏。
- 文档/Playground URL 很难转成内部文件和函数，因为 CoSIL 没有显式的“外部概念到仓库符号”的映射阶段。

### 6.3 GraphLocator

GraphLocator 的定位依赖图结构、因果链和仓库图。但 URL 当前更多是文本证据，不是图上的 typed node。

理想情况下，URL 应该进入图结构：

```text
URL node -> evidence type -> extracted API/symbol -> repo file/function -> graph expansion
```

实际运行中，GraphLocator 更容易在两个环节受限：

- URL 没有成为图扩展的种子节点；
- graph cache、repo structure、跨语言解析不稳定时，URL 给出的外部线索无法稳定接入代码图。

因此它对“GitHub blob 文件路径”这类 URL 可以间接受益，但对文档、Playground、UI 路由类 URL 的利用不足。

### 6.4 GALA

GALA 更偏图像和代码图对齐。它会把 website links 拼进输入文本，但没有明显的通用网页抓取、URL 分类、URL-to-symbol 映射机制。

所以 GALA 在 SWE 的 Playground/UI 类样本上 file-level 有一定优势，但 function-level 仍然弱。原因是视觉或网页现象可以帮助判断组件大方向，却不能自动推断具体函数。

### 6.5 MM-IR / BM25

MM-IR 的 evidence builder 可以拼接 `web_cache` 中的网页文本，但常规运行里如果没有预构建 web cache，BM25 主要看到的是 problem statement 和 URL 字符串。

BM25 的优势是简单稳定：URL 里出现文件名、API 名、类名时能直接召回。劣势也明显：

- 不打开网页；
- 不理解 URL 类型；
- 不解码 playground；
- 不区分直接文件线索和噪声附件；
- 不会从文档语义跳到代码实现。

所以 BM25 对“URL 含 gold basename”的 function recall 有明显收益，但对大部分间接 URL 不够。

## 7. 为什么 URL 没有被处理好

综合数据和日志，主要问题有六类。

### 7.1 URL 被当成普通文本，而不是证据对象

现在多数 baseline 看到的是：

```text
Related URLs:
- https://play.tailwindcss.com/...
- https://prettier.io/docs/...
```

但系统不知道这些 URL 分别是 playground、文档、源码、PR、issue、commit、图片附件。不同 URL 应该触发不同处理逻辑：

| URL 类型 | 应该触发的处理 |
|---|---|
| GitHub blob | 解析 repo/path/line，作为文件和函数候选 |
| Playground | 解码或抓取复现代码，抽取 API/token/config |
| 文档/规范 | 提取概念和 API，映射到仓库符号 |
| 产品路由 | route-to-component 映射 |
| issue/讨论 | 抽取维护者分析和文件名，过滤噪声 |
| PR/commit | 防泄露处理，只保留非答案级元信息 |

### 7.2 URL 内容和 gold 往往是间接关系

SWE 中只有 5 个样本的 GitHub blob 直接命中 gold 文件；Omni full-candidates 中直接命中是 76 个样本。也就是说，大多数 URL 并不直接写着答案。

例如：

- Chart.js 文档 URL 指向配置概念，gold 可能在 docs、element、controller 多处。
- p5.js editor URL 指向可视化复现，gold 在 WebGL renderer/material。
- mypy docs URL 指向类型理论，gold 在 `subtypes.py`、`messages.py` 等内部模块。
- Prettier playground URL 指向格式化输入输出，gold 在 printer/comment/doc utils。

这说明 URL 更像“问题机制证据”，而不是“文件名证据”。

### 7.3 Playground 没有被结构化解析

Playground 链接通常包含最小复现。现有处理如果只是把 URL 放进 prompt，等于丢掉了最有价值的内容。

应该从 Playground 中抽取：

- 输入代码；
- 配置；
- expected output / actual output；
- 涉及的语言模式；
- API、AST node、CSS class、plugin 名称；
- 触发错误信息。

然后把这些信息转成仓库搜索 query 和图扩展 seed。

### 7.4 文档/规范没有映射到代码实现

文档 URL 的价值不是标题本身，而是文档中的概念。例如：

```text
CommonMark emphasis rule -> Lexer/Tokenizer/Renderer
Prettier trailing comment behavior -> comment printer / estree printer
mypy Callable semantics -> subtypes / messages / checker
Chart.js bar border radius -> bar element / controller / docs
```

当前 baseline 缺少 `doc concept -> repo symbol` 这一步。

### 7.5 安全跳过 PR/commit 后没有保留足够结构信息

跳过 PR/commit 详细抓取是对的，因为它可能直接泄露 patch。但是跳过不等于完全忽略。至少可以安全保留：

- URL 类型；
- repo；
- issue/PR/commit 编号；
- 是否同仓库；
- URL 路径中出现的非 patch 文件名；
- issue 标题级信息，如果可安全获取。

当前逻辑常常变成“跳过详细抓取，只留下 URL 字符串”，信息利用不足。

### 7.6 噪声 URL 没有过滤

Omni 中有头像、附件、IssueHunt、Gitter、博客、无关页面等混入。比如 `avatars0.githubusercontent.com`、`avatars3.githubusercontent.com` 这类 URL 对代码定位几乎没有价值。如果不分类过滤，会污染 BM25 和 LLM 注意力。

## 8. 对后续框架的具体改进建议

### 8.1 增加 URL Evidence Parser

第一步应该把 URL 解析成结构化证据，而不是只追加文本。

建议输出格式：

```json
{
  "url": "...",
  "type": "github_blob | github_issue | github_pr | github_commit | playground | docs | route | discussion | image_noise | other",
  "repo": "babel/babel",
  "path": "packages/babel-generator/src/index.ts",
  "line": 74,
  "safe_to_fetch": true,
  "leakage_risk": "low | medium | high",
  "evidence_text": "...",
  "symbols": ["generator", "typescript", "comment"],
  "candidate_files": ["..."],
  "confidence": 0.0
}
```

### 8.2 建立 URL 类型到 agent 动作的路由

不同 URL 不应该走同一个 prompt 模板。

| URL 类型 | Agent 动作 |
|---|---|
| GitHub blob | 解析 path/line，读取同文件、邻近函数、import/export、调用者 |
| GitHub issue | 抽取标题、错误信息、维护者提到的文件名和 API |
| PR/commit | 防泄露，只解析元信息，不读取 patch diff |
| Playground | 抓取/解码复现代码，抽取 API、配置和错误输出 |
| 文档/规范 | 抽取文档标题、章节、API 名，映射到 repo symbol |
| 产品路由 | 根据 route/table/router 文件映射到页面组件 |
| 讨论/问答 | 抽取问题关键词，过滤用户头像、签名、无关链接 |

### 8.3 把 URL 证据接入图检索

URL 不应该只进入 LLM prompt，而应该进入图：

```text
URL -> Evidence Node -> Concept/API Node -> File/Function Node -> Call/Import/Test/Route Graph
```

例如：

```text
play.tailwindcss.com URL
  -> extracted CSS classes / config
  -> candidate concepts: arbitrary variants, parser, config resolver
  -> files: src/util/dataTypes.js, src/util/resolveConfig.js
  -> graph expansion: tests, callers, plugin chain
```

这样可以把“外部复现”转成“仓库内部搜索路线”。

### 8.4 URL-aware rerank 和 verifier

最终候选文件/函数应该被 URL 证据重新打分：

- 如果 GitHub blob path 直接命中文件，文件分应上调。
- 如果文件名只在无关 URL 或头像 URL 中出现，不应上调。
- 如果 Playground 解析出的 API 与函数名、测试名、文档名一致，应上调。
- 如果文档章节和代码注释/测试名一致，应上调。
- 如果候选文件无法解释 URL 中的复现行为，应降权。

### 8.5 增加 URL 消融实验

为了证明 URL 处理是否有效，后续应该增加三个实验设置：

| 设置 | 含义 |
|---|---|
| no-url | 删除所有 URL，只保留 issue 文本和图片 |
| url-string | 当前方式，只追加 URL 字符串 |
| url-structured | URL 分类、抓取、解析、图接入、rerank |

重点报告四组：

- GitHub blob 直接命中 gold 文件样本；
- Playground 样本；
- 文档/规范样本；
- URL 多但噪声高的样本。

如果 `url-structured` 只在 GitHub blob 上提升，而在 Playground/文档上没提升，说明仍然只是“路径解析”，没有解决真正的多模态跨语言定位问题。

## 9. 结论

URL 在这两个 benchmark 中不是边缘信息。SWE 全量有 65/102 个样本带 URL；Omni full-candidates 有 615/631 个样本带 URL。尤其是 Omni，URL 几乎是 issue 上下文的一部分。

但 URL 和定位的关系并不简单：

- 少量 URL 是直接文件线索；
- 更多 URL 是复现、文档、规范、路由、讨论和历史上下文；
- 它们往往指向“问题机制”，而不是直接指向 gold 文件；
- 当前 baseline 大多把 URL 当普通文本处理，或者只做浅层网页摘要，缺少 URL 类型化、复现解析、文档概念映射、route-to-component、URL-to-graph 这些关键步骤。

因此，URL 处理不足确实是现有定位效果不稳定的重要原因之一，尤其影响 Playground、文档规范、UI 路由和跨语言项目。后续框架如果要有明确创新点，建议把 URL 作为第一类证据对象，而不是 prompt 附件：先分类，再安全抓取，再抽取概念和符号，最后接入仓库图检索和 agent 搜索动作。

