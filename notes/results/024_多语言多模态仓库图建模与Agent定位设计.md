# 多语言多模态仓库图建模与 Agent 定位设计

本文回答一个核心问题：在真实仓库中，不同文件之间并不都存在函数调用关系，很多关键修改发生在 CSS、JSON、Markdown、配置、路由、样式、测试 fixture、图片资源、文档或顶层常量中。那么面向多语言、多模态 issue 定位时，应该如何统一建模仓库结构、调用关系、数据流、配置依赖和视觉/URL 证据？

结论先行：

```text
不能只建 call graph。
应该建一个多层异构仓库证据图：

Evidence-aware Multilingual Repository Graph

它同时包含：
1. 代码实体图：file / class / function / method / variable / export / import
2. 非代码实体图：CSS selector / JSON key / route path / config key / markdown section / asset
3. 运行语义图：route / UI component / style / data model / URL builder / renderer pipeline
4. 多模态证据图：image region / visible text / web URL / GitHub URL / repro URL / document URL
5. 评估适配层：哪些节点可做 file-level，哪些节点可做 module/function-level，哪些只能做 evidence-level
```

这样才能处理我们 benchmark 里反复出现的问题：

- Issue URL 指向复现 example，但真实修复在底层语义层。
- 图片指向 UI 按钮，但真实修复在 URL builder 或 state selector。
- CSS/SCSS/JSON 没有函数，但仍然是合法、关键的修复目标。
- Python/Java/JS/TS 的语言结构不同，不能只用一套函数调用图。
- 多文件 patch 常常不是调用链关系，而是配置、样式、测试、路由、组件、数据模型之间的跨层关系。

## 1. 相关工作与可借鉴思想

### 1.1 Code Property Graph：AST、CFG、DFG 的统一图

Code Property Graph（CPG）最早用于漏洞发现，把 AST、控制流图、数据流图等放到一个统一的有向多图中。经典论文强调 CPG 通过图遍历同时检查代码结构、控制流和数据依赖。

参考：

