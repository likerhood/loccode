# 多语言语义仓库图资料调研与 Benchmark 适配规划

本文回答一个具体问题：**多语言仓库图到底应该怎么建？是不是可以用统一的 AST/数据流/语义图模板覆盖 JavaScript、Python、Java、CSS、JSON 等不同语言？**

结论先写在前面：

> 可以有统一 schema，但不能有单一语义边。多语言仓库图应该采用“统一节点/边接口 + 语言特定 edge extractor + benchmark 任务特定机制边”的设计。也就是说，顶层图格式统一，但 Python、Java、JavaScript/TypeScript、CSS/JSON/Markdown 需要抽取不同的关键关系。

## 1. 联网调研结论

### 1.1 Code Property Graph：统一图思想成立，但原始目标不是 issue localization

Code Property Graph（CPG）最经典的思想是把多种程序表示合并为一张 property graph。原始论文将 AST、CFG、PDG 合并，CPG 规范和 Joern 文档也强调它是面向代码查询的语言无关中间表示。

可参考资料：

- CPG 经典论文：<https://www.ieee-security.org/TC/SP2014/papers/ModelingandDiscoveringVulnerabilitieswithCodePropertyGraphs.pdf>
- Joern CPG 文档：<https://docs.joern.io/code-property-graph/>
- CPG 规范：<https://cpg.joern.io/>
- Fraunhofer CPG 项目：<https://fraunhofer-aisec.github.io/cpg/>

CPG 的核心是：

```text
AST 语法结构
CFG 控制流
PDG / DFG 数据依赖
Call graph 调用关系
Type / symbol 信息
统一进一张可查询图
```

这个方向对我们有价值，因为它说明：**统一图不是只放调用关系，而是允许多个 representation 共存。**

但是 CPG 的原始目标偏漏洞发现、静态分析和程序查询；我们的任务是多模态 issue localization，有几个额外需求：

1. issue 里有图片、URL、复现页面、文档链接；
2. gold patch 可能落在 CSS、JSON、Markdown、配置、测试 fixture，而不是函数；
3. 很多修复是业务流程、UI 状态、formatter pipeline、dependency migration，不是传统 source-to-sink taint flow；
4. benchmark 需要 top-k localization 和三层评估，而不是回答固定安全查询。

所以我们不能直接说“用 CPG 就解决了”。更准确的说法是：

> 我们借鉴 CPG 的统一 property graph 思想，但要扩展为 issue-localization-oriented semantic repository graph。

### 1.2 CodeQL：数据流有 local/global 区分，适合做精确边，但成本较高

CodeQL 官方文档把数据流分为 local data flow 和 global data flow。local flow 通常在单个函数/方法内，更便宜；global flow 跨函数、属性和调用，更强但成本更高。CodeQL 还为 Java/Kotlin、JavaScript/TypeScript、C/C++ 等语言提供数据流库。

可参考资料：

- CodeQL data flow 总览：<https://codeql.github.com/docs/writing-codeql-queries/about-data-flow-analysis/>
- CodeQL Java/Kotlin data flow：<https://codeql.github.com/docs/codeql-language-guides/analyzing-data-flow-in-java/>
- CodeQL JavaScript/TypeScript data flow：<https://codeql.github.com/docs/codeql-language-guides/analyzing-data-flow-in-javascript-and-typescript/>
- CodeQL C/C++ data flow：<https://codeql.github.com/docs/codeql-language-guides/analyzing-data-flow-in-cpp/>

对我们有用的点：

1. **local/global 分层非常适合 Agent。**  
   Agent 不应该一开始就跑全局数据流。应该先围绕候选 seed 做 local graph，再按需要扩展 global edges。

2. **source/sink 思想可以改造成 evidence/target。**  
   安全分析中 source 是污点来源，sink 是危险使用点；issue localization 中 source 可以是 issue evidence seed，target 是 patch target 候选。

3. **不同语言的数据流 API 不完全一样。**  
   CodeQL 虽然提供统一理念，但实际每个语言都有专门文档和库。这说明多语言统一不是“所有语言一套 extractor”，而是“统一接口 + 语言专门实现”。

