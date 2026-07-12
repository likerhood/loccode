# 面向多模态跨语言 Issue 定位的修复思路与创新框架

本文档重新聚焦两个核心问题：

1. **跨语言适配**：同一个 issue 里的症状、截图、URL、错误日志往往是语言无关的，但真正要定位的代码实体是语言相关的。JavaScript/TypeScript、Java、Python、Markdown/MDX、CSS/SCSS 等语言的目录组织、符号命名、测试约定、依赖边都不同，不能用一套统一的关键词检索口径解决。
2. **Agentic 搜索分析检索框架**：现有 agent 容易在仓库里“边搜边迷路”：先被 issue 里的高频词带到错误模块，再被相似文件名或相邻目录吸走，最后输出局部合理但全局错误的文件。我们需要的是有状态、有证据、有反证、有停止条件的搜索闭环，而不是自由形式的多轮问答。

因此，这里提出一个更清晰的创新故事：

> **把 Issue 定位从“问模型哪里要改”改成“跨语言证据路由 + 显式搜索状态 + 多文件闭包验证”的仓库级诊断过程。**

框架暂命名为 **X-LocAgent：Cross-language Evidence-Routed Agentic Localization**。

## 1. 背景：为什么现有 baseline 容易失败

我们目前在 SWE-bench Multimodal 和 OmniGIRL 上看到的失败，不只是模型能力不足，而是任务结构本身更复杂。

### 1.1 多模态 evidence 和代码语言之间存在断层

SWE-bench Multimodal 的 issue 往往带有截图、网页 URL、UI 行为描述。截图和 URL 可以告诉我们“症状发生在哪个产品页面、哪个 UI 状态、哪个用户流程”，但它们不能直接告诉我们具体文件。模型需要把视觉/网页证据转换成代码侧检索信号：

- 页面名、产品名、路由名、组件名；
- 文案、按钮、状态枚举、CSS class；
- 前端状态、API endpoint、store/selectors；
- 截图里的视觉异常对应的 layout、style、rendering、formatter、chart/plugin 等代码区域。

如果这一步没做好，LocAgent/GraphLocator 这类 agent 就容易出现“语义相近但模块错误”的搜索漂移。例如 issue 在 WooCommerce 页面，agent 却因为 `site`、`plan`、`checkout` 等词跑到 Jetpack 或 signup 相关目录。

### 1.2 跨语言仓库不能只靠统一关键词

OmniGIRL 的样本覆盖 JavaScript、TypeScript、Java、Python、Markdown/MDX、CSS/SCSS 等不同语言。不同语言的“定位路径”完全不同：

| 语言/生态 | 常见真实定位线索 | 容易误伤的线索 |
|---|---|---|
| JavaScript/TypeScript | component、hook、store、selector、route、test snapshot、package workspace | 同名 UI 文案、storybook/demo、generated file |
| Java | package path、class/method、exception、unit test、interface/impl、Maven/Gradle module | API 文档、example、test-only helper |
| Python | module path、import chain、decorator、class/function、CLI entrypoint、test failure | README/example、typing stub、compat wrapper |
| Markdown/MDX | docs route、frontmatter、embedded component、example snippet | 普通文档文本相似但不影响行为 |
| CSS/SCSS | class name、theme token、layout relation、component import | 全局样式名、legacy CSS、snapshot-only file |

所以跨语言定位的关键不是“一个 dense embedding 覆盖所有语言”，而是：**先识别 evidence 属于哪种代码生态，再用该生态下更可靠的检索语法和图边扩展。**

### 1.3 Agent 没有显式状态时，会重复、漂移、过早停止

从轨迹看，agent 失败常见有三类：

1. **漂移**：从正确产品域漂到相似但错误的 package。
2. **局部闭环**：反复检查同一批文件，缺少新的扩展边。
3. **空响应/无效响应**：LLM 返回空文本、tool call 或泛泛解释，系统继续写入空结果，导致评估极低。

