# 证据提取与仓库图分离的 Agent 定位和修复框架

本文重新整理一个关键设计判断：**issue 相关证据提取** 和 **仓库图建模** 应该分开，而不是把图片、URL、文档、代码结构、调用关系全部塞进一张大图里。

更合理的系统分层是：

```text
Issue Evidence Layer
  负责理解问题、提取证据、判断证据角色、形成可解释需求。

Repository Navigation Graph
  负责提供仓库结构导航、语义边扩展、候选定位和路径解释。

Reasoning / Planning Layer
  负责把证据和图连接起来，形成定位链路，并进一步服务代码修复。
```

这个分离很重要。证据提取回答的是：

```text
这个 issue 到底在说什么？
图片、URL、代码片段、文档链接分别提供了什么信息？
哪些是复现入口，哪些是行为规范，哪些只是背景，哪些可能直接指向修复位置？
```

仓库图回答的是：

```text
给定一些证据种子，仓库里有哪些文件、函数、类、组件、配置、样式、测试和它们相关？
应该沿哪些 import/call/reference/route/state/delegate/parameter-flow 边扩展？
候选文件是否形成完整 patch closure？
```

这两个问题不能混在一起。混在一起会导致图过大、语义不清、Agent 搜索失控，也会让证据角色和代码关系互相污染。

## 1. 为什么证据和图要分开

### 1.1 Issue 证据不是仓库实体

Issue 中的图片、URL、playground、外部文档、GitHub issue/PR、StackOverflow 链接，本质上不是代码仓库中的实体。它们是外部证据。

例如：

```text
https://github.com/Automattic/wp-calypso/blob/master/client/state/current-user/selectors.js#L157
```

这个 URL 指向仓库文件，但在 `Automattic__wp-calypso-21409` 中，它不是最终 patch target，而是 email verification 状态的 evidence seed。真实修复在 WooCommerce dashboard/address/location flow。

如果直接把这个 URL 当作图中的强目标节点，Agent 就会被误导。

正确做法是：

```text
URL evidence card:
  type = GitHubCodeURL
  target_file = client/state/current-user/selectors.js
  symbol = isCurrentUserEmailVerified
  role = evidence_only

Repository graph:
  selector -> references/usages -> WooCommerce flow components
```

也就是说，URL 先进入证据层，由证据层判断角色；仓库图只负责根据这个 seed 做结构扩展。

### 1.2 图片需要先转成问题语义，不应直接进入代码图

图片中的信息一般是：

```text
UI 文案
按钮/输入框/弹窗
layout diff
chart/canvas 渲染现象
PDF 排版问题
截图中的路径、报错、状态
```

这些不是仓库节点。它们需要先转成结构化证据：

```text
image symptom:
  type = Web UI flow
  visible_text = ["Store Location", "Create your store"]
  user_action = click create store
  expected_behavior = block unsupported-country user until email verification
  likely_mechanism = route/component/state guard
```

然后再进入仓库图：

```text
Store Location
  -> route/component search
  -> state selector/action expansion
  -> dashboard/address/location files
```

如果把图片节点直接和所有可能文件连接，图会非常噪声。图片证据应该先被解释，再作为搜索约束进入图。

### 1.3 仓库图应该稳定，证据层应该按 issue 动态生成

仓库图是仓库级基础设施。它应该相对稳定：

```text
文件
函数
类
组件
路由
配置 key
CSS selector
测试
import/export/call/reference/delegate/route/style/config edges
```

同一个仓库里的多个 issue 可以复用同一张图。

证据层是 issue-specific 的。每个 issue 的图片、URL、问题描述、复现步骤不同，所以 evidence cards 每次动态生成。

因此更合理的存储结构是：

```text
repo_graphs/
  Automattic__wp-calypso/
    nodes.jsonl
    edges.jsonl
    graph_summary.json

issue_evidence/
  Automattic__wp-calypso-21409/
    evidence_cards.jsonl
    issue_summary.json
    evidence_reasoning.md
```

然后定位时临时建立 bridge：

```text
evidence seed -> graph seed -> graph path -> candidate files
```

### 1.4 分开之后推理链路更清楚

如果证据和图混在一起，最终路径可能变成：

```text
image -> component -> selector -> url -> docs -> file -> function
```

很难判断这条路径的每一步到底是证据解释、仓库关系，还是模型猜测。