我们的取舍：

```text
不用一开始做完整 CodeQL 级全局数据流。
先做轻量 typed edges：
  local_def_use
  parameter_pass
  return_flow
  field_access
  import_reference
  call
  test_target
再对少数高价值案例接入 CodeQL/Joern/SCIP。
```

### 1.3 SCIP / LSIF：适合做跨语言 symbol navigation，不等于数据流

SCIP 是语言无关的代码索引协议，用于 go-to-definition、find references、find implementations 等代码导航。LSIF 是类似方向的较早格式，LSIF.dev 已注明 LSIF 已被 SCIP 取代。

可参考资料：

- SCIP 官方站点：<https://scip-code.org/>
- SCIP GitHub：<https://github.com/scip-code/scip>
- Sourcegraph SCIP 介绍：<https://sourcegraph.com/blog/announcing-scip>
- LSIF 规范：<https://microsoft.github.io/language-server-protocol/specifications/lsif/0.4.0/specification/>
- LSIF.dev：<https://lsif.dev/>
- scip-java：<https://sourcegraph.github.io/scip-java/>

SCIP/LSIF 能解决的问题：

```text
symbol -> definition
symbol -> references
interface/class -> implementations
method -> overrides
跨文件精确导航
```

这对我们的多语言图很关键。因为 LocAgent/CoSIL/GraphLocator 的很多失败不是“完全不知道关键词”，而是：

- 找到 symbol 后不知道它在哪些文件引用；
- 找到 interface 后不知道 internal implementation；
- 找到 URL 指向的代码后不知道这是 target 还是 evidence-only；
- 找到一个组件后不知道哪些 route/render/state 关系与它有关。

SCIP/LSIF 的局限：

- 它主要提供 code intelligence，不直接提供完整数据流、配置流、样式流；
- 对 CSS/JSON/Markdown/资源文件帮助有限；
- 对 benchmark 里的 “visual symptom -> mechanism -> patch closure” 没有直接建模。

因此适合放在我们的图中作为一类边：

```text
defines
references
implements
overrides
go_to_definition
find_references
```

而不是替代整个仓库图。

### 1.4 tree-sitter：适合多语言结构抽取，但不是语义分析

tree-sitter 是 parser generator 和增量解析库，可以为源文件构建 concrete syntax tree。它支持很多语言，适合做多语言结构抽取。

可参考资料：

- tree-sitter 官方：<https://tree-sitter.github.io/>
- tree-sitter GitHub：<https://github.com/tree-sitter/tree-sitter>

它适合做：

```text
文件 -> 类/函数/方法/变量/导入语句
JSX/TSX -> component/function/hook
Python -> class/function/import
Java -> class/method/interface
CSS -> selector/rule/property
Markdown/MDX -> section/code block/import-like syntax
JSON/YAML -> config key path
```

但它不直接解决：

- 变量指向哪个定义；
- 函数调用是否动态分派到某个实现；
- 参数值跨函数怎么传；
- Python 动态属性、JS dynamic import、React state flow；
- CSS selector 到 React component 的真实绑定。

因此 tree-sitter 是多语言图的**结构底座**，不是完整语义图。

### 1.5 WALA 等程序分析框架：强语义分析有价值，但落地成本高

WALA 支持 Java type system、class hierarchy analysis、Java/JavaScript 前端、interprocedural dataflow、call graph、pointer analysis、slicing 等。

可参考资料：

- WALA GitHub：<https://github.com/wala/wala>

这说明成熟程序分析框架可以提供更强的边：

```text
call graph
pointer analysis
class hierarchy
interprocedural dataflow
program slicing
```

但对我们的项目，直接大规模接入 WALA/CodeQL/Joern 有成本：

- 每个 benchmark 样本要 checkout 特定 commit；
- 前端仓库依赖复杂，构建成本高；
- Python/JS 动态特性和配置文件很多；
- 评估主要是 localization，不一定需要完整 sound analysis；
- 服务器运行 baseline 已经较重，不能再引入非常慢的全仓库分析作为默认路径。

所以更实际的策略是：

> P0/P1 阶段做轻量多语言 semantic repository graph；P2 阶段对少数语言和高价值边接入成熟分析器。