这说明搜索框架不能只记录“走过哪些命令”，还需要维护一个明确的 **belief state**：

- 当前候选文件为什么可能正确；
- 它支持哪些 issue evidence；
- 它缺少哪些 evidence；
- 它和哪些反证冲突；
- 当前 top-k 是否覆盖多文件 patch closure。

## 2. 联网调研得到的启发

下面这些工作对我们的方案有直接启发：

| 方向 | 代表工作 | 对本方案的启发 |
|---|---|---|
| 多模态 issue benchmark | SWE-bench Multimodal | 多模态 issue 不是简单加图片，而是要求把 UI/视觉证据映射到代码位置。 |
| 跨语言 issue benchmark | OmniGIRL | 真实 issue 横跨多语言、多仓库、多生态，统一检索策略会被语言差异拖垮。 |
| Agentic 定位 | LocAgent | 仓库级定位需要 agent 使用工具搜索、阅读、推理，但 agent 需要更强的状态管理和反证机制。 |
| Call graph/semantic graph | CoSIL | 结构图可以帮助从 seed 文件扩展到相关实现，但图边必须和语言生态适配。 |
| Repository graph | RepoGraph、KGCompass | 仓库知识图谱可把文件、符号、调用、依赖、测试关系组织成可搜索空间。 |
| 代码表示学习 | CodeBERT、GraphCodeBERT、UniXcoder | Dense retrieval 有价值，但要和符号检索、路径先验、语言 adapter 结合。 |
| 跨文件定位 | HitMore 等多文件 bug localization 工作 | 多文件真实 patch 需要 seed-to-closure，而不是只追求第一个命中文件。 |

这些工作共同指向一个结论：**单一检索器、单一 agent、单一图结构都不够。真正需要的是跨语言证据路由，把 issue evidence 转换成不同语言下可执行的搜索策略，再用 agent 搜索闭环逐步收敛。**

## 3. 核心创新故事

### 3.1 传统做法的问题

传统流程大致是：

```text
Issue 文本/图片/URL
  -> LLM 总结
  -> BM25/Dense/Graph 检索
  -> 让 LLM 选文件
  -> 输出 top-k
```

这个流程的问题是中间缺少两个关键层：

1. **跨语言 evidence adapter**：没有把同一类证据翻译成不同语言生态里的检索语法。
2. **agentic belief state**：没有把每一步搜索的证据、反证、覆盖缺口显式保存下来。

### 3.2 X-LocAgent 的故事

X-LocAgent 把任务拆成三个阶段：

```text
阶段 A：证据规范化
  Issue + 图片 + URL + 日志
  -> 语言无关 Intent Frame

阶段 B：跨语言路由
  Intent Frame
  -> JS/TS、Java、Python、Docs、CSS 等 Language Adapter
  -> 每种语言自己的检索 query、路径先验、符号类型、图边类型

阶段 C：Agentic 搜索闭环
  Hybrid Retrieve -> Inspect -> Expand -> Verify -> Reflect -> Stop
  -> 带证据表和多文件闭包的定位结果
```

一句话说：

> **先把 issue 变成语言无关的故障意图，再把故障意图路由到语言相关的搜索策略，最后让 agent 用显式状态表完成检索、阅读、扩展和验证。**

## 4. X-LocAgent 总体框架

### 4.1 Issue Intent Frame：把 issue 变成可路由的证据

第一步不是直接检索，而是把 issue 解析成结构化意图。

```yaml
issue_id: Automattic__wp-calypso-21492
symptom:
  type: ui_behavior
  description: 授权流程里按钮或状态不符合预期
domain:
  product: wp-calypso
  candidate_area: jetpack / oauth / authorize
modal_evidence:
  images: [...]
  urls: [...]
text_evidence:
  keywords:
    - authorize
    - connection
    - jetpack
  negative_keywords:
    - signup
    - plans
    - checkout
expected_code_artifacts:
  - route
  - component
  - state selector
  - API helper
language_hints:
  - JavaScript
  - TypeScript
```