分开之后路径更清楚：

```text
Evidence reasoning:
  Image shows Store Location flow.
  GitHub URL points to email verification selector.
  Issue asks to block unsupported-country users before wp-admin.

Graph navigation:
  isCurrentUserEmailVerified
    -> references/usages
    -> WooCommerce dashboard/store-location components
    -> address/location state files

Repair planning:
  Add guard after address setup.
  Use selector result to branch supported vs unsupported countries.
  Update dashboard/location flow and tests.
```

这条链路既能用于定位，也能用于后续代码修复。

## 2. 推荐系统架构

### 2.1 三层架构

```text
Layer A: Evidence Extraction / Evidence Reasoning
  输入 issue text、image_urls、web_urls、code snippets
  输出 evidence cards、problem summary、candidate mechanisms

Layer B: Repository Navigation Graph
  输入仓库代码、repo_structures、tree-sitter/LSP/SCIP、配置/样式/测试解析
  输出 repo nodes、typed edges、queryable graph

Layer C: Agent Reasoning and Repair Planning
  输入 evidence cards + repo graph query results
  输出 localization candidates、path explanation、patch closure、repair plan
```

这个架构的关键是：**Evidence Layer 不直接决定最终文件，Graph Layer 不直接解释 issue 语义，Reasoning Layer 负责连接两者。**

### 2.2 数据流

```text
Issue
  |
  v
Evidence Extractor
  - URL parser
  - image/OCR analyzer
  - problem statement parser
  - code snippet parser
  - evidence role classifier
  |
  v
Evidence Cards
  |
  v
Seed Mapper
  - symbol seed
  - route seed
  - API seed
  - UI text seed
  - config seed
  - file/path seed
  |
  v
Repository Graph Query
  - search nodes
  - expand typed edges
  - trace paths
  |
  v
Candidate Set
  |
  v
Closure Verifier
  - API closure
  - UI flow closure
  - render pipeline closure
  - config/test closure
  |
  v
Localization Output + Repair Plan
```

## 3. Layer A：Issue 证据提取层

### 3.1 目标

证据层目标不是直接预测文件，而是生成结构化、可审计的 evidence cards。

每个 card 应回答：

```text
这个证据是什么？
它来自哪里？
它包含哪些可检索信号？
它在定位中应该扮演什么角色？
它的置信度是多少？
```

### 3.2 Evidence Card Schema

```json
{
  "instance_id": "Automattic__wp-calypso-21409",
  "evidence_id": "url:1",
  "source_type": "GitHubCodeURL",
  "raw": "https://github.com/Automattic/wp-calypso/blob/master/client/state/current-user/selectors.js#L157",
  "role": "evidence_only",
  "confidence": 0.86,
  "extracted": {
    "repo": "Automattic/wp-calypso",
    "file": "client/state/current-user/selectors.js",
    "line": 157,
    "symbols": ["isCurrentUserEmailVerified"],
    "keywords": ["email_verified", "current user", "verification"]
  },
  "reason": "URL points to a selector used to check verification state; issue requires flow blocking logic, so selector is evidence rather than final patch target."
}
```

图片 card：

```json
{
  "instance_id": "Automattic__wp-calypso-21409",
  "evidence_id": "image:1",
  "source_type": "Image",
  "image_type": "WebUI",
  "role": "symptom",
  "visible_text": ["Business Plan", "Create your store", "Please check your email"],
  "ui_elements": [
    {"type": "button", "text": "Create your store"},
    {"type": "notice", "text": "Please check your email to confirm your address"}
  ],
  "mechanism_hints": ["signup flow", "email verification guard", "store location flow"],
  "reason": "Image shows the flow allows proceeding despite email verification notice."
}
```

### 3.3 证据角色分类

建议固定这些角色：

| Role | 含义 | 用法 |
|---|---|---|
| `direct_target` | 证据直接指向可能修复文件/函数 | 高权重 seed，但仍需 closure 验证 |
| `evidence_only` | 证据相关，但不是最终修复点 | 低 direct-rank，高 expansion seed |
| `reproduction` | 复现入口、playground、运行 URL | 解析输入/配置/行为差异 |
| `behavior_spec` | 文档/API/规范 | 抽 expected behavior、参数语义 |
| `historical_context` | issue/PR/commit 讨论 | 抽历史文件、旧 patch、设计意图 |
| `symptom` | 图片/错误截图/视觉现象 | 转成机制 hint |
| `weak_context` | 弱背景网页 | 低权重，只作为补充 |

