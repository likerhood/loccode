# 结合 Benchmark 特点的 Code Property Graph 与语义仓库图定位方案

本文解释 Code Property Graph、Semantic Code Graph、CodeQL data-flow、SCIP/LSP 这类思想如何和我们的 SWE-bench Multimodal、OmniGIRL benchmark 结合。重点不是泛泛介绍图，而是回答一个工程问题：

```text
我们的定位任务为什么不能只靠文本检索、函数调用图或 parser？
如果要把多模态证据、URL、跨语言代码结构、CSS/JSON/Markdown 这类非函数文件纳入 Agent 定位，图应该怎么建、怎么用、怎么评估？
```

## 1. 外部框架能提供什么

### 1.1 Code Property Graph：把 AST、控制流、数据依赖放到一个图里

Code Property Graph（CPG）的核心思想是：不要只看语法树，也不要单独看调用图，而是把 AST、CFG、PDG 等程序分析视图合并到一个带标签、带属性的图中。Yamaguchi 等人在经典 CPG 论文中明确提出，CPG 将抽象语法树、控制流图和程序依赖图合并到一个联合数据结构中，用图遍历来发现漏洞模式。

这对我们有两个直接启发：

1. 定位不能只做 “issue 文本 -> 文件名 BM25”。
2. 真实修复位置往往由多种关系共同决定：语法结构、函数调用、参数传递、状态更新、配置引用、测试覆盖、UI 路由。

但 CPG 不是直接拿来就够用。传统 CPG 主要面向代码内部结构，对我们的 benchmark 中的图片、网页 URL、GitHub issue、playground、CSS、JSON、Markdown、截图 OCR 文本等外部证据覆盖不足。

### 1.2 CodeQL data-flow：局部流和全局流的区别

CodeQL 文档把 data-flow graph 和 AST 明确区分开：AST 反映语法结构，而 data-flow graph 反映运行时值如何在程序中传播。它还区分 local data-flow 和 global data-flow：local 只看同一函数内部，global 会跨函数、对象属性继续传播。

这个区分对我们的失败样本非常关键。

例如 `pyca__cryptography-7520` 不是一个单文件问题。Issue 要求新增 `kdf_rounds` 参数，真实修复链是：

```text
public encryption builder
  -> internal encryption object
  -> backend._private_key_bytes
  -> OpenSSH serializer
  -> kdf options writer
```

如果只做 local search，可能命中 `ssh.py`；但要完整定位 4 个 gold 文件，就必须做跨函数、跨对象、跨模块的参数传播闭包。这正是 global data-flow 思想在定位任务里的对应物。

### 1.3 SCIP / LSP：提供跨语言代码导航基础能力

SCIP 是 language-agnostic code intelligence protocol，目标是用统一索引格式支持 go-to-definition、find references 等代码导航能力。LSP 也提供 go-to-definition、go-to-implementation、find-references、call hierarchy、type hierarchy 等标准接口。

这些能力适合做我们仓库图的底座：

```text
symbol mention
  -> definition
  -> references
  -> implementations / overrides
  -> incoming / outgoing calls
```

但 SCIP/LSP 也不是完整答案。它们解决的是“代码符号在哪里定义、哪里被引用”，而不是：

- Issue 里的 URL 是 patch target 还是 evidence seed？
- 图片里的按钮、错误样式、表格错位应该映射到哪个 route/component/style pipeline？
- CSS selector、JSON key、Markdown docs section 如何和代码文件关联？
- Python type checker 的 binder frame、Java resource ownership、JS/TS route-state-component 关系如何成为可搜索边？

因此，SCIP/LSP 更适合作为结构索引组件，而不是完整的定位方法。

### 1.4 Tree-sitter：适合抽结构，不等于理解语义

Tree-sitter 可以用 query/tag 提取定义、引用等语法节点，也适合多语言快速解析。我们已有 `repo_structures` 的很多信息，本质上也属于这类结构抽取。

但 parser 的边界也很明确：

```text
parser 能告诉我们“这里有一个函数/类/导入/调用表达式”，
但不能天然告诉我们“这个 URL 是复现入口还是真实修复点”，
也不能天然知道“这个 CSS selector 被哪个 React component 视觉使用”。
```

所以多语言适配不是“多装几个 parser”，而是“针对不同语言和生态补齐不同的语义边”。

## 2. 我们 benchmark 的真实特点

结合已有 `006/010/014/018/020/022/027` 文档，当前 benchmark 有几个稳定事实。

### 2.1 SWE-bench Multimodal 更偏图片、URL、多文件、多 hunk

