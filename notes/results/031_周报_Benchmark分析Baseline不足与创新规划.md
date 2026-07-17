# 周报：多模态 Benchmark 分析、Mimo-v2.5 Baseline 结果与方法规划

时间范围：2026 年 7 月中旬  
主题：SWE-bench Multimodal / OmniGIRL 的多模态证据分析、现有 baseline 定位不足、以及后续 Agent 框架设计

## 1. 本周核心进展

本周主要完成了三件事：

1. **重新梳理 benchmark 的多模态证据结构**  
   重点分析 issue 中的图片、网页 URL、GitHub 代码 URL、playground URL、文档 URL 与真实 gold patch 之间的关系。结论是：图片和 URL 不是附属信息，而是影响定位方向的关键证据；但它们经常不是 patch target 本身，而是 reproduction evidence、context evidence 或 mechanism evidence。

2. **整理 Mimo-v2.5 在 SWE-bench Multimodal 全量 Clean15 上的结果**  
   使用服务器跑完的 `mimo-v2.5` 结果，对 LocAgent、CoSIL、GraphLocator、GALA 和 BM25-MMIR 做了统一 Clean15 复评估。Clean15 保留 92/102 个样本，排除了 gold file/module/function 数超过 15 的样本，使 `Acc@15` 更公平。

3. **从典型失败案例中归纳方法缺口**  
   重点分析了 URL 误导、图片症状到代码机制映射失败、多文件 patch closure 不完整、函数级定位弱等问题。基于这些问题，形成了后续方案：把 issue 证据提取和仓库图建模分开，图作为 Agent 的辅助导航层，而不是让 LLM 直接在原始 issue 文本中盲搜。

## 2. Benchmark 的多模态证据到底是什么

### 2.1 SWE-bench Multimodal：图片主导，URL 辅助定位

SWE-bench Multimodal dev 全量有 102 个样本，主要来自 5 个前端/渲染相关仓库：

| 仓库 | 样本数 | 主要问题类型 |
|---|---:|---|
| Automattic/wp-calypso | 37 | Web UI、业务流程、状态管理、路由、表单 |
| chartjs/Chart.js | 24 | 图表渲染、Canvas 事件、legend/title/layout |
| diegomura/react-pdf | 11 | PDF 布局、样式解析、渲染差异 |
| markedjs/marked | 14 | Markdown 解析、文本渲染 |
| processing/p5.js | 16 | Canvas/WebGL、shader、图形 API |

Clean15 后保留 92 个样本。其多模态组合如下：

| 数据集 | Clean15 样本数 | 图片+网页URL | 仅图片 | 仅网页URL | 纯文本 |
|---|---:|---:|---:|---:|---:|
| SWE-bench Multimodal dev | 92 | 73 | 19 | 0 | 0 |

这说明 SWE-bench Multimodal 本质上是一个**图片主导的定位 benchmark**。所有 Clean15 样本都有图片，其中大多数还带 URL。图片通常展示 UI、图表、PDF、Canvas 或 Markdown 渲染现象；URL 则提供复现页面、代码入口、文档或 issue 讨论。

### 2.2 图片和定位的关系

图片不是直接告诉模型“改哪个文件”，而是给出**症状类型**。症状需要被翻译成代码机制：

| 图片类型 | 定位时真正需要识别的代码机制 |
|---|---|
| Web UI 页面截图 | route、component、state selector、reducer/action、表单字段、业务流程 |
| 图表/Canvas 截图 | scale、layout、plugin lifecycle、event propagation、drawing primitive |
| PDF/排版渲染截图 | stylesheet expansion、unit resolve、layout engine、border/background/text drawing |
| Markdown/文本渲染截图 | tokenizer、lexer/parser、renderer、HTML escaping、link/image 规则 |
| WebGL/图形截图 | renderer、context attributes、texture upload、blend function、shader/resource closure |

现有 baseline 的主要问题是：它们常常把图片描述停留在表象层。例如“legend 被画了两次”会被定位到 `plugin.legend.js` 或 `plugin.title.js`，但真实修复点可能是 plugin lifecycle 的 cache invalidation；“margin auto 渲染错误”会被定位到 example 或 layout setter，但真实修复点在 stylesheet `expand/resolve` 层。

### 2.3 URL 和定位的关系

Clean15 中 URL 的角色不是单一的：

