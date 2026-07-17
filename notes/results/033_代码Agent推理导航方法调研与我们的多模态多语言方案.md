# 代码 Agent 推理导航方法调研与我们的多模态多语言方案

本文回答一个问题：**别人做代码 Agent 时，是如何让 Agent 在仓库中推理、搜索、导航和定位的？我们在多模态、多语言 issue localization 中应该怎么做？**

结论先写在前面：

> 现有代码 Agent 大致有四条路线：工具接口型、分阶段流程型、软件工程分析型、仓库图导航型。它们都能解决部分代码定位问题，但对我们的 benchmark 来说还不够，因为 SWE-bench Multimodal 和 OmniGIRL 的关键不是“让 Agent 会 grep/打开文件”，而是让 Agent 先理解图片和 URL 的证据角色，再通过多语言仓库图做机制级导航和 patch closure 验证。

## 1. 联网调研：别人怎么做 Agent 推理和导航

### 1.1 SWE-agent：Agent-Computer Interface 路线

SWE-agent 的核心贡献不是新的检索算法，而是 Agent-Computer Interface（ACI）。论文强调，自定义 ACI 能显著提升 Agent 创建/编辑代码、导航仓库、执行测试和程序的能力。

参考资料：

- SWE-agent paper: <https://proceedings.neurips.cc/paper_files/paper/2024/file/5a7c947568c1b1328ccc5230172e1e7c-Paper-Conference.pdf>
- OpenReview: <https://openreview.net/forum?id=mXpq6ut8J3>
- GitHub: <https://github.com/swe-agent/swe-agent>

SWE-agent 的思路可以概括为：

```text
GitHub issue
  -> LLM agent
  -> ACI tools
      search
      open file
      edit file
      run tests
      observe feedback
  -> iterative repair
```

它的启发：

1. 工具接口比裸 shell 更重要。  
   Agent 如果只有自由 shell，容易产生不稳定搜索、错误编辑和无效观察。结构化工具能约束行为。

2. Agent 需要可观察反馈。  
   搜索结果、文件内容、测试输出都应该形成下一步决策依据。

3. 工具设计会影响 Agent 推理行为。  
   如果工具只支持全文搜索，Agent 就会偏关键词；如果工具支持结构图查询，Agent 才可能做结构导航。

对我们的不足：

- SWE-agent 主要面向纯文本 GitHub issue 和代码修复；
- 没有专门处理图片、URL role、playground、文档 API；
- 仓库导航主要依赖文件搜索和 shell，而不是多语言语义图；
- 对 evidence-only URL 和 patch closure 没有显式 verifier。

我们的吸收方式：

```text
保留 ACI 思想，但工具应该从 grep/open/edit 扩展为：
  parse_issue_evidence
  classify_url_role
  query_repo_graph
  expand_patch_closure
  verify_evidence_target
```

### 1.2 OpenHands：通用平台和事件驱动 Agent 路线

OpenHands 强调平台化、沙箱执行、命令行交互、浏览网页、写代码、多 Agent 协作等能力。它解决的是“如何构建可运行的软件工程 Agent 平台”。

参考资料：

- OpenHands ICLR paper: <https://proceedings.iclr.cc/paper_files/paper/2025/file/a4b6ad6b48850c0c331d1259fc66a69c-Paper-Conference.pdf>
- OpenHands SDK paper: <https://arxiv.org/html/2511.03690v1>
- OpenHands GitHub: <https://github.com/OpenHands/openhands>
- OpenHands website: <https://www.openhands.dev/>

OpenHands 的典型结构：

```text
Agent
  -> sandboxed environment
  -> shell
  -> browser
  -> file editor
  -> event stream
  -> user interaction
```

它的启发：

1. 对网页 URL，Agent 确实需要 browser 或网页读取能力。  
   这对 OmniGIRL 里的 GitHub issue/PR、文档 URL、playground URL 很关键。

2. 事件流可以保留完整轨迹。  
   我们分析失败样本时，很需要真实 trajectory。OpenHands 这类事件架构适合审计和复盘。

3. 平台能力和定位方法要分开。  
   OpenHands 给的是执行环境和工具底座，不直接等于好的 localization policy。

对我们的不足：

- “能打开网页”不等于“知道 URL 是 evidence 还是 target”；
- “能浏览图片”不等于“能把视觉症状映射到 route/component/layout pipeline”；
- 通用 Agent 平台没有内置 benchmark-specific evidence routing；
- 对多语言仓库语义边没有默认保障。