## 2. 对我们的 benchmark 来说，为什么“统一模板”不够

### 2.1 SWE-bench Multimodal 的真实问题不是传统数据流占主导

SWE-bench Multimodal Clean15 里，图片和 URL 经常给的是视觉症状、页面入口、示例链接或相关代码。典型样本包括：

| 样本 | 证据类型 | 真实需要的图关系 |
|---|---|---|
| `Automattic__wp-calypso-21409` | UI 截图 + current-user selector URL | selector -> signup/dashboard flow -> address/country/settings |
| `diegomura__react-pdf-1178` | example URL + layout diff 图片 | example -> style property -> expand -> resolve -> layout |
| `chartjs__Chart.js-8162` | 图表截图 | legend/title affected component -> plugin lifecycle invalidation |
| `processing__p5.js-5917` | WebGL 图形症状 | renderer state -> texture upload -> blend/shader/resource closure |

这些关系不完全是传统 AST/CFG/DFG：

- `selector -> component` 是前端状态使用关系；
- `route -> page component` 是框架路由关系；
- `style property -> stylesheet expansion` 是 domain-specific pipeline；
- `legend/title -> plugin lifecycle` 是 framework mechanism；
- `package -> replacement abstraction -> lockfile/docs` 是 dependency migration closure。

因此，如果只建统一 `AST + call + dataflow`，会漏掉 benchmark 的核心定位关系。

### 2.2 OmniGIRL 的多语言问题更明显

OmniGIRL full-candidates Clean15 中语言分布包括 JavaScript、Python、TypeScript、Java、少量 C。URL 又高度多样：GitHub issue/PR、GitHub blob、mypy docs、Prettier playground、Tailwind playground、StackOverflow、Gist 等。

不同语言里的关键边不同：

| 语言/生态 | 典型失败 | 必要语义边 |
|---|---|---|
| Python / mypy | `del Foo` 后读取类名未报错 | name binding、symbol table、binder frame、type state |
| Python / cryptography | `kdf_rounds` 参数未传到 OpenSSH serializer | public API -> encryption object -> backend dispatch -> serializer |
| Java / AssertJ/Gson/Netty | public API 与 internal delegate/override/helper 脱节 | class hierarchy、implements、overrides、delegate call、test target |
| JS/TS / Prettier/Babel/Tailwind | playground 复现未映射到 parser/plugin/printer | parser option、AST node kind、printer pipeline、plugin config |
| Web frontend | URL route 或 UI screenshot 未映射到 component/state | route、component render、selector、reducer/action、style |

这说明：

> 多语言不是“换 parser”，而是“换关键语义边”。

## 3. 统一 schema 应该长什么样

### 3.1 统一节点类型

建议采用分层节点，不要求每种语言都有全部节点。

```text
Repository
Package
Directory
File

Symbol
  Module
  Class
  Interface
  Function
  Method
  Variable
  Field
  TypeAlias

FrontendEntity
  Route
  Component
  Hook
  Selector
  Reducer
  Action
  StoreSlice

ResourceEntity
  ConfigKey
  StyleSelector
  StyleProperty
  MarkdownSection
  JSONPath
  YAMLPath
  Asset
  Shader
  Fixture
  Snapshot

TestEntity
  TestFile
  TestCase
  Assertion
```

这样设计的原因：

1. `File/Class/Function` 适合传统代码；
2. `Route/Component/Selector/Reducer` 适合 wp-calypso、React、前端 UI；
3. `StyleSelector/ConfigKey/MarkdownSection/JSONPath` 适合非函数 gold；
4. `Shader/Asset/Fixture/Snapshot` 适合 p5.js、图形、测试、渲染 benchmark。

### 3.2 统一边类型

建议把边分成 8 类。

#### A. 文件和结构边

```text
contains
declares
belongs_to
```

来源：

- repo_structures
- tree-sitter
- ctags
- 简单文件系统扫描

#### B. 语言符号边

```text
imports
exports
defines
references
calls
returns_to
passes_argument_to
reads_field
writes_field
inherits
implements
overrides
```

来源：