| URL 角色 | SWE dev Clean15 样本数 | 含义 | 风险 |
|---|---:|---|---|
| 直接指向 gold 文件 | 5 | URL 指向真实需要修改的文件 | 有帮助，但仍可能漏多文件闭包 |
| 指向相关代码但非 gold 文件 | 3 | URL 是上下文入口，不是 patch target | 最容易误导 Agent |
| 历史讨论/补丁线索 | 6 | issue/PR/旧讨论中有设计或修改线索 | 需要抽取 diff、文件提及、设计意图 |
| 复现行为线索 | 17 | 产品页面、demo、CodeSandbox、官方示例 | 需要解析 route、API、配置、输入 |
| 弱网页线索 | 26 | 网页上下文弱，可能只是产品页面或泛链接 | 应降权，不能直接当定位目标 |
| 无 URL | 35 | 依赖图片和文本 | 需要更强视觉症状解析 |

关键结论：**URL 不等于答案。**  
很多 URL 只是 evidence seed。例如 `Automattic__wp-calypso-21409` 的 URL 指向 `current-user/selectors.js#L157`，它确实是 email verification 的状态入口，但真实 patch 在 WooCommerce dashboard/address/setup/settings 的 10 个文件里。如果 baseline 直接把 URL 文件当作目标，会从一开始就偏。

### 2.4 OmniGIRL：URL 主导，多语言更明显

OmniGIRL full-candidates Clean15 保留 445 条样本，其中 413 条是仅网页 URL，只有 32 条包含图片。这和 SWE 完全不同：Omni 的难点主要是**URL 证据解析 + 多语言代码结构导航**。

典型 URL 类型包括：

| URL 类型 | 典型来源 | 需要抽取的信息 |
|---|---|---|
| GitHub blob | `github.com/.../blob/...#Lx` | repo/path/line/symbol，判断是否 gold 或 evidence-only |
| GitHub issue/PR | issue、PR、review、commit | 旧补丁、设计讨论、文件提及、回归原因 |
| Playground/REPL | prettier、mypy-play、Babel、Tailwind | 输入代码、配置、版本、parser、复现 API |
| 文档/API | Python docs、mypy docs、W3C、TypeScript docs | API 语义、边界行为、类型规则 |
| 外部弱网页 | 产品页、博客、issue bounty 页面 | 只作为弱语义上下文，不能高权重定位 |

因此 Omni 的多模态处理不能只做“打开 URL + 摘要”。不同语言需要不同 resolver：

- JavaScript/TypeScript：解析 playground、route、component、formatter/transpiler 配置。
- Python：解析文档/API、类型规则、参数传播、异常行为。
- Java：解析类、方法、接口、override/implements、测试邻域。

## 3. Mimo-v2.5 在 SWE 全量 Clean15 上的 baseline 结果

实验口径：

- 数据集：`SWE-bench Multimodal full-dev`
- 原始样本数：102
- Clean15 保留样本数：92
- Clean15 定义：gold file/module/function 数量均在 1..15 内
- 模型：`mimo-v2.5`
- Baseline：LocAgent、CoSIL、GraphLocator、GALA、BM25-MMIR

### 3.1 总体结果

| Baseline | File REC@All | Module REC@All | Function REC@All | File Acc@15 | Function Acc@15 |
|---|---:|---:|---:|---:|---:|
| LocAgent | 59.77 | 67.79 | 52.38 | 42.39 | 21.74 |
| CoSIL | 43.35 | 37.19 | 18.89 | 26.09 | 10.87 |
| GraphLocator | 21.88 | 17.43 | 7.18 | 11.96 | 3.26 |
| GALA | 57.26 | 48.21 | 22.70 | 39.13 | 13.04 |
| BM25-MMIR | 45.41 | 48.51 | 22.08 | 30.43 | 13.04 |

结论：

1. **LocAgent 是当前 Mimo-v2.5 下综合最强 baseline。**  
   File REC@All 59.77，Function REC@All 52.38，说明 Agent 搜索在强模型下确实能获得更好的语义理解和候选召回。

2. **GALA 文件级接近 LocAgent，但函数级明显弱。**  
   GALA File REC@All 57.26，接近 LocAgent；但 Function REC@All 只有 22.70，说明它能找到相关文件，却不能稳定落到函数或代码实体。

3. **BM25 召回可用，但噪声高。**  
   BM25 File REC@All 45.41，说明词法检索仍有价值；但它不是最终定位器，更适合作为第一阶段候选召回。

4. **GraphLocator 在该设置下整体偏弱。**  
   File Acc@15 11.96，Function Acc@15 3.26。问题不是单纯模型弱，而是图扩展高度依赖初始 seed；一旦 URL 或图片 seed 错，因果链会沿错误方向扩散。

### 3.2 严格 Acc@15 结果

严格 Acc@15 表示 top-15 必须覆盖该层级所有 gold，适合衡量“能否完整定位修复闭包”。