我们的吸收方式：

```text
借鉴 OpenHands 的 event trace / browser / sandbox，
但在定位层增加：
  URL resolver
  evidence card
  mechanism router
  graph navigation tools
```

### 1.3 AutoCodeRover：软件工程分析 + LLM 搜索路线

AutoCodeRover 面向 GitHub issue 自动程序改进，强调 LLM 与软件工程分析/代码搜索能力结合，最终定位 patch 位置并生成修改。

参考资料：

- AutoCodeRover paper: <https://arxiv.org/html/2404.05427v3>
- PDF: <https://arxiv.org/pdf/2404.05427>
- GitHub: <https://github.com/AutoCodeRoverSG/auto-code-rover>
- ACM: <https://dl.acm.org/doi/10.1145/3650212.3680384>

它的方向：

```text
issue
  -> code search
  -> suspicious location prioritization
  -> patch generation
  -> validation
```

它的启发：

1. 软件工程任务不能只靠 LLM 闲聊，需要搜索、定位、验证。  
2. 定位和修复应该联动，定位结果最好能解释为什么要改这些文件。  
3. 测试和分析能力可以帮助优先排序 patch location。

对我们的不足：

- 我们当前任务更强调 localization 评估，不一定每个样本都能跑测试；
- 多模态图片/URL 证据不是 AutoCodeRover 的核心；
- 多语言和前端/渲染/样式/配置闭包需要额外建模。

我们的吸收方式：

```text
将 AutoCodeRover 的“搜索 + 分析 + 验证”思想改成：
  evidence search
  graph mechanism analysis
  localization closure verification
```

### 1.4 Agentless：分阶段、可解释、低复杂度路线

Agentless 的核心观点是：复杂 autonomous Agent 不一定必要。它采用 localization、repair、patch validation 的分阶段流程，减少让 LLM 自由决策的复杂性。

参考资料：

- Agentless paper: <https://arxiv.org/abs/2407.01489>
- GitHub: <https://github.com/openautocoder/agentless>
- ACM page: <https://dl.acm.org/doi/abs/10.1145/3715754>

Agentless 的流程可抽象为：

```text
issue
  -> localization
  -> repair
  -> validation
```

它的启发：

1. 不一定要让 Agent 自由决定每一步。  
   对我们来说，URL 分类、图片分类、patch closure 检查都应该是固定阶段，而不是每次让 LLM 想起才做。

2. 分阶段流程更可控、更可复评估。  
   我们可以分别评估 evidence extraction、seed mapping、graph expansion、rerank、closure verification。

3. 简单 baseline 很重要。  
   BM25-MMIR 在我们的结果里仍有较强召回，说明第一阶段召回不应被复杂 Agent 掩盖。

对我们的不足：

- Agentless 的 localization 仍主要面向文本 issue 和代码；
- 没有解决图片/URL 证据角色；
- 没有专门建模多语言 semantic edges。

我们的吸收方式：

```text
采用 Agentless 的阶段化思想：
  Stage 1: evidence extraction
  Stage 2: candidate recall
  Stage 3: graph expansion
  Stage 4: rerank
  Stage 5: closure verification
```

### 1.5 Aider Repo Map：静态 repo map + 重要符号排序路线

Aider 的 repo map 使用 tree-sitter 构建仓库摘要，包含重要类、函数、类型和调用签名，让 LLM 了解代码结构。Aider 文档强调 repo map 可以帮助模型理解代码关系，并在上下文预算内提供相关结构。

参考资料：

- Aider repo map article: <https://aider.chat/2023/10/22/repomap.html>
- Aider repo map docs: <https://aider.chat/docs/repomap.html>
- Aider ctags note: <https://aider.chat/docs/ctags.html>

典型思路：

```text
Repository
  -> parse with tree-sitter
  -> extract classes/functions/signatures
  -> rank important symbols
  -> put compact repo map into prompt
```

它的启发：

1. 仓库地图可以显著减少盲搜。  
2. tree-sitter 是多语言结构抽取的实用底座。  
3. 图不一定要全量展示给模型，可以摘要化、按需检索。

对我们的不足：

