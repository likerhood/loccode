# 跨语言图检索与 Agent 定位框架设计

本文接着 008 文档继续往下细化，重点回答一个问题：

> 既然 LocAgent、CoSIL、GraphLocator、GALA 都在用某种“图”或“搜索”，为什么它们在多语言、多模态、仓库级 issue 定位中仍然不稳？我们自己的跨语言框架到底应该怎么设计？

结论先写在前面：

> **不要试图为所有语言、所有仓库一次性构建一张全量调用图。更合理的路线是：用轻量跨语言实体图做底座，用语言 adapter 补足语义边，用 agent 在搜索过程中按需扩展局部图，并用 evidence verifier 防止搜索漂移。**

我把这个框架暂命名为：

> **PolyGraph-Agent：面向多语言仓库的证据路由图检索 Agent**

它不是一个单独的检索器，而是一个上层定位范式：

```text
Issue / 图片 / URL / 报错
  -> Evidence Frame
  -> Language Router
  -> PolyGraph Index
  -> Agentic Search State
  -> Patch Closure Verifier
  -> Top-k file/module/function
```

## 1. 现有 baseline 的“图”到底是什么

### 1.1 LocAgent：全仓搜索 + repo structure + 多语言图 fallback

LocAgent 的优势是 agent 能调用工具搜索代码、读取实体、逐步定位。它不是单纯 BM25，而是结合了仓库结构索引和图后处理。从这次 OmniGIRL full-candidates 的日志看，它在一些样本里会出现：

```text
Graph index for webpack__webpack-18319 has no file nodes; using multilingual graph fallback.
Built multilingual graph for ... webpack_webpack: nodes=15109 edges=38619
Loaded repo structure index ... files=7156 symbols=7321
```

这说明 LocAgent 已经有某种多语言 graph fallback：当原始 graph index 没有 file nodes 时，它会构建一个 multilingual graph，用文件、符号和边辅助后处理。

但实际问题也很明显：

1. **agent 的 query 生成不稳定。** 日志里多次出现 `search_code_snippets was called without search_terms or line_nums`，系统只能从 issue context 自动填词。自动填词经常把 URL、路径、markdown 片段、用户本机路径、文档链接等混进 query。
2. **缺少语言级搜索语法。** Java 的 package/class/method、Python 的 import/module、JS/TS 的 component/hook/selector 被放进同一套搜索工具里，agent 自己要猜该怎么搜。
3. **容易被仓库内高频词吸走。** 例如 Webpack 样本里，`webpack.config.js` 这种文件名非常强，LocAgent 容易进入 `examples/*/webpack.config.js`，而不一定是真实实现。
4. **多文件 closure 弱。** SWE 全量里 LocAgent File@8 为 17.65，Omni60 File@8 为 46.67。它在单文件、小补丁上强，在 SWE 多文件、多 hunk、UI 链路上明显吃亏。

LocAgent 给我们的启发是：**agent 搜索是必要的，但必须让 agent 带着语言 adapter 和显式 belief state 搜索，不能让它自由调用工具。**

### 1.2 CoSIL：调用/语义结构能提升文件级，但实体级不足

CoSIL 的优势是文件级候选比较集中。结果上：

| 数据集 | File@1 | File@8 | File MRR | Function@8 |
|---|---:|---:|---:|---:|
| SWE full | 10.78 | 18.63 | 37.01 | 4.90 |
| Omni full-candidates | 22.35 | 34.55 | 42.58 | 2.85 |
| Omni60 | 30.00 | 38.33 | 35.14 | 1.67 |

这说明 CoSIL 很擅长把候选压到少量看起来相关的文件，尤其在 Omni full-candidates 上 File@8 达到 34.55，比 LocAgent 的 25.99 更高。

但它的 Function@8 在 Omni60 只有 1.67，在 Omni full 也只有 2.85。也就是说：

> CoSIL 的图/结构信息能帮助“找到大概文件”，但没有稳定完成“语言相关的实体级定位”。

原因可能是：

- 文件级 prompt 比函数级 prompt 更稳定；
- 调用关系对 Java/Python/JS/TS 的覆盖方式不同；
- 顶层代码、配置、测试数据、MD/MDX/CSS 等非函数修改无法映射到函数；
- 同名 API 或同名工具类会让调用图附近的候选互相干扰。

CoSIL 给我们的启发是：**结构图不能只服务于 file rerank，还要服务于实体边界、语言 adapter 和 patch closure。**

### 1.3 GraphLocator：因果链/图推理表达力强，但构图重、局部陷阱明显

GraphLocator 的思路更像把 issue 和代码实体组织成一条因果链或解释链。它在一些样本上能给出更收敛的结果，Omni60 的 File F1@15 是 20.49，高于 LocAgent 和 BM25-MMIR。

但是它的两个短板非常突出。

第一，**构图成本很高**。这次 OmniGIRL full-candidates 的 GraphLocator 日志中，`babel__babel-15096` 开始构建图：

```text
Graph cache for issue babel__babel-15096 not found, construct...
Generating membership hierarchical graph: 82% | 14163/17258 [5:28:05 ...]
```

也就是说，一个 Babel 仓库样本构图就可能跑数小时。结果目录里当前 `GraphLocator/newtest/omnigirl-full-candidates/results/openai_qwen3-vl-8b/loc_results.json` 只有 13 个样本，没有完整评估文件。这不是模型效果问题，而是全量图构建范式本身在大仓库、多语言、全集上不经济。

第二，**图搜索容易局部陷阱**。SWE full 的 GraphLocator File@8 只有 6.86，日志里出现过：

```text
Max turn reached, stopping.
```

这说明它可能围绕一个合理但错误的局部子图探索到预算耗尽。因果链表达力强，但如果 seed 错了，图会把错误 seed 周围的节点越解释越合理。

GraphLocator 给我们的启发是：**不能先构全图再让模型推理；应该先 evidence routing，再按需构局部图，并且每轮扩展都要做反证检查。**

### 1.4 GALA：多模态前端强，但跨语言稳定性不足

GALA 在 SWE full 上是 file-level 最强：

| 数据集 | File@1 | File@8 | File MRR | Empty |
|---|---:|---:|---:|---:|
| SWE full | 10.78 | 25.49 | 47.40 | 0.00 |
| Omni60 | 6.67 | 20.00 | 12.83 | 43.33 |

这个差异很说明问题：GALA 对 SWE 这种前端 UI、多图片、多 URL 的 benchmark 有优势，可能因为它能更好地做图像-代码候选对齐；但在 Omni60 这种 Java/Python/TypeScript/JavaScript 混合的小补丁集合上，空预测比例非常高。

它的问题不是“不会看图”，而是：

- 图像/视觉 seed 对纯文本、Java/Python、后端库问题帮助有限；
- 多语言代码结构不统一时，GALA 的候选生成链路容易断；
- 如果没有语言 router，它不知道该把 issue 当成前端 UI、Java API、Python type checker、文档问题还是 CSS/layout 问题。

GALA 给我们的启发是：**多模态对齐应该作为证据通道之一，而不是整个框架的中心；没有图片或图片不关键时，要能自动降级到语言结构检索。**

### 1.5 MM-IR/BM25：低成本召回强，但精度和语义闭包不足

BM25-MMIR 在 Omni full-candidates 上：

| 数据集 | File@1 | File@8 | File@15 | Module@15 | Function@15 |
|---|---:|---:|---:|---:|---:|
| Omni full-candidates | 6.66 | 26.15 | 34.07 | 20.76 | 9.51 |
| Omni60 | 8.33 | 40.00 | 43.33 | 21.67 | 21.67 |

这说明跨语言 issue 里很多线索是词面强信号：类名、函数名、错误名、URL path、测试名。BM25 便宜、稳、可复现，很适合作为第一层召回。

但它的问题也明显：

- 同名测试、同名工具类、docs/example 会大量混入；
- 它不知道 Java package、Python import、JS component 的语义边；
- 它不会从 seed 文件扩展到 helper/test/style/config；
- 它不能解释为什么候选文件支持 issue。

BM25 给我们的启发是：**第一层必须保留词面召回，但必须交给语言 adapter、图边和 verifier 做重排。**

## 2. 现有 baseline 在多语言场景下的共同不足

### 2.1 语言被当成“文件扩展名”，而不是搜索策略

现在很多流程会识别 `.js`、`.py`、`.java`，但这还不够。真正的语言适配应该包括：

- 这个语言的实体类型是什么：class/function/method/interface/hook/component/selector/plugin；
- 这个语言的主边是什么：import/call/inheritance/test-to-impl/component composition/config-to-runtime；
- 这个语言的路径先验是什么：`src/main/java`、`src/test/java`、`packages/*/src`、`client/extensions/*`、`tests/fixtures`；
- 这个语言容易误伤什么：examples、docs、generated、snapshots、compat wrappers、typing stubs。

没有这些，agent 只能把所有语言都当成“文本文件集合”。

### 2.2 “调用图”不是跨语言的唯一答案

用户提到的理解很重要：

- LocAgent 更像全量仓库搜索/调用图辅助；
- CoSIL 更像动态或过程中的调用/语义图；
- GraphLocator 更像因果链图；
- GALA 更像多模态代码图对齐。

但跨语言 issue localization 不能只靠调用图，因为很多真实修改不在调用链上：

