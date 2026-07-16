# 多模态 URL 证据处理与跨语言 Agent 构图方案

本文整理我们前面对 SWE-bench Multimodal、OmniGIRL、Clean15 结果和失败轨迹的分析，并结合 OpenHands-Versa、SWE-bench Multimodal、OmniGIRL、CoSIL 等相关工作，形成一个更清晰的研究叙事：

> 多模态 Issue 定位的关键不是“把图片和 URL 塞给模型”，而是把图片、网页 URL、代码 URL、复现页面、文档链接和跨语言代码结构统一转成可检索、可验证、可迭代扩展的证据图。当前 baseline 的核心不足，是没有稳定区分“证据入口”和“真实修改目标”，也没有让 Agent 在多语言仓库里用语言感知的图关系约束搜索。

## 1. 相关工作给我们的启发

### 1.1 OpenHands-Versa：通用工具集，而不是任务专用规则

OpenHands-Versa 的核心主张是：不要为每个 benchmark 设计高度特化的 agent，而是给单个 agent 配备少量高价值通用工具，包括代码编辑与执行、Web search、多模态 Web browser、多模态文件访问。论文报告它在 SWE-bench Multimodal、GAIA、The Agent Company 上都取得强结果，并强调其优势来自更好的信息访问和多模态浏览能力。

对我们最有价值的是三点：

1. **Web search 先于浏览**：OpenHands-Versa 不直接猜 URL，而是先用 search API 找候选链接，再基于 snippets 选择目标 URL。这能减少无效 URL 和错误导航。
2. **多模态浏览用于视觉验证**：在 SWE-bench Multimodal 上，它更频繁使用浏览器观察前端页面和截图，用视觉反馈确认修改是否正确。
3. **错误仍然集中在验证不足**：论文也指出 SWE-bench Multimodal 上经常失败于没有构造充分测试、没有按复现步骤验证、过早认为修复正确。

这说明 OpenHands-Versa 解决的是“Agent 能访问网页和图片”的底座问题，但还没有完全解决我们关心的定位问题：**URL 是 evidence seed 还是 patch target？图片如何转成仓库中的 route/component/function 约束？多语言仓库如何构图？**

### 1.2 SWE-bench Multimodal：图片确实有用，但会增加搜索复杂度

SWE-bench Multimodal 论文的核心结论是：视觉信息对前端、图表、PDF、Canvas、UI bug 很重要；去掉图片会降低系统表现，尤其是非文本视觉元素更明显。但论文同时指出，多模态工具会增加 Agent 复杂度，例如需要构建网页、截图、对比视觉输出，成本和失败模式都会增加。

这和我们的 Clean15 分析一致：

- SWE Clean15 几乎全部有图片，很多样本是视觉症状主导。
- 但 baseline 经常只把图片 URL 当字符串，不会把视觉内容转成“图例高度、hitbox、布局断行、颜色、位置、route、component”这些代码约束。
- 即使 LocAgent 能找到文件，function Acc 仍然低，说明视觉证据没有有效落到函数级实体。

### 1.3 OmniGIRL：多语言、多模态、多领域，但 URL 比图片更关键

OmniGIRL 是 GitHub issue resolution benchmark，特点是 multilingual、multimodal、multi-domain。我们在 `014_Clean15样本图片URL证据类型与多模态定位处理方案.md` 中统计过：Omni full-candidates Clean15 中绝大多数样本是 URL 主导，图片很少。

这意味着 Omni 和 SWE 的多模态重点不同：

| Benchmark | 主模态 | 主要难点 |
|---|---|---|
| SWE-bench Multimodal | 图片 + 部分 URL | 视觉症状到前端代码实体的映射 |
| OmniGIRL | URL + issue 文本 | URL 角色识别、外部文档/PR/代码链接到跨语言仓库实体的映射 |

所以我们的框架不能只做“图像 caption”，也不能只做“打开 URL”。必须同时处理：

- GitHub blob URL 指向的代码 path/line/symbol；
- GitHub issue/PR/commit 中的历史补丁和讨论；
- playground/REPL URL 中编码的复现代码和配置；
- docs/API URL 中的概念、参数、异常行为；
- 图片中的 UI 现象、报错文本、视觉 layout 差异。

### 1.4 CoSIL 和现有图定位方法：图有用，但跨语言和多模态证据入口不足

CoSIL 使用 LLM 动态构造函数调用图，并在图上迭代搜索、剪枝上下文。它证明了“图搜索 + LLM 选择”对函数级定位有价值。但在我们自己的运行中，CoSIL 在多语言、多模态数据上存在几个明显问题：