这个 Intent Frame 解决两个问题：

1. 把截图、URL、标题、正文、错误日志都放到同一个证据表中。
2. 提前生成反证词，避免 agent 被相似但错误的业务域吸走。

### 4.2 Language Adapter：不同语言有不同搜索语法

X-LocAgent 不让所有语言共享同一个 prompt，而是为每类语言/生态提供 adapter。

#### JS/TS Adapter

适合 SWE-bench Multimodal 里的 wp-calypso、Chart.js、p5.js，也适合 OmniGIRL 里的 Babel/Webpack/Prettier 类项目。

搜索策略：

- 优先 path query：`client/`, `components/`, `state/`, `packages/`, `src/`, `plugins/`；
- 优先 symbol query：component name、hook、selector、action、route、plugin、formatter；
- 图边扩展：import/export、component composition、test -> implementation、snapshot -> source；
- 反证：storybook/demo/docs/generated 文件默认降权。

示例：

```text
Issue 说 “comment formatting in prettier is wrong”
JS/TS adapter 不只搜 comment，还会生成：
  - printer
  - doc builder
  - comments attach
  - AST node kind
  - language plugin path
并降低 docs、website、benchmark snapshot 的优先级。
```

#### Java Adapter

适合 assertj、gson、spring 等项目。

搜索策略：

- package path 和 class name 权重大于自然语言相似度；
- test failure 中的 `ClassName.methodName` 直接生成 implementation query；
- interface/impl、abstract class、builder/factory、exception path 是关键图边；
- Maven/Gradle module 作为 first-stage router。

#### Python Adapter

搜索策略：

- import chain、decorator、CLI entry、module path 比普通关键词更重要；
- test name 和 fixture name 是强信号；
- `__init__.py`、compat wrapper、typing stub 需要特殊降权或展开。

#### Docs/CSS/MDX Adapter

这类文件容易被误认为“代码无关”，但在多模态 issue 里可能是 gold。

搜索策略：

- 如果 URL 指向 docs 页面，MD/MDX/frontmatter 需要进入候选；
- 如果截图是 layout/style 问题，CSS/SCSS/theme token 需要进入候选；
- docs 中嵌入的 component 示例需要和代码组件建立边。

### 4.3 Hybrid Retriever：多路召回但不是简单拼接

召回通道包括：

| 通道 | 解决什么问题 | 典型输入 |
|---|---|---|
| BM25 | 精确词、错误信息、路径片段 | 报错文本、函数名、UI 文案 |
| Dense | 语义近似、跨语言描述 | issue 摘要、症状描述 |
| Symbol | 函数、类、变量、导入导出 | adapter 生成的 symbol query |
| Path | monorepo package、目录域 | URL、产品名、repo namespace |
| Graph | seed 文件扩展到相关实现 | import/call/test/component edge |
| Visual seed | 截图 UI 元素转代码线索 | button text、route、layout token |

关键创新不是“通道越多越好”，而是每个通道都有 **router weight**：

```text
score(file) =
  w_bm25(language, modality)  * bm25
+ w_dense(language, modality) * dense
+ w_symbol(language)          * symbol
+ w_path(repo_type)           * path
+ w_graph(stage)              * graph
+ w_visual(has_image)         * visual
- penalty(negative_domain, generated_file, docs_only_mismatch)
```

例如 JS/TS UI issue 中，path、symbol、visual seed 权重应更高；Java exception issue 中，symbol、package、test-to-impl 权重应更高。

### 4.4 Agentic Belief State：让 agent 搜索时不迷路

每轮搜索后，agent 不直接输出结果，而是更新一张状态表：

| 字段 | 含义 |
|---|---|
| candidate | 候选文件/函数 |
| evidence_supported | 支持它的 issue 证据 |
| missing_evidence | 它还没有解释的症状 |
| contradiction | 和 issue 冲突的证据 |
| expansion_edges | 可以继续扩展的图边 |
| confidence | 当前置信度 |
| coverage_role | seed / helper / test / style / docs / unknown |