### 3.4 证据层输出不应包含最终答案

证据层可以输出：

```text
candidate symbols
candidate mechanisms
candidate language/router
candidate route/component/API/config
```

但不应该直接输出：

```text
最终 top-15 文件
最终 function candidates
```

否则证据层就会和定位层混在一起，难以调试错误来源。

## 4. Layer B：Repository Navigation Graph 仓库导航图

### 4.1 目标

仓库图的目标是提供稳定的可查询结构：

```text
给定一个 seed，能找到它在仓库中的定义、引用、调用、组件关系、配置关系、样式关系、测试关系、参数流和委托关系。
```

它不负责理解 issue，只负责回答仓库结构问题。

### 4.2 仓库图 Schema

节点：

```text
File
Module
Class
Function
Method
Variable
Symbol
Route
Component
Hook
Selector
Reducer
Action
URLBuilder
ConfigKey
StyleSelector
DocSection
Fixture
Snapshot
Test
```

边：

```text
contains
imports
exports
calls
references
inherits
implements
overrides
tests
routes_to
renders
selects_state
dispatches_action
styles
configures
documents
builds_url
parameter_flows_to
delegates_to
serializes_to
owns_resource
retains_resource
releases_resource
```

注意：这里不把图片和 URL 当作永久仓库节点。图片和 URL 属于 issue evidence。仓库图只保存仓库内部实体和关系。

### 4.3 仓库图可以分层构建

P0 基础结构：

```text
repo_structures -> File/Class/Function/Module nodes
contains edges
import/export/reference/test edges
```

P1 高频语义边：

```text
JS/TS:
  route/component/state/style/url builder

Python:
  parameter flow/API-to-backend/name binding

Java:
  delegate/override/implements/resource operation

CSS/JSON/Markdown:
  selector/config/doc section entities
```

P2 精确索引：

```text
LSP/SCIP
local/global data-flow
call hierarchy
type hierarchy
```

### 4.4 仓库图的查询接口

```text
search_nodes(query, kind=None, language=None)
get_node(node_id)
expand(node_ids, edge_types, max_hops)
trace_path(source_nodes, target_kinds)
find_references(symbol)
find_tests(file_or_symbol)
find_closure(seed_nodes, closure_type)
```

这些接口是 Agent 的工具，不直接暴露底层 JSON。

## 5. Layer C：推理与修复规划层

### 5.1 这个层的职责

推理层负责把证据层和图层连接起来：

```text
Evidence cards
  -> search seeds
  -> selected edge types
  -> graph paths
  -> candidate files/entities
  -> closure verification
  -> repair plan
```

它需要做判断：

```text
当前证据是 target 还是 seed？
应该使用哪些图边？
候选集合是否覆盖完整机制？
是否需要继续扩展？
是否需要查询测试或调用方？
```

### 5.2 推理链路格式

建议每个预测都输出类似结构：

```json
{
  "instance_id": "pyca__cryptography-7520",
  "evidence_summary": [
    "Issue asks to add kdf_rounds to OpenSSH private key encryption.",
    "URL is historical context from ansible community.crypto."
  ],
  "selected_seeds": [
    {"seed": "kdf_rounds", "source": "issue_text", "role": "parameter"},
    {"seed": "BestAvailableEncryption", "source": "issue_text", "role": "public_api"}
  ],
  "graph_paths": [
    [
      "BestAvailableEncryption",
      "_KeySerializationEncryption",
      "backend._private_key_bytes",
      "ssh._serialize_ssh_private_key"
    ]
  ],
  "candidate_files": [
    "src/cryptography/hazmat/primitives/_serialization.py",
    "src/cryptography/hazmat/primitives/serialization/__init__.py",
    "src/cryptography/hazmat/backends/openssl/backend.py",
    "src/cryptography/hazmat/primitives/serialization/ssh.py"
  ],
  "closure_type": "api_parameter_flow",
  "repair_plan": [
    "Add kdf_rounds to public encryption builder.",
    "Store it in the internal encryption object.",
    "Propagate it through backend serialization.",
    "Use it when writing OpenSSH KDF options."
  ]
}
```