- [Modeling and Discovering Vulnerabilities with Code Property Graphs](https://www.ieee-security.org/TC/SP2014/papers/ModelingandDiscoveringVulnerabilitieswithCodePropertyGraphs.pdf)
- [Fraunhofer CPG 文档](https://fraunhofer-aisec.github.io/cpg/)

对我们的启发：

```text
不要把调用关系、数据流、语法结构分开看。
应该把它们作为不同 edge type 放进同一个异构图。
```

但 CPG 的局限也明显：它更偏程序分析，适合函数、变量、表达式；对 CSS、JSON、Markdown、图片 URL、网页复现链接等多模态证据覆盖不足。

### 1.2 Semantic Code Graph：跨语言稳定实体 ID

Semantic Code Graph 强调为多语言项目生成稳定的代码元素标识，支持 Scala/Java 等混合语言项目分析和可视化。

参考：

- [Semantic Code Graph](https://arxiv.org/html/2310.02128v2)

对我们的启发：

```text
多语言统一建模的核心不是把所有语言强行解析成同一种 AST，
而是为不同语言实体提供统一 entity schema 和 stable id。
```

例如：

```text
python:function:pkg.module.Class.method
java:method:com.foo.Bar#baz(String)
typescript:function:src/components/Foo.tsx::Foo
css:selector:client/foo/style.scss::.button.primary
json:key:package.json::scripts.test
```

### 1.3 LSIF / SCIP：用语言服务器能力做精确跨文件引用

LSIF 和 SCIP 都是持久化代码智能索引格式，目标是让编辑器或代码浏览器在不实时启动语言服务器的情况下支持 go-to-definition、find-references 等能力。

参考：

- [LSIF.dev](https://lsif.dev/)
- [VS Code: Language Server Index Format](https://code.visualstudio.com/blogs/2019/02/19/lsif)
- [Sourcegraph: SCIP](https://sourcegraph.com/blog/announcing-scip)
- [GitLab Code Intelligence](https://docs.gitlab.com/user/project/code_intelligence/)

对我们的启发：

```text
对 Python / Java / TypeScript / Go 这类语言，不应只依赖 tree-sitter。
能用 LSP/LSIF/SCIP 时，应优先获得精确 def-use / reference / symbol relation。
tree-sitter 更适合补充结构和不支持语言的粗粒度解析。
```

### 1.4 RepoGraph：面向 LLM agent 的仓库级代码图

RepoGraph 提出面向 AI software engineering 的 repository-level graph，用图结构作为 LLM agent 的导航模块。论文强调 repo-level 任务不能只看局部文件，需要仓库范围上下文。

参考：

- [RepoGraph: Enhancing AI Software Engineering with Repository-level Code Graph](https://arxiv.org/abs/2410.14684)
- [ICLR 2025 RepoGraph OpenReview](https://openreview.net/forum?id=dw9VUsSHGB)

对我们的启发：

```text
图不是最终答案，而是 agent 的导航地图。
Graph retrieval 应该服务于“下一步搜哪里、扩展哪些邻居、剪掉哪些误导证据”。
```

### 1.5 KGCompass：Repository-aware Knowledge Graph 与路径引导修复

KGCompass 构造 repository-aware knowledge graph，把 issue/PR 等仓库 artifact 与文件、类、函数等代码实体连接起来，并通过 path-guided repair 缩小候选位置。论文摘要中明确提到其知识图是 language-agnostic 且可增量更新。

参考：

- [KGCompass arXiv](https://arxiv.org/abs/2503.21710)
- [KGCompass GitHub](https://github.com/GLEAM-Lab/KGCompass)

对我们的启发：

```text
Issue 到代码不是单跳匹配，而是多跳路径：
issue term -> artifact -> code entity -> neighbor entity -> patch target。
```

但 KGCompass 仍然主要面向 repair context 和 function-level candidate，和我们的多模态 URL/图片证据、CSS/JSON 非函数文件还有差距。

### 1.6 OpenHands-Versa 与多模态 browsing

OpenHands-Versa 强调通用 agent 工具集，包括代码编辑、执行、web search、多模态 web browsing 和文件访问。相关论文也提到 SWE-agent Multimodal 能打开图片、服务本地 HTML、进行视觉验证。

参考：

- [OpenHands-Versa GitHub](https://github.com/adityasoni9998/OpenHands-Versa)
- [OpenHands blog: Building a Provably Versatile Agent](https://www.openhands.dev/blog/building-a-provably-versatile-agent)
- [Coding Agents with Multimodal Browsing are Generalist Problem Solvers](https://arxiv.org/pdf/2506.03011)

对我们的启发：

```text
多模态定位不能只把图片 caption 拼进 prompt。
应该把图片/网页内容转成结构化 evidence node，再连接到仓库图。
```

例如图片中出现 `Edit` 按钮，不应直接搜索 `Edit`，而应生成：

```text
image_region: button[label=Edit]
edge: visual_action -> UI component candidate
edge: action -> route/url builder candidate
```

## 2. 我们当前 benchmark 暴露的建模问题

### 2.1 只用 call graph 不够

真实仓库里很多关系不是函数调用：

| 关系类型 | 例子 | 是否是函数调用 |
|---|---|---|
| CSS selector 被 JSX className 使用 | `.reader-post-actions` -> `className="reader-post-actions"` | 否 |
| JSON 配置控制构建入口 | `package.json::scripts.test` -> test runner | 否 |
| route path 映射到 controller | `/read/feeds/:feed/posts/:post` -> reader controller | 否 |
| URL builder 生成外部路径 | `getEditURL` -> `/post/{site}/{id}` | 不是传统调用关系 |
| Markdown 文档描述 API 行为 | docs -> function behavior | 否 |
| test fixture 对应 parser/renderer | fixture -> parser function | 否 |
| image evidence 指向 UI 元素 | screenshot button -> component/action | 否 |

所以如果只建：

```text
function A calls function B
```

会漏掉大量真实 patch 关系。

### 2.2 CSS/JSON/Markdown 没有 function，但仍然是修复目标

例如：

```text
style.scss
package.json
tsconfig.json
README.md
fixtures/*.json
snapshots/*.snap
```

这些文件可能没有 function-level gold，但它们是合法定位目标。对这类文件，图中应该有对应的非代码实体节点：

```text
css_selector
json_key
markdown_section
snapshot_case
fixture_record
asset_file
config_entry
```

否则 agent 只能把它们当普通文本块，无法知道它们和代码文件之间的关系。

### 2.3 多语言项目中的实体粒度不一致

JavaScript/TypeScript：

```text
function
arrow function
React component
hook
selector
route
Redux action/reducer
CSS module
```

Python：

```text
module
class
function
method
decorator
fixture
test case
```

Java：

```text
package
class
interface
method
annotation
test class
```

C/C++：

```text
translation unit
function
macro
struct
header declaration
```

CSS/SCSS：

```text
selector
class
id
mixin
variable
import
```

JSON/YAML：

```text
key path
schema field
script name
dependency name
config option
```

因此统一图不能只叫 `function`。需要更一般的 schema：

```text
Entity {
  id
  type
  language
  file
  name
  span
  parent
  text
  properties
}
```

其中 `type` 可以是：

```text
file | directory | module | class | function | method | variable |
export | import | route | config_key | css_selector | css_variable |
markdown_section | test_case | fixture | asset | url | image_region
```

## 3. 统一多语言多模态仓库图设计

### 3.1 图的总体结构

建议设计为异构有向多图：

```text
G = (V, E)

V: 节点集合
E: 带类型、权重、置信度、来源的边集合
```

每条边不仅有类型，还要有来源：

```text
edge = {
  src,
  dst,
  type,
  weight,
  confidence,
  source: tree-sitter | lsp | scip | regex | build-parser | llm | vision | url-parser
}
```

这是为了处理现实中的不确定性。例如：

- LSP def-use 边置信度高；
- tree-sitter 结构边中等；
- LLM 推断的 UI action -> URL builder 边置信度低，但有启发价值；
- URL parser 得到的 GitHub blob path 边置信度高；
- screenshot OCR 得到的按钮文本边置信度中等。

### 3.2 节点类型

#### 代码实体节点

```text
File
Directory
Module
Class
Function
Method
Variable
Export
Import
TestCase
```

示例：

```text
file:client/lib/posts/utils.js
function:client/lib/posts/utils.js::getEditURL
method:src/main/java/org/assertj/Assert.java#isEqualTo
function:packages/stylesheet/src/expand.js::processBoxModel
```

#### 非代码实体节点

```text
CSSSelector
CSSVariable
JSONKey
YAMLKey
MarkdownSection
RoutePath
ConfigOption
Asset
Snapshot
FixtureRecord
```

示例：

```text
css_selector:client/foo/style.scss::.reader-post-actions
json_key:package.json::scripts.test
route:/read/feeds/:feedId/posts/:postId
markdown_section:docs/api.md#margin
fixture:packages/stylesheet/tests/fixtures/margin-auto.json
```

#### 多模态证据节点

```text
Issue
Image
ImageRegion
OCRText
URL
WebPage
GitHubBlobURL
GitHubIssueURL
ReproURL
APIDocURL
VideoURL
```

示例：

```text
url:https://wordpress.com/read/feeds/76552105/posts/1804969891
image_region:button[label=Edit]
url:https://github.com/diegomura/react-pdf/blob/master/packages/examples/src/knobs/index.js#L20
```

### 3.3 边类型

#### 结构边

```text
contains: directory -> file, file -> function, class -> method
defines: file -> export/function/class
imports: file -> file/module
exports: symbol -> file/module
```

#### 代码语义边

```text
calls: function -> function
references: function -> variable/function/class
overrides: method -> method
implements: class -> interface
inherits: class -> class
data_reads: function -> variable/config
data_writes: function -> variable/config
returns_url: function -> route/url pattern
```

#### 配置与构建边

```text
configures: json_key -> tool/module
script_runs: package_json_script -> file/test
depends_on: package -> package
loads: config_file -> source_file
```

示例：

```text
package.json::scripts.test -> packages/stylesheet/tests/resolve.test.js
tsconfig.json::compilerOptions.paths -> src/*
webpack.config.js -> client/entrypoints/*
```

#### UI / Route / Style 边

```text
route_to_component: route -> component
component_uses_style: component -> css_selector
component_imports_style: component -> style_file
className_matches_selector: JSX className -> css_selector
action_to_handler: UI action -> function
handler_builds_url: function -> URL builder
```

示例：

```text
image_region:button[label=Edit]
  -> component:ReaderPostActions
  -> function:onEditClick
  -> function:getEditURL
```

#### 测试与复现边

```text
test_targets: test_case -> function/file
fixture_used_by: fixture -> test_case
example_reproduces: example_file -> behavior
snapshot_compares: snapshot -> renderer/layout function
```

示例：

```text
packages/examples/src/knobs/index.js
  -> reproduction:margin_auto_layout
  -> stylesheet:expandStyles
```

#### 多模态证据边

```text
url_points_to_file: GitHubBlobURL -> file
url_points_to_line: GitHubBlobURL -> line/function
url_describes_api: APIDocURL -> API concept
url_reproduces_route: ReproURL -> route
image_mentions_text: ImageRegion -> OCRText
image_shows_component: ImageRegion -> component
image_shows_behavior: Image -> behavior
```

### 3.4 边权重与置信度

不同边不应该等价。

建议权重：

| 边来源 | 置信度 | 用法 |
|---|---:|---|
| GitHub blob URL 解析出的文件路径 | 高 | 可直接作为 seed，但需判断 evidence-only 或 target |
| LSP/SCIP def-use | 高 | 精确跳转、引用扩展 |
| import/export | 高 | 文件级扩展 |
| tree-sitter function/class span | 中高 | 结构定位 |
| route parser | 中 | Web/UI repo 很重要 |
| CSS selector/className 匹配 | 中 | 前端样式定位 |
| JSON key/script 解析 | 中 | 配置和测试入口 |
| OCR/图片 caption | 中低 | 需要证据角色识别 |
| LLM 推断边 | 低 | 只用于候选扩展，不直接当强证据 |

## 4. CSS、JSON、Markdown 等非调用文件如何建模

### 4.1 CSS/SCSS

CSS 没有函数，但有 selector、变量、mixin、import。

节点：

```text
css_file
css_selector
css_variable
scss_mixin
```

边：

```text
scss_imports: style_file -> style_file
defines_selector: style_file -> selector
component_imports_style: jsx_file -> style_file
className_matches_selector: component -> selector
```

例子：

```text
client/blocks/reader-post-actions/index.jsx
  --component_imports_style-->
client/blocks/reader-post-actions/style.scss

className="reader-post-actions__edit"
  --className_matches_selector-->
.reader-post-actions__edit
```

这样即使 gold 是 CSS 文件，也能从 UI 图片中的按钮或 JSX component 扩展到 style 文件。

### 4.2 JSON/YAML

JSON/YAML 的核心实体是 key path。

节点：

```text
json_key:package.json::scripts.test
json_key:tsconfig.json::compilerOptions.paths
yaml_key:.github/workflows/ci.yml::jobs.test.steps
```

边：

```text
script_runs
configures
loads
declares_dependency
workflow_runs
```

例子：

```text
package.json::scripts.test
  -> jest.config.js
  -> packages/stylesheet/tests/resolve.test.js
```

对于 benchmark 中的配置类 bug，函数调用图完全无效，必须依赖配置边。

### 4.3 Markdown / 文档

Markdown 常常是 API 行为说明或 example 文档。

节点：

```text
markdown_section
code_block
api_name
```

边：

```text
documents: markdown_section -> function/class/config_key
example_uses: code_block -> API/function
mentions_option: markdown_section -> config_key
```

例如 Python/Java benchmark 中大量 URL 是文档/API 说明，不能只当文本，而应抽取：

```text
API name
parameter name
expected behavior
version
exception type
```

### 4.4 图片资源与 snapshot

图片资源、snapshot 文件本身没有函数，但它们连接测试和渲染 pipeline。

节点：

```text
asset:image.png
snapshot:test.snap
visual_region
```

边：

```text
snapshot_generated_by: snapshot -> test_case
test_targets: test_case -> renderer/layout/parser
image_used_by: asset -> component/test
```

对 react-pdf、Chart.js、p5.js 这类视觉类 benchmark 非常关键。

## 5. 多语言适配策略

### 5.1 不同语言使用不同解析器，但输出统一 schema

建议分层：

```text
Language Adapter
  -> Universal Entity Schema
  -> Universal Edge Schema
  -> Repository Graph
```

语言适配器：

| 语言/文件 | 优先工具 | 备选 |
|---|---|---|
| Python | pyright/jedi/LSP + tree-sitter | ast |
| Java | jdtls/LSIF/SCIP + tree-sitter | javaparser |
| TypeScript/JavaScript | tsserver/SCIP + tree-sitter | babel parser |
| C/C++ | clangd/LSIF + tree-sitter | ctags |
| CSS/SCSS | postcss/sass parser | regex + tree-sitter-css |
| JSON/YAML | structured parser | jsonpath/yamlpath |
| Markdown | markdown parser | heading/code block regex |

核心要求：

```text
不同语言产出的节点必须能进入同一个图。
```

例如：

```text
Java method
Python function
TS React component
CSS selector
JSON config key
```

都统一为：

```text
Entity(id, type, language, file, span, name, properties)
```

### 5.2 多语言统一边类型

不要为每种语言定义完全不同的边，而要使用通用关系：

```text
contains
defines
imports
references
calls
reads
writes
configures
tests
documents
styles
routes_to
renders
generates_url
```

这样 Java 的 method call、Python 的 function call、TS 的 hook call 都可以归到 `calls`；CSS selector 和 JSX className 则归到 `styles` 或 `className_matches_selector`。

### 5.3 处理跨语言边

跨语言边在真实项目里很常见：

| 跨语言关系 | 示例 |
|---|---|
| JS/TS -> CSS/SCSS | React component import style |
| JS/TS -> JSON | package config, i18n messages |
| Python -> YAML | config loading |
| Java -> XML/JSON | Spring config, Gson fixture |
| C/C++ -> header | declaration / implementation |
| Markdown -> code | docs example maps to API |

这些边通常不是编译器 call graph，需要专门抽取：

```text
import './style.scss'
className="foo"
load_config("config.yaml")
open("fixture.json")
@Value("${config.key}")
```

### 5.4 新增函数和无函数文件的评估适配

多语言图还要服务评估。

建议每个实体带：

```text
evaluable_levels = [file, module, function]
```

例如：

```text
JS function -> file/module/function
CSS selector -> file/module-like, not function
JSON key -> file/module-like, not function
Markdown section -> file/module-like, not function
新增函数 -> file-level reliable, function-level uncertain
```

这样评估报告可以区分：

```text
function 定位失败
```

和：

```text
该 gold 本身不可做 function-level 评估
```

## 6. Agent 如何使用这个图

### 6.1 第一步：证据角色识别

输入 issue 后，agent 先不直接搜索文件，而是把证据分类：

```text
image: UI symptom / visual diff / error screenshot / chart rendering
url: GitHub code / repro page / API doc / issue discussion / playground / weak webpage
text: API name / error message / route / component / config / behavior
```

例子一：

```text
Reader Edit link broken
image: UI action evidence
url: runtime route evidence
hint: wrong generated URL
target layer: URL builder / data normalization
```

例子二：

```text
margin auto broken
image: layout visual diff
url: reproduction example
target layer: stylesheet expand / resolve
```

### 6.2 第二步：生成多路 query

同一个 issue 应生成多路 query：

```text
surface query: Reader Edit link
semantic query: generated edit URL / post type / default post type
graph query: route -> action -> URL builder
file query: utils / posts / getEditURL
```

对于 `margin auto`：

```text
surface query: packages/examples/src/knobs margin auto
semantic query: box model auto value expand resolve
graph query: example -> stylesheet -> layout
file query: expandStyles processBoxModel resolveStyles
```

### 6.3 第三步：图扩展，不同证据走不同边

不是所有 seed 都同权。

GitHub example URL：

```text
seed = reproduction evidence
扩展方向：example -> tests -> semantic API -> implementation
降权：example file itself
```

运行 URL：

```text
seed = route evidence
扩展方向：route -> controller/component -> action handler -> URL builder/state
```

图片按钮：

```text
seed = visual UI action
扩展方向：button label -> component/action -> handler
```

CSS selector：

```text
seed = style evidence
扩展方向：selector -> component -> style file / layout code
```

### 6.4 第四步：候选 rerank

候选文件分数不应只来自文本相似度。

建议分数：

```text
score(file) =
  lexical_score
  + dense_score
  + graph_proximity_score
  + evidence_role_score
  + language_router_score
  + patch_layer_prior
  - evidence_only_penalty
```

其中：

```text
evidence_only_penalty
```

非常关键。比如 URL 指向 example 文件或相关代码但非 gold 文件时，不能直接把它排第一。

### 6.5 第五步：failure-aware verifier

在输出前，agent 自检：

```text
如果我预测的是 example 文件，它是否只是复现？
如果我预测的是 UI component，bug 是否可能在 URL builder/state/style pipeline？
如果我预测的是 renderer，问题是否其实在 stylesheet/layout input？
如果 gold 可能是 CSS/JSON，我的候选是否覆盖了非函数文件？
```

这种 verifier 对我们两个真实案例都有效：

- `wp-calypso-23915`：会把 UI action 继续追到 URL builder；
- `react-pdf-1178`：会把 example/renderer 降权，把 stylesheet expand/resolve 升权。

## 7. 针对当前 baseline 的不足分析

### 7.1 LocAgent

优势：

```text
能交互式搜索，部分情况下可以从表层 UI 跳到内部函数。
```

不足：

```text
搜索 query 仍然强依赖 issue surface terms。
对 CSS/JSON/配置/样式关系缺少专门边。
多语言实体统一不足，function 之外的定位粒度不稳定。
```

### 7.2 CoSIL

优势：

```text
可以动态构造搜索过程，能做一定反思。
```

不足：

```text
如果初始语义层判断错，会在错误子图内反复搜索。
对 reproduction URL 和 patch target 的区分不足。
```

### 7.3 GraphLocator

优势：

```text
有图和因果链思想。
```

不足：

```text
图的边类型偏代码结构，对非调用关系支持不足。
一旦 seed 错，图扩展会扩大错误区域。
```

### 7.4 GALA

优势：

```text
在视觉/代码对齐和图对齐上有潜力。
```

不足：

```text
容易停在视觉表层对应的组件、layout node、renderer。
缺少“视觉症状 -> 内部语义层”的显式映射。
```

### 7.5 BM25 / Dense

优势：

```text
简单稳定，能抓住文件名/API 名/错误词。
```

不足：

```text
无法区分 URL 是 evidence 还是 target。
无法做多跳数据流、配置流、样式流推理。
```

## 8. 建议的创新框架

可以把方法命名为：

```text
M3RepoGraph-Agent
Multimodal Multilingual Multi-relation Repository Graph Agent
```

核心思想：

```text
将 issue 中的文本、图片、URL 转成结构化 evidence node；
将多语言代码、配置、样式、文档转成统一 repository graph；
通过 evidence-role-aware graph traversal 找到真正 patch target。
```

整体流程：

```text
Issue
  -> Evidence Parser
      -> text evidence
      -> image evidence
      -> URL evidence
  -> Language Router
      -> JS/TS adapter
      -> Python adapter
      -> Java adapter
      -> CSS/JSON/Markdown adapter
  -> Repository Graph Builder
      -> syntax/import/call/dataflow/config/style/route/test edges
  -> Evidence-role-aware Retriever
      -> seed classification
      -> graph expansion
      -> rerank
  -> Agent Search
      -> inspect candidate paths
      -> verify evidence-to-target chain
  -> Output
      -> file/module/function candidates
      -> explanation path
```

输出不只给文件，还给路径：

```text
image_region(Edit button)
  -> ReaderPostActions
  -> onEditClick
  -> getEditURL
  -> client/lib/posts/utils.js
```

或者：

```text
image(layout diff)
  -> margin:auto semantic
  -> stylesheet expand
  -> processBoxModel
  -> packages/stylesheet/src/expand.js
```

这类路径可以直接写进论文，作为可解释定位证据。

## 9. 实现优先级

### 9.1 第一阶段：低成本可实现

先做文件级异构图，不追求完整 CPG：

```text
file imports file
file defines function/class
component imports CSS
className matches CSS selector
package.json scripts/config
route string -> file
GitHub URL -> file/line
image OCR/caption -> text evidence
```

目标：

```text
提升 file-level localization。
```

### 9.2 第二阶段：实体级增强

加入：

```text
function/class span
calls/references
test targets
config key
route handler
CSS selector
```

目标：

```text
提升 module/function-level recall，但只在可评估实体上报告。
```

### 9.3 第三阶段：跨语言精确索引

引入：

```text
LSIF/SCIP/LSP
语言专用解析器
CPG/Joern-like 分析
```

目标：

```text
更准的 def-use / reference / call / dataflow。
```

### 9.4 第四阶段：多模态 evidence graph

加入：

```text
图片 OCR
UI element detection
URL role classifier
web page summarizer
playground/parser extraction
```

目标：

```text
把图片和 URL 从 prompt 文本变成结构化图节点。
```

## 10. 论文故事线

可以这样组织创新动机：

```text
现有 agent 把 issue 文本、图片 caption、URL summary 混合作为普通文本检索。
这导致两类错误：

1. Evidence-as-target 错误：
   URL 指向 example、文档、相关代码，但模型把它当 patch target。

2. Surface-layer 错误：
   图片显示 UI 或渲染现象，模型停在 UI/renderer，
   但真实 patch 在 URL builder、style resolver、config loader、data model。

为解决这个问题，我们提出 evidence-aware multilingual repository graph。
它统一建模代码、配置、样式、文档、图片、URL 和语言实体关系，
并让 agent 沿着 typed graph path 从多模态证据走到真实修复层。
```

可以配两个典型例子：

```text
Reader Edit link:
image/button + runtime URL -> URL builder -> getEditURL

react-pdf margin auto:
visual layout diff + example URL -> stylesheet semantic expansion -> processBoxModel
```

## 11. 与评估指标的关系

这个图设计也能解释为什么 file-level 应作为主指标：

```text
CSS/JSON/Markdown/新增函数等目标不一定有 function gold。
多语言结构抽取不完全可靠。
file-level 是最稳定的跨语言、跨文件类型评价层。
```

但图仍然可以输出 module/function：

```text
当实体可映射时，报告 module/function。
当实体不可映射时，报告 selector/config_key/route/section 等替代实体。
```

因此建议未来评估扩展为：

```text
File-level: 主指标
Entity-level: function/class/selector/config_key/route/test_case 的统一实体指标
Function-level: 仅在可映射函数样本上作为子集指标
```

这比强行把所有样本都压成 function-level 更严谨。

## 12. 最终建议

不要把多语言多模态定位框架设计成“更大的 call graph”。应该设计成：

```text
Typed Evidence Graph + Multilingual Repository Graph + Agent Traversal
```

最重要的三个创新点：

1. **证据角色识别**：区分 URL/图片是 reproduction、symptom、API doc、code pointer，还是 patch target。
2. **多关系仓库图**：除调用关系外，显式建模 style、route、config、test、documentation、asset、URL builder 等关系。
3. **统一实体层**：将 function 与 CSS selector、JSON key、route、markdown section 等并列为可定位实体，解决无函数文件和跨语言实体不一致问题。

这样才能真正覆盖我们 benchmark 中的复杂样本，而不是只在函数调用图能解释的样本上有效。