- SCIP/LSP/LSIF
- CodeQL/Joern/WALA
- tree-sitter + 轻量 symbol resolver

#### C. 前端框架边

```text
routes_to
renders
uses_hook
selects_state
dispatches_action
reduces_action
connects_to_store
uses_component
```

来源：

- JS/TS AST
- JSX/TSX AST
- React/Redux pattern extractor
- route config parser
- import/reference edges

#### D. 配置和构建边

```text
configures
enables_plugin
declares_dependency
locks_dependency
aliases_module
builds_entry
```

来源：

- package.json
- npm-shrinkwrap/package-lock/yarn.lock
- webpack/babel/tsconfig/jest config
- pyproject/setup.cfg/tox.ini
- Maven/Gradle

#### E. 样式和渲染边

```text
styles
uses_style_property
expands_style_property
resolves_style_value
draws
measures
clips
fills
```

来源：

- CSS/SCSS parser
- stylesheet pipeline code pattern
- component import of style files
- domain-specific extractor for react-pdf/chart/p5

#### F. 测试和 fixture 边

```text
tests
asserts_behavior
uses_fixture
matches_snapshot
regresses_from
```

来源：

- test naming convention
- import/reference
- snapshot paths
- fixture JSON paths
- pytest/jest/mocha/junit patterns

#### G. 文档和 API 边

```text
documents
mentions_symbol
describes_option
describes_behavior
links_to_external_api
```

来源：

- Markdown/MDX docs
- README
- docstrings
- URL evidence resolver 输出后映射到 repo docs

#### H. 机制边

这是我们自己的关键创新，不是传统工具天然提供的。

```text
evidence_maps_to_mechanism
mechanism_suggests_seed
seed_expands_to_closure
candidate_explains_evidence
candidate_requires_neighbor
```

例如：

```text
margin:auto visual diff
  evidence_maps_to_mechanism -> style value expansion
style value expansion
  mechanism_suggests_seed -> packages/stylesheet/src/expand.js
expand.js
  seed_expands_to_closure -> resolve.js
```

## 4. 语言适配策略

### 4.1 JavaScript / TypeScript / 前端仓库

SWE 的 Automattic/wp-calypso、Chart.js、react-pdf、p5.js，以及 Omni 的 Prettier/Babel/Tailwind 都需要 JS/TS 适配。

必要边：

```text
imports / exports
calls
component renders component
route maps to page component
selector reads state
action dispatches reducer
config enables plugin/parser
style file styles component
test imports target
```

关键 extractor：

```text
tree-sitter-js / tree-sitter-ts
tsserver / SCIP TypeScript
React/Redux pattern extractor
route config extractor
package/config parser
```

Benchmark 对应：

- `Automattic__wp-calypso-21409`：selector URL 需要扩展到 WooCommerce dashboard/address flow；
- `Chart.js-8162`：legend/title 组件要跳到 plugin lifecycle；
- `p5.js-5917`：renderer JS 节点要扩展到 shader/resource closure；
- Prettier playground：URL hash 需要解析成 parser/options/input code，再映射到 parser/printer/plugin。

### 4.2 Python

Omni 的 Python 样本集中在 mypy、cryptography、scipy/statsmodels 等。

必要边：

```text
imports
calls
class inherits
decorator applies_to function/class
parameter passes to callee
exception raised/caught
type rule / binder state
public API delegates to backend
test calls API
```

关键 extractor：

```text
tree-sitter-python
pyright/jedi/rope 可选
CodeQL Python 可选
自定义 lightweight def-use
```

Benchmark 对应：

- `python__mypy-13481`：不是普通 call graph，而是 name binding、symbol table、binder frame、deleted variable state；
- `pyca__cryptography-7520`：需要 public API 到 backend serializer 的参数传播闭包；
- statsmodels/scipy 类样本：URL 文档中的 API 参数需要映射到模型类、参数校验、测试。

### 4.3 Java

Omni 中 Java 样本常见 AssertJ、Gson、Netty 等库。

必要边：

```text
package contains class
class implements interface
method overrides method
public API delegates to internal implementation
constructor initializes field
test targets class/method
resource ownership flow
```