- 对图片和 URL 的结构化使用不足；
- 对跨语言实体边界不稳定，尤其是 JS/TS、Java、Python、CSS/MDX/JSON 混合仓库；
- 动态构图依赖 LLM 推断，容易漏掉真实调用边、类型边、配置边、路由边；
- file-level 有一定能力，function-level 掉得很明显。

因此，我们需要的是 **多语言静态/轻动态混合图 + 多模态证据路由 + Agent 搜索闭环**，而不是单一调用图。

## 2. 我们数据中的核心现象

### 2.1 URL 不是答案，而是证据入口

Clean15 统计显示，SWE 和 Omni 里很多 URL 并不直接指向真实 gold 文件。它们通常扮演这些角色：

| URL 角色 | 含义 | 例子 | 正确处理方式 |
|---|---|---|---|
| `patch-target` | URL 直接指向真实修改文件/函数 | GitHub blob URL 命中 gold 文件 | 高权重加入候选，并扩展邻近函数/测试 |
| `evidence-only` | URL 指向相关代码，但不是 patch target | `current-user/selectors.js#L157` 只是状态 selector | 降权作为 evidence seed，沿调用/引用/状态流扩展 |
| `reproduction-entry` | URL 指向复现页面/playground | Prettier playground、Tailwind play | 解析输入代码、配置、parser、版本 |
| `expected-behavior-doc` | URL 指向规范/API/文档 | Python docs、W3C、mypy docs | 抽取 API 名、参数、行为规则 |
| `historical-context` | URL 指向 issue/PR/commit | GitHub issue/PR/compare | 抽取文件提及、旧 patch、review comment |
| `weak-context` | URL 只提供弱背景 | 产品页、IssueHunt、头像/徽章 | 低权重，只抽 title/关键词 |

当前 baseline 的典型错误是：把 `evidence-only` 当成 `patch-target`。例如 `Automattic__wp-calypso-21409` 中，URL 指向 `isCurrentUserEmailVerified` selector，但真实 patch 在 WooCommerce dashboard/address flow。LocAgent、CoSIL、GraphLocator、GALA 都被 selector 或 signup 路径牵引，漏掉真实业务链路。

### 2.2 图片不是 caption，而是可验证的视觉约束

图片中包含的信息大致分为：

| 图片内容 | 可提取证据 | 对定位的作用 |
|---|---|---|
| UI 页面截图 | 页面区域、按钮、文案、弹窗、空白、错位 | route/component/state 搜索 |
| 图表/Canvas/SVG | 坐标、legend、tooltip、hitbox、颜色、文字位置 | rendering/layout/math function 搜索 |
| PDF/排版截图 | pagination、line break、font、page layout | layout engine / renderer 函数搜索 |
| 报错截图 | error text、stack frame、环境信息 | symbol/API 搜索 |
| playground 截图 | 输入输出差异、配置项、parser | resolver + function verifier |

只做图片 caption 不够，因为 caption 常常只会说“图例显示不正确”“按钮位置错误”。真正用于定位的是结构化视觉约束：

```text
legend item wraps into two lines
-> hitbox height is too small
-> search functions: calculateItemHeight, draw legend, fit legend, hitbox
```

这就是为什么 Chart.js、p5.js、react-pdf 这类样本容易 file hit 但 function miss：模型能看懂大概文件区域，却没有把视觉症状转成函数级机制。

### 2.3 多语言不是换 parser，而是换图关系

Omni 的失败样本说明，跨语言定位不能只统一成“文件 + 函数”两级。不同语言里的关键边不同：

| 语言/生态 | 关键实体 | 关键边 |
|---|---|---|
| JavaScript/TypeScript 前端 | route、component、hook、selector、reducer、utility、test | import/export、JSX component use、state selector use、route mapping、config/plugin |
| Python | module、class、function、type rule、decorator、test | import、call、inheritance、type flow、exception flow、fixture |
| Java | package、class、interface、method、override、generic type | call、override/implements、inheritance、constructor、test target |
| CSS/SCSS/MDX/JSON/YAML | style rule、docs block、config key | selector-to-component、config-to-plugin、doc-to-export |

所以我们的图应该是 `typed heterogeneous repository graph`，不是单一 call graph。

## 3. OpenHands-Versa 对 URL 和多模态处理的可借鉴点

OpenHands-Versa 的设计可以抽象成：

```text
General tools
  -> search engine
  -> multimodal browser
  -> multimodal file viewer
  -> code execution/editing
  -> iterative verification
```