- 配置文件：`webpack.config.js`、`pyproject.toml`、`mypy.ini`；
- 文档/MDX：URL 对应文档页或示例；
- 样式：CSS/SCSS/theme token；
- 测试/fixture/snapshot；
- 顶层常量、schema、类型定义；
- generated 或 package metadata。

因此我们需要的是 **多关系证据图**，调用边只是其中一种。

### 2.3 全量图构建成本和局部搜索预算冲突

GraphLocator 在 Babel 上构图数小时，这是一个很现实的工程约束。大仓库里如果每个样本都构一张全图，成本不可接受；但如果只做局部图，又容易漏掉跨 package 边。

这说明图应该分层：

1. **仓库级轻量索引**：文件、路径、语言、符号、导入导出、测试文件配对。
2. **候选级语义索引**：只对 top-N 文件构更细 AST/调用/实体图。
3. **必要时重型分析**：对少数高置信 seed 启动 CodeQL/CPG/LSP/SCIP 级分析。

### 2.4 Agent 缺少反证和覆盖目标

很多失败不是“完全不知道”，而是“知道一部分但停错地方”。

例如 SWE `Automattic__wp-calypso-21492` 的真实文件是：

- `client/jetpack-connect/authorize.js`
- `client/jetpack-connect/utils.js`

LocAgent/CoSIL/GALA 都能靠近 Jetpack 相关区域，但容易落到 `plans`、`signup`、`state/jetpack` 等相邻文件。这说明 agent 需要显式问：

- 这个候选是否解释了 `authorize` 证据？
- 它是否只是同一业务域的相邻页面？
- issue 需要的是 UI component、route、state，还是 helper？
- 当前 top-k 是否覆盖 helper 文件？

没有这些问题，agent 会把“相关”当成“正确”。

## 3. 可借鉴的跨语言图和索引技术

这里不建议我们完全照搬任何一个系统，但可以吸收它们的分层思想。

### 3.1 Tree-sitter：跨语言语法实体底座

Tree-sitter 是解析器生成工具和增量解析库，可以为源文件构建 concrete syntax tree。它的优势是：

- 语言覆盖广；
- 速度快；
- 适合抽取函数、类、import、注释、字符串、JSX/TSX 结构；
- 很适合作为 repo structure 的底层解析器。

但 Tree-sitter 不理解完整语义：

- 不保证找到真实 definition/reference；
- 对动态语言、类型推断、跨文件解析弱；
- 不知道 package/build/test 语义。

所以它适合做 **Layer 0：跨语言 syntax/entity extraction**，不适合单独做定位。

参考：Tree-sitter 官方介绍：https://tree-sitter.github.io/

### 3.2 LSP / SCIP / LSIF：统一 definition/reference 索引

LSP 提供 go-to-definition、find-references 等语言服务能力。SCIP/LSIF 则把这些能力预计算成索引格式，适合代码导航。

这类技术适合做：

- definition/reference；
- symbol occurrence；
- cross-file reference；
- language-specific semantic indexing。

它们对我们很有价值，因为跨语言定位最缺的就是“同一个 API 在哪个文件定义、哪些文件引用、测试文件对应哪个实现”。

不足是：

- 每种语言都需要可用的 language server 或 indexer；
- 构建和缓存复杂；
- 对老版本仓库、monorepo、生成代码可能不稳定。

所以它适合做 **Layer 1：semantic xref graph**，按仓库缓存，而不是每个样本临时构建。

参考：

- LSP: https://microsoft.github.io/language-server-protocol/
- SCIP: https://github.com/scip-code/scip
- Sourcegraph SCIP: https://sourcegraph.com/blog/announcing-scip
- LSIF: https://lsif.dev/

### 3.3 CodeQL / Joern CPG：重型语义图

CodeQL 把代码当成可查询数据库，支持数据流分析。Joern 的 Code Property Graph 把 AST、CFG、PDG 等统一成代码属性图，适合安全和深层程序分析。

它们适合：

- 数据流/控制流；
- call graph；
- taint-like relation；
- API misuse；
- 安全漏洞或复杂行为 bug。

但对于我们的定位任务，不能默认全量使用：

- 构建成本高；
- 支持语言有限或配置复杂；
- 前端 UI、CSS、MDX、配置文件不一定适合；
- 对每个 issue 都跑重分析不现实。

所以它们适合做 **Layer 2：on-demand heavy graph**，只在高价值候选上启用。

参考：

- CodeQL data flow: https://codeql.github.com/docs/writing-codeql-queries/about-data-flow-analysis/
- Joern CPG: https://docs.joern.io/code-property-graph/

### 3.4 Kythe：跨语言 cross-reference 图思想

Kythe 提供一种面向多语言 cross-reference 的图 schema。它的启发是：跨语言不是把所有语言压成一种 AST，而是让不同语言 analyzer 产出统一的图 schema。

这对我们很关键：我们也不应该强迫 Java、Python、JS/TS 用同一套节点，而应该用统一上层 schema 包住各语言自己的实体。

参考：Kythe overview: https://kythe.io/docs/kythe-overview.html

## 4. 我们应该做的 PolyGraph-Agent

### 4.1 核心设计原则

PolyGraph-Agent 的原则：

1. **语言无关 evidence，语言相关搜索。**
2. **图是分层的，不是一次性全量的。**
3. **调用边只是多关系图的一部分。**
4. **agent 必须维护 belief state。**
5. **每轮扩展都要有反证检查。**
6. **最终目标不是单点命中，而是 patch closure。**

### 4.2 统一图 schema

建议定义一个跨语言统一 schema，但保留语言特异字段。

#### 节点类型

| 节点 | 说明 |
|---|---|
| `Repo` | 仓库 |
| `Package` | npm package、Maven module、Python package、workspace |
| `File` | 源文件、测试、配置、文档、样式 |
| `Symbol` | class/function/method/interface/component/hook/selector |
| `Route` | Web route、docs route、API route |
| `Test` | 测试文件、测试用例、snapshot |
| `Config` | webpack/mypy/tsconfig/package/pyproject 等 |
| `Asset` | 图片、CSS、snapshot、fixture |
| `IssueEvidence` | issue 文本、URL、截图、错误日志、代码片段 |

#### 边类型

| 边 | 说明 |
|---|---|
| `contains` | package -> file -> symbol |
| `imports` | 文件 import 另一个文件或包 |
| `calls` | 函数调用 |
| `defines` | 文件定义符号 |
| `references` | 文件引用符号 |
| `extends/implements` | 继承或接口实现 |
| `test_of` | 测试对应实现 |
| `renders` | component 渲染 child component |
| `styles` | CSS/SCSS 样式作用于组件 |
| `configures` | config 影响 runtime |
| `documents` | docs/MDX 说明 API 或组件 |
| `mentions` | issue evidence 提到 path/symbol/url/text |
| `contradicts` | evidence 和候选冲突 |

这里最关键的是：**`calls` 只是一条边，不是唯一边。**

### 4.3 分层构图策略

#### Layer 0：轻量跨语言实体图

构建时机：准备数据或首次运行时。

技术：

- Tree-sitter；
- regex fallback；
- path parser；
- repo structure；
- package metadata。

产物：

- file list；
- language；
- class/function/method/component；
- import/export；
- test/config/docs/style 标记；
- symbol-to-file 倒排索引。

这个层必须快，适合所有样本。

#### Layer 1：语义 cross-reference 图

构建时机：仓库级缓存，能构就构，不能构就降级。

技术：

- LSP；
- SCIP/LSIF；
- language-specific static analyzer；
- TypeScript server、JDT、Pyright/Jedi 等。

产物：

- definition/reference；
- implementation；
- test-to-impl；
- import resolved path；
- package internal dependency。

这个层解决“同名但不同包”的问题。

#### Layer 2：按需重型图

构建时机：只对 top-N seed 或疑难样本。

技术：

- CodeQL；
- Joern CPG；
- call graph；
- data/control flow；
- domain-specific query。

产物：

- call/data-flow path；
- API misuse path；
- exception propagation；
- state transition。

这个层解决深层行为问题，但不能默认全量跑。

### 4.4 Language Adapter

#### JS/TS Adapter

主要处理：

- React/Vue/component；
- hooks；
- store/selectors/actions；
- route/controller；
- package workspace；
- formatter/parser/plugin；
- test/snapshot/style。

核心边：

```text
component -> child component
component -> style
component -> state selector/action
test/snapshot -> source
plugin -> parser/printer/options
route -> page component
```

适合样本：

- SWE `wp-calypso`;
- SWE `Chart.js`;
- Omni `babel`, `webpack`, `prettier`, `tailwindcss`。

#### Java Adapter

主要处理：

- package path；
- class/method；
- interface/impl；
- exception；
- test class -> production class；
- Maven module。

核心边：

```text
TestClass -> ClassUnderTest
Interface -> Implementation
Exception -> throw/catch site
Builder/Factory -> Product
API class -> internal helper
```

适合样本：

- Omni `assertj`;
- Omni `gson`。

#### Python Adapter

主要处理：

- module/import；
- function/class；
- decorator；
- CLI entry；
- typing；
- test fixture。

核心边：

```text
test -> module
import -> definition
typing error -> checker/type node
CLI option -> parser/config
fixture -> tested behavior
```

适合样本：

- Omni `mypy`;
- Omni `google-cloud-python` 等。