SWE-bench Multimodal dev 全量 102 个样本中，平均每个样本约 2.95 张图片、2.02 个网页 URL。Clean15 后仍然存在大量 UI 截图、图表截图、PDF/排版截图、Markdown 渲染截图等视觉证据。

它的定位难点通常是：

```text
图片/URL 给出用户可见症状
  -> 需要转换成 route / component / state / renderer / stylesheet / parser
  -> 真实 patch 常在底层实现或跨文件闭包中
```

典型例子：

- `Automattic__wp-calypso-21409`：图片是 WooCommerce signup/store location flow，URL 指向 email verification selector，但真实修改在 dashboard/address/location flow。
- `diegomura__react-pdf-1178`：URL 指向 example，图片展示 PDF layout diff，但真实修复在 stylesheet expand/resolve。
- `Automattic__wp-calypso-23915`：运行 URL 是 Reader post 页面，真实修复在 post edit URL builder。

这些都不是普通 call graph 能稳定解决的问题。

### 2.2 OmniGIRL 更偏 URL、多语言、少文件，但 function/entity 映射有噪声

OmniGIRL full-candidates 的主要证据不是图片，而是 URL。很多样本有文档/API URL、GitHub issue/PR、代码 blob 链接、StackOverflow、playground、repro URL。

从语言上看，它覆盖 Python、Java、JavaScript、TypeScript、C 等。不同语言里的“正确搜索边”完全不同：

| 语言/生态 | 常见证据 | 真实定位需要的边 |
|---|---|---|
| Python / mypy | playground、错误信息、类型行为 | symbol table、binder frame、type narrowing、state update |
| Python / cryptography | GitHub issue、public API 参数 | public API -> internal object -> backend dispatch -> serializer |
| Java / AssertJ | StackOverflow、代码 URL、断言输出 | public assertion API -> internal delegate -> error factory |
| Java / Netty | class name、resource ownership 描述 | mentioned class -> field/helper type -> superclass/override -> retain/copy/release |
| JS/TS / Babel/Prettier | playground、配置、formatter output | parser/plugin/config -> transform/print pipeline -> snapshot/test |

所以 OmniGIRL 的关键不是“每个语言都能 parse”，而是“每种语言/生态都能展开正确的结构边”。

### 2.3 Clean15 说明：file-level 很重要，entity-level 需要可评估性约束

Clean15 清洗显示：

- SWE dev 全量 102 个样本中，Three-level-clean@15 保留 92 个。
- OmniGIRL full-candidates 631 个样本中，Three-level-clean@15 保留 445 个。
- OmniGIRL unified60 只有 40/60 个样本适合作为三层主评估。

这说明 file-level 是最稳定主指标；module/function 指标要在 entity 可映射样本上报告。否则 CSS/JSON/顶层代码/新增函数等样本会把“定位能力”和“结构抽取覆盖率”混在一起。

这也反过来说明，仓库图不能只建 Function 节点，还要建：

```text
File
Class
Function/Method
Variable/Symbol
Route
Component
Selector
Reducer/Action
ConfigKey
StyleSelector
DocSection
TestCase
Fixture
Snapshot
URL Evidence
Image Evidence
```

## 3. 为什么现有 baseline 会失败

### 3.1 URL 被当成文本，而不是 typed evidence

当前 baseline 常见问题是：把 URL 内容或 URL path 拼进 prompt 或检索 query，但没有判断 URL 的角色。

URL 至少分成这些角色：

| URL 角色 | 应该怎么用 | 常见错误 |
|---|---|---|
| 直接指向 gold 代码 | 强 seed，沿引用/调用/测试扩展 | 只返回该文件，漏 closure |
| 指向相关代码但非 gold | evidence-only，不能直接当 target | 被误导到错误文件 |
| playground/repro | 解析输入、配置、版本、输出差异 | 只搜索 playground 域名或标题 |
| 文档/API | 抽取行为规范、API 名、参数语义 | 当普通网页摘要 |
| issue/PR/commit | 抽取历史补丁、相关文件、设计讨论 | 只拿标题或关键词 |
| 外部网页/弱线索 | 低权重背景证据 | 噪声进入搜索 |

`Automattic__wp-calypso-21409` 就是典型反例：代码 URL 指向 `isCurrentUserEmailVerified` selector，但真实修复不是 selector 文件，而是 WooCommerce dashboard/address/location flow。Agent 应该把 selector 当成 state evidence，再沿 `selector -> flow usage -> blocking behavior` 扩展。

### 3.2 图片被 caption 化，缺少视觉到代码结构的映射

图片 caption 能告诉模型“这里有按钮、表单、错位、图例、PDF layout diff”，但定位需要下一步转换：