它没有为 SWE-bench Multimodal 写复杂的 benchmark-specific localization pipeline，而是依赖通用工具让 Agent 自己完成搜索、浏览、运行和验证。这一点适合作为我们论文里的对比：

| 维度 | OpenHands-Versa | 我们需要补充的定位范式 |
|---|---|---|
| URL 获取 | Search API 找链接，再浏览 | URL role classifier：判断 URL 是 target/evidence/doc/repro/history |
| 页面处理 | 多模态浏览器截图 + AXTree/页面观察 | 将页面元素转成 route/component/state/search query |
| 图片处理 | 多模态文件/网页观察 | 视觉症状结构化：layout、hitbox、render、text、state |
| 代码处理 | 编辑、执行、测试 | 语言感知 repo graph + entity rerank |
| 验证 | 运行测试/视觉检查 | localization verifier：检查 evidence path 是否能解释 gold-like failure |
| 泛化目标 | 一个 agent 适配多任务 | 一个定位框架适配多模态、多语言、多仓库结构 |

换句话说，OpenHands-Versa 证明了“多模态浏览 + 搜索 + 执行”是必要基础；我们的创新应放在更细的定位层：**把多模态和 URL 输入变成结构化证据图，并让 Agent 基于证据图做跨语言实体搜索和验证。**

## 4. 建议框架：Evidence-Routed Multilingual Agent Localization

### 4.1 总体流程

```text
Issue text + images + URLs
        |
        v
Evidence Ingestion
  - URL parser
  - image analyzer
  - issue text parser
  - stack/error parser
        |
        v
Evidence Role Router
  - patch-target
  - evidence-only
  - reproduction-entry
  - expected-behavior-doc
  - historical-context
  - weak-context
        |
        v
Mechanism Translator
  - UI symptom -> component/state/layout/rendering mechanism
  - doc/API -> API behavior and constraints
  - playground -> input/config/parser/output delta
  - code URL -> symbol/path/line evidence
        |
        v
Multilingual Repository Graph
  - file/function/class/module graph
  - import/export/call/inheritance/type/config/route/style/test edges
        |
        v
Agent Search Policy
  - choose search tool by evidence role and language
  - expand graph from seeds
  - rerank entities
  - verify patch closure
        |
        v
Top-k file/module/function localization
```

### 4.2 Evidence Ingestion：先把输入拆成证据

输入不应直接送给 LLM 做一次性推理，而要拆成结构化证据：

```json
{
  "evidence_id": "url_1",
  "source": "issue_url",
  "type": "github_blob",
  "repo": "Automattic/wp-calypso",
  "path": "client/state/current-user/selectors.js",
  "line": 157,
  "symbol": "isCurrentUserEmailVerified",
  "role_guess": "evidence-only",
  "confidence": 0.78
}
```

图片也类似：

```json
{
  "evidence_id": "image_1",
  "source": "issue_image",
  "type": "ui_screenshot",
  "visual_claims": [
    "user is redirected to wp-admin before email verification",
    "verification prompt should block setup flow"
  ],
  "mechanism_hints": ["route_guard", "signup_flow", "state_selector", "dashboard_redirect"]
}
```

这样 Agent 后续搜索时不会把所有输入混成一段长文本。

### 4.3 URL Role Router：避免被 URL 误导

URL 处理的关键是分类：

1. 如果是 GitHub blob URL：
   - 解析 repo/path/line；
   - 查 line 所在 symbol；
   - 判断该 path 是否直接是候选 patch target；
   - 如果 issue 文本只是“参考这个 selector/API”，则标为 evidence-only；
   - 从该 symbol 出发查 references/import/use edges。

2. 如果是 GitHub issue/PR/commit：
   - 抽取被提到的文件路径、函数名、commit diff、review comment；
   - 历史 patch 不能直接当 gold，但可作为 high-value candidate。

3. 如果是 playground/REPL：
   - 解析 URL hash/query；
   - 抽取代码片段、配置、parser、版本；
   - 搜索对应 parser/printer/plugin/transformer。

4. 如果是 docs/API：
   - 抽取 API 名、参数、异常条件；
   - 搜索仓库中 API usage 和 wrapper。

5. 如果是外部弱网页：
   - 只抽 title 和关键词；
   - 降权，避免污染 top-k。

### 4.4 Image Mechanism Translator：从视觉现象到代码机制

图片分析不能停在自然语言描述，而要输出可搜索机制：