#### Docs/Style/Config Adapter

主要处理：

- Markdown/MDX；
- CSS/SCSS；
- JSON/YAML；
- config files。

核心边：

```text
URL -> docs page
docs page -> embedded component/API
style token -> component
config option -> runtime path
fixture/snapshot -> source behavior
```

这类 adapter 很重要，因为 module/function gold 为 0 的样本并不代表没有修改，而是修改落在实体结构外。

## 5. Agent 搜索范式

### 5.1 从自由搜索改为状态机

不要让 agent 自由调用工具，而是用状态机约束：

```text
PLAN
  -> 生成 Evidence Frame
  -> 选择 Language Adapter

RETRIEVE
  -> BM25 / Dense / Symbol / Path / Graph 多路召回

INSPECT
  -> 阅读 top candidates
  -> 记录支持证据和反证

EXPAND
  -> 根据 adapter 选择边扩展
  -> 只扩展能解释未覆盖 evidence 的边

VERIFY
  -> 检查候选集合是否覆盖 issue 关键证据
  -> 检查是否 domain/language/path mismatch

STOP / REFORMULATE
  -> 覆盖足够则停止
  -> 否则改写 query 或切换 adapter
```

### 5.2 Belief State 表

每个候选必须有证据表：

| 字段 | 说明 |
|---|---|
| `candidate` | 文件/函数/模块 |
| `language` | 候选语言 |
| `role` | seed/helper/test/style/config/docs |
| `support` | 支持证据 |
| `missing` | 未覆盖证据 |
| `contradiction` | 反证 |
| `next_edges` | 可扩展边 |
| `score` | 综合分数 |

示例：

| 候选 | role | 支持 | 反证 | 下一步 |
|---|---|---|---|---|
| `packages/babel-traverse/src/scope/index.ts` | seed | scope、TypeScript、traverse | 无 | 扩展 tests/types |
| `packages/babel-types/src/definitions/typescript.ts` | related | TypeScript 词面强 | 不解释 scope 行为 | 降权 |
| `packages/babel-plugin-transform-typescript/src/index.ts` | related | TypeScript plugin | issue 不是 transform | 降权 |

这个表能解决 `babel__babel-16377` 这类样本的跨包漂移问题。

### 5.3 Query Reformulation 也要语言化

不能只让 LLM “换个说法”。Query rewrite 应该由 adapter 控制。

例如 Java:

```text
issue: recursive comparison map null handling
queries:
  - RecursiveComparisonAssert
  - Maps.assertContains
  - org.assertj.core.internal.Maps
  - recursive comparison test
negative:
  - docs
  - examples
```

例如 Python/mypy:

```text
issue: Overloaded method has both abstract and non-abstract variants
queries:
  - checkmember
  - overload
  - abstractmethod
  - semantic analyzer
  - type checker error code
negative:
  - docs common_issues
  - user local path /home/xxm/Desktop
```

日志里 LocAgent 自动从 issue 中提取 `/home/xxm/Desktop`、`mypy.readthedocs.io`、`github.com` 这类 query，说明现在缺少这一步过滤。

### 5.4 LLM Agent 到底应该怎样“想”和“搜”

这里需要把 Agent 的逻辑说得更清楚。我们现在看到的 LocAgent、GraphLocator、CoSIL 失败，不是因为 LLM 不会读代码，而是因为 LLM 在仓库级定位时经常缺少三个东西：

1. **证据结构化**：issue 里哪些是错误栈、哪些是 URL、哪些是图片描述、哪些是无关路径、哪些是用户环境噪声。
2. **语言搜索语法**：同一个关键词在 JS/TS、Java、Python、Markdown、CSS 中应该触发完全不同的搜索动作。
3. **搜索状态记忆**：已经看过哪些候选，哪些证据被解释了，哪些证据还没解释，哪些候选只是“相关”但不是“修改点”。

所以我们不能把 Agent 理解成“让 LLM 多轮调用 search”。更合理的 Agent 是一个带状态的定位控制器：

```text
Evidence Frame
  -> 生成候选搜索计划
  -> 执行一轮检索
  -> 阅读候选
  -> 更新 belief state
  -> 判断缺口
  -> 沿语言相关边扩展
  -> 反证检查
  -> 输出 top-k 或改写 query
```

这个过程里，LLM 负责理解和选择，但它不应该自由发挥。真正稳定的系统应该把 LLM 放在一个受控循环里。

#### 5.4.1 第一步：把 issue 拆成 Evidence Frame

一个多模态 issue 不能直接丢给搜索器。它应该先被拆成结构化证据：

| 字段 | 例子 | 作用 |
|---|---|---|
| `symptom` | bar border radius 渲染错误、inline SVG 文件名非法、lazy compilation accept 失败 | 决定问题类型 |
| `surface` | UI、rendering、compiler、loader、API、docs、typing、test | 决定语言/生态 adapter |
| `modal_evidence` | 图片、截图、网页 URL、CodeSandbox、GitHub discussion | 决定是否启用视觉或网页解析 |
| `code_terms` | `assetModuleFilename`、`resolveMatches`、`ContextReplacementPlugin` | 进入 symbol/BM25 检索 |
| `stack_terms` | 报错函数、报错文件、异常类型 | 进入 call/xref/exception 扩展 |
| `path_terms` | `css-loader`、`webpack.config.js`、`src/elements` | 进入路径检索，但要过滤外部路径 |
| `negative_terms` | `github.com`、`stackoverflow.com`、`node_modules`、用户本机路径 | 防止 query 污染 |
| `expected_artifacts` | source、test、style、config、fixture、snapshot | 用于 patch closure |

当前 baseline 的很多失败，就是因为没有这个拆分。比如 LocAgent 日志里出现过自动填词：

```text
search_code_snippets was called without search_terms or line_nums.
Auto-filled search_terms from the issue context:
['//github.com/webpack/webpack/discussions/15264',
 'github.com', 'webpack', 'discussions', '15264', '/sup', 'sup',
 '//stackoverflow.com/questions/ask']
```

这些词大多不该直接作为代码搜索 query。它们应该进入 `modal_evidence.url` 或 `negative_terms`，而不是进入 `search_code_snippets`。

#### 5.4.2 第二步：由 Language Router 决定搜索策略

Evidence Frame 之后，Agent 要先判断这是哪类仓库问题。不是只判断文件扩展名，而是判断“应该用哪套搜索动作”。

| 识别结果 | 搜索重点 | 应优先调用的图边 |
|---|---|---|
| JS/TS UI 或 React/Vue 组件 | component、route、state、style、test/snapshot | renders、imports、selector-to-component、style-to-component |
| Chart.js / canvas / p5.js 渲染 | controller、element、scale、helper、视觉回归测试 | test-image-to-source、element-helper、controller-element |
| Webpack/Babel/构建工具 | option、loader、plugin、parser、fixture、workspace package | option-to-plugin、loader-pipeline、fixture-to-source、package-dependency |
| Java 库/API | class、method、interface、assertion/test | test-to-class、interface-to-impl、method-call、exception-flow |
| Python typing/CLI | module、import、decorator、error message、test fixture | import、decorator、fixture-to-source、type-checker-flow |
| Docs/Markdown/MDX | doc page、frontmatter、embedded component、URL route | url-to-doc、doc-to-component、mdx-import |
| CSS/SCSS/theme | class、token、selector、component usage | class-to-component、style-import、theme-token |

这一步会改变 Agent 的行为。例如同样看到 `webpack.config.js`：

- 如果 issue 是“用户配置示例报错”，`webpack.config.js` 可能只是复现配置，不是修改点。
- 如果 issue 是“配置 schema 不接受某个 option”，应该去 schema/option parser。
- 如果 issue 是“assetModuleFilename 生成非法文件名”，应该去 asset module filename/template/runtime 逻辑，而不是一直搜 examples。

这就是语言和生态 adapter 的价值。

#### 5.4.3 第三步：每轮搜索都要更新 Belief State

Agent 每看一个候选，都不能只说“看起来相关”。它需要填一个状态表：

| 字段 | 解释 |
|---|---|
| `covered_evidence` | 这个候选解释了哪些证据 |
| `uncovered_evidence` | 还有哪些关键证据没解释 |
| `role` | seed、helper、test、config、style、docs、noise |
| `language_reason` | 为什么这个候选符合当前语言/生态 |
| `modal_reason` | 是否解释图片、URL、网页、报错栈 |
| `contradiction` | 为什么它可能是错的 |
| `next_action` | 读文件、沿边扩展、降权、改写 query、停止 |

一个好的 Agent 输出中间状态应该类似这样：

| 候选 | 支持证据 | 缺口 | 反证 | 下一步 |
|---|---|---|---|---|
| `lib/asset/AssetGenerator.js` | 解释 `assetModuleFilename` 和 filename 生成 | 还没解释 CSS inline SVG | 无 | 沿 loader/runtime 边扩展 |
| `examples/asset-modules/webpack.config.js` | 含配置示例 | 不解释运行时代码 | examples 目录，可能只是复现 | 降权 |
| `node_modules/next/dist/.../css-loader` | 出现在用户错误栈 | 不属于当前 repo | 外部依赖路径 | 作为线索，不输出 |

这比自由搜索稳定得多。

#### 5.4.4 第四步：多模态证据不是“直接找图片对应文件”