| 层级 | LocAgent | CoSIL | GraphLocator | GALA | BM25-MMIR |
|---|---:|---:|---:|---:|---:|
| File Acc@15 | 42.39 | 26.09 | 11.96 | 39.13 | 30.43 |
| Module Acc@15 | 43.48 | 25.00 | 13.04 | 34.78 | 40.22 |
| Function Acc@15 | 21.74 | 10.87 | 3.26 | 13.04 | 13.04 |

这个表说明：即使在 Clean15 过滤后，函数级完整覆盖仍然很难。原因包括：

- 真实修复经常跨多个文件和多个函数；
- 图片/URL 给的是症状或入口，不是全部 patch target；
- CSS/SCSS/JSON/Markdown 等非函数文件会让 function-level 指标天然更难解释；
- 新增函数、新增模块、结构抽取不完整，也会影响函数级 gold 映射。

## 4. 典型失败案例和原因

### 4.1 `Automattic__wp-calypso-21409`：URL 指向证据入口，但真实修复在 WooCommerce flow

Issue：Store signup flow 需要在用户进入 `wp-admin` 前强制 email verification。Issue 包含 UI 截图和一个代码 URL：

```text
client/state/current-user/selectors.js#L157
isCurrentUserEmailVerified
```

真实 gold 是 10 个 WooCommerce dashboard/address/setup/settings 文件，例如：

```text
client/extensions/woocommerce/app/dashboard/store-location-setup-view.js
client/extensions/woocommerce/components/address-view/index.js
client/extensions/woocommerce/lib/countries/index.js
client/extensions/woocommerce/state/sites/settings/actions.js
```

Mimo-v2.5 结果：

| Baseline | file_rec@all | 失败表现 |
|---|---:|---|
| LocAgent | 0.10 | 命中 `store-location-setup-view.js`，但被 email selector、signup config 牵引，漏 9/10 gold |
| CoSIL | 0.00 | 停在 `current-user/selectors.js`、signup steps、email verification |
| GraphLocator | 0.00 | 从 current-user/email-verification seed 沿错误图路径扩散 |
| GALA | 0.10 | 命中少量 WooCommerce 相关文件，但闭包不足 |

失败原因：

- URL 是 evidence seed，不是 patch target；
- 图片展示的是用户流程状态，不能直接映射为某个 selector 文件；
- 真实修改需要从 `email verified selector` 扩展到 WooCommerce onboarding、address、country、settings action 的业务闭包；
- 当前 baseline 缺少“URL 角色识别”和“业务流程 patch closure”。

方法启发：

```text
URL selector evidence
  -> email verification state
  -> store signup / dashboard flow
  -> address and country setup
  -> settings actions and selectors
  -> patch target closure
```

### 4.2 `diegomura__react-pdf-1178`：示例 URL 和截图是复现证据，真实修复在 stylesheet pipeline

Issue：`margin: auto` 在 react-pdf v2 中失效。Issue 给出 example URL 和渲染差异截图。

真实 gold：

```text
packages/stylesheet/src/expand.js
packages/stylesheet/src/resolve.js
```

Mimo-v2.5 结果：

| Baseline | file_rec@all | 失败表现 |
|---|---:|---|
| LocAgent | 0.50 | 命中 `expand.js`，漏 `resolve.js` |
| CoSIL | 0.00 | 偏 layout/yoga/renderer |
| GraphLocator | 0.00 | 偏 examples、image、renderer、tests |
| GALA | 0.00 | 偏 layout margin setter |

LocAgent 的 reasoning 已经接近真实原因：

```text
User writes margin: 'auto'
The style is expanded by packages/stylesheet/src/expand.js
processBoxModel('marginTop', 'auto')
```

失败原因：

- example URL 是 reproduction evidence，不是修复文件；
- 截图表现为布局错误，但真实修复在 stylesheet expand/resolve pipeline；
- Mimo 能写出正确解释，但最终候选没有把解释链条完整转成文件闭包；
- 需要从 style expansion 继续追到 resolve/castFloat，而不是停在 example 或 layout setter。

方法启发：

```text
visual layout symptom
  -> CSS-like style property: margin:auto
  -> style expansion
  -> style resolve / unit conversion
  -> layout engine input
```

### 4.3 `chartjs__Chart.js-8162`：图片显示 legend/title 重复，真实修复是 plugin lifecycle

Issue：legend 和 title 被渲染两次。

Mimo-v2.5 预测倾向：

```text
src/core/core.controller.js
src/core/core.layouts.js
src/plugins/plugin.legend.js
src/plugins/plugin.title.js
```

真实 gold：

```text
src/core/core.plugins.js::invalidate
```