关键 extractor：

```text
scip-java
jdtls
tree-sitter-java
CodeQL Java / WALA 可选
```

Benchmark 对应：

- AssertJ：public assertion API 通常 delegate 到 internal comparison/helper；
- Gson：类型 adapter、factory、reflection/exclusion strategy；
- Netty：resource ownership、retain/release、buffer lifecycle、handler pipeline。

### 4.4 CSS / SCSS / JSON / YAML / Markdown / MDX

这些文件没有函数，但在 benchmark 中可能是 gold。不能把它们排除。

必要节点：

```text
StyleSelector
StyleProperty
ConfigKey
JSONPath
YAMLPath
MarkdownSection
MDXComponent
Snapshot
Fixture
```

必要边：

```text
style selector styles component
config key configures plugin/module
markdown section documents API
fixture used by test
snapshot expected_by test
```

Benchmark 对应：

- wp-calypso 样式修复：SCSS 文件和 React component 之间需要 `styles` 边；
- Chart.js fixture：JSON fixture 和测试/渲染行为之间需要 `uses_fixture` 边；
- Markdown/marked：文档、样例和 parser/renderer 之间需要 `documents` / `tests` / `mentions_symbol` 边。

## 5. 为什么不能只做全仓库 CPG

全仓库 CPG 或全局数据流理论上强，但在我们的场景里有三个问题：

1. **成本太高。**  
   每个样本都要 checkout 特定 commit，仓库多、语言多、依赖复杂。如果每个 issue 都跑全局分析，实验成本会非常高。

2. **错 seed 会导致错扩展。**  
   GraphLocator 的失败已经说明：如果初始 seed 被 URL 或图片表象误导，图越大，错路径扩散越严重。

3. **很多关键关系不是传统 CPG 默认边。**  
   route、React component、Redux selector、CSS selector、package lock、playground parser option、视觉症状机制，这些都需要任务特定抽取。

因此推荐：

```text
先轻量索引全仓库；
再围绕 issue evidence seed 局部扩展；
必要时调用重分析工具。
```

## 6. 我们的建模方案

### 6.1 总体原则

```text
统一 schema
语言特定 extractor
任务特定 mechanism edges
局部图扩展
verifier 检查闭包
```

### 6.2 分层图架构

#### Layer 0：文件和文本索引

```text
File
Path
Extension
Language
Repo
Commit
Chunk
```

用途：

- BM25 / embedding 检索；
- 快速候选召回；
- repo 大小和语言分布统计。

#### Layer 1：语法实体图

```text
File -> Class/Function/Method/Variable
File -> StyleSelector/ConfigKey/MarkdownSection
```

来源：

- repo_structures；
- tree-sitter；
- ctags；
- 简单 JSON/YAML/CSS parser。

用途：

- 支撑 file/module/function/generalized entity 评估；
- 给 Agent 提供可定位实体。

#### Layer 2：符号导航图

```text
defines
references
imports
exports
implements
overrides
```

来源：

- SCIP/LSP/LSIF；
- tsserver/jdtls/pyright；
- tree-sitter fallback。

用途：

- 从 URL 指向 symbol 扩展到 references；
- 从 public API 扩展到 internal implementation；
- 从 test 扩展到 target。

#### Layer 3：轻量语义流图

```text
calls
passes_argument_to
returns_to
reads_field
writes_field
dispatches_action
selects_state
configures
styles
tests
```

来源：

- language-specific AST patterns；
- framework-specific patterns；
- config parser；
- optional CodeQL/Joern/WALA。

用途：

- 做 patch closure；
- 做 Agent graph actions；
- 做候选重排。

#### Layer 4：任务机制图

```text
symptom -> mechanism
mechanism -> seed entity
seed -> required closure
candidate -> explains evidence
```

来源：

- issue evidence extractor；
- VLM/image summary；
- URL resolver；
- LLM mechanism classifier；
- benchmark case library。

用途：

- 防止 URL 误导；
- 把图片症状转成代码机制；
- 把 reasoning 转成可验证候选集合。

## 7. 查询动作设计

Agent 不应该直接拿整张图，而应该使用小的查询动作。