示例：

| 候选 | 支持证据 | 缺口 | 反证 | 下一步 |
|---|---|---|---|---|
| `client/jetpack-connect/authorize.jsx` | URL/authorize/Jetpack | API helper 未覆盖 | 无 | 查 import/helper |
| `client/signup/steps/checkout.jsx` | 有 checkout 文案 | issue 不在 signup | domain mismatch | 降权 |
| `state/jetpack-connect/selectors.js` | 状态词匹配 | UI component 未覆盖 | 无 | 扩展 component |

这比自由形式 chain-of-thought 更可控，也便于我们做 failure-aware verifier。

### 4.5 Agent 搜索状态机

X-LocAgent 的 agent 按固定状态机工作：

```text
PLAN
  解析 issue，生成 Intent Frame 和语言 adapter

RETRIEVE
  多路召回 top-N 文件和实体

INSPECT
  阅读候选文件局部上下文，抽取支持/反证

EXPAND
  基于 import/call/test/component/package 边扩展

VERIFY
  检查候选集合是否解释全部 issue evidence

REFLECT
  如果漂移或覆盖不足，改写 query 或切换 adapter

STOP
  满足覆盖、预算或失败条件后输出 top-k
```

停止条件不是“模型觉得够了”，而是：

- top-k 候选覆盖了 Intent Frame 的关键 evidence；
- 没有 unresolved high-priority evidence；
- 反证分数低于阈值；
- 多文件 closure 已补齐相关 helper/test/style 文件；
- 或者明确失败并返回可诊断的 failure reason。

### 4.6 多文件 Patch Closure：从命中一个文件到覆盖一组文件

我们的 strict 指标要求覆盖所有 gold 文件，因此只命中一个核心文件不够。

X-LocAgent 在 seed 文件后做 closure expansion：

```text
seed file
  -> imported helper
  -> tested implementation
  -> paired style file
  -> route/component parent
  -> state/action/selectors
  -> config/schema/type definition
```

不同语言 closure 规则不同：

| 语言生态 | closure 边 |
|---|---|
| JS/TS 前端 | component -> style/test/story/snapshot/state/hook |
| Chart.js/p5.js | plugin -> scale/controller/test/docs sample |
| Java | test -> class -> interface/impl -> exception/helper |
| Python | test -> module -> imported helper -> CLI/config |
| Docs/MDX | page -> embedded component -> data/frontmatter |

这可以专门针对 `gold_file > 1`、`hunk > 5` 的样本提升 file-level recall。

## 5. 结合现有失败样本的具体改进方向

### 5.1 SWE-bench Multimodal：业务域漂移

现象：

- issue 明明属于某个产品域，agent 检索到相似关键词后跑到另一个产品域；
- UI 文案、URL、截图没有被转成可靠 path/symbol signal。

修复：

1. 从 URL 和截图提取 domain seed；
2. domain seed 先约束 package/path，再检索 symbol；
3. 如果候选文件来自另一个业务域，记录 contradiction；
4. verifier 检查候选是否解释截图/URL/正文三类 evidence。

### 5.2 OmniGIRL：跨语言 query 不适配

现象：

- 同样是 “parser fails”，Babel、Python parser、Java JSON parser 的定位路径完全不同；
- 统一 dense retrieval 会把语义相似但语言生态不对的文件排前。

修复：

1. 先识别 repo language 和 package ecosystem；
2. 根据语言 adapter 生成不同 query；
3. rerank 时给语言一致、package 一致、test-to-impl 一致的候选加分；
4. 对 docs/example/generated 文件做场景化降权，而不是一律删除。

### 5.3 GraphLocator：图搜索局部陷阱

现象：

- 构图成本高；
- 如果 seed 错了，图扩展会沿错误邻域越走越深；
- 有时 LLM 空响应后仍继续，导致结果质量不稳定。

修复：