| 视觉现象 | 机制标签 | 搜索入口 |
|---|---|---|
| legend 文本换行后点击区域错误 | `layout.hitbox.legend` | `calculateItemHeight`, `fit`, `draw`, `handleEvent` |
| PDF 分页断行错误 | `layout.pagination.text` | `shouldBreak`, `splitText`, `wrap`, `height` |
| Canvas/WebGL 图形错位 | `render.coordinate.transform` | `vertex`, `matrix`, `scale`, `draw` |
| 按钮显示但状态不对 | `state.selector.route_guard` | selector、reducer、component、route |
| playground 输出格式不对 | `printer.ast.formatting` | printer、comments、doc builder |

这一步是 function-level 提升的核心。否则模型只知道“图不对”，不知道应该找 hitbox、layout、parser、printer 还是 state flow。

### 4.5 Multilingual Repository Graph：语言感知异构图

建议构建统一 schema，但每种语言有自己的 edge extractor：

```text
Node:
  File
  Module
  Class
  Function/Method
  Route
  Component
  ConfigKey
  Test
  StyleSelector
  DocSection

Edge:
  imports
  exports
  calls
  references
  inherits
  implements
  overrides
  routes_to
  renders
  selects_state
  dispatches_action
  configures
  tests
  styles
  documents
```

多语言适配不是强求所有语言都有同样的边，而是把不同语言的关键关系归一到同一套 typed edges：

- Java 的 `implements/overrides` 对应“动态分派候选扩展”；
- Python 的 `import/type_flow/decorator` 对应“运行时行为和类型规则扩展”；
- JS/TS 的 `component/render/selector/reducer/route` 对应“前端状态和页面入口扩展”；
- CSS/MDX/JSON 的 `styles/configures/documents` 对应“非函数 patch closure 扩展”。

### 4.6 Agent Search Policy：让 LLM 决策，但动作必须受约束

Agent 每一步不应自由调用 `search_code_snippets(any string)`，而应输出结构化动作：

```json
{
  "goal": "verify whether email verification selector affects WooCommerce setup flow",
  "evidence": ["url_1", "image_1"],
  "language": "javascript",
  "search_space": ["references", "route", "component", "state"],
  "query": ["isCurrentUserEmailVerified", "woocommerce", "dashboard", "store location"],
  "expected_findings": ["component using selector", "redirect guard", "setup flow route"]
}
```

搜索工具返回后，Agent 必须记录：

- 命中的证据是什么；
- 是否解释了 issue symptom；
- 是否只是相关入口而非 patch target；
- 下一步应该扩展哪类边。

这可以直接减少我们日志里看到的 `search empty terms`、`evidence URL 误导`、`file hit but function miss`。

## 5. 结合典型失败样本的设计动机

### 5.1 `Automattic__wp-calypso-21409`：代码 URL 是 evidence-only

Issue 给出 `isCurrentUserEmailVerified` selector 的 GitHub URL，但 gold patch 在 WooCommerce dashboard/address flow。当前 baseline 把 selector 当 target，因此预测偏到 current-user 或 signup 目录。

正确流程应该是：

```text
code URL -> selector evidence
image/text -> email verification should block wp-admin/dashboard flow
selector references -> signup/dashboard/woocommerce setup components
route/state graph -> address setup/store location/settings actions
patch closure -> dashboard + address + settings files
```

这里的创新点是 URL role router：先判断 `selectors.js#L157` 是状态来源，而不是最终修改位置。

### 5.2 Chart.js legend/hitbox 类样本：图片必须转成视觉机制

Chart.js 多个样本的 gold function 是 `handleEvent`、`calculateItemHeight`、`calculateItemWidth`、`_draw` 等，但 baseline 经常只定位到 legend 文件或相邻函数。

正确流程应该是：

```text
image -> legend wraps / hitbox wrong / click event mismatch
mechanism -> layout.hitbox.legend + event.dispatch
graph -> plugin.legend.js functions around fit/draw/handleEvent
verifier -> predicted functions must explain both rendering and interaction
```

这里的创新点是 Image Mechanism Translator：从视觉症状到函数族，而不是从图片到 caption。

### 5.3 Prettier/Tailwind playground 样本：URL hash 是结构化复现数据

Omni 中很多 Prettier/Tailwind 样本 URL 指向 playground。当前 baseline 常把 URL 当普通文本，或者只搜框架名，导致命中 website/playground 或 integration 目录，而不是 printer/parser/core 文件。

正确流程应该是：