### 5.3 为什么推理链路可以服务代码修复

定位只需要输出文件/函数；修复需要知道为什么这些文件要一起改。

例如 `pyca__cryptography-7520`：

```text
定位输出:
  _serialization.py
  serialization/__init__.py
  backend.py
  ssh.py

修复计划:
  public API 增加 kdf_rounds
  internal object 保存 kdf_rounds
  backend 识别 OpenSSH + encryption object
  serializer 写入 rounds
```

如果只有 top-k 文件，修复 Agent 仍然不知道怎么改。  
如果有 reasoning path，就能得到 patch skeleton。

再比如 `Automattic__wp-calypso-21409`：

```text
证据:
  图片显示用户可以点击 Create your store
  URL 指向 email verification selector

图路径:
  selector -> WooCommerce store location flow -> address setup -> dashboard blocking logic

修复计划:
  在 store location/address setup 后检查 country + email verification
  对 unsupported country 且未验证邮箱的用户阻断进入 wp-admin
  supported country 继续进入 dashboard setup
```

这说明 reasoning chain 是定位与修复之间的桥。

## 6. 分离后的错误诊断方式

把证据层和图层分开后，失败原因可以拆开分析。

### 6.1 证据层错误

```text
URL role 识别错：
  evidence_only 被当成 direct_target。

图片症状识别错：
  layout issue 被当成 renderer issue，实际是 stylesheet resolve。

playground 未解码：
  配置和输入代码没有进入 search seed。

文档/API 没抽出关键参数：
  API behavior 没形成 mechanism hint。
```

### 6.2 图层错误

```text
缺少边：
  public API 无法扩展到 internal delegate。

边错误：
  selector 误连到无关 component。

实体缺失：
  CSS selector / config key / doc section 没建节点。

图过度扩展：
  seed 太泛，候选文件膨胀。
```

### 6.3 推理层错误

```text
选错 edge type：
  应该走 parameter_flow，却只走 references。

closure 判断不完整：
  命中 serializer，漏 public API 和 backend。

过早停止：
  找到相关文件就输出，没有验证 patch closure。
```

这种诊断比“Acc@15 低”更有解释价值。

## 7. 和现有文档规划的关系

`028` 和 `029` 更强调“图应该包含什么”。本文强调“证据和图不应该混为一层”。

关系可以理解为：

```text
028:
  为什么 CPG / Semantic Code Graph 思想对我们的 benchmark 有用。

029:
  如果要做证据感知多语言仓库异构图，节点/边/工具/评估怎么规划。

030:
  更细化地拆分系统边界：
    issue evidence extraction 是动态问题理解；
    repository graph 是稳定导航基础设施；
    reasoning path 是二者之间的桥，并服务后续代码修复。
```

## 8. 最小可行实现规划

### 8.1 目录设计

```text
semantic_localization/
  evidence/
    extract_evidence.py
    classify_url_role.py
    analyze_image_card.py
    parse_playground.py
    schemas.py

  repo_graph/
    build_repo_graph.py
    extract_nodes.py
    extract_edges_common.py
    extract_edges_js_ts.py
    extract_edges_python.py
    extract_edges_java.py
    extract_edges_noncode.py
    query_graph.py

  reasoning/
    seed_mapper.py
    graph_policy.py
    closure_verifier.py
    repair_planner.py
    path_explainer.py
```

输出：

```text
artifacts/
  evidence_cards/<benchmark>/<instance_id>.jsonl
  repo_graphs/<repo>/nodes.jsonl
  repo_graphs/<repo>/edges.jsonl
  reasoning_traces/<benchmark>/<instance_id>.json
```

### 8.2 P0：先做证据层

目标：先把 issue 证据讲清楚，不碰复杂图。

任务：

```text
1. URL 分类：GitHub code / playground / docs / issuePR / commit / external
2. URL role：direct_target / evidence_only / reproduction / behavior_spec / historical_context / weak_context
3. 图片 card：image_type / visible_text / UI elements / symptom / mechanism hints
4. Issue text card：API names / error messages / code snippets / config names
```

验证：

```text
对已有典型失败样本手工检查 evidence card 是否合理：
  Automattic__wp-calypso-21409
  diegomura__react-pdf-1178
  pyca__cryptography-7520
  python__mypy-13481
```