失败原因：

- 图片和 issue 文本显示的是受影响组件：legend/title；
- baseline 顺着表象组件查找 draw/render/layout；
- 真实 bug 在 plugin lifecycle/cache invalidation；
- 当前方法缺少“受影响组件 -> 控制机制”的 mechanism router。

方法启发：

```text
visual symptom: duplicated legend/title
  -> affected component: legend/title plugin
  -> mechanism hypothesis: lifecycle / cache / invalidation
  -> target: core.plugins.js::invalidate
```

### 4.4 `processing__p5.js-5917`：WebGL 问题需要 JS 控制点 + shader/resource closure

Issue：WebGL `premultipliedAlpha` 默认行为异常。

Mimo-v2.5 结果：

| Baseline | file_rec@all | 失败表现 |
|---|---:|---|
| LocAgent | 0.22 | 命中 `RendererGL.js`、`material.js`，漏 shader/resource 闭包 |
| CoSIL | 0.11 | 命中 RendererGL，但偏 Immediate/Retained/Image |
| GraphLocator | 0.11 | RendererGL + tests/manual examples |
| GALA | 0.44 | 命中部分图形相关文件，但仍闭包不足 |

失败原因：

- Mimo 能抓住 `premultipliedAlpha`、`UNPACK_PREMULTIPLY` 这类关键 token；
- 但 WebGL 修复不是单个 JS 文件，往往还涉及 texture upload、blend function、shader output、renderer state；
- 当前 repo structure 对 shader/resource 文件覆盖也不完整，导致文件级和函数级评估都容易失真。

方法启发：

```text
WebGL issue
  -> context attributes
  -> texture upload state
  -> renderer/material control point
  -> shader/resource closure
  -> examples/tests
```

### 4.5 `Automattic__wp-calypso-33948`：依赖迁移不能只搜旧依赖名

Issue：`localForage` 的 Apache 2.0 license 与 GPLv2 不兼容，需要替换依赖。

真实 gold 包含：

```text
CREDITS.md
client/lib/browser-storage/README.md
client/lib/browser-storage/bypass.ts
client/lib/browser-storage/index.ts
client/lib/user/support-user-interop.js
client/lib/user/user.js
client/state/initial-state.js
npm-shrinkwrap.json
package.json
webpack.config.js
```

Mimo-v2.5 结果：

| Baseline | file_rec@all | 失败表现 |
|---|---:|---|
| LocAgent | 0.00 | 只找 `client/lib/localforage/*` |
| CoSIL | 0.10 | 只命中 `package.json` |
| GraphLocator | 0.00 | 偏 notifications/selectors/UI |
| GALA | 0.00 | 空或无有效预测 |

失败原因：

- 模型识别到了 `localForage` 是关键 seed；
- 但修复不是改旧依赖文件，而是做 dependency migration；
- 需要覆盖新 abstraction、所有 use sites、构建配置、lockfile、credits/docs；
- 现有 baseline 缺少“依赖迁移闭包”。

方法启发：

```text
old dependency
  -> package declaration / lockfile
  -> use sites
  -> replacement abstraction
  -> build config
  -> credits/docs
```

## 5. 现有 baseline 的不足总结

| Baseline | 优点 | 主要不足 |
|---|---|---|
| LocAgent | 强模型下语义理解和搜索能力最好，能写出较好的 root cause reasoning | reasoning 到最终候选的转换不稳定；命中入口后缺少 patch closure verifier |
| CoSIL | 文件级可用，能做一定结构化分析 | 容易停在局部实现层；函数级弱；多文件闭包不足 |
| GraphLocator | 有图和因果链思想 | 过度依赖初始 seed；URL/图片 seed 错时图扩展沿错误路径走；跨资源文件覆盖不足 |
| GALA | 文件级和模块级排序较强 | 函数级弱；对 evidence-only URL 和非函数资源闭包处理不足 |
| BM25-MMIR | 召回器可用，适合第一阶段候选生成 | 噪声大、精度低，不能判断 URL 角色和 patch closure |

核心问题不是“模型不够强”这么简单。Mimo-v2.5 已经显著提升了 LocAgent/GALA 的语义理解，但失败案例显示：强模型仍然会把证据入口当修复目标，或者写出正确推理却漏掉最终文件闭包。

## 6. 我们的方案思路

### 6.1 总体判断

后续方法应该把两件事分开：

1. **Issue Evidence Extraction：理解 issue 证据**  
   负责解析图片、URL、错误描述、复现步骤、代码链接、playground、文档/API，判断它们分别是什么角色。