多模态样本里，图片和 URL 经常不是最终修改文件，而是症状证据。

比如 Chart.js 样本：

- `chartjs__Chart.js-8650` 有 145 张图片；
- `chartjs__Chart.js-9399` 有 41 张图片；
- 日志里 GALA 对 `chartjs__Chart.js-9399` 出现过图片请求 400，但流程仍继续处理。

这类样本不能把每张图片都等价送给 VLM。更合理的处理是：

```text
多张图片
  -> 去重/聚类
  -> 抽取视觉症状
  -> 转成渲染属性约束
  -> 路由到图形库 adapter
```

例如：

| 视觉症状 | 语言化证据 | 搜索策略 |
|---|---|---|
| bar 边角、圆角、裁剪异常 | `bar`, `radius`, `borderSkipped`, `rect path` | 搜 `element.bar`、`addNormalRectPath`、`parseEdge` |
| tooltip/hover 命中错误 | `interaction`, `nearest`, `intersect`, `point in area` | 搜 `core.interaction`、`helpers.canvas` |
| layout 间距、legend 溢出 | `layout`, `box`, `fit`, `padding` | 搜 layout controller/helper |

这样图片变成了结构化约束，而不是一个黑盒 embedding。

#### 5.4.5 第五步：Patch Closure 要主动补文件

我们的 strict 指标要求 top-k 覆盖所有 gold file/module/function。很多 baseline 失败不是 seed 完全错，而是只找到一个 seed，没有补齐 helper/test/style/config。

因此 Agent 的停止条件不能是“我找到一个相关文件”。应该是：

```text
是否已覆盖全部关键证据？
是否缺 helper？
是否缺测试或 fixture？
是否缺 style/config/schema？
当前 top-k 是单文件问题还是多文件 closure？
```

在 SWE/Chart.js 这种样本中，真实修改可能同时跨：

- controller；
- element；
- interaction；
- layout；
- helper；
- visual fixture。

如果 Agent 只输出 `src/elements/element.bar.js`，它可能 file-level 部分正确，但 strict full-coverage 会失败。

### 5.5 结合实际失败案例重新看 Agent 应该怎么改

下面用我们运行日志里的具体样本来说明。

#### 案例 A：Webpack/Next/Tailwind 类样本，URL 和外部路径污染 query

在 OmniGIRL full-candidates 的 LocAgent 日志中，有一类 Webpack 相关样本会出现这样的过程：

```text
search_code_snippets was called without search_terms or line_nums.
Auto-filled search_terms from the issue context:
['When i concatenate the',
 'codesandbox.io',
 '/node_modules/next/dist/build/webpack/loaders/css-loader/src/index.js',
 'node_modules']
```

随后 Agent 生成了这样的分析：

```text
The problem involves a webpack error related to dynamically naming nested groups
in Tailwind CSS, specifically in a Next.js project...
Potential areas:
- Tailwind CSS's resolveMatches function
- Next.js's CSS loader configuration
- Tailwind CSS's group name resolution logic
```

问题在于：这个分析听起来合理，但对仓库定位非常危险。

它把证据混成了三类：

1. 用户复现环境：Next.js、CodeSandbox、`node_modules`。
2. 可能的外部依赖：Tailwind CSS、Next.js css-loader。
3. 当前 repo 内真正可修改的 Webpack 代码。

如果没有 Evidence Frame，Agent 会在这三类之间乱跳。对于当前 repo 的定位，`node_modules/next/...` 应该是外部栈线索，不应该直接作为输出文件；`codesandbox.io` 是复现 URL，不应该作为代码检索词；`Tailwind CSS` 可能是症状来源，但如果仓库是 Webpack，它更可能需要定位 loader/asset/module/runtime 逻辑。

改进后的 Agent 应该这样走：

```text
Evidence Frame:
  symptom = CSS/loader/webpack pipeline error
  external_context = Next.js, CodeSandbox, node_modules path
  code_terms = css-loader, webpack, resolveMatches, group, loader
  negative_terms = codesandbox.io, node_modules, next/dist
  expected_role = loader/runtime/plugin logic

Language Router:
  ecosystem = JS build tool
  adapter = webpack-loader-pipeline

Search Plan:
  1. path search: lib/*loader*, lib/*Module*, lib/*Plugin*
  2. symbol search: loader, css, asset, module filename
  3. fixture search: test cases mentioning the error or option
  4. reject external node_modules path as output
```

然后 Belief State 应该把候选分成：

| 候选类型 | 处理 |
|---|---|
| `examples/*/webpack.config.js` | 可作为复现线索，但默认降权 |
| `test/configCases/...` | 高价值，因为 fixture 通常对应实现 |
| `lib/*.js` 实现文件 | 高价值 seed |
| `node_modules/next/dist/...` | 外部证据，不输出 |
| GitHub discussion/StackOverflow | URL 证据，不进入代码 top-k |

这就是多语言/多生态 Agent 和普通搜索 Agent 的差别。

#### 案例 B：Webpack `assetModuleFilename`，配置词很强但真实修改在实现链路

另一个 OmniGIRL 日志片段反复出现：

```text
css-loader
assetModuleFilename
inline SVG
filename
.svg
```

Agent 的自然反应是搜 `assetModuleFilename` 和 `css-loader`。这一步没错，但问题是 `webpack.config.js` 和 examples 里也大量出现这些词。普通 BM25 或自由 Agent 会被配置文件吸走。

更好的搜索过程是：

1. **第一轮**：用 `assetModuleFilename` 找到所有配置、测试、实现。
2. **角色分类**：
   - examples/config 是复现；
   - test/configCases 是行为规格；
   - lib 目录是实现；
   - docs 是解释，不是修复点。
3. **图扩展**：
   - 从 test/configCases 沿 `fixture-to-source` 找实现；
   - 从 option/schema 沿 `option-to-runtime` 找 filename 生成逻辑；
   - 从 loader 线索沿 `loader-pipeline` 找 asset module。
4. **反证**：
   - 如果候选只包含配置值但不生成 filename，降权；
   - 如果候选属于 `examples/`，除非 gold 明确是 example，否则不进 top-k 前列。

这类问题体现的是：**跨语言图不只是 call graph，而是 option/config/test/runtime 关系图。**

#### 案例 C：Chart.js 多图片样本，视觉证据需要转成图形库语义

SWE full 中 Chart.js 的多模态样本很典型：

```text
chartjs__Chart.js-8650 images=145 urls=1
chartjs__Chart.js-9399 images=41 urls=1
```

其中 `chartjs__Chart.js-9399` 的 gold 文件是：

```text
src/elements/element.bar.js
```

gold function 包括：

```text
addNormalRectPath
hasRadius
parseEdge
skipOrLimit
startEnd
swap
```

`chartjs__Chart.js-8650` 的 gold 文件跨多个区域：

```text
src/controllers/controller.line.js
src/core/core.controller.js
src/core/core.interaction.js
src/core/core.layouts.js
src/elements/element.point.js
src/helpers/helpers.canvas.js
```

这两个样本说明：图片很多时，问题可能不是“找到图片对应的文件”，而是要把视觉症状翻译成图形库内部概念。

对于 Chart.js，Agent 应该有一个 `chart-rendering adapter`：

| 图片症状 | 搜索词 | 图扩展 |
|---|---|---|
| bar 圆角/边缘异常 | `bar`, `radius`, `rect`, `borderSkipped` | `element.bar` -> drawing helper -> tests |
| hover 命中区错误 | `interaction`, `nearest`, `intersect`, `point` | `core.interaction` -> `helpers.canvas` -> element |
| layout 或 canvas 边界错误 | `layout`, `area`, `chartArea`, `clip` | controller -> layout -> canvas helper |

当前 GALA 在 SWE full 上 file-level 最强，说明视觉证据有价值；但日志里也出现了图片请求 400。我们的框架不应该依赖“每张图片都成功送进 VLM”。应该先做图像聚类和症状摘要：

```text
145 张图片
  -> hash/尺寸/相似度去重
  -> 选择代表图
  -> VLM 摘要视觉差异
  -> 转成 code terms
  -> 进入语言 adapter
```

这样即使部分图片失败，也不会导致整个定位链路断掉。

#### 案例 D：Babel 大仓，GraphLocator 全量构图不经济

OmniGIRL full-candidates 的 GraphLocator 日志中，`babel__babel-15096` 出现：

```text
Graph cache for issue babel__babel-15096 not found, construct...
Saving graph to .../babel__babel-15096.auto.json
```

同一批日志和 LocAgent 输出显示 Babel 仓库结构巨大：

```text
Loaded repo structure index for babel__babel-15096: files=25325 symbols=18097
```

GraphLocator 结果目录里 full-candidates 当前只有 13 个样本的 `loc_results.json`，说明它在大仓全集上很容易被构图成本卡住。

Babel 这种 monorepo 不适合“每个 issue 构一张全仓因果图”。更合适的是：

```text
Evidence Router:
  issue terms -> package/workspace candidates

Package Sharding:
  packages/babel-parser
  packages/babel-traverse
  packages/babel-types
  packages/babel-generator
  plugins/*

Local Graph:
  只对 top-3 package 构局部图

Cross-package Edge:
  parser AST -> traverse path -> types definition -> plugin transform
```