1. seed 进入图之前先由 evidence verifier 过滤；
2. 图扩展必须带 contradiction check；
3. 每轮扩展后重算 domain consistency；
4. 空响应不写入定位结果，而是换 query、换 adapter 或失败退出。

### 5.4 CoSIL/GALA：输出空或结构不兼容

现象：

- LLM 返回空值或 tool call，导致空定位；
- repo structure 中 function/module 结构有时不符合预期；
- 评估时 module/function gold 映射可能为 0。

修复：

1. 输出前做非空和格式校验；
2. 允许 fallback 到 file-level seed；
3. 对 function/module gold 为空的样本，报告为“不可映射实体”，不要误判成无代码修改；
4. 对结构解析失败的语言增加 adapter-specific parser。

## 6. 详细落地规划

### Phase 0：数据和失败模式标准化

目标：把现有 SWE 全量、SWE60、Omni60、Omni full-candidates 的样本和轨迹统一成可分析格式。

产物：

- `analysis/issue_frames/*.jsonl`
- `analysis/failure_cases/*.jsonl`
- 每个样本包含：
  - images/url/text counts；
  - language；
  - gold file/module/function；
  - hunk；
  - baseline top-k；
  - 失败类型：domain drift / language mismatch / empty response / multi-file miss / graph trap。

### Phase 1：Issue Intent Frame 抽取器

先不训练模型，使用规则 + LLM 低成本抽取。

字段：

```python
class IssueIntentFrame:
    issue_id: str
    repo: str
    modality: dict
    symptom_type: str
    product_domain: list[str]
    operation: list[str]
    visible_text: list[str]
    url_terms: list[str]
    error_terms: list[str]
    expected_artifacts: list[str]
    negative_hints: list[str]
    language_hints: list[str]
```

验证：

- 抽取结果是否覆盖 issue 里的 URL、图片、报错、标题关键词；
- 是否能生成负向 domain hint；
- 是否能和 gold 文件路径产生可解释联系。

### Phase 2：Language Adapter 与多路召回

先实现 4 个 adapter：

1. `JSTSAdapter`
2. `JavaAdapter`
3. `PythonAdapter`
4. `DocsStyleAdapter`

每个 adapter 输出：

```python
class SearchPlan:
    bm25_queries: list[str]
    dense_queries: list[str]
    symbol_queries: list[str]
    path_priors: list[str]
    graph_edges: list[str]
    negative_patterns: list[str]
```

实验：

- BM25 only；
- Dense only；
- BM25 + dense；
- + language adapter；
- + path/symbol prior；
- + visual/url seed。

### Phase 3：Agentic Belief State 搜索闭环

实现一个轻量 agent，不直接依赖某个 baseline：

```text
for step in budget:
    retrieve candidates
    inspect top candidates
    update belief state
    verify coverage and contradiction
    if stop_condition:
        break
    reformulate query or expand graph
return ranked candidates with evidence table
```

每个候选输出证据：

```json
{
  "file": "client/jetpack-connect/authorize.jsx",
  "score": 0.82,
  "supported_evidence": ["url: authorize", "text: jetpack connection", "symbol: Authorize"],
  "missing_evidence": ["state selector"],
  "contradictions": [],
  "role": "seed"
}
```

### Phase 4：多文件 Closure 与 strict 指标优化

针对 strict full-coverage 指标，增加 closure 阶段：

1. 从 top seed 文件找 related files；
2. 给 related files 标注 role；
3. 用 verifier 判断是否需要放进 top-k；
4. 控制 top-k 不被低质量邻居填满。

### Phase 5：评估与消融

核心评估维度：

| 评估维度 | 指标 |
|---|---|
| 排名命中 | File/Module/Function Acc@K, MRR, MAP |
| 集合覆盖 | Recall/Precision/F1, SL |
| 多文件覆盖 | gold_file>=3 子集的 Recall@15 |
| 跨语言稳健性 | 按语言拆分的 Acc@K |
| 多模态收益 | image-only / url-only / image+url / text-only 子集 |
| agent 稳定性 | 空响应率、循环率、平均步数、漂移率 |
| 成本 | token、API 调用数、平均运行时间 |