- repo map 主要是静态结构摘要，不处理 issue evidence；
- 重要符号排名不等于 patch target ranking；
- 对 CSS/JSON/Markdown、URL/playground、图片症状没有专门支持；
- 不能解决 evidence-only URL 误导。

我们的吸收方式：

```text
用 repo map 做全局 orientation，
但真正定位时要：
  evidence-specific seed
  typed graph query
  closure verification
```

### 1.6 RepoGraph：仓库级图作为插件的导航路线

RepoGraph 将仓库表示为图，并作为插件帮助已有 AI software engineering 系统进行 repository-wide navigation。论文说明它可以接入 localization 和 editing 阶段，为 LLM 提供结构化上下文。

参考资料：

- RepoGraph paper: <https://arxiv.org/html/2410.14684v1>
- ICLR PDF: <https://proceedings.iclr.cc/paper_files/paper/2025/file/4a4a3c197deac042461c677219efd36c-Paper-Conference.pdf>

RepoGraph 的核心思路：

```text
repository
  -> graph construction
  -> subgraph retrieval
  -> structured context
  -> plug into localization/editing
```

它的启发：

1. 图更适合作为可插拔导航模块，而不是完全替代 Agent。
2. 子图检索比整仓库图直接塞 prompt 更可控。
3. 图可以服务 localization，也可以服务 editing。

对我们的不足：

- 通用 repo graph 不一定知道图片/URL 的证据角色；
- 如果 seed 错，子图也会围绕错误中心扩展；
- 需要加入多模态 evidence router 和 benchmark mechanism router。

我们的吸收方式：

```text
RepoGraph-style subgraph retrieval
  + evidence role classifier
  + multilingual typed edges
  + patch closure verifier
```

### 1.7 LocAgent / CoSIL：图引导定位和迭代搜索路线

LocAgent 通过 directed heterogeneous graph 表示代码结构，包括 files/classes/functions 以及 imports/invocations/inheritance 等依赖关系，用 LLM agent 做多跳搜索和定位。CoSIL 则强调 LLM-driven iterative code repository graph searching。

参考资料：

- LocAgent paper: <https://arxiv.org/html/2503.09089v1>
- LocAgent ACL PDF: <https://aclanthology.org/2025.acl-long.426.pdf>
- CoSIL 相关索引可见于 repository-level code generation 资料：<https://github.com/YerbaPage/Awesome-Repo-Level-Code-Generation>

它们的启发：

1. 图搜索确实适合 code localization。  
2. LLM 可以在图上做多跳推理，而不是只读 top-k 文件。  
3. 结构边对函数级定位有价值。

我们实验中暴露的问题：

- 多语言、多模态、多资源文件下，图边不够；
- URL 和图片证据没有先转换成图 seed；
- GraphLocator/CoSIL 容易从错误 seed 扩散；
- 函数级和非函数资源的细粒度评估仍不稳。

我们的改进：

```text
不是放弃图，而是让图变成：
  evidence-aware
  multilingual
  mechanism-aware
  closure-verifiable
```

## 2. 现有方法的共性和缺口

### 2.1 共性

现有方法有效的共同点：

| 共性 | 说明 |
|---|---|
| 工具化 | Agent 需要 search/open/edit/run/test 等工具 |
| 分阶段 | localization、repair、validation 常被拆开 |
| 仓库结构 | repo map、repo graph、code graph 能改善上下文 |
| 反馈循环 | 搜索结果、测试结果、文件内容驱动下一步 |
| 子图/摘要 | 不把整个仓库塞 prompt，而是检索相关结构 |

### 2.2 缺口

对我们的 benchmark 来说，现有方法普遍缺四件事：

1. **缺证据角色识别**  
   图片、GitHub blob、issue URL、playground URL、文档 URL 被混在 issue 文本中。Agent 不知道它们是 patch target、reproduction evidence、context evidence 还是 weak evidence。

2. **缺视觉症状到代码机制的翻译**  
   Web UI 截图、Chart.js 图表、react-pdf 排版、p5.js WebGL 图形都需要先转成机制假设，而不是只生成自然语言描述。

3. **缺多语言/多资源 typed edges**  
   Python 需要 binder/type/parameter flow；Java 需要 override/delegate/resource ownership；JS/TS 需要 route/component/state/plugin pipeline；CSS/JSON/Markdown 需要 style/config/doc/fixture edges。