### 7.1 符号导航动作

```text
find_definition(symbol)
find_references(symbol)
find_implementations(interface_or_method)
find_overrides(method)
```

用于：

- GitHub code URL；
- Java/Python public API；
- JS/TS exported function。

### 7.2 数据/参数流动作

```text
trace_argument_flow(function, parameter)
trace_return_flow(function)
trace_field_writes(field)
trace_field_reads(field)
```

用于：

- `kdf_rounds` 参数传播；
- `margin:auto` style value 流；
- UI form field default/placeholder 流。

### 7.3 前端状态/组件动作

```text
find_routes(component_or_path)
find_renderers(component)
find_selectors(component)
find_reducers(action_or_state_key)
find_actions(component_or_event)
```

用于：

- wp-calypso dashboard/settings flow；
- React/Redux UI 问题；
- URL path 到 component。

### 7.4 机制闭包动作

```text
expand_patch_closure(seed, mechanism_type)
verify_candidate_closure(candidates, evidence_cards)
```

机制类型：

```text
ui_flow
style_pipeline
chart_plugin_lifecycle
webgl_resource
dependency_migration
public_api_to_backend
parser_printer_pipeline
```

## 8. 泛化性如何保证

### 8.1 不按仓库写死，而按机制写 extractor

不要写：

```text
if repo == wp-calypso: ...
if repo == react-pdf: ...
```

应该写：

```text
if evidence indicates UI route/state issue:
    use frontend graph actions

if evidence indicates layout/style issue:
    use style pipeline actions

if evidence indicates public API parameter:
    use API-to-backend parameter flow actions
```

这样可以从 SWE 迁移到 Omni，也可以从 JavaScript 迁移到 Python/Java。

### 8.2 schema 统一，边抽取可缺省

不是每个语言都有所有边。图节点需要记录 edge confidence 和 extractor provenance：

```json
{
  "edge_type": "passes_argument_to",
  "source": "src/cryptography/.../_serialization.py:BestAvailableEncryption",
  "target": "src/cryptography/.../backend.py:_private_key_bytes",
  "confidence": 0.72,
  "extractor": "python_ast_parameter_flow_v1"
}
```

没有精确工具时，可以先用 lower-confidence heuristic edge；有 SCIP/CodeQL 时再升级为 high-confidence edge。

### 8.3 支持非函数实体，避免评估和方法脱节

函数级指标仍然可以保留，但图应该支持 generalized semantic entity：

```text
Function
Class
Method
StyleSelector
ConfigKey
MarkdownSection
JSONPath
Shader
Fixture
Snapshot
```

这样 CSS/JSON/Markdown 不会被强行塞进 function 评估，也能让定位方法输出更合理的细粒度目标。

## 9. 和现有 baseline 的关系

### 9.1 LocAgent

LocAgent 的优势是 LLM 搜索和 reasoning。我们补的是：

- evidence role classifier；
- graph actions；
- patch closure verifier；
- reasoning-to-candidate 执行化。

### 9.2 CoSIL

CoSIL 有动态调用图思想。我们补的是：

- 多语言边；
- 非调用关系；
- URL/image evidence 到机制 seed；
- 非函数实体。

### 9.3 GraphLocator

GraphLocator 有因果链和图定位思想。我们补的是：

- 局部而非全仓库图；
- evidence seed 验证；
- 错 seed 时的反证和重路由；
- 多语言 typed edges。

### 9.4 GALA

GALA 有图对齐和结构检索。我们补的是：

- 证据角色；
- 机制 router；
- patch closure；
- 多语言非代码资源。

## 10. 实施路线

### P0：先做轻量统一图，不接重型分析器

目标：一周内可验证。

输入：

```text
repo_structures/*.json
samples.jsonl
已有 loc_results / loc_trajs
仓库 checkout
```

输出：

```text
semantic_repo_graphs/<benchmark>/<instance_id>/
  nodes.jsonl
  edges.jsonl
  graph_meta.json
```

实现：

```text
build_file_nodes.py
build_structure_nodes.py
extract_import_edges.py
extract_test_edges.py
extract_config_edges.py
extract_style_edges.py
```