2. **Repository Navigation Graph：辅助 Agent 在仓库中导航**  
   负责提供代码结构、调用关系、状态流、组件关系、配置关系、样式关系、测试关系等 typed edges，帮助 Agent 从 evidence seed 扩展到 patch target closure。

这样做的原因是：issue 证据和仓库结构不是同一种信息。图片/URL 是外部症状和线索；仓库图是内部代码导航地图。把二者混在一个 prompt 里让 LLM 自己猜，稳定性很差。

### 6.2 方案框架

建议框架：

```text
Issue
  -> Evidence Extractor
      -> image cards
      -> URL cards
      -> reproduction cards
      -> API / concept cards
      -> code pointer cards

Evidence Router
  -> 判断 URL / 图片角色
  -> evidence-only / reproduction / direct-code / docs-api / weak-context

Mechanism Translator
  -> UI symptom -> route/component/state/action
  -> layout symptom -> stylesheet/resolve/layout engine
  -> chart symptom -> scale/plugin/event/lifecycle
  -> WebGL symptom -> renderer/texture/shader/resource
  -> dependency issue -> package/use-site/replacement/config/docs

Repository Navigation Graph
  -> File / Function / Class
  -> Component / Route / Selector / Reducer / Action
  -> ConfigKey / StyleSelector / Resource / Test
  -> imports / calls / renders / selects_state / dispatches / styles / configures / tests

Agent Search and Verification
  -> seed search
  -> typed graph expansion
  -> candidate rerank
  -> patch closure verifier
  -> final localization + repair reasoning chain
```

### 6.3 创新点

1. **证据角色识别**  
   不再把所有 URL 都当普通文本。GitHub blob、issue/PR、playground、docs、产品 URL、图片 URL 分别解析，并判断它是 patch target、evidence seed 还是 weak context。

2. **图片症状到代码机制的转换**  
   不是只让 VLM 描述图片，而是把图片转成定位机制：UI route、layout pipeline、chart plugin lifecycle、WebGL resource closure 等。

3. **多语言/多资源仓库图**  
   图不是单一 call graph，而是 typed heterogeneous repository graph。JS/TS 前端需要 component/state/route 边；Python 需要 import/type/binder/API 参数流；Java 需要 inheritance/override/delegate；CSS/JSON/MDX 需要 style/config/doc edges。

4. **Patch closure verifier**  
   解决“命中一个入口但漏掉闭包”的问题。比如 `21409` 命中 `store-location-setup-view.js` 后，需要检查 dashboard/address/countries/settings 是否补齐；`1178` 命中 `expand.js` 后，需要检查 `resolve.js` 是否补齐。

5. **定位链路服务修复**  
   输出不只是 top-k 文件，而是 evidence-to-target reasoning chain。这个链路可以直接服务后续自动修复：知道为什么改这些文件、它们之间如何传递状态、参数或样式。

## 7. 下一步计划

### 7.1 实验侧

1. 固定 Clean15 作为主要分析口径，同时保留全集结果作为补充。
2. 对 SWE 和 Omni 分别输出按证据类型分组的结果表。
3. 继续补充典型失败案例，要求每个案例包含：
   - issue 多模态信息；
   - gold patch；
   - baseline 预测；
   - 真实轨迹片段；
   - 失败原因；
   - 对方案设计的启发。

### 7.2 方法侧

P0：证据抽取层

```text
extract_issue_evidence.py
classify_url_role.py
parse_github_blob.py
parse_playground_url.py
summarize_image_symptom.py
```

P1：机制翻译层

```text
ui_mechanism_router.py
layout_mechanism_router.py
chart_mechanism_router.py
webgl_mechanism_router.py
dependency_migration_router.py
```

P2：仓库导航图

```text
build_repo_graph.py
extract_js_ts_edges.py
extract_python_edges.py
extract_java_edges.py
extract_resource_edges.py
```

P3：Agent 搜索和验证

```text
evidence_to_seed.py
typed_graph_expand.py
candidate_rerank.py
patch_closure_verify.py
localization_trace_export.py
```

## 8. 一句话汇报

本周完成了 SWE-bench Multimodal 和 OmniGIRL 的多模态证据分析，并在 SWE 全量 Clean15 上整理了 Mimo-v2.5 的 baseline 结果。结果显示，Mimo 明显提升了 Agent 的语义理解能力，但典型失败仍集中在 URL 角色误判、图片症状无法映射到底层机制、多文件 patch closure 不完整、函数级定位弱等问题。下一步方案是构建“证据抽取层 + 多语言仓库导航图 + patch closure verifier”的 Agent 定位框架，让图片和 URL 先转成结构化证据，再通过仓库图导航到完整修复目标。