4. **缺 patch closure verifier**  
   Agent 命中一个入口后，常常漏掉其他 gold 文件。比如 `21409` 命中 `store-location-setup-view.js` 但漏 WooCommerce settings 闭包；`1178` 命中 `expand.js` 但漏 `resolve.js`。

## 3. 我们应该怎么做 Agent 推理和导航

### 3.1 总体方案：Evidence-Routed Graph-Navigating Agent

建议框架名称：

```text
Evidence-Routed Graph-Navigating Agent
证据路由驱动的图导航 Agent
```

整体流程：

```text
Issue
  -> Evidence Extraction
  -> Evidence Role Routing
  -> Mechanism Hypothesis
  -> Candidate Recall
  -> Graph Navigation
  -> Patch Closure Verification
  -> Final Localization + Reasoning Trace
```

### 3.2 Stage 1：Evidence Extraction

把 issue 中的多源信息抽成 evidence cards。

```json
{
  "evidence_id": "url_1",
  "type": "github_blob",
  "raw": "https://github.com/Automattic/wp-calypso/blob/master/client/state/current-user/selectors.js#L157",
  "parsed": {
    "repo": "Automattic/wp-calypso",
    "path": "client/state/current-user/selectors.js",
    "line": 157,
    "symbol_hint": "isCurrentUserEmailVerified"
  }
}
```

图片 evidence card：

```json
{
  "evidence_id": "image_1",
  "type": "image",
  "image_kind": "web_ui_screenshot",
  "symptom": "signup flow requires email verification before wp-admin",
  "visible_entities": ["store signup", "email verification", "wp-admin"]
}
```

这个阶段要做：

- URL 抽取；
- URL host/type 分类；
- GitHub blob 解析；
- GitHub issue/PR 摘要；
- playground 参数解析；
- docs/API 摘要；
- 图片类型和症状摘要；
- issue 关键词和复现行为抽取。

### 3.3 Stage 2：Evidence Role Routing

每个 evidence card 必须判断角色。

| 角色 | 含义 | 处理 |
|---|---|---|
| `direct_patch_target` | 证据直接指向 gold 候选 | 高权重 seed |
| `evidence_only_code` | 指向相关代码但非修复点 | 作为入口，但必须扩展 |
| `reproduction` | 复现页面/示例/playground | 解析输入、配置、route、API |
| `docs_api` | 文档/API/规范 | 抽取概念和行为规则 |
| `history_patch` | issue/PR/commit/讨论 | 抽取旧文件、设计意图、diff |
| `weak_context` | 弱网页或泛链接 | 降权，只补充语义 |

这是我们相对现有 Agent 的关键改进。

例如 `Automattic__wp-calypso-21409`：

```text
current-user/selectors.js#L157
  role = evidence_only_code
  not direct_patch_target
```

否则 Agent 会把 selector 当答案，导致偏移。

### 3.4 Stage 3：Mechanism Hypothesis

把 issue 证据转成机制假设。

| 证据 | 机制假设 |
|---|---|
| UI 截图 + route URL | route/component/state/action flow |
| PDF layout diff | stylesheet expansion / resolve / layout engine |
| Chart.js 图表异常 | scale/plugin/event/lifecycle/draw pipeline |
| WebGL 图形异常 | renderer/context/texture/blend/shader |
| Python API 文档 | public API / type rule / parameter flow |
| Java code URL | public API / internal delegate / override |
| dependency/license issue | package/use-site/replacement/lockfile/docs |

机制假设不是最终答案，而是决定下一步用什么图查询动作。

### 3.5 Stage 4：Candidate Recall

候选召回应组合多路来源：

```text
BM25 lexical retrieval
Dense retrieval
URL direct path seed
Symbol seed
Image mechanism seed
Playground API/config seed
Docs/API concept seed
Historical PR/diff seed
```

BM25-MMIR 在我们的结果中仍然有价值：SWE Clean15 中 BM25 File REC@All 为 45.41，说明词法召回可以作为第一阶段。但它的 PRE@All 很低，所以不能直接当最终定位器。

### 3.6 Stage 5：Graph Navigation

Agent 不应该自由搜索，而应该使用 typed graph actions。

#### 通用动作

```text
find_definition(symbol)
find_references(symbol)
find_neighbors(entity, edge_types)
find_tests(entity)
find_configs(entity)
```

#### 前端动作