```text
visible UI text
  -> route/page
  -> component
  -> state selector / action / reducer
  -> utility / URL builder / stylesheet / renderer pipeline
```

对 Chart.js、p5.js、react-pdf 这类样本，图片通常不是直接指向文件名，而是指出渲染行为。真实 patch 可能在：

- chart interaction / legend / scale；
- canvas drawing primitive；
- PDF stylesheet expansion / layout resolve；
- markdown token parser / renderer。

因此，图片节点应该进入图，而不是只变成 prompt 文本。

### 3.3 多语言结构边缺失

现有 baseline 多数是：

```text
Issue/URL/图片文本
  -> BM25 / LLM search
  -> 局部读文件
  -> 输出 top-k
```

这对关键词和文件名强重合的样本可行，但对以下样本失效：

- `python__mypy-13481`：需要 `del Foo -> TypeInfo -> binder.get_declaration` 的类型状态边。
- `pyca__cryptography-7520`：需要 `kdf_rounds -> encryption builder -> backend -> ssh serializer` 的参数流闭包。
- `assertj__assertj-1332`：需要 `public assertion API -> internal Strings delegate`。
- `netty__netty-14086`：需要 `SslHandler -> helper queue -> superclass override -> ByteBuf ownership operation`。

这些边不是通用 parser 自动给出的，也不是简单调用图一定能得到的。它们需要语言感知的异构图。

## 4. 我们应该建什么图

建议把方法命名为：

```text
Evidence-aware Multilingual Semantic Repository Graph
```

中文可以写作：

```text
证据感知的多语言语义仓库图
```

它不是传统 CPG 的简单复刻，而是在 CPG 的代码结构/控制流/数据流基础上，加上 benchmark 所需的多模态证据、URL 角色、非函数实体和语言特定边。

### 4.1 节点设计

```text
Code Node:
  File
  Module
  Class
  Function
  Method
  Variable
  Symbol
  Import
  Export

Frontend Node:
  Route
  Component
  Hook
  Selector
  Reducer
  Action
  URLBuilder

Non-code Node:
  ConfigKey
  StyleSelector
  MarkdownSection
  Fixture
  Snapshot
  Asset

Evidence Node:
  IssueText
  Image
  ImageRegion
  OCRText
  WebURL
  GitHubCodeURL
  PlaygroundURL
  DocsURL
  IssuePRURL
  CommitURL
```

### 4.2 边设计

基础代码边：

```text
contains
imports
exports
calls
references
defines
inherits
implements
overrides
tests
```

语言/生态边：

```text
parameter_flows_to
delegates_to
state_updates
state_reads
type_narrows
binds_symbol
dispatches_action
selects_state
renders
routes_to
styles
configures
documents
serializes_to
builds_url
owns_resource
releases_resource
```

证据边：

```text
mentions
shows_text
shows_widget
links_to_code
links_to_docs
links_to_repro
is_evidence_for
is_possible_target
contradicts_target
```

核心要求是：每条边必须有 `type`、`source`、`confidence`、`extractor`，不要把所有关系混成一个无类型邻接表。

示例：

```json
{"src":"url:github/blob/client/state/current-user/selectors.js#L157","dst":"file:client/state/current-user/selectors.js","type":"links_to_code","role":"evidence_only","confidence":0.95}
{"src":"function:isCurrentUserEmailVerified","dst":"component:woocommerce/store-location-setup-view","type":"selects_state","confidence":0.62}
{"src":"component:store-location-setup-view","dst":"file:client/extensions/woocommerce/app/dashboard/store-location-setup-view.js","type":"defined_in","confidence":1.0}
```

## 5. 针对 benchmark 的图扩展策略

### 5.1 SWE Multimodal：从视觉/URL 证据到 UI/渲染 pipeline

SWE 的主要策略应该是：

```text
image/url evidence
  -> evidence role classification
  -> route/component/render pipeline seeds
  -> typed graph expansion
  -> patch closure verification
```

针对不同图片类型：

| 图片/URL 类型 | 图中转换 |
|---|---|
| Web UI 截图 | visible text -> route -> component -> state/action/reducer/style |
| Chart/Canvas 截图 | API/options -> chart element/scale/plugin -> render/update pipeline |
| PDF/排版截图 | style token -> stylesheet expand/resolve -> layout engine -> renderer |
| Markdown/text 渲染截图 | syntax/token -> parser -> renderer -> snapshot/test |
| GitHub code URL | code pointer -> role 判断 -> direct target 或 evidence seed |
| Playground/demo URL | decode input/config/version -> pipeline seed |