```text
playground URL -> decode input code + parser + options + expected output delta
language router -> JS/TS formatter pipeline
repo graph -> parser/printer/comment/doc builder
candidate verifier -> predicted function must transform this AST/output
```

这里的创新点是 Playground Resolver：把 URL 解析成可运行/可搜索的最小复现。

### 5.4 Python/Java 样本：文档和代码 URL 要进入语言特定图

Omni 中 Python/Java 样本经常包含 docs 或 GitHub blob URL。比如 mypy 失败样本里，issue 线索常指向类型规则，但真实修改在 `binder.py`、`checker.py`、`nodes.py` 等内部模块。Java 样本里，URL 常指向类或方法，但真实修复可能在 generic base class、override method 或测试邻域。

正确流程应该是：

```text
docs/API URL -> API behavior rule
language router -> Python type flow / Java inheritance and override graph
symbol search -> class/method candidates
graph expansion -> callers/callees/tests/subclasses
verifier -> predicted method must explain issue behavior
```

这里的创新点是 Multilingual Typed Graph：不同语言用不同边，但统一到一个 evidence-guided search schema。

## 6. 最终方法故事

可以把论文动机写成三层递进：

### 6.1 现象

Clean15 后，baseline 不再被 `gold > 15` 和不可映射实体天然限制，但 function-level 仍然明显低。说明问题不是评估不公平，而是定位系统没有把多模态、多 URL、多语言证据转成函数级搜索约束。

### 6.2 原因

当前方法普遍存在三类错误：

1. **证据角色混淆**：把 URL 指向的 evidence file 当成 patch target。
2. **模态机制缺失**：图片只被 caption，没有转成 layout/render/state/parser 等机制。
3. **语言图关系不足**：统一文本搜索或单一调用图不能覆盖 JS/TS、Python、Java、CSS/JSON/MDX 的真实 patch closure。

### 6.3 方案

提出 Evidence-Routed Multilingual Agent Localization：

- URL/Image/Text 先进入 evidence graph；
- evidence role router 判断证据角色；
- mechanism translator 把视觉和 URL 内容转成代码机制；
- multilingual repository graph 提供语言感知扩展；
- Agent 每一步搜索都有 evidence、language、edge type、expected finding；
- 最后用 verifier 检查候选是否能解释 symptom 和 patch closure。

## 7. 实现路线

### 7.1 第一阶段：离线证据抽取和统计

目标是先不改 baseline，只生成 evidence JSON：

```text
samples.jsonl
  -> evidence/*.json
  -> url_roles.csv
  -> image_claims.csv
  -> language_router.csv
```

包括：

- URL host/path/type/role；
- GitHub blob path/line/symbol；
- playground decoded config/input；
- docs/API entity；
- image caption + structured mechanism tags；
- issue text 中的 file/function/API/error。

### 7.2 第二阶段：多语言 repo graph

先覆盖高价值边：

- JS/TS：import/export、component use、selector/action/reducer、route、test；
- Python：import、class/function、call、decorator、test、type-related names；
- Java：package/class/method、inheritance、implements、override、call/test；
- 配置/样式/文档：config key、style selector、docs mention。

输出统一 graph：

```text
repo_graph.jsonl
entity_index.jsonl
edge_index.jsonl
```

### 7.3 第三阶段：Agent 约束搜索

改造 LocAgent 的 search tool：

- 输入必须包含 evidence id、语言、edge type；
- 禁止空 search terms；
- 支持从 URL/code symbol 扩展 references；
- 支持从 image mechanism 扩展候选函数族；
- 支持候选解释评分。

### 7.4 第四阶段：Clean15 + 全集复评估

先用已有定位结果做 rerank/post-process，不重新跑所有 baseline：

- 对已有 top-k 预测做 evidence-aware rerank；
- 用 clean15 过滤后的样本复评估；
- 比较 file/module/function Acc@1/3/5/8/10/12/13/15、MRR@15、MAP@15。

## 8. 参考资料

- OpenHands-Versa paper: https://arxiv.org/abs/2506.03011
- OpenHands-Versa repository: https://github.com/adityasoni9998/OpenHands-Versa
- OpenHands blog on Versa: https://www.openhands.dev/blog/building-a-provably-versatile-agent
- SWE-bench Multimodal paper: https://arxiv.org/abs/2410.03859
- SWE-bench Multimodal overview: https://www.swebench.com/multimodal.html
- OmniGIRL paper entry: https://dl.acm.org/doi/abs/10.1145/3728871
- CoSIL paper: https://arxiv.org/abs/2503.22424
- OpenHands paper: https://arxiv.org/abs/2407.16741