```text
find_route_components(route)
find_component_state(component)
find_selector_users(selector)
find_action_reducers(action)
find_style_files(component)
```

#### Python 动作

```text
trace_parameter_flow(symbol, parameter)
find_callers(function)
find_callees(function)
find_type_rule_neighbors(symbol)
find_exception_flow(error)
```

#### Java 动作

```text
find_implementations(interface)
find_overrides(method)
find_delegate_chain(public_api)
find_resource_lifecycle(symbol)
```

#### 机制动作

```text
expand_style_pipeline(seed)
expand_chart_lifecycle(seed)
expand_webgl_resource_closure(seed)
expand_dependency_migration(seed)
expand_api_to_backend(seed)
```

### 3.7 Stage 6：Patch Closure Verification

这是最关键的一步。Verifier 检查候选是否覆盖了机制闭包。

示例一：`react-pdf-1178`

```text
reasoning says:
  margin:auto -> expand.js -> resolve/castFloat

verifier checks:
  expand.js in candidates? yes
  resolve.js in candidates? no
  => ask Agent to add/inspect resolve.js
```

示例二：`wp-calypso-21409`

```text
reasoning says:
  email verification selector -> store signup flow -> WooCommerce dashboard/address setup

verifier checks:
  current-user selector only? not enough
  dashboard/store-location/address/countries/settings files covered? no
  => expand WooCommerce setup closure
```

Verifier 类型：

| 机制 | closure 检查 |
|---|---|
| UI flow | route、component、state、action、style 是否齐 |
| Style pipeline | expand、resolve、layout input 是否齐 |
| Plugin lifecycle | affected plugin、controller、lifecycle/cache 是否齐 |
| Dependency migration | package、lockfile、use sites、replacement abstraction、docs/credits 是否齐 |
| API parameter flow | public API、internal object、backend dispatch、format serializer 是否齐 |

## 4. 和别人方案的对比

| 方法 | 强项 | 对我们不足 | 我们怎么补 |
|---|---|---|---|
| SWE-agent | ACI 工具设计、交互修复 | 没有多模态证据路由和仓库语义图 | 设计 evidence/graph/closure 工具 |
| OpenHands | 平台、沙箱、浏览器、事件流 | 平台通用，不决定定位策略 | 借鉴 browser/event trace，补 evidence router |
| AutoCodeRover | 软件工程搜索与验证 | 图片/URL/多语言资源不是核心 | 加 mechanism router 和 typed graph |
| Agentless | 分阶段、可控、低成本 | 多模态和多语言边不足 | 用阶段化框架组织我们的 pipeline |
| Aider RepoMap | repo map、tree-sitter、结构摘要 | 主要是静态符号，不处理 evidence/closure | repo map 作为 orientation，图查询按 evidence 驱动 |
| RepoGraph | 仓库图插件、子图检索 | seed 错会错扩展；缺证据角色 | evidence-aware subgraph retrieval |
| LocAgent/CoSIL | 图引导定位 | 多语言/多模态/非函数资源边不足 | 扩展 typed edges 和 verifier |

## 5. 我们的具体 Agent 设计

### 5.1 Agent 不应该只有一个自由 LLM

建议拆成 5 个可控模块：

```text
Evidence Agent
  负责解析 issue 图片、URL、文档、复现信息

Mechanism Agent
  负责把证据转成机制假设

Navigation Agent
  负责调用 graph tools 进行局部导航

Rerank Agent
  负责根据证据和图路径排序候选

Verifier Agent
  负责检查 patch closure 和 evidence-target mismatch
```

这不一定要实现成 5 个进程，也可以是一个 LLM + 5 个固定阶段。重点是阶段职责要固定，不能让 LLM 每次自由发挥。

### 5.2 Agent 状态

Agent 每轮都维护结构化状态：

```json
{
  "evidence_cards": [],
  "mechanism_hypotheses": [],
  "seed_entities": [],
  "visited_entities": [],
  "candidate_files": [],
  "candidate_entities": [],
  "closure_requirements": [],
  "missing_closure": [],
  "decision_log": []
}
```

这样可以避免轨迹只是一堆自然语言，后续无法评估。

### 5.3 工具接口

建议工具接口：

```text
parse_issue_evidence(issue_id)
classify_evidence_role(evidence_id)
generate_mechanism_hypotheses(evidence_ids)
search_candidates(query, filters)
query_repo_graph(seed, edge_types, depth)
trace_flow(seed, flow_type)
expand_patch_closure(seed, mechanism_type)
verify_candidates(candidates, evidence_cards, mechanism_hypotheses)
export_reasoning_trace()
```