也就是说，GraphLocator 的因果链思想可以保留，但构图粒度要从“全仓”改成“证据路由后的局部包图”。

#### 案例 E：Automattic Jetpack，多文件 closure 比单 seed 更重要

SWE full 中 `Automattic__wp-calypso-21492` 的 gold 文件是：

```text
client/jetpack-connect/authorize.js
client/jetpack-connect/utils.js
```

这类样本对 Agent 很容易产生“业务域正确但文件不全”的失败。`jetpack-connect`、`plans`、`signup`、`state/jetpack` 都可能在文本上相关，但 strict full-coverage 需要同时覆盖 route/page 和 helper。

正确的 Agent 过程应该是：

1. 找到 `jetpack-connect` 业务域；
2. 判断 issue 是 authorization/connect flow，不是 plan UI 或 generic state；
3. 把 page/route seed 和 helper utils 看成 patch closure；
4. 如果只找到 `authorize.js`，沿 import/export 或 same-folder helper 边扩展到 `utils.js`；
5. 如果只找到 `utils.js`，沿 caller edge 反查 `authorize.js`。

这个案例说明：**文件级定位不是 top-1 相似度问题，而是一个覆盖问题。**

#### 案例 F：GraphLocator 在 SWE full 出现 `Max turn reached`

SWE full 的 GraphLocator 日志里出现过：

```text
Max turn reached, stopping.
```

这通常意味着模型围绕一个局部解释链走到预算耗尽。图方法的一个危险点是：只要初始 seed 看起来合理，后续图扩展会不断找到“相关邻居”，但不一定能回到真正 gold。

我们的 Agent 必须加入反证检查：

| 反证问题 | 目的 |
|---|---|
| 这个候选是否解释了所有关键 evidence？ | 防止只解释局部 |
| 它是否位于 examples/docs/generated？ | 防止路径误伤 |
| 它是否只是同名 API，而非同一执行链？ | 防止符号同名 |
| 继续扩展是否只产生同类邻居？ | 检测图局部陷阱 |
| 是否需要切换 adapter？ | 从 call graph 切到 config/test/style graph |

当连续两轮没有覆盖新 evidence 时，Agent 应该停止当前局部图，回到 Evidence Frame 重新路由，而不是继续扩展。

### 5.6 我们框架中的 Agent 具体执行模板

下面是一个可以直接实现的执行模板。

#### Step 1：Evidence Parser

```json
{
  "issue_type": "build-tool-asset-filename",
  "primary_language": "javascript",
  "ecosystem": "webpack",
  "modalities": ["url", "code-snippet"],
  "positive_terms": ["assetModuleFilename", "inline SVG", "css-loader", ".svg"],
  "negative_terms": ["github.com", "stackoverflow.com", "node_modules", "codesandbox.io"],
  "expected_roles": ["test", "runtime", "plugin", "helper"],
  "risk": ["examples drift", "external dependency drift"]
}
```

#### Step 2：Adapter Plan

```json
{
  "adapter": "js-build-tool",
  "queries": [
    {"kind": "symbol", "terms": ["assetModuleFilename"]},
    {"kind": "path", "terms": ["lib", "asset", "module", "filename"]},
    {"kind": "test", "terms": ["inline SVG", ".svg", "filename"]},
    {"kind": "config", "terms": ["assetModuleFilename"]}
  ],
  "expand_edges": [
    "test_to_source",
    "option_to_runtime",
    "loader_pipeline",
    "same_package_helper"
  ],
  "downrank_paths": ["examples/", "docs/", "node_modules/"]
}
```

#### Step 3：Candidate Belief Update

```json
{
  "candidate": "lib/asset/AssetGenerator.js",
  "role": "runtime",
  "support": ["asset filename generation", "extension handling"],
  "missing": ["css-loader inline SVG reproduction"],
  "contradiction": [],
  "next_edges": ["test_to_source", "same_package_helper"],
  "score": 0.82
}
```

#### Step 4：Patch Closure Verifier

```text
seed candidate exists?
helper candidate exists?
test/fixture candidate exists?
config/schema candidate exists if issue mentions option?
style/docs candidate exists if issue mentions CSS/MDX?
all high-confidence candidates have role?
any top candidate is external/noise?
```

#### Step 5：Stop Rule

Agent 只有在下面条件满足时才停止：

1. top-k 中至少有一个 seed；
2. 关键 evidence 被覆盖；
3. 没有明显外部路径或 examples 污染；
4. 如果 issue 暗示多文件修改，closure 已经补齐 helper/test/config；
5. 如果 function gold 可能为空，输出 file/module 时不要硬编函数。

### 5.7 为什么这就是“多语言 + 多模态”的 Agent 适配

这套逻辑和普通 Agent 的区别在于：

| 普通 Agent | PolyGraph-Agent |
|---|---|
| 直接把 issue 丢给 search | 先拆 Evidence Frame |
| LLM 自己决定搜什么 | Language Adapter 生成搜索计划 |
| 搜到相关文件就输出 | Belief State 检查支持、缺口和反证 |
| 主要靠文本相似度 | 文本、视觉、URL、路径、符号、图边共同投票 |
| 调用图是主要结构 | 调用、import、test、config、style、doc、route 多关系图 |
| 容易被 examples/docs/URL 污染 | negative evidence 和 role rerank 显式降权 |
| 单 seed 成功就停 | Patch Closure Verifier 补齐多文件 |

所以我们的创新不是“又做一个图”，而是：

> **把 LLM Agent 的搜索行为语言化、证据化、图约束化，并用 failure-aware verifier 把多模态和跨语言噪声挡在 top-k 之外。**

## 6. 多语言下“调用关系”的正确理解

### 6.1 不是所有语言都适合同一种 call graph

JS/TS 中，UI 问题经常通过 component composition、state/action、route、style 传播，不一定是函数调用。

Java 中，method call、interface implementation、exception flow 更可靠。

Python 中，import、decorator、dynamic dispatch、typing checker 逻辑比普通 call graph 更重要。

Docs/CSS/Config 中，根本没有传统意义上的 call graph。

所以我们应该把“调用图”泛化成：

> **Issue-relevant relation graph**，即和 issue 定位相关的多关系图。

### 6.2 每种语言的高价值边不同

| 语言/生态 | 高价值边 | 低价值或易误伤边 |
|---|---|---|
| JS/TS 前端 | component renders、route-to-page、state selector、test/snapshot-to-source、style-to-component | examples、storybook、generated、global util |
| Babel/Webpack/Prettier | package workspace、parser/printer/plugin、test fixture、option/schema | website/docs、benchmark-only file |
| Java | test-to-class、interface-to-impl、method call、exception flow、package module | API docs、example、test utility |
| Python | import、test fixture、decorator、typing error path、CLI config | docs common_issues、local path、stub-only unless typing issue |
| Markdown/MDX | URL-to-doc、frontmatter、embedded component | unrelated docs text |
| CSS/SCSS | class/token-to-component、theme import | global reset/legacy style |

### 6.3 图扩展必须服务于 patch closure

Graph expansion 的目标不是“找更多相关文件”，而是补齐 patch closure：

- seed 文件；
- direct helper；
- paired test；
- style/config/schema；
- sibling file；
- generated fixture/snapshot。

如果扩展出的文件没有角色，就不应该进入 top-k。

## 7. 针对实际运行结果的改进点

### 7.1 针对 LocAgent

问题：

- Omni full 上 File@8 只有 25.99，低于 CoSIL 34.55；
- 日志中大量无显式 search_terms，自动 query 混入 URL/用户路径/docs；
- Webpack 样本最终停在 `examples/*/webpack.config.js`；
- 多语言 fallback graph 有用，但还没有被 agent 显式利用。

改进：

1. 给 `search_code_snippets` 加 language adapter query guard；
2. 自动过滤 `github.com`、本地路径、docs URL、StackOverflow、readthedocs 这类非代码 query；
3. 如果 query 来自 URL，先解析 URL path/domain，不直接全文作为 search term；
4. tool observation 输出候选时增加 role：source/test/docs/example/config/generated；
5. agent 每步必须更新 belief state，禁止没有 query 的 broad search。

### 7.2 针对 CoSIL

问题：

- Omni full File@8 很好，但 Function@8 只有 2.85；
- Omni60 File@1 最高，但 Function@8 只有 1.67；
- 容易停在文件级语义相似，而不做实体边界判断。

改进：

1. CoSIL 输出的 file candidates 作为 seed；
2. 用 PolyGraph 的 language adapter 下钻到 function/module；
3. 对 function gold 为 0 的样本不要强制函数定位，改为 file/top-level entity；
4. 加 test-to-impl 和 package-specific rerank。

### 7.3 针对 GraphLocator

问题：

- SWE full File@8 只有 6.86；
- Omni full GraphLocator 只完成 13 个样本，Babel 构图极慢；
- Max turn 说明图搜索有局部陷阱。

改进：

1. 不对每个 issue 构完整因果图；
2. 先用 BM25/adapter 得到 top-N seed；
3. 只对 seed 邻域构局部 causal graph；
4. 每轮扩展做 contradiction check；
5. 大仓库按 package/workspace 分片构图。

### 7.4 针对 GALA

问题：

- SWE full 最强，说明视觉/代码对齐有效；
- Omni60 Empty 43.33，跨语言和非视觉场景不稳定。

改进：