### 8.3 P1：做轻量仓库图

目标：图作为导航基础设施，先覆盖高频边。

任务：

```text
1. 从 repo_structures 生成 File/Class/Function/Module
2. contains/imports/references/tests
3. JS/TS route/component/state/style 基础边
4. Python parameter flow/API-to-backend 基础边
5. Java delegate/override 基础边
6. CSS/JSON/Markdown semantic entity 节点
```

验证：

```text
给定 evidence seed，能查询到合理候选路径。
```

### 8.4 P2：做推理链路和 closure verifier

目标：从定位走向修复计划。

任务：

```text
1. evidence seed -> graph seed 映射
2. edge-type selection policy
3. trace path 输出
4. closure verifier
5. repair plan skeleton
```

验证：

```text
对典型失败样本输出：
  evidence summary
  graph path
  candidate files
  missing closure roles
  repair plan
```

### 8.5 P3：接入 Agent

目标：让 Agent 真正用工具，而不是只读文档。

工具：

```text
classify_evidence(instance_id)
map_evidence_to_seeds(instance_id)
query_repo_graph(repo, seed, edge_types, max_hops)
verify_patch_closure(instance_id, candidate_files)
generate_repair_plan(instance_id, candidate_files)
```

## 9. 评估方式

### 9.1 定位评估

继续保留：

```text
File Acc@1/3/5/8/10/12/13/15
File MRR@15
File MAP@15
File REC@All
```

函数/实体级：

```text
Function-level eligible:
  仅在 function gold 可映射样本上报告

Semantic entity-level:
  Function / Method / StyleSelector / ConfigKey / DocSection / Fixture / Snapshot
```

### 9.2 证据层评估

```text
URL type accuracy
URL role accuracy
image symptom type accuracy
evidence seed hit rate
mechanism hint relevance
```

### 9.3 图层评估

```text
gold path reachable rate
average hops to gold
expansion precision
edge coverage by language
non-code entity coverage
```

### 9.4 推理链路评估

```text
path explanation hit rate
closure completeness
missing-role detection accuracy
repair plan usefulness
```

这几个新指标能解释模型为什么错，而不是只给一个最终 Acc。

## 10. 论文故事线

可以这样写：

```text
Existing localization agents often conflate issue understanding and repository navigation.
They treat images, URLs, code links, and document links as plain text retrieval cues, while using repository structures only as files or functions.
Our benchmark analysis shows that this conflation causes systematic failures: evidence-only URLs are mistaken as patch targets, visual symptoms are not translated into code mechanisms, and multilingual semantic relations are missing.

We therefore decouple issue evidence extraction from repository graph modeling.
The evidence layer produces typed evidence cards and mechanism hints.
The repository graph provides stable typed navigation over code and non-code entities.
The reasoning layer connects them through path-guided search and patch closure verification, producing localization results and repair-oriented reasoning traces.
```

中文：

```text
现有 Agent 往往把 issue 理解和仓库导航混在一起：
图片、URL、代码链接、文档链接被当作普通文本检索线索；
仓库结构又只被简化成文件和函数。

我们的 benchmark 分析显示，这种混合会导致系统性失败：
evidence-only URL 被误认为 patch target；
视觉症状没有转换成代码机制；
Python/Java/JS 等语言特定语义边缺失；
CSS/JSON/Markdown 等非函数修复目标无法表达。

因此，我们将系统拆成三层：
证据层负责 issue evidence extraction；
仓库图层负责 typed repository navigation；
推理层负责 evidence-to-graph mapping、path-guided localization 和 patch closure verification。
这样得到的推理链路不仅能提升定位，也能直接服务代码修复规划。
```

## 11. 结论

你的直觉是对的：证据提取和图建模应该分开。

更准确的框架不是：

```text
把 issue evidence 和 repository 全部塞进一张大图。
```

而是：

```text
Issue evidence extraction:
  动态理解每个 issue，输出证据卡和机制 hint。

Repository graph:
  稳定表达仓库结构和语言/生态语义关系，作为导航基础设施。

Reasoning chain:
  把证据卡映射到图 seed，沿 typed edges 扩展，验证 patch closure，并生成修复计划。
```

这样系统边界更清楚，错误可诊断，推理链路可解释，并且天然支持从 localization 过渡到 repair。