### 5.4 推理轨迹格式

每个样本输出机器可读 trace：

```json
{
  "instance_id": "diegomura__react-pdf-1178",
  "evidence": [
    {
      "type": "github_blob",
      "role": "reproduction",
      "path": "packages/examples/src/knobs/index.js"
    },
    {
      "type": "image",
      "role": "visual_layout_symptom",
      "symptom": "margin auto layout difference"
    }
  ],
  "mechanism": [
    "style expansion",
    "style resolve"
  ],
  "graph_paths": [
    [
      "packages/examples/src/knobs/index.js",
      "uses_style_property: margin",
      "packages/stylesheet/src/expand.js",
      "flows_to",
      "packages/stylesheet/src/resolve.js"
    ]
  ],
  "final_candidates": [
    "packages/stylesheet/src/expand.js",
    "packages/stylesheet/src/resolve.js"
  ],
  "closure_check": {
    "required": ["expand", "resolve"],
    "covered": ["expand", "resolve"],
    "missing": []
  }
}
```

这个 trace 可以直接用于论文案例展示。

## 6. 和我们的失败案例如何对应

### 6.1 `Automattic__wp-calypso-21409`

现有失败：

```text
URL 指向 current-user selector
baseline 把 selector 当核心 target
真实 patch 在 WooCommerce dashboard/address/settings closure
```

我们的 Agent：

```text
classify URL as evidence_only_code
mechanism = UI signup flow + email verification state
graph action:
  find_selector_users(isCurrentUserEmailVerified)
  find_route_components(store signup/dashboard)
  expand_ui_flow_closure(WooCommerce onboarding)
verifier:
  check dashboard/address/countries/settings closure
```

### 6.2 `diegomura__react-pdf-1178`

现有失败：

```text
Mimo reasoning 正确，但 final candidates 漏 resolve.js
```

我们的 Agent：

```text
image symptom -> layout/style pipeline
URL example -> reproduction, not target
graph action:
  expand_style_pipeline(margin:auto)
verifier:
  expand.js + resolve.js 必须同时覆盖
```

### 6.3 `chartjs__Chart.js-8162`

现有失败：

```text
定位到 legend/title 表象组件
真实修复在 core.plugins.js::invalidate
```

我们的 Agent：

```text
image symptom -> duplicated plugin rendering
mechanism hypothesis -> plugin lifecycle/cache invalidation
graph action:
  affected component legend/title
  find plugin lifecycle controller
  find invalidation/cache functions
```

### 6.4 `pyca__cryptography-7520`

现有失败：

```text
BM25 能命中部分文件
LocAgent/CoSIL 不完整
缺 public API -> backend serializer 参数传递闭包
```

我们的 Agent：

```text
URL/issue concept -> kdf_rounds parameter
mechanism -> public API parameter flow
graph action:
  trace_argument_flow(kdf_rounds)
  expand_api_to_backend(BestAvailableEncryption)
verifier:
  public interface + backend dispatch + ssh serializer 是否齐
```

### 6.5 `python__mypy-13481`

现有失败：

```text
playground URL 给复现
真实问题在 binder deleted variable state
普通 call graph 不够
```

我们的 Agent：

```text
playground resolver -> code snippet: del Foo; print(Foo)
mechanism -> name binding / deleted variable state
graph action:
  find semantic analysis entry
  find binder state operations
  find read/delete variable handling
```

## 7. 工程实现规划

### P0：先加证据层

实现：

```text
scripts/agent_nav/extract_evidence.py
scripts/agent_nav/classify_url_role.py
scripts/agent_nav/parse_github_url.py
scripts/agent_nav/parse_playground_url.py
scripts/agent_nav/summarize_image_evidence.py
```

输出：

```text
evidence_cards/<benchmark>/<instance_id>.json
```

### P1：加轻量 repo graph 查询

实现：

```text
scripts/agent_nav/build_semantic_repo_graph.py
scripts/agent_nav/query_repo_graph.py
scripts/agent_nav/extract_js_ts_edges.py
scripts/agent_nav/extract_python_edges.py
scripts/agent_nav/extract_java_edges.py
scripts/agent_nav/extract_resource_edges.py
```