这能解释为什么当前 baseline 在 Web UI 和 PDF/排版截图上弱：它们缺少从用户可见症状到程序结构层的中间节点。

### 5.2 OmniGIRL：从 URL 角色和语言路由到语义边

Omni 的主要策略应该是：

```text
URL classifier + language router
  -> language-specific graph expansion
  -> candidate closure verifier
```

语言路由示例：

| 语言 | 触发线索 | 扩展边 |
|---|---|---|
| Python / type checker | `mypy-play`, `false positive/negative`, `type`, `del`, `narrowing` | symbol table、binder frame、type flow |
| Python / crypto/API | `parameter`, `serialization`, `backend`, `format` | parameter flow、API-to-backend、serializer sink |
| Java / assertion | `assertThat`, `diff`, `StackOverflow`, `ShouldBeEqual` | public API -> internal delegate -> error factory |
| Java / Netty | `ByteBuf`, `retain`, `release`, `handler` | ownership、override、helper queue |
| JS/TS formatter | `playground`, `parser`, `printWidth`, `babel/prettier` | config -> parser/transform/printer -> snapshot |

这样做的目标不是让 LLM 一次性想出所有路径，而是给 Agent 明确的下一步工具：

```text
expand_by(type="parameter_flows_to")
expand_by(type="delegates_to")
expand_by(type="selects_state")
expand_by(type="routes_to")
expand_by(type="styles")
```

## 6. Agent 搜索范式应该怎么改

### 6.1 先做 evidence typing，不直接搜

当前很多失败来自一开始 query 就偏了。改进后的第一步应该是结构化证据：

```text
Input issue:
  image_urls
  web_urls
  text
  code snippets

Output evidence cards:
  type: screenshot / code-url / docs-url / playground-url / issue-url
  role: direct-target / evidence-only / reproduction / behavior-spec / weak-background
  extracted symbols
  extracted routes
  extracted UI text
  extracted API names
  confidence
```

### 6.2 再按语言和证据类型选择图扩展器

不要所有样本都用同一个搜索策略。

```text
if evidence.role == code-url and direct_target_confidence high:
    start from linked file, then expand references/tests/neighbor closure

if evidence.role == code-url but evidence_only:
    lower direct rank, expand usage graph first

if evidence.type == playground:
    decode config/input/output, then route to parser/formatter/render pipeline

if language == Python and issue mentions type/state:
    expand binder/type-flow edges

if language == Java and issue mentions public API:
    expand delegate/override/implementation edges
```

### 6.3 最后用 closure verifier 检查候选是否解释完整 issue

多文件 patch 不是 top-k 排序问题，而是闭包问题。Verifier 应该问：

```text
这个候选集合是否覆盖：
1. evidence seed？
2. public API / entry point？
3. internal implementation？
4. target behavior sink？
5. test/snapshot/fixture？
```

例如 `pyca__cryptography-7520`，只返回 `ssh.py` 不够，因为新增参数必须从 public API 进入 backend，再到 serializer。Verifier 应该发现 closure 缺口：

```text
ssh.py found
_serialization.py missing
serialization/__init__.py missing
backend.py missing
```

## 7. 可实现路线

### 7.1 第一阶段：不做重型全程序分析，先做轻量异构图

可先实现 JSONL 图：

```text
repo_graph/
  nodes.jsonl
  edges.jsonl
  evidence.jsonl
```

节点记录：

```json
{
  "id": "function:src/cryptography/hazmat/primitives/serialization/ssh.py::_serialize_ssh_private_key",
  "kind": "Function",
  "file": "src/cryptography/hazmat/primitives/serialization/ssh.py",
  "language": "Python",
  "start_line": 638,
  "end_line": 720
}
```

边记录：

```json
{
  "src": "class:BestAvailableEncryption",
  "dst": "class:_KeySerializationEncryption",
  "type": "parameter_flows_to",
  "evidence": "kdf_rounds",
  "extractor": "python_param_flow_heuristic",
  "confidence": 0.73
}
```

### 7.2 第二阶段：结合 SCIP/LSP/Tree-sitter

可按优先级接入：

1. `repo_structures`：已有 file/module/function 范围。
2. Tree-sitter：补充 import/export/call/component/style selector。
3. LSP/SCIP：补充 definition/reference/implementation/override。
4. 语言规则：补充 Python binder、Java delegate/override、JS route/state/style。
5. URL/image resolver：补充 evidence nodes。

### 7.3 第三阶段：让 Agent 使用图工具

新增工具接口可以是：

```text
classify_evidence(issue)
search_graph_nodes(query, kind, language)
expand_graph(node_ids, edge_types, max_hops)
trace_paths(source_nodes, target_kinds)
verify_patch_closure(candidate_files, evidence_cards)
```