1. 把 GALA 的视觉 seed 当作一个通道，而不是主流程；
2. 如果样本没有图片或图片不关键，自动降级到 text+language graph；
3. 对 Java/Python 样本关闭视觉优先策略；
4. GALA 输出为空时回退到 BM25/CoSIL seed。

### 7.5 针对 MM-IR/BM25

问题：

- Omni full File@15 达 34.07，说明召回强；
- 但 File@1 只有 6.66，precision/rank 不够。

改进：

1. BM25 做 first-stage recall；
2. language adapter 做 rerank；
3. graph edge 做 closure；
4. agent verifier 做最终过滤。

## 8. 推荐的整体实现架构

### 8.1 模块结构

建议新建一个实验框架目录：

```text
PolyGraphAgent/
  adapters/
    js_ts.py
    java.py
    python.py
    docs_style_config.py
  index/
    tree_sitter_index.py
    path_index.py
    symbol_index.py
    xref_index.py
    graph_store.py
  retrieval/
    bm25.py
    dense.py
    symbol.py
    path.py
    graph_expand.py
  agent/
    evidence_frame.py
    belief_state.py
    planner.py
    verifier.py
    closure.py
  evaluation/
    run_baseline_bridge.py
    analyze_failures.py
```

### 8.2 每个样本的处理流程

```text
1. load issue sample
2. extract evidence frame
3. detect primary language/ecosystem
4. build or load Layer 0 index
5. optional load Layer 1 xref graph
6. run hybrid retrieval
7. agent inspect top candidates
8. graph closure expansion
9. verifier rerank and filter
10. output file/module/function top-k
```

### 8.3 和现有 baseline 融合

可以先不重写所有 baseline，而是做 meta-localizer：

```text
BM25/MM-IR candidates
CoSIL candidates
LocAgent candidates
GraphLocator candidates if available
GALA visual candidates if available
        ↓
PolyGraph-Agent Reranker
        ↓
Patch Closure Verifier
        ↓
Final top-k
```

这样可以利用现有结果，同时证明框架创新点。

## 9. 实验设计

### 9.1 主实验

| 数据集 | 目的 |
|---|---|
| SWE-bench Multimodal full-dev 102 | 多模态、前端、多文件、多 hunk |
| SWE60 | 小规模可复现实验 |
| OmniGIRL unified60 | 跨语言小补丁 |
| OmniGIRL full-candidates 631 | 跨语言全集稳定性 |

### 9.2 分组实验

建议按以下维度分组：

- 语言：JS/TS、Java、Python、Docs/Config/CSS；
- 模态：仅图片、仅 URL、图片+URL、纯文本；
- patch 规模：gold_file=1、2-5、>5；
- hunk 规模：hunk=1、2-5、>5；
- function gold：0、1、2-5、>5；
- 仓库规模：files < 1000、1000-5000、>5000；
- baseline failure type：domain drift、language mismatch、empty response、multi-file miss、graph trap。

### 9.3 消融实验

| 版本 | 组件 | 目标 |
|---|---|---|
| V0 | BM25 only | 低成本召回基线 |
| V1 | BM25 + language adapter | 验证跨语言 query 的价值 |
| V2 | V1 + symbol/path rerank | 验证实体和路径先验 |
| V3 | V2 + graph closure | 验证多文件补齐 |
| V4 | V3 + agent belief state | 验证搜索闭环 |
| V5 | V4 + visual/url evidence | 验证多模态证据 |
| V6 | V5 + failure verifier | 验证稳定性和空结果控制 |

## 10. 预期创新点

### 创新点 1：跨语言 Evidence Router

不是简单识别语言，而是把 issue evidence 转换成语言相关搜索计划。

### 创新点 2：分层 PolyGraph

把 Tree-sitter、path/symbol index、LSP/SCIP、CodeQL/CPG 按成本分层，不再每个样本全量构图。

### 创新点 3：Agentic Belief State

agent 每轮必须维护候选证据、反证、缺口和下一步边，避免自由搜索漂移。

### 创新点 4：Patch Closure Verifier

针对 strict full-coverage 指标，显式从 seed 扩展 helper/test/style/config，而不是只找一个最像的文件。

### 创新点 5：Failure-aware Graph Search

把我们实际观察到的失败类型作为 verifier 规则：URL 污染、docs 污染、examples 污染、同名包漂移、空输出、图局部陷阱。

## 11. 可以写成论文/项目的故事

可以这样讲：

> 现有仓库级 issue localization 方法通常选择三条路线：LLM agent 搜索、代码图推理、多模态候选对齐。我们在 SWE-bench Multimodal 和 OmniGIRL 上发现，这三条路线在多语言、多模态场景下各有系统性失败：agent 容易 query 漂移，图方法构建成本高且局部陷阱明显，多模态对齐对跨语言纯文本样本不稳定。为此，我们提出 PolyGraph-Agent：一个跨语言证据路由的 agentic 定位框架。它先把 issue 解析成语言无关的 Evidence Frame，再通过语言 adapter 生成语言相关的检索计划，并在分层 PolyGraph 上执行带 belief state 的检索、阅读、扩展和验证。该框架把调用图泛化为 issue-relevant relation graph，并通过 patch closure verifier 面向 strict full-coverage 指标补齐多文件修改。实验可在 SWE full、SWE60、Omni60、Omni full-candidates 上验证其对多模态、多语言、多文件样本的稳健提升。

## 12. 最终框架范式：把 Agent 做成“跨语言多模态定位编译器”

前面的内容已经分别讨论了 baseline、图索引、语言 adapter、Agent 状态机和失败案例。这里把最终范式再收束一下。我们要做的不是简单增强某个 baseline，也不是“给 LocAgent 加一张图”或“给 GraphLocator 加更多搜索”。更准确的定位是：

> **把仓库级 issue localization 重新建模成一个跨语言、多模态、证据驱动的 Agentic Retrieval 编译过程。**

也就是说，issue、图片、URL、报错栈、代码片段不是直接进入搜索器，而是先被编译成一个中间表示；语言 adapter 再把这个中间表示编译成不同语言/生态下的检索计划；Agent 在执行计划时不断维护证据状态、反证状态和 patch closure 状态；最后输出 file/module/function top-k。

这个范式可以叫：

> **Evidence-Compiled PolyGraph Agent**

核心思想如下：

```text
Raw Issue + Images + URLs + Logs
        ↓
Evidence IR                     # 多模态、URL、错误栈、代码词、噪声词的结构化中间表示
        ↓
Language / Ecosystem Router      # 判断 JS UI、JS build tool、Python typing、Java API、Docs/CSS...
        ↓
Adapter-Compiled Search Plan     # 每种语言生成不同 query、边、降权规则、closure 目标
        ↓
Hybrid Retrieval + PolyGraph     # BM25 / Dense / Symbol / Path / Visual / URL / Graph 多路召回
        ↓
Agentic Belief State             # 每轮记录候选支持证据、缺口、反证、下一条边
        ↓
Patch Closure Verifier           # 补齐 seed/helper/test/style/config/docs 等多文件闭包
        ↓
Three-level Localization         # 输出 file / module / function top-k
```

### 12.1 为什么叫“编译器”而不只是 Agent

普通 Agent 往往是：

```text
issue -> LLM decides search terms -> search -> read -> answer
```

这个过程太自由，所以会出现我们日志里反复看到的问题：

- URL 被当成代码搜索词；
- `node_modules`、用户本地路径、StackOverflow 链接污染 query；
- Java/Python/JS/TS 被同一套搜索动作处理；
- 找到一个相关 seed 就停止，漏掉 helper/test/config；
- 图搜索进入局部解释链，预算耗尽；
- 多模态图片被当成黑盒输入，没有转成代码可用的症状约束。

“编译器式 Agent”多了一层中间表示和受控执行：

| 阶段 | 普通 Agent | Evidence-Compiled Agent |
|---|---|---|
| 输入 | 直接读 issue | 先拆成 Evidence IR |
| 语言处理 | LLM 猜 | Router 选择语言/生态 adapter |
| 搜索词 | 自由生成 | adapter 编译 query、path、symbol、negative terms |
| 图边 | 全量或固定图 | 根据证据按需选择边 |
| 多模态 | 直接问 VLM | 图片/URL 转成症状约束 |
| 停止条件 | “看起来够了” | closure verifier 检查覆盖与反证 |

所以这里的 Agent 不只是聊天式推理器，而是一个定位控制器：它负责在不同证据通道、不同语言 adapter、不同图边之间调度。

### 12.2 Evidence IR：多模态和多语言的共同入口

Evidence IR 是整个系统的中间表示。它的目标不是总结 issue，而是把 issue 变成可检索、可验证、可路由的证据字段。

一个样本的 Evidence IR 应该包含：