输出：

```text
semantic_repo_graphs/<benchmark>/<instance_id>/nodes.jsonl
semantic_repo_graphs/<benchmark>/<instance_id>/edges.jsonl
```

### P2：加机制 router

实现：

```text
scripts/agent_nav/mechanism_router.py
scripts/agent_nav/ui_flow_router.py
scripts/agent_nav/style_pipeline_router.py
scripts/agent_nav/chart_lifecycle_router.py
scripts/agent_nav/webgl_router.py
scripts/agent_nav/api_parameter_flow_router.py
```

### P3：加 closure verifier

实现：

```text
scripts/agent_nav/verify_patch_closure.py
scripts/agent_nav/export_reasoning_trace.py
```

指标：

```text
file/module/function Acc@K
REC/PRE/F1
closure_recall
evidence_target_mismatch rate
missing_closure count
```

### P4：接入 baseline

可以先不改所有 baseline，只做外置 rerank/verify：

```text
已有 baseline loc_results
  -> evidence cards
  -> graph expansion
  -> closure verifier
  -> reranked/augmented loc_results
  -> clean15 reevaluation
```

这样不需要重跑所有大模型。

## 8. 论文叙事

可以这样讲：

1. 现有软件工程 Agent 主要通过工具接口、仓库搜索、repo map 或 repo graph 导航代码。
2. 这些方法在 SWE-bench 类纯文本 issue 上有效，但在多模态、多语言 issue localization 中暴露出系统性不足。
3. 我们的 benchmark 分析显示：图片和 URL 常常是 evidence，不是 patch target；修复点需要通过机制关系和多语言语义边才能到达。
4. 因此提出 Evidence-Routed Graph-Navigating Agent：
   - 先把图片/URL/文档/复现解析成 evidence cards；
   - 再判断 evidence role；
   - 再生成机制假设；
   - 再用多语言仓库图导航；
   - 最后用 patch closure verifier 检查完整性。

英文摘要式表述：

```text
Existing software engineering agents mainly rely on interactive tools, repository search, or static repository maps to navigate codebases.
However, our analysis of SWE-bench Multimodal and OmniGIRL shows that multimodal issue localization requires a different control loop.
Images and URLs often act as evidence rather than direct patch targets, and their useful information must be translated into code mechanisms such as UI state flow, layout pipelines, plugin lifecycles, API parameter propagation, and dependency migration closures.
We therefore propose an Evidence-Routed Graph-Navigating Agent.
The agent first converts issue evidence into typed evidence cards, routes each evidence item according to its role, maps evidence to mechanism hypotheses, navigates a multilingual semantic repository graph through typed actions, and verifies patch closure before producing final localization results.
```

## 9. 参考资料

- SWE-agent paper: <https://proceedings.neurips.cc/paper_files/paper/2024/file/5a7c947568c1b1328ccc5230172e1e7c-Paper-Conference.pdf>
- SWE-agent OpenReview: <https://openreview.net/forum?id=mXpq6ut8J3>
- SWE-agent GitHub: <https://github.com/swe-agent/swe-agent>
- OpenHands paper: <https://proceedings.iclr.cc/paper_files/paper/2025/file/a4b6ad6b48850c0c331d1259fc66a69c-Paper-Conference.pdf>
- OpenHands SDK: <https://arxiv.org/html/2511.03690v1>
- OpenHands GitHub: <https://github.com/OpenHands/openhands>
- AutoCodeRover paper: <https://arxiv.org/html/2404.05427v3>
- AutoCodeRover GitHub: <https://github.com/AutoCodeRoverSG/auto-code-rover>
- Agentless paper: <https://arxiv.org/abs/2407.01489>
- Agentless GitHub: <https://github.com/openautocoder/agentless>
- Aider repo map: <https://aider.chat/2023/10/22/repomap.html>
- Aider repo map docs: <https://aider.chat/docs/repomap.html>
- RepoGraph paper: <https://arxiv.org/html/2410.14684v1>
- RepoGraph ICLR PDF: <https://proceedings.iclr.cc/paper_files/paper/2025/file/4a4a3c197deac042461c677219efd36c-Paper-Conference.pdf>
- LocAgent paper: <https://arxiv.org/html/2503.09089v1>
- LocAgent ACL PDF: <https://aclanthology.org/2025.acl-long.426.pdf>