建议消融表：

| 方法 | 跨语言 adapter | visual/url seed | graph closure | belief verifier | 预期变化 |
|---|---|---|---|---|---|
| BM25 | 否 | 否 | 否 | 否 | 精确词有效，但跨语言和多文件弱 |
| BM25 + Dense | 否 | 否 | 否 | 否 | 语义召回增强，但容易语义漂移 |
| + Adapter | 是 | 否 | 否 | 否 | 语言一致性提升 |
| + Visual/URL | 是 | 是 | 否 | 否 | 多模态 issue 定位提升 |
| + Closure | 是 | 是 | 是 | 否 | 多文件 recall 提升 |
| + Verifier | 是 | 是 | 是 | 是 | 空结果、漂移、误扩展下降 |

## 7. 论文/项目叙事建议

如果后续写论文或项目报告，可以用下面这个故事线：

1. **问题提出**：现有 issue localization 在多模态、多语言、仓库级场景下失效，根因不是单纯检索不足，而是 evidence 与代码生态之间缺少路由层。
2. **观察分析**：通过 SWE-bench Multimodal 和 OmniGIRL 发现，失败集中在 domain drift、language mismatch、multi-file miss、empty/invalid agent response。
3. **核心方法**：提出 X-LocAgent，用 Issue Intent Frame 把 issue 规范化，用 Language Adapter 把证据转换成语言相关搜索计划，用 Belief State Agent 完成搜索、扩展、验证。
4. **关键创新**：
   - Cross-language evidence routing；
   - Agentic belief-state search；
   - Multi-file patch closure；
   - Failure-aware verifier。
5. **实验验证**：在 SWE 全量、SWE60、Omni60、Omni candidates 上做整体和分组评估，证明方法对跨语言、多模态、多文件样本有稳定增益。

## 8. 和现有 baseline 的关系

X-LocAgent 不是完全替代现有 baseline，而是可以作为上层框架复用它们：

| 现有 baseline | 在 X-LocAgent 中的角色 |
|---|---|
| LocAgent | agent tool execution 和局部代码阅读能力 |
| GraphLocator | repo graph 构建和结构扩展能力 |
| CoSIL | call graph / semantic graph 辅助定位 |
| GALA | LLM reasoning + structured localization |
| MM-IR | BM25/dense 检索底座 |

也就是说，X-LocAgent 可以先实现成一个 **meta-localizer**：

```text
X-LocAgent
  -> 生成 adapter-aware search plan
  -> 调用 MM-IR/LocAgent/GraphLocator 得到候选
  -> 统一 evidence rerank
  -> 做 closure 和 verifier
  -> 输出最终 top-k
```

这样开发风险更低，也能解释为什么它比单个 baseline 更适合跨语言多模态场景。

## 9. 参考资料

- SWE-bench Multimodal: https://www.swebench.com/multimodal.html
- SWE-bench Multimodal paper: https://arxiv.org/abs/2410.03859
- OmniGIRL: https://arxiv.org/abs/2505.04606
- LocAgent: https://aclanthology.org/2025.acl-long.426.pdf
- CoSIL: https://arxiv.org/abs/2503.22424
- RepoGraph: https://arxiv.org/abs/2410.14684
- KGCompass: https://arxiv.org/html/2503.21710v1
- CodeBERT: https://arxiv.org/abs/2002.08155
- GraphCodeBERT: https://arxiv.org/abs/2009.08366
- UniXcoder: https://arxiv.org/abs/2203.03850
- CrossCodeEval: https://arxiv.org/abs/2310.11248
- SWE-agent multimodal usage: https://swe-agent.com/latest/usage/multimodal/
- HitMore multi-file bug localization: https://weiqin-zou.github.io/papers/IST2025.pdf