### P1：语言特定边

JS/TS：

```text
extract_react_edges.py
extract_redux_edges.py
extract_route_edges.py
extract_package_edges.py
```

Python：

```text
extract_python_import_edges.py
extract_python_call_edges.py
extract_python_param_flow_edges.py
```

Java：

```text
extract_java_inheritance_edges.py
extract_java_override_edges.py
extract_java_test_edges.py
```

### P2：证据到图的查询动作

```text
query_semantic_repo_graph.py
  --action find_references
  --action trace_argument_flow
  --action expand_patch_closure
  --action find_state_flow
```

### P3：接入 Agent

新增工具：

```text
search_evidence_mapped_seeds
query_repo_graph
expand_patch_closure
verify_localization_closure
```

### P4：评估

新增评估：

```text
file/module/function 原指标
generalized_entity 指标
closure_recall
evidence_target_mismatch rate
```

## 11. 论文叙事建议

可以这样组织故事：

1. 多模态 issue localization 不只是多输入检索；图片和 URL 往往是 evidence，不是 target。
2. 现有方法要么依赖 LLM 自由搜索，要么依赖单一调用图/因果图，难以处理多语言、多资源、多机制 patch。
3. 通过 benchmark 分析发现，失败集中在 URL role mismatch、visual symptom-to-mechanism gap、multilingual semantic edge missing、patch closure missing。
4. 因此提出 evidence-aware multilingual semantic repository graph：
   - evidence 层动态解析 issue；
   - repository graph 层稳定提供 typed navigation；
   - Agent 通过 typed actions 查询局部图；
   - verifier 检查 patch closure。
5. 这比单纯扩大 BM25、换模型、建全仓库 call graph 更适合真实 benchmark。

英文摘要式表述：

```text
We propose an evidence-aware multilingual semantic repository graph for multimodal issue localization.
Unlike conventional call graphs or CPG-only approaches, our graph separates dynamic issue evidence from stable repository semantics.
Issue images, URLs, reproduction pages, documentation links, and code pointers are first converted into typed evidence cards.
The agent then navigates a multilingual repository graph with language-specific semantic edges, including symbol references, data/parameter flow, UI route-state-component relations, configuration dependencies, style/resource links, and test/fixture relations.
This design addresses evidence-target mismatch, visual symptom-to-mechanism gaps, and patch closure failures observed in SWE-bench Multimodal and OmniGIRL.
```

## 12. 参考资料

- Modeling and Discovering Vulnerabilities with Code Property Graphs: <https://www.ieee-security.org/TC/SP2014/papers/ModelingandDiscoveringVulnerabilitieswithCodePropertyGraphs.pdf>
- Joern Code Property Graph documentation: <https://docs.joern.io/code-property-graph/>
- CPG specification: <https://cpg.joern.io/>
- Fraunhofer CPG: <https://fraunhofer-aisec.github.io/cpg/>
- CodeQL data flow overview: <https://codeql.github.com/docs/writing-codeql-queries/about-data-flow-analysis/>
- CodeQL Java/Kotlin data flow: <https://codeql.github.com/docs/codeql-language-guides/analyzing-data-flow-in-java/>
- CodeQL JavaScript/TypeScript data flow: <https://codeql.github.com/docs/codeql-language-guides/analyzing-data-flow-in-javascript-and-typescript/>
- CodeQL C/C++ data flow: <https://codeql.github.com/docs/codeql-language-guides/analyzing-data-flow-in-cpp/>
- SCIP official site: <https://scip-code.org/>
- SCIP GitHub: <https://github.com/scip-code/scip>
- Sourcegraph SCIP intro: <https://sourcegraph.com/blog/announcing-scip>
- LSIF specification: <https://microsoft.github.io/language-server-protocol/specifications/lsif/0.4.0/specification/>
- LSIF.dev: <https://lsif.dev/>
- scip-java: <https://sourcegraph.github.io/scip-java/>
- tree-sitter official: <https://tree-sitter.github.io/>
- tree-sitter GitHub: <https://github.com/tree-sitter/tree-sitter>
- WALA GitHub: <https://github.com/wala/wala>