Agent 的行为从“直接猜文件”变成：

```text
先把证据结构化
再选择图扩展边
再解释候选路径
最后输出可验证的 patch target
```

这也能产出更好的论文证据，因为每个预测都有路径解释：

```text
playground URL -> parser option -> formatter pipeline -> printer function -> snapshot test
image button -> route -> component -> action -> URL builder
public API -> internal delegate -> serializer sink
```

## 8. 论文故事线建议

可以把贡献讲成三层：

### 8.1 观察：多模态 issue 定位失败不是因为没有看见证据，而是没有理解证据角色

我们的日志显示，baseline 经常能抓到 URL、图片 OCR、API 名、错误消息，但仍然定位错。原因是证据角色没有被区分：

```text
direct target
evidence-only seed
reproduction entry
behavior specification
weak background
```

### 8.2 方法：证据感知的多语言语义仓库图

在 CPG 的结构/控制/数据流思想上，加入多模态和跨语言定位需要的实体与边：

```text
Code structure + semantic flow + repository artifact + multimodal evidence
```

这区别于：

- 只做 BM25/dense retrieval；
- 只做 function call graph；
- 只做 repo structure；
- 只把图片/URL 摘要拼进 prompt。

### 8.3 机制：typed path-guided Agent search

Agent 不再自由漫游，而是受 typed graph 约束：

```text
evidence node
  -> typed edges
  -> candidate nodes
  -> closure verification
```

这样可以解释并修复我们看到的典型失败：

- URL 误导：降低 evidence-only code URL 的 target 权重。
- 图片弱映射：把 visible UI 转成 route/component/state/style。
- Python 失败：补 binder/type-flow/parameter-flow。
- Java 失败：补 delegate/override/resource ownership。
- CSS/JSON/Markdown：补非函数实体和 file-level closure。

## 9. 和现有 baseline 的差异

| 方法 | 主要能力 | 缺口 | 我们的改进点 |
|---|---|---|---|
| LocAgent | LLM 主导搜索和工具调用 | 搜索路径不稳定，容易被 URL/关键词误导 | evidence typing + typed graph expansion |
| CoSIL | 动态/反思式定位 | 容易停在局部相关文件，closure 不完整 | patch closure verifier |
| GraphLocator | 图/因果链定位 | 初始 seed 错时图扩展也错；边类型不足 | evidence-role-aware seed + language-specific edges |
| GALA | 代码图对齐/检索 | 非代码实体、多模态证据和 URL role 弱 | multimodal evidence nodes + non-code nodes |
| BM25-MMIR | lexical retrieval 强 | 能命中词面文件，但不能闭包和语义跳转 | BM25 作为 seed，不作为最终路径 |

## 10. 最终建议

短期实现重点：

1. 为 URL 和图片建立 evidence cards，而不是直接拼 prompt。
2. 为每个 benchmark 样本记录 evidence role、language router、graph expansion path。
3. 先实现轻量 typed edges：`imports/references/tests/routes_to/renders/selects_state/styles/configures/delegates_to/parameter_flows_to`。
4. 用 Clean15 主评估 file-level 和 eligible entity-level，同时报告长尾诊断集。
5. 对每个预测输出 path explanation，便于论文动机和错误分析。

长期研究目标：

```text
Evidence-aware Multilingual Semantic Repository Graph
  = CPG-style code structure
  + CodeQL-style semantic flow
  + SCIP/LSP-style precise symbol navigation
  + multimodal evidence typing
  + repository artifact/entity graph
  + Agent path-guided search and closure verification
```

这就是我们在多模态跨语言 issue 定位上的核心创新点：不是“又一个检索器”，而是把 issue 中异构证据转换成可搜索、可扩展、可验证的仓库语义路径。

## 参考资料

- [Modeling and Discovering Vulnerabilities with Code Property Graphs](https://www.ieee-security.org/TC/SP2014/papers/ModelingandDiscoveringVulnerabilitieswithCodePropertyGraphs.pdf)
- [CodeQL: About data flow analysis](https://codeql.github.com/docs/writing-codeql-queries/about-data-flow-analysis/)
- [CodeQL: Analyzing data flow in Java and Kotlin](https://codeql.github.com/docs/codeql-language-guides/analyzing-data-flow-in-java/)
- [SCIP Code Intelligence Protocol](https://scip-code.org/)
- [scip-java](https://sourcegraph.github.io/scip-java/)
- [Language Server Protocol 3.17 specification](https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/)
- [Tree-sitter code navigation systems](https://tree-sitter.github.io/tree-sitter/4-code-navigation.html)