| 字段 | 说明 | 示例 |
|---|---|---|
| `symptom` | 用户看到的问题现象 | tooltip 位置错误、asset filename 非法、abstract overload 报错 |
| `surface` | 问题表面类型 | UI/rendering、build tool、typing、API、docs、style |
| `modal_evidence` | 图片、截图、网页、CodeSandbox、GitHub discussion | Chart.js 截图、Next.js sandbox、issue URL |
| `visual_assertions` | 图片转成的代码可用约束 | bar radius clipping、legend overflow、hover hit area |
| `url_evidence` | URL 的角色 | 复现链接、文档链接、外部依赖、GitHub 讨论 |
| `stack_terms` | 报错栈、异常、文件名 | `css-loader`, `assetModuleFilename`, `TypeError` |
| `code_terms` | API、函数、类、配置项 | `resolveMatches`, `RecursiveComparisonAssert`, `parseEdge` |
| `path_terms` | 可疑路径或包名 | `babel-traverse`, `language-js`, `jetpack-connect` |
| `negative_terms` | 不应直接进入代码搜索的噪声 | `github.com`, `stackoverflow.com`, `node_modules`, 本地路径 |
| `expected_roles` | 预计 patch 可能涉及的文件角色 | seed、helper、test、fixture、style、config、schema、docs |

例如 Webpack/Next/Tailwind 的报错不能直接搜 `codesandbox.io` 或 `/node_modules/next/dist/...`。Evidence IR 会把它们分开：

```json
{
  "surface": "build-tool-loader",
  "code_terms": ["css-loader", "assetModuleFilename", "inline SVG", ".svg"],
  "url_evidence": ["CodeSandbox reproduction"],
  "external_context": ["Next.js", "node_modules/next/dist/build/webpack/loaders/css-loader"],
  "negative_terms": ["codesandbox.io", "node_modules", "github.com"],
  "expected_roles": ["test", "fixture", "runtime", "schema", "loader"]
}
```

这一步是多模态和跨语言适配的入口。没有 Evidence IR，后面所有搜索都是在混乱文本上做碰运气。

### 12.3 Language / Ecosystem Router：不是识别扩展名，而是选择搜索语法

多语言适配不能只做 `.py`、`.java`、`.js` 分类。真正要区分的是“这个 issue 应该用哪种仓库语义去搜”。

| Router 输出 | 典型仓库 | 优先证据 | 高价值边 | 常见误伤 |
|---|---|---|---|---|
| JS/TS UI Adapter | wp-calypso、React/Vue 项目 | component、route、state、style、screenshot | route-to-component、selector-to-component、style-import、test-snapshot | signup/plans/state 通用文件 |
| Chart/Canvas Adapter | Chart.js、p5.js | visual assertion、element/controller/helper | controller-to-element、element-to-helper、visual-test-to-source | demo、docs、fixture 误伤 |
| JS Build Tool Adapter | Webpack、Babel、Prettier | option、parser、printer、loader、fixture | test-to-source、option-to-runtime、package dependency | examples、docs、外部 node_modules |
| Python Typing/CLI Adapter | mypy、pytest、tqdm | error message、decorator、import、test name | import、test-to-source、decorator、type-checker-flow | docs、stub、common issues |
| Java API Adapter | gson、netty、assertj | class、method、package、stack trace | test-to-class、method-call、interface-to-impl、exception-flow | examples、integration tests |
| Docs/CSS/Config Adapter | Tailwind、MDX、style repo | URL、frontmatter、selector、theme token | doc-to-component、style-to-component、config-to-runtime | module/function gold 为空 |

同一个词在不同 adapter 中含义不同。比如 `scope`：

- 在 Babel 中可能指 `babel-traverse/src/scope`；
- 在 CSS/Tailwind 中可能指 selector scope；
- 在 Python typing 中可能指 semantic analyzer symbol scope；
- 在 Java 中可能是 dependency injection scope。

如果没有 Router，Agent 会被同名概念带偏。

### 12.4 PolyGraph 不是一张图，而是一组按需启用的关系

“跨语言图”不应该理解为统一的一张超级调用图。调用图只是其中一种边。我们真正需要的是 issue-relevant relation graph：

| 边类型 | 解释 | 适用场景 |
|---|---|---|
| `imports` | 文件/模块依赖 | JS/Python/Java 基础扩展 |
| `calls` | 函数/方法调用 | 实现逻辑追踪 |
| `defines` | 文件定义符号 | symbol rerank |
| `references` | 符号引用 | LSP/SCIP 类导航 |
| `test_to_source` | 测试/fixture 对应实现 | Webpack/Babel/Prettier/Java |
| `option_to_runtime` | 配置项到运行时实现 | Webpack、Babel、Chart.js option |
| `route_to_component` | URL/route 到页面组件 | wp-calypso、React apps |
| `style_to_component` | CSS/SCSS class 到组件 | UI/CSS 问题 |
| `visual_to_render_entity` | 视觉症状到绘制实体 | Chart.js、p5.js、canvas |
| `doc_to_symbol` | 文档/API 名到代码实体 | docs、MDX、API reference |
| `package_to_package` | monorepo package 依赖 | Babel、Webpack、Calypso |

这里的创新点是：**图边由 Evidence IR 和 Language Adapter 选择，而不是固定全量展开。**

例如：

- Chart.js 图片里出现 bar 圆角问题，启用 `visual_to_render_entity`、`controller_to_element`、`element_to_helper`。
- Webpack 配置项问题，启用 `option_to_runtime`、`test_to_source`、`loader_pipeline`。
- Babel TypeScript scope 问题，启用 `package_to_package`、`symbol_reference`、`test_to_source`，但降权 `babel-types` 里只解释 TypeScript 名词、不解释 scope 行为的文件。
- Omni 中 `module/function=0` 的样本，启用 `docs_style_config_adapter`，不要强行找函数。

### 12.5 Agent 的动作空间要显式设计

Agent 不应该只有 `search` 和 `read`。它需要一组带约束的动作：

| 动作 | 输入 | 输出 | 作用 |
|---|---|---|---|
| `extract_evidence` | issue、图片、URL | Evidence IR | 结构化证据 |
| `route_language` | Evidence IR、repo profile | adapter | 选择语言/生态策略 |
| `retrieve_text` | 正负 query | 文件候选 | BM25/keyword 召回 |
| `retrieve_symbol` | API/class/function 名 | 符号候选 | 精确实体召回 |
| `retrieve_path` | package/path terms | 路径候选 | monorepo/package 定位 |
| `retrieve_visual` | visual assertions | 渲染实体候选 | 多模态转代码 |
| `inspect_candidate` | 文件/实体 | support/missing/contradiction | 更新 belief |
| `expand_graph` | seed + edge type | 新候选 | 局部图扩展 |
| `classify_role` | candidate | seed/helper/test/style/config/docs/noise | patch closure |
| `verify_closure` | candidate set | gap report | 判断是否漏文件 |
| `reformulate` | gap report | 新 query/adapter | 修正搜索方向 |
| `final_rerank` | belief state | top-k | 输出三层预测 |

每个动作都必须写入 belief state。这样才可以 debug：模型为什么把某个文件排前面？它解释了哪些证据？它是不是只是同名但不解释症状？

### 12.6 Belief State 是 Agent 的核心，而不是附属日志

每个候选都应该有一条结构化状态：

```json
{
  "candidate": "client/jetpack-connect/authorize.js",
  "level": "file",
  "role": "seed",
  "language": "JavaScript",
  "support": ["jetpack-connect", "authorization flow", "route-level behavior"],
  "missing": ["helper function for URL/state mapping"],
  "contradiction": [],
  "next_edges": ["same-folder-helper", "imports", "caller-callee"],
  "score": 0.86
}
```

对比一个容易误伤的候选：

```json
{
  "candidate": "client/jetpack-connect/plans.jsx",
  "role": "related-ui",
  "support": ["jetpack-connect", "plans appears in issue context"],
  "missing": ["does not explain authorization callback"],
  "contradiction": ["issue is authorize/utils rather than plan selection"],
  "next_edges": [],
  "score": 0.31
}
```

这就是 Agent 能从“相关区域”走向“真实修改点”的关键。没有 belief state，LocAgent 容易停在 `plans`、`signup`、`state` 这类高频相关文件。

### 12.7 多模态证据的正确使用方式

多模态不是“把图片喂给 VLM，然后让 VLM 猜文件名”。图片通常只告诉我们症状，不直接告诉我们文件。

建议处理成三步：

```text
Image / Screenshot
  -> Visual Assertion
  -> Domain Concept
  -> Code Search Terms + Graph Edges
```

例子：

| 图片现象 | Visual Assertion | Domain Concept | 代码搜索/图边 |
|---|---|---|---|
| bar 圆角裁剪错误 | bar rect radius/clipping | Chart.js bar element drawing | `element.bar`, `parseEdge`, `addNormalRectPath` |
| tooltip hover 区域异常 | hit test mismatch | interaction controller | `core.interaction`, `helpers.canvas`, element point |
| layout 溢出 | legend/box overflow | layout engine | `core.layouts`, `fit`, `padding` |
| UI 页面按钮状态错 | route/state mismatch | React route + state selector | route-to-component、selector-to-component |
| 文档页面示例不一致 | URL doc mismatch | MD/MDX/API docs | url-to-doc、doc-to-symbol |

这样做有两个好处：

1. 图片请求失败或图片太多时，系统仍然可以用已抽取的 visual assertions 继续搜索。
2. 视觉证据可以和语言 adapter 对齐，而不是成为孤立的 VLM 输出。

SWE 全量中 GALA file-level 最强，说明多模态线索确实有用；但 GALA 在 Omni60 上 Empty 很高，也说明不能让多模态通道成为唯一中心。我们的框架应该把视觉作为 evidence channel，而不是唯一定位器。

### 12.8 多语言适配的关键是“关系选择”，不是“语言翻译”

跨语言不是把 Python 问题翻译成英文或把 Java 类名抽出来就结束。真正要适配的是每种语言的高价值关系。

| 语言/生态 | 主要实体 | 高价值关系 | 低价值/易误伤 |
|---|---|---|---|
| Python | module、function、class、decorator | import、test-to-source、decorator、error-code-to-checker | docs、typing stubs、examples |
| Java | package、class、method、interface | test-to-class、method-call、inheritance、exception-flow | integration examples、generated |
| JS/TS UI | component、route、hook、selector、style | route-to-component、state-selector、style-import、snapshot-to-component | generic state/utils |
| JS Build Tool | option、plugin、loader、parser、fixture | option-to-runtime、fixture-to-source、package dependency | examples config、external node_modules |
| Markdown/MDX | page、frontmatter、embedded component | url-to-doc、mdx-import、doc-to-symbol | plain text high-frequency words |
| CSS/SCSS | selector、token、theme variable | style-to-component、theme-token、visual assertion | unrelated class names |

这解释了为什么单一 call graph 不够。很多 benchmark 样本根本不是“函数调用错了”，而是配置、文档、样式、测试 fixture、渲染路径、包边界的问题。

### 12.9 Patch Closure：面向 strict 指标的核心机制

我们的评估是 strict full-coverage。也就是说，找到一个 seed 文件还不够，需要覆盖所有 gold 文件、module、function。SWE 失败样本尤其体现这一点：成功样本往往文件数少，失败样本的 gold file 和 hunk 明显更多。

因此 Agent 必须显式做 patch closure：

```text
seed implementation
  + helper/utils
  + test/fixture/snapshot
  + config/schema
  + style/component
  + docs if issue is docs/API
```

Patch Closure Verifier 应该问：

| 问题 | 目的 |
|---|---|
| 这个 issue 是单文件修复还是多文件修复？ | 决定是否扩展 |
| 当前候选是否只有 seed，没有 helper？ | 补 utils/helper |
| 是否有 option/config 证据？ | 补 schema/runtime |
| 是否有 visual/style 证据？ | 补 CSS/component/render helper |
| 是否有测试或 fixture 暗示？ | 补 test/source 对 |
| 是否出现 docs/examples 污染？ | 降权非实现文件 |

这一步正好针对当前 baseline 的共同问题：它们经常能找到相关区域，但不一定能补齐多文件闭包。

### 12.10 对应具体失败案例的范式推演

#### Jetpack authorize：从业务域相关到 patch closure

`Automattic__wp-calypso-21492` 的真实文件是 `authorize.js` 和 `utils.js`。现有 baseline 经常找到 `plans.jsx`、`signup.js`、`state/jetpack` 等相关但不精确的文件。

PolyGraph-Agent 应该这样做：

```text
Evidence IR:
  surface = Jetpack connect authorization flow
  path_terms = jetpack-connect, authorize
  expected_roles = route/page + helper

Router:
  JS/React app adapter

Retrieval:
  path search jetpack-connect/authorize
  symbol search authorize/connect/url/state

Belief:
  authorize.js = seed, explains route/auth flow
  utils.js = helper, same-folder/import closure
  plans.jsx = related UI but contradicts authorize intent

Output:
  authorize.js, utils.js 前排
```

这里不是需要更大的模型，而是需要 Agent 明确区分 seed/helper/related-ui。

#### Chart.js bar radius：从图片到渲染实体

`chartjs__Chart.js-9399` 的 gold 在 `element.bar.js`，函数包括 `parseEdge`、`addNormalRectPath`、`hasRadius` 等。

PolyGraph-Agent 应该这样做：

```text
Image:
  bar drawing visual diff

Visual Assertion:
  rounded rectangle / border radius / clipping

Router:
  Chart/canvas adapter

Search:
  bar radius rect path borderSkipped

Graph:
  element.bar -> drawing helper -> visual test

Verify:
  candidate functions explain visual assertion
```

这说明多模态证据最终必须落到图形库语义上，而不是只做图片 embedding。

#### Babel TypeScript scope：从同名 TypeScript 漂移到包级路由

`babel__babel-16377` 的真实文件在 `packages/babel-traverse/src/scope/index.ts`，但 baseline 容易跑到 `babel-types` 或 `transform-typescript`。

PolyGraph-Agent 应该这样做：

```text
Evidence:
  TypeScript + scope behavior

Router:
  Babel monorepo adapter

Package routing:
  scope/traverse evidence > type definition evidence

Candidate contrast:
  babel-traverse/scope/index.ts explains scope behavior
  babel-types/definitions/typescript.ts only explains TypeScript vocabulary
  transform-typescript plugin explains transform pipeline, not scope ownership

Decision:
  elevate traverse/scope, downrank types/plugin
```

这就是跨语言/跨包场景中反证的重要性。

#### Webpack asset filename：从配置项到运行时实现

Webpack 样本里 `assetModuleFilename`、`css-loader`、`.svg`、`node_modules/next` 等词会混在一起。普通搜索容易被 examples 或外部路径吸走。

PolyGraph-Agent 应该这样做：

```text
Evidence:
  asset filename generation issue
  external context = Next.js/css-loader/node_modules
  negative = node_modules, codesandbox, stackoverflow

Router:
  JS build tool adapter

Search:
  option symbol assetModuleFilename
  test fixture inline svg
  runtime filename generator

Graph:
  option -> schema -> runtime
  fixture -> source
  loader pipeline

Verify:
  examples/config are reproduction, not main patch
```

这可以直接解决 URL/外部路径污染问题。

### 12.11 框架实现可以分三阶段推进

不需要一开始做一个巨大的系统。建议按阶段落地。

#### Stage 1：Evidence Router + Hybrid Recall

目标：先解决 query 污染和语言搜索计划问题。

实现：

- Evidence IR parser；
- negative term filter；
- JS/Python/Java/Docs-CSS 四个 adapter；
- BM25 + symbol + path 多路召回；
- 输出 file-level top-k。

验证：

- Omni60、SWE60；
- 和 BM25/MM-IR、LocAgent 对比；
- 看 URL 污染、examples 污染是否减少。

#### Stage 2：Belief State + Patch Closure

目标：解决“找到相关 seed 但漏 helper/test/config”的问题。

实现：

- candidate role classifier；
- support/missing/contradiction 结构化记录；
- closure expansion；
- final rerank；
- 输出 file/module/function top-k。

验证：

- SWE full 多文件样本；
- Jetpack、WooCommerce、Chart.js、p5.js 样本；
- 重点看 File REC/F1 和 strict File@8/15 是否提升。

#### Stage 3：PolyGraph 深化 + 多模态症状抽取

目标：解决跨包、跨语言、视觉症状到代码实体的深层问题。

实现：

- Tree-sitter 跨语言实体图；
- optional LSP/SCIP xref；
- visual assertion extractor；
- adapter-specific graph edges；
- graph trap detector。

验证：

- Omni full-candidates；
- SWE full；
- 对比 GraphLocator 构图成本和 GALA 多模态优势。

### 12.12 最终论文/项目故事

这个故事可以这样讲：

> 现有仓库级 Issue 定位方法在多模态和跨语言场景下出现三类系统性失败：LLM Agent 容易被 URL、外部路径和高频词污染；图方法构建成本高且容易陷入局部解释链；多模态方法在前端截图样本上有效，但对纯文本和跨语言样本不稳定。我们提出 Evidence-Compiled PolyGraph Agent，将 Issue 定位建模为一个从多模态证据到语言相关搜索计划的编译过程。该框架先抽取 Evidence IR，再由 Language/Ecosystem Router 选择 adapter，把证据编译成 BM25、symbol、path、visual 和 graph 多路检索动作。Agent 在执行过程中维护 belief state，显式记录支持、缺口和反证，并通过 Patch Closure Verifier 面向 strict full-coverage 指标补齐 seed/helper/test/config/style 等多文件闭包。实验上可在 SWE-bench Multimodal、OmniGIRL 以及清洗后的 Three-level-clean@15 集合上验证该框架对多语言、多模态、多文件定位的提升。

一句话总结：

> **我们的创新不是“更大模型 + 更多搜索”，而是把多语言、多模态 issue localization 变成一个有中间表示、有语言 adapter、有证据状态、有图约束、有 closure verifier 的受控 Agentic Retrieval 框架。**

## 13. 参考资料

- Tree-sitter: https://tree-sitter.github.io/
- LSP: https://microsoft.github.io/language-server-protocol/
- SCIP: https://github.com/scip-code/scip
- Sourcegraph SCIP: https://sourcegraph.com/blog/announcing-scip
- LSIF: https://lsif.dev/
- CodeQL data flow: https://codeql.github.com/docs/writing-codeql-queries/about-data-flow-analysis/
- Joern Code Property Graph: https://docs.joern.io/code-property-graph/
- Kythe overview: https://kythe.io/docs/kythe-overview.html
- SWE-bench Multimodal: https://www.swebench.com/multimodal.html
- OmniGIRL: https://arxiv.org/abs/2505.04606
- LocAgent: https://aclanthology.org/2025.acl-long.426.pdf
- CoSIL: https://arxiv.org/abs/2503.22424
- RepoGraph: https://arxiv.org/abs/2410.14684
- KGCompass: https://arxiv.org/html/2503.21710v1
