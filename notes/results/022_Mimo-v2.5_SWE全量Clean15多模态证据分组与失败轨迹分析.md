# Mimo-v2.5 在 SWE 全量 Clean15 上的多模态证据分组与失败轨迹分析

本文重新基于当前本地真实文件计算，不沿用旧表。旧表的问题是只给了 REC@All 的粗分组，没有区分 Mimo-v2.5 与 Qwen3-VL-8B，也没有把具体样本、预测文件和 Agent 轨迹放在一起。

## 1. 数据来源与口径

- 样本：`unpacked_results/swefull_results_mimov2.5/swebench_multimodal_full_dev_mimo-v2.5_20260712_152753/repo/clean_subsets/swebench_multimodal-full-dev.clean15.samples.jsonl`，Clean15 后共 `92` 条。
- Clean15 口径：只保留 gold file/module/function 数量都在 1..15 的样本，避免 Acc@15 被不可覆盖样本天然压低。
- 指标：表格主要使用严格评估 `REC@All`，单位是百分比。括号中的数字表示该组 `file_rec@all = 0` 的样本数，即 `zero_file`。
- Mimo-v2.5：来自服务器解包结果 `unpacked_results/swefull_results_mimov2.5/.../results/mimo-v2.5`。
- Qwen3-VL-8B：来自 `collected_results/qwen8b_mimo_compare_20260711_212220`，只作为同一 Clean15 口径下的模型对照。
- Omni60/Omni full 的 Mimo-v2.5 per-instance Clean15 结果当前不在本地文件树中；本文不把 Qwen 的 Omni 结果误写成 Mimo。

## 2. Mimo-v2.5 与 Qwen3-VL-8B 的总体对照

| 模型 | Baseline | 样本数 | File REC@All | Module REC@All | Function REC@All | File Acc@15 | Function Acc@15 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Mimo-v2.5 | LocAgent | 92 | 59.77 | 67.79 | 52.38 | 42.39 | 21.74 |
| Mimo-v2.5 | CoSIL | 92 | 43.35 | 37.19 | 18.89 | 26.09 | 10.87 |
| Mimo-v2.5 | GraphLocator | 92 | 21.88 | 17.43 | 7.18 | 11.96 | 3.26 |
| Mimo-v2.5 | GALA | 92 | 57.26 | 48.21 | 22.70 | 39.13 | 13.04 |
| Mimo-v2.5 | BM25-MMIR | 92 | 45.41 | 48.51 | 22.08 | 30.43 | 13.04 |
| Qwen3-VL-8B | LocAgent | 92 | 26.45 | 32.83 | 15.32 | 19.57 | 7.61 |
| Qwen3-VL-8B | CoSIL | 92 | 28.10 | 24.33 | 8.59 | 18.48 | 4.35 |
| Qwen3-VL-8B | GraphLocator | 92 | 15.46 | 16.56 | 7.77 | 7.61 | 3.26 |
| Qwen3-VL-8B | GALA | 92 | 40.32 | 38.46 | 19.65 | 25.00 | 11.96 |
| Qwen3-VL-8B | BM25-MMIR | 92 | 45.41 | 48.51 | 22.08 | 30.43 | 13.04 |

结论：Mimo-v2.5 对 LLM 型 baseline 的提升很明显，尤其 LocAgent 从 Qwen 的 File REC@All 26.45 提升到 59.77，Function REC@All 从 15.32 提升到 52.38。GALA 也提升明显。GraphLocator 仍然偏低，说明它的问题不只是模型能力，而是初始证据种子和图扩展路径容易偏。BM25-MMIR 不依赖 LLM，所以两组中相同。

## 3. 按 URL 角色看 Mimo-v2.5 File REC@All

表格格式为 `REC@All (zero_file)`。

| URL 角色 | 样本数 | LocAgent | CoSIL | GraphLocator | GALA | BM25-MMIR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 直接指向 gold 文件 | 5 | 65.00 (0) | 66.67 (0) | 33.33 (0) | 78.33 (0) | 48.33 (1) |
| 指向相关代码但非 gold 文件 | 3 | 31.11 (0) | 11.11 (2) | 0.00 (3) | 14.44 (1) | 25.56 (1) |
| 历史讨论/补丁线索 | 6 | 27.93 (1) | 29.80 (1) | 34.80 (1) | 37.41 (2) | 22.04 (3) |
| 复现行为线索 | 17 | 71.37 (3) | 64.51 (4) | 23.53 (13) | 81.18 (1) | 64.71 (4) |
| 弱网页线索 | 26 | 69.28 (4) | 42.54 (10) | 25.00 (16) | 58.79 (7) | 38.78 (12) |
| 无URL | 35 | 54.23 (6) | 35.44 (11) | 16.79 (24) | 48.57 (7) | 46.24 (11) |

新的分组结果和旧表不完全一致，因为这里按当前 Clean15 样本和实际 gold 文件重新判断 URL 角色。核心结论没有变化，但 Mimo-v2.5 后强弱差异更清楚：

1. `指向相关代码但非 gold 文件` 仍然是最危险的 URL 类型。GraphLocator 在这 3 个样本上 zero_file 为 3，说明代码 URL 如果不是 patch target，会强烈误导因果链或图扩展。
2. `直接指向 gold 文件` 对 GALA 和 LocAgent 有帮助，但不能解决多文件 patch closure。URL 只能给一个入口，真实补丁经常需要沿状态流、组件流或渲染流扩展。
3. `复现行为线索` 和部分 `弱网页线索` 在 Mimo 下表现较好，说明模型能利用 route、demo 页面、产品关键词和 issue 语义；但这些 URL 仍需要进一步解析成 route、component、event 或 API，而不是只作为普通文本。
4. `无URL` 不等于纯文本，因为 SWE Multimodal Clean15 全部有图片；这类样本主要依赖图片和 issue 文本。

## 4. 按图片类型看 Mimo-v2.5 File REC@All

| 图片类型 | 样本数 | LocAgent | CoSIL | GraphLocator | GALA | BM25-MMIR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Web UI页面截图 | 33 | 50.36 (6) | 20.82 (14) | 10.28 (24) | 30.13 (13) | 22.35 (18) |
| 图表/Canvas渲染截图 | 22 | 63.92 (4) | 53.27 (6) | 14.29 (18) | 68.31 (2) | 58.07 (5) |
| 图形/动画/Canvas截图 | 15 | 64.81 (1) | 57.96 (2) | 37.41 (5) | 70.19 (2) | 80.93 (0) |
| PDF/排版渲染截图 | 10 | 43.50 (3) | 19.50 (6) | 10.67 (7) | 60.33 (1) | 10.50 (8) |
| Markdown/文本渲染截图 | 12 | 85.28 (0) | 88.75 (0) | 57.64 (3) | 92.92 (0) | 70.28 (1) |

结论：

1. Web UI 页面截图仍是最大弱点。即使 Mimo-v2.5 能读图，UI 截图也需要把页面、route、component、state selector 和业务流连接起来；这不是单次视觉描述能完成的。
2. PDF/排版渲染截图对 CoSIL、GraphLocator、BM25 都很难。图片描述通常只说“排版错了”，真正修改点在 layout engine、measurement、border/background drawing 等深层逻辑。
3. Markdown/文本渲染和 Canvas/图形类相对更容易，因为 issue 文本里通常含有 API 名、token 名、事件名、渲染规则，检索和 LLM 都有更明确的语义锚点。

## 5. 典型样本与真实轨迹分析

### 5.1 `Automattic__wp-calypso-21409`

- Issue 摘要：Store: Signup Flow needs to require email verification
- 图片数量：2；URL 数量：2；图片类型：Web UI页面截图；URL 角色：指向相关代码但非 gold 文件
- 图片 URL：
  - `https://user-images.githubusercontent.com/22080/34058152-cf2dccfa-e18e-11e7-99f6-8a6f1f7a2dc4.png`
  - `https://user-images.githubusercontent.com/22080/34058228-0f78b5f4-e18f-11e7-8133-e57bceea7374.png`
- 网页 URL：
  - `https://github.com/Automattic/wp-calypso/blob/master/client/state/current-user/selectors.js#L157`
- Gold 文件：
  - `client/extensions/woocommerce/app/dashboard/index.js`
  - `client/extensions/woocommerce/app/dashboard/required-plugins-install-view.js`
  - `client/extensions/woocommerce/app/dashboard/setup-footer.js`
  - `client/extensions/woocommerce/app/dashboard/store-location-setup-view.js`
  - `client/extensions/woocommerce/components/address-view/index.js`
  - `client/extensions/woocommerce/components/form-location-select/states.js`
  - `client/extensions/woocommerce/components/query-locations/index.js`
  - `client/extensions/woocommerce/lib/countries/index.js`
  - `client/extensions/woocommerce/state/sites/locations/selectors.js`
  - `client/extensions/woocommerce/state/sites/settings/actions.js`

| Baseline | File REC@All | Module REC@All | Function REC@All | Top 5 预测文件 |
| --- | ---: | ---: | ---: | ---: |
| LocAgent | 10.00 | 20.00 | 10.00 | `client/extensions/woocommerce/app/dashboard/store-location-setup-view.js`; `client/components/email-verification/email-verification-dialog/index.jsx`; `client/extensions/woocommerce/app/dashboard/setup-notices.js`; `client/state/current-user/selectors.js`; `client/signup/config/flows.js` |
| CoSIL | 0.00 | 0.00 | 0.00 | `client/state/current-user/selectors.js`; `client/signup/config/flows.js`; `client/signup/config/steps.js`; `client/signup/steps/design-type-with-store/pressable-store/index.jsx`; `client/components/email-verification/index.js` |
| GraphLocator | 0.00 | 0.00 | 0.00 | `client/state/current-user/selectors.js`; `client/extensions/woocommerce/app/settings/email/mailchimp/setup-steps/key-input.js`; `client/signup/steps/design-type-with-atomic-store/new-site-image.jsx`; `client/signup/steps/design-type-with-store/new-site-image.jsx`; `client/state/current-user/email-verification/actions.js` |
| GALA | 10.00 | 20.00 | 30.00 | `client/signup/config/flows.js`; `client/state/current-user/selectors.js`; `client/extensions/woocommerce/components/store-address/index.js`; `client/extensions/woocommerce/lib/countries/index.js`; `client/signup/config/steps.js` |
| BM25-MMIR | 10.00 | 20.00 | 10.00 | `client/extensions/woocommerce/app/dashboard/store-location-setup-view.js`; `client/blocks/eligibility-warnings/hold-list.jsx`; `client/signup/steps/design-type-with-atomic-store/index.jsx`; `client/components/tinymce/plugins/simple-payments/dialog/form.jsx`; `client/signup/processing-screen/index.jsx` |

LocAgent 真实轨迹片段：

```text
USER: Given the following GitHub problem description, your objective is to localize the specific files, classes or functions, and lines of code that need modification or contain key information to resolve the issue. Follow these steps to localize the issue: ## Step 1: Categorize and Extract Key Problem Information - Classify the problem statement into the following categories: Problem description, error trace, code to reproduce the bug, and additional context. - Identify modules in the 'Automattic' package mentioned in each category. - Use extracted keywords and line numbers to search for relevant code references for additional context. - When using retrieval tools, never call `search_code_snippets` with empty arguments. Always provide concrete `search_terms` or `line_nums`. - For JavaScript/TypeScript/frontend repositories, search JS/TS/JSX/TSX files first. For example: `search_code_snippets(

ASSISTANT: I'll systematically analyze this problem about requiring email verification in the signup flow for non-supported countries. Let me start by exploring the repository structure and locating the key modules mentioned. ## Step 1: Categorize and Extract Key Problem Information The problem involves: - **Signup Flow**: The WordPress.com store signup flow - **Email Verification**: New verification step after Address Page form - **Country-based branching**: Different paths for supported vs non-supported countries - **Key selector**: `isCurrentUserEmailVerified` Let me search for the relevant code.<tool_call> <function=explore_tree_structure> <parameter=start_entities>["/"]</parameter> <parameter=traversal_depth>2</parameter> <parameter=dependency_type_filter>["contains"]</parameter>

ASSISTANT: I notice there's no dedicated "address" step in the signup flow. Let me search for address-related components and the key selector mentioned in the issue.<tool_call> <function=search_code_snippets> <parameter=search_terms>["isCurrentUserEmailVerified"]</parameter> <parameter=file_path_or_pattern>**/*.js</parameter>

TOOL: OBSERVATION: ##Searching for term "isCurrentUserEmailVerified"... ### Search Result: Found code snippet in file `client/extensions/woocommerce/app/dashboard/setup-notices.js`. Source: Retrieved code content using text fallback keyword search (bm25). ``` 1 | /** @format */ 2 | 3 | /** 4 | * External dependencies 5 | */ 6 | 7 | import React, { Component } from 'react'; 8 | import PropTypes from 'prop-types'; 9 | import { connect } from 'react-redux'; 10 | import { get } from 'lodash'; 11 | import { localize } from 'i18n-calypso'; 12 | 13 | /** 14 | * Internal dependencies 15 | */ 16 | import { getCurrentUser, isCurrentUserEmailVerified } from 'state/current-user/selectors'; 17 | import Notice from 'components/notice'; 18 | 19 | class SetupNotices extends Component { 20 | static propTypes = { 21 | currentUserEmail: PropTypes.string, 22 | currentUserEmailVerified: PropTypes.bool, 23 | transl
```

CoSIL 真实输出片段：

```
client/state/current-user/selectors.js
client/signup/config/flows.js
client/signup/steps/design-type-with-store/pressable-store/index.js
client/components/email-verification/index.js
client/signup/config/steps.js
```

分析：这个样本不是“找 email selector”这么简单。URL 指向 `isCurrentUserEmailVerified`，它是证据入口，但 gold patch 落在 WooCommerce dashboard、store location、address view 和 countries/settings 状态流上。Mimo LocAgent 能命中 `store-location-setup-view.js`，但仍被 email verification dialog、current-user selector、signup flow 牵引，导致 10 个 gold 文件只召回 1 个。这里需要 evidence seed 与 patch target 分离，并沿业务流程做 patch closure。

### 5.2 `diegomura__react-pdf-433`

- Issue 摘要：Setting a border on a rounded <View> causes unexpected results
- 图片数量：4；URL 数量：0；图片类型：PDF/排版渲染截图；URL 角色：无URL
- 图片 URL：
  - `https://user-images.githubusercontent.com/4199296/49249306-b037e380-f3d0-11e8-96cd-29eee986683b.png`
  - `https://user-images.githubusercontent.com/4199296/49249354-c5ad0d80-f3d0-11e8-8e2d-393dee2530e1.png`
  - `https://user-images.githubusercontent.com/4199296/49249430-f42ae880-f3d0-11e8-9272-cefd5bca1b0d.png`
  - `https://user-images.githubusercontent.com/4199296/49249444-fb51f680-f3d0-11e8-8f24-49d22bc27962.png`
- Gold 文件：
  - `src/dom.js`
  - `src/elements/Base.js`
  - `src/elements/Image.js`
  - `src/mixins/borders.js`
  - `src/mixins/clipping.js`

| Baseline | File REC@All | Module REC@All | Function REC@All | Top 5 预测文件 |
| --- | ---: | ---: | ---: | ---: |
| LocAgent | 60.00 | 75.00 | 57.14 | `src/stylesheet/transformStyles.js`; `src/renderer.js`; `src/elements/Note.js`; `src/mixins/borders.js`; `src/elements/View.js` |
| CoSIL | 20.00 | 25.00 | 57.14 | `src/mixins/borders.js`; `src/elements/View.js`; `src/utils/styles.js`; `src/utils/url.js`; `src/utils/jpeg.js` |
| GraphLocator | 40.00 | 25.00 | 14.29 | `index.d.ts`; `src/elements/Document.js`; `src/elements/Image.js`; `src/elements/Note.js`; `src/elements/Page.js` |
| GALA | 20.00 | 0.00 | 0.00 | `src/mixins/borders.js`; `src/elements/View.js`; `src/renderer.js`; `src/stylesheet/transformStyles.js`; `src/utils/styles.js` |
| BM25-MMIR | 80.00 | 100.00 | 42.86 | `index.d.ts`; `src/elements/Base.js`; `tests/stylesheet.test.js`; `src/stylesheet/transformStyles.js`; `tests/layout.test.js` |

LocAgent 真实轨迹片段：

```text
USER: Given the following GitHub problem description, your objective is to localize the specific files, classes or functions, and lines of code that need modification or contain key information to resolve the issue. Follow these steps to localize the issue: ## Step 1: Categorize and Extract Key Problem Information - Classify the problem statement into the following categories: Problem description, error trace, code to reproduce the bug, and additional context. - Identify modules in the 'diegomura' package mentioned in each category. - Use extracted keywords and line numbers to search for relevant code references for additional context. - When using retrieval tools, never call `search_code_snippets` with empty arguments. Always provide concrete `search_terms` or `line_nums`. - For JavaScript/TypeScript/frontend repositories, search JS/TS/JSX/TSX files first. For example: `search_code_snippets(s

ASSISTANT: I'll start by exploring the repository structure and searching for code related to border rendering and borderRadius in react-pdf. <function=explore_tree_structure> <parameter=start_entities>["/"]</parameter> <parameter=traversal_depth>2</parameter> <parameter=dependency_type_filter>["contains"]</parameter>

ASSISTANT: <tool_call> <function=search_code_snippets> <parameter=search_terms>["border", "borderRadius"]</parameter> <parameter=file_path_or_pattern>**/*.js</parameter>

TOOL: OBSERVATION: ##Searching for term "border"... ### Search Result: Found code snippet in file `src/mixins/borders.js`. Source: Retrieved code content using text fallback keyword search (bm25). ``` 1 | const Borders = { 2 | drawBorders() { 3 | const { left, top, width, height } = this.getAbsoluteLayout(); 4 | 5 | const { 6 | borderTopWidth = 0, 7 | borderRightWidth = 0, 8 | borderBottomWidth = 0, 9 | borderLeftWidth = 0, 10 | } = this; 11 | 12 | const { 13 | borderTopLeftRadius = 0, 14 | borderTopRightRadius = 0, 15 | borderBottomRightRadius = 0, 16 | borderBottomLeftRadius = 0, 17 | borderTopColor = 'black', 18 | borderRightColor = 'black', 19 | borderBottomColor = 'black', 20 | borderLeftColor = 'black', 21 | borderTopStyle = 'solid', 22 | borderRightStyle = 'solid', 23 | borderBottomStyle = 'solid', 24 | borderLeftStyle = 'solid', 25 | } = this.getComputedStyles(); 26 | 27 | // Save curr
```

CoSIL 真实输出片段：

```text
Based on the bug report and repository structure, the issue involves incorrect border rendering on rounded `<View>` elements. The border fails to follow the `borderRadius` curvature, suggesting problems in style parsing, border drawing logic, or rounded shape handling. The following files are the most likely culprits, ordered by importance:
src/elements/View.js
src/mixins/border.js
src/styles/stylesheet.js
src/utils/border.js
src/utils/shape.js
```
分析：图片展示 borderRadius 增大后边框渲染异常。LocAgent 和 CoSIL 都会搜索 `border`/`borderRadius` 并找到 `src/mixins/borders.js`，这是强信号；但它们也容易扩散到 View、renderer、style transform 等邻域。该类样本的问题不是找不到入口，而是需要识别“视觉症状对应的底层绘制 primitive”，函数级定位应落到 `drawBorders`、`drawHorizontalBorder` 等边框绘制函数。

### 5.3 `chartjs__Chart.js-10301`

- Issue 摘要：Legend event onLeave
- 图片数量：3；URL 数量：2；图片类型：图表/Canvas渲染截图；URL 角色：复现行为线索
- 图片 URL：
  - `https://user-images.githubusercontent.com/58777964/157239796-95ccabbb-7ac1-4e58-89ca-c902b1df0dfe.png`
  - `https://user-images.githubusercontent.com/58777964/157240018-395c6e62-d8e3-431f-8926-7644d5441078.png`
  - `https://user-images.githubusercontent.com/58777964/157241538-f55bf466-916f-4763-b0ea-ef78ef847127.png`
- 网页 URL：
  - `https://codesandbox.io/s/react-chartjs-2-chart-js-issue-template-forked-3kw5p0?file=/src/App.tsx`
  - `https://www.chartjs.org/docs/latest/samples/legend/events.html`
- Gold 文件：
  - `src/plugins/plugin.legend.js`

| Baseline | File REC@All | Module REC@All | Function REC@All | Top 5 预测文件 |
| --- | ---: | ---: | ---: | ---: |
| LocAgent | 100.00 | 100.00 | 100.00 | `src/plugins/plugin.legend.js`; `src/core/core.controller.js`; `src/core/core.defaults.js` |
| CoSIL | 100.00 | 100.00 | 0.00 | `src/plugins/plugin.legend.js`; `src/core/core.controller.js`; `src/platform/platform.dom.js`; `src/core/core.plugins.js`; `src/helpers/helpers.segment.js` |
| GraphLocator | 100.00 | 100.00 | 0.00 | `docs/samples/area/line-boundaries.md`; `test/fixtures/plugin.legend/legend-line-chart-area.json`; `docs/samples/area/line-datasets.md`; `docs/samples/area/line-drawtime.md`; `docs/samples/area/line-stacked.md` |
| GALA | 100.00 | 0.00 | 0.00 | `src/core/core.controller.js`; `src/plugins/plugin.legend.js`; `src/core/core.interaction.js`; `src/platform/platform.dom.js`; `src/helpers/helpers.dom.js` |
| BM25-MMIR | 0.00 | 100.00 | 50.00 | `src/platform/platform.dom.js`; `types/index.esm.d.ts`; `test/specs/core.controller.tests.js`; `src/core/core.defaults.js`; `karma.conf.js` |

LocAgent 真实轨迹片段：

```text
USER: Given the following GitHub problem description, your objective is to localize the specific files, classes or functions, and lines of code that need modification or contain key information to resolve the issue. Follow these steps to localize the issue: ## Step 1: Categorize and Extract Key Problem Information - Classify the problem statement into the following categories: Problem description, error trace, code to reproduce the bug, and additional context. - Identify modules in the 'chartjs' package mentioned in each category. - Use extracted keywords and line numbers to search for relevant code references for additional context. - When using retrieval tools, never call `search_code_snippets` with empty arguments. Always provide concrete `search_terms` or `line_nums`. - For JavaScript/TypeScript/frontend repositories, search JS/TS/JSX/TSX files first. For example: `search_code_snippets(sea

TOOL: OBSERVATION: src/plugins ├── contains ── src/plugins/index.js ├── contains ── src/plugins/plugin.decimation.js │ ├── contains ── src/plugins/plugin.decimation.js:lttbDecimation │ ├── contains ── src/plugins/plugin.decimation.js:minMaxDecimation │ ├── contains ── src/plugins/plugin.decimation.js:cleanDecimatedDataset │ ├── contains ── src/plugins/plugin.decimation.js:cleanDecimatedData │ ├── contains ── src/plugins/plugin.decimation.js:getStartAndCountOfVisiblePointsSimplified │ └── contains ── src/plugins/plugin.decimation.js:destroy ├── contains ── src/plugins/plugin.filler │ ├── contains ── src/plugins/plugin.filler/filler.drawing.js │ ├── contains ── src/plugins/plugin.filler/filler.helper.js │ ├── contains ── src/plugins/plugin.filler/filler.options.js │ ├── contains ── src/plugins/plugin.filler/filler.segment.js │ ├── contains ── src/plugins/plugin.filler/filler.target.js │ ├── cont

ASSISTANT: <tool_call> <function=get_entity_contents> <parameter=entity_names>["src/plugins/plugin.legend.js:Legend", "src/plugins/plugin.legend.js:afterEvent"]</parameter>

TOOL: OBSERVATION: ##Searching for entity `src/plugins/plugin.legend.js:Legend`... ### Search Result: Found class `src/plugins/plugin.legend.js:Legend`. Source: Exact match found for entity name `src/plugins/plugin.legend.js:Legend`. ``` 33 | export class Legend extends Element { 34 | 35 | /** 36 | * @param {{ ctx: any; options: any; chart: any; }} config 37 | */ 38 | constructor(config) { 39 | super(); 40 | 41 | this._added = false; 42 | 43 | // Contains hit boxes for each dataset (in dataset order) 44 | this.legendHitBoxes = []; 45 | 46 | /** 47 | * @private 48 | */ 49 | this._hoveredItem = null; 50 | 51 | // Are we in doughnut mode which has a different data type 52 | this.doughnutMode = false; 53 | 54 | this.chart = config.chart; 55 | this.options = config.options; 56 | this.ctx = config.ctx; 57 | this.legendItems = undefined; 58 | this.columnSizes = undefined; 59 | this.lineWidths = undef
```

CoSIL 真实输出片段：

```text
Based on the bug report analysis and the provided repository structure, here are the top-5 most likely culprit files, ordered by importance:

```
src/plugins/plugin.legend.js
src/core/core.controller.js
src/platform/platform.dom.js
src/core/core.plugins.js
src/helpers/helpers.events.js
```

**Reasoning:**

1. **`src/plugins/plugin.legend.js`** - Most critical since the issue directly involves legend event handling (`onLeave` not triggering). This file implements the legend plugin including event handling for hover/leave interactions.

2. **`src/core/core.controller.js`** - The main chart controller manages event propagation and mouse event handling. The bug involves events not being properly dispatched when the mouse leaves the chart area.

3. **`src/platform/platform.dom.js`** - Handles DOM event listeners and event propagation. The bug involves mouseout events not being captured when moving quickly outside the chart.

4. **`src/core/core.plugins.js`** - Manages plugin lifecycle and event handling. Since the legend is a plugin, event delegation might be affected here.

5. **`src/helpers/helpers.events.js`** - Contains event utility functions that might affect how mouseleave events
```

分析：URL 是 Chart.js 官方 legend events 示例，图片/复现描述说明快速移出 legend 时 `onLeave` 不稳定。LocAgent/CoSIL 都能把问题映射到 `plugin.legend.js` 和 DOM event 流，Mimo 在这类 API+事件语义样本上表现较好。剩余风险在于事件从 `platform.dom.js` 到 `core.controller.js` 再到 legend plugin 的传播链，单文件命中不等于函数级覆盖完整。

### 5.4 `markedjs__marked-1435`

- Issue 摘要：[Bug] We have to use '\' to add the '('
- 图片数量：1；URL 数量：7；图片类型：Markdown/文本渲染截图；URL 角色：历史讨论/补丁线索
- 图片 URL：
  - `https://user-images.githubusercontent.com/40081831/53847026-28263300-3fea-11e9-8c93-9acc880bde90.png`
- 网页 URL：
  - `https://github.com/markedjs/marked/files/2933754/Sample.txt`
  - `https://github.com/nodejs/nodejs.org/issues/2119`
  - `https://liebdich.com`
  - `https://t`
  - `https://twitter.com/matteocollina`
  - `https://twitter.com/pracucci`
- Gold 文件：
  - `lib/marked.js`

| Baseline | File REC@All | Module REC@All | Function REC@All | Top 5 预测文件 |
| --- | ---: | ---: | ---: | ---: |
| LocAgent | 100.00 | 100.00 | 100.00 | `lib/marked.js` |
| CoSIL | 100.00 | 100.00 | 0.00 | `lib/marked.js` |
| GraphLocator | 100.00 | 100.00 | 0.00 | `lib/marked.js` |
| GALA | 100.00 | 100.00 | 100.00 | `lib/marked.js` |
| BM25-MMIR | 100.00 | 100.00 | 100.00 | `test/original/markdown_documentation_syntax.html`; `test/original/markdown_documentation_basics.html`; `package.json`; `test/index.js`; `lib/marked.js` |

LocAgent 真实轨迹片段：

```text
USER: Given the following GitHub problem description, your objective is to localize the specific files, classes or functions, and lines of code that need modification or contain key information to resolve the issue. Follow these steps to localize the issue: ## Step 1: Categorize and Extract Key Problem Information - Classify the problem statement into the following categories: Problem description, error trace, code to reproduce the bug, and additional context. - Identify modules in the 'markedjs' package mentioned in each category. - Use extracted keywords and line numbers to search for relevant code references for additional context. - When using retrieval tools, never call `search_code_snippets` with empty arguments. Always provide concrete `search_terms` or `line_nums`. - For JavaScript/TypeScript/frontend repositories, search JS/TS/JSX/TSX files first. For example: `search_code_snippets(se

TOOL: OBSERVATION: / ├── contains ── docs │ ├── contains ── docs/demo │ └── contains ── docs/index.html ├── contains ── index.js ├── contains ── lib │ └── contains ── lib/marked.js └── contains ── marked.min.js └── contains ── marked.min.js:a

ASSISTANT: <function=get_entity_contents> <parameter=entity_names>["lib/marked.js"]</parameter>

TOOL: OBSERVATION: ##Searching for entity `lib/marked.js`... ### Search Result: Found file `lib/marked.js`. Source: Exact match found for entity name `lib/marked.js`. ``` 1 | /** 2 | * marked - a markdown parser 3 | * Copyright (c) 2011-2018, Christopher Jeffrey. (MIT Licensed) 4 | * https://github.com/markedjs/marked 5 | */ 6 | 7 | ;(function(root) { 8 | 'use strict'; 9 | 10 | /** 11 | * Block-Level Grammar 12 | */ 13 | 14 | var block = { 15 | newline: /^\n+/, 16 | code: /^( {4}[^\n]+\n*)+/, 17 | fences: noop, 18 | hr: /^ {0,3}((?:- *){3,}|(?:_ *){3,}|(?:\* *){3,})(?:\n+|$)/, 19 | heading: /^ *(#{1,6}) *([^\n]+?) *(?:#+ *)?(?:\n+|$)/, 20 | nptable: noop, 21 | blockquote: /^( {0,3}> ?(paragraph|[^\n]*)(?:\n|$))+/, 22 | list: /^( {0,3})(bull) [\s\S]+?(?:hr|def|\n{2,}(?! )(?!\1bull )\n*|\s*$)/, 23 | html: '^ {0,3}(?:' // optional indentation 24 | + '<(script|pre|style)[\\s>][\\s\\S]*?(?:</\\1>[^
```

CoSIL 真实输出片段：

```text
```
lib/InlineLexer.js
lib/Lexer.js
lib/Parser.js
lib/marked.js
lib/Renderer.js
```
```

分析：这是 Markdown 文本渲染类样本，截图和附件说明 URL 中括号解析错误。Mimo LocAgent 能直接定位 `lib/marked.js::findClosingBracket` 和 link/href 规则，属于多模态证据被成功压缩成语法规则的例子。它说明当图片或 URL 能转成明确 token/API/grammar 线索时，LLM-Agent 的定位效果会明显好于 Web UI/PDF 场景。

## 6. OmniGIRL 60 Mimo-v2.5 Clean15 解包结果补充分析

这一节基于刚解压的服务器包：`result_archives/omnigirl_unified60_mimo-v2.5_20260716_155146.tar.gz`。解压位置是 `unpacked_results/omnigirl_unified60_mimo-v2.5_20260716_155146/`。

需要先说明一个口径问题：压缩包路径叫 `omnigirl-unified60`，但里面 60 条预测的 `instance_id` 与本地当前 `LocAgent/newtest/omnigirl-unified60/data/samples.jsonl` 只重合 8 条，与本地 Clean15 只重合 6 条。实际这 60 条可以在 `MM-IR/data/omnigirl-full-candidates/source_omnigirl_full.jsonl` 中全部找到。因此下面把它称为“服务器 Omni60 Mimo 样本集”，不把它和本地旧 unified60 Clean15 结果直接混合。

这次分析已经重新按服务器 Omni60 自身生成 Clean15：先用服务器预测里的 60 个 `instance_id` 从 `MM-IR/data/omnigirl-full-candidates/source_omnigirl_full.jsonl` 抽出样本，再用本地 `MM-IR/data/omnigirl-full-candidates/repo_structures` 计算 gold file/module/function 数量，最后只保留三层 gold 都在 `1..15` 的样本。Clean15 后保留 24/60 条，排除 36 条。

排除原因需要单独说明：有 21 条样本本地没有对应 `repo_structures`，无法判断 module/function gold，因此不能纳入严格三层 Clean15；另外还有样本因为 `function_zero`、`module_zero` 或 gold 数量超过 15 被排除。这意味着下面的分析是“可严格三层评估的 clean 子集”，不是原始 60 条全集。

Clean15 相关文件：

- 样本：`clean_subsets/omnigirl-server60-mimo-v2.5.clean15.samples.jsonl`
- manifest：`clean_subsets/omnigirl-server60-mimo-v2.5.clean15.manifest.json`
- 复评估目录：各 baseline 结果目录下的 `eval_server60_clean15/` 和 `eval_strict_server60_clean15/`

### 6.1 服务器 Omni60 Clean15 样本画像

| 维度 | 分布 |
|---|---|
| 样本数 | 原始 60；Clean15 保留 24 |
| 语言 | Python: 10；JavaScript: 9；TypeScript: 3；Java: 2 |
| 仓库 Top | python/mypy: 9；prettier/prettier: 6；tailwindlabs/tailwindcss: 3；assertj/assertj、google/gson、iamkun/dayjs、pyca/cryptography、statsmodels/statsmodels、webpack/webpack 各 1 |
| 图片数 | 无图片: 22；有图片: 2 |
| URL 类型 | 文档/API URL: 8；复现/演示 URL: 6；其他网页 URL: 4；GitHub issue/PR/commit URL: 3；图片 URL: 2；GitHub 代码 URL: 1 |

Clean 后的 Omni60 仍然和 SWE Multimodal 差异很大：SWE 是图片密集型，Omni Clean15 主要是跨语言、URL/文本复现密集型。24 条里只有 2 条有图片；URL 类型集中在文档/API、playground/repl、GitHub issue/PR/commit、GitHub blob 代码链接和其他网页链接。

### 6.2 Mimo-v2.5 Clean15 严格指标汇总

| Baseline | File Acc@1 | File Acc@15 | File MRR@15 | File MAP@15 | File REC@All | Module Acc@15 | Module REC@All | Function Acc@15 | Function REC@All | Empty(file/module/function) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| LocAgent | 41.67 | 58.33 | 66.39 | 59.44 | 65.97 | 41.67 | 65.97 | 29.17 | 41.32 | 0.00/0.00/0.00 |
| CoSIL | 33.33 | 37.50 | 57.08 | 43.89 | 48.26 | 33.33 | 42.71 | 12.50 | 19.44 | 0.00/4.17/4.17 |
| GraphLocator | 4.17 | 20.83 | 9.84 | 7.44 | 25.35 | 12.50 | 18.06 | 8.33 | 10.42 | 0.00/8.33/16.67 |
| GALA | 20.83 | 37.50 | 36.81 | 31.39 | 39.93 | 33.33 | 35.42 | 4.17 | 8.51 | 45.83/50.00/54.17 |

结论：Clean15 后 LocAgent 仍然最好，File Acc@15 为 58.33，File REC@All 为 65.97；CoSIL 和 GALA 的 File Acc@15 都是 37.50，但 GALA 的 empty 仍然很高。GraphLocator 在 Clean15 下仍然明显偏低，File Acc@15 只有 20.83，说明它的问题不是由非 clean 样本单独造成的，而是初始种子和图扩展策略在跨语言 URL/复现样本上不稳定。

### 6.3 按语言分组的 File REC@All

表格为 `平均 File REC@All (zero_file 数)`，zero_file 表示该组中完全没有命中 gold 文件的样本数。

| 主语言 | 样本数 | LocAgent | CoSIL | GraphLocator | GALA |
|---|---:|---:|---:|---:|---:|
| Python | 10 | 65.00 (3) | 60.00 (3) | 45.00 (5) | 0.00 (10) |
| JavaScript | 9 | 59.26 (2) | 45.37 (3) | 6.48 (7) | 73.15 (1) |
| TypeScript | 3 | 100.00 (0) | 16.67 (2) | 33.33 (2) | 100.00 (0) |
| Java | 2 | 50.00 (1) | 50.00 (1) | 0.00 (2) | 0.00 (2) |

语言差异很明显：Python/mypy 类样本常有长 traceback、外部项目 URL 或 issue/PR 链接，模型容易停在 `semanal.py`、`build.py` 这类表层错误栈文件；Java/AssertJ/Gson/Netty 样本通常是 API 行为或异常消息修正，需要沿 assertion/API facade 到 internal helper；TypeScript/Babel/Tailwind 样本经常有 playground URL，定位关键在解析复现输入和编译配置，而不是只检索 URL 文本。

### 6.4 按 URL 类型分组的 File REC@All

| URL 类型 | 样本数 | LocAgent | CoSIL | GraphLocator | GALA |
|---|---:|---:|---:|---:|---:|
| 文档/API URL | 8 | 79.17 (1) | 72.92 (1) | 54.17 (3) | 4.17 (7) |
| 复现/演示 URL | 6 | 79.17 (1) | 41.67 (3) | 0.00 (6) | 87.50 (0) |
| 其他网页 URL | 4 | 37.50 (2) | 50.00 (1) | 37.50 (2) | 50.00 (2) |
| GitHub issue/PR/commit URL | 3 | 8.33 (2) | 8.33 (2) | 8.33 (2) | 0.00 (3) |
| 图片 URL | 2 | 100.00 (0) | 0.00 (2) | 0.00 (2) | 100.00 (0) |
| GitHub 代码 URL | 1 | 100.00 (0) | 100.00 (0) | 0.00 (1) | 0.00 (1) |

这里的“无URL”只表示 issue 文本里没有显式 URL，不表示没有复现代码。Omni 的关键不是图片，而是 URL 的结构化解析：playground/repl URL 里有输入代码和配置；GitHub blob URL 给出 path/line/symbol；issue/PR/commit URL 给出历史补丁线索；文档/API URL 给出行为规范。当前 baseline 基本把这些都压成普通文本，所以会出现两类失败：一类是被 URL 指向的相关文件误导，另一类是没有解析 URL hash 中的复现程序和配置。

### 6.5 图片样本补充

| 图片分组 | 样本数 | LocAgent | CoSIL | GraphLocator | GALA |
|---|---:|---:|---:|---:|---:|
| 无图片 | 22 | 62.88 (6) | 52.65 (7) | 27.65 (14) | 34.47 (13) |
| 有图片 | 2 | 100.00 (0) | 0.00 (2) | 0.00 (2) | 100.00 (0) |

Clean15 后只有 2 条图片样本，主要是错误输出截图或 issue 内联图片，和 SWE 的 UI/PDF/Canvas 视觉定位不同。因此 Omni 这里的“多模态”更准确地说是 URL/网页/复现上下文多模态，而不是图片主导。

### 6.6 典型样本与失败轨迹

#### 样本 `assertj__assertj-1763`：Java / `assertj/assertj`

Issue 真实问题：`hasNoNullFieldsOrProperties()` 在自定义 `Map` 委托类上误报。样例里用户写了一个 `DelegateMap implements Map<String, String>`，内部委托给 `HashMap`，然后调用 `Assertions.assertThat(map).hasNoNullFieldsOrProperties()`。期望是不报错；实际 AssertJ 在字段/属性反射过程中没有正确处理 Map 委托对象。

URL 证据：
- https://github.com/joel-costigliola/assertj-core/commit/337f99eee5cdcab9270145c47b429cbc48fb0134

Gold 文件：
- `src/main/java/org/assertj/core/util/introspection/PropertyOrFieldSupport.java`

| Baseline | File REC@All | Top 预测文件 |
|---|---:|---|
| LocAgent | 0.00 | `src/main/java/org/assertj/core/internal/CommonErrors.java`, `src/main/java/org/assertj/core/api/AssertionsForInterfaceTypes.java`, `src/main/java/org/assertj/core/internal/Urls.java`, `src/main/java/org/assertj/core/internal/Paths.java`, `src/main/java/org/assertj/core/internal/OnFieldsComparator.java` |
| CoSIL | 0.00 | `src/main/java/org/assertj/core/api/AbstractObjectAssert.java`, `src/main/java/org/assertj/core/groups/Properties.java`, `src/main/java/org/assertj/core/util/introspection/Introspection.java`, `src/main/java/org/assertj/core/api/AbstractMapAssert.java`, `src/main/java/org/assertj/core/internal/Files.java` |
| GraphLocator | 0.00 | `src/main/java/org/assertj/core/api/Assertions.java`, `src/test/java/org/assertj/core/error/ShouldHaveSameHashCode_create_Test.java`, `src/test/java/org/assertj/core/error/ClassModifierShouldBe_create_Test.java`, `src/test/java/org/assertj/core/api/classes/ClassAssert_hasAnnotation_Test.java`, `src/test/java/org/assertj/core/api/classes/ClassAssert_hasAnnotations_Test.java` |
| GALA | 0.00 | 空 |

LocAgent 输出片段：

~~~text
src/main/java/org/assertj/core/internal/CommonErrors.java
function: arrayOfValuesToLookForIsEmpty
line: 29
function: iterableOfValuesToLookForIsEmpty
line: 33

src/main/java/org/assertj/core/api/AssertionsForInterfaceTypes.java
function: AssertDelegateTarget_example
line: 364
function: assertThat
line: 80

src/main/java/org/assertj/core/internal/Urls.java
function: assertHasPath
line: 56
function: assertHasUserInfo
line: 88

src/main/java/org/assertj/core/internal/OnFieldsComparator.java
function: getFields
line: 49
function: description
line: 65
~~~

CoSIL 推理片段：

~~~text
Based on the bug report and repository structure, here are the most likely culprit files for the issue where hasNoNullFieldsOrProperties() fails for delegate Map implementations:

src/main/java/org/assertj/core/api/AbstractObjectAssert.java
src/main/java/org/assertj/core/internal/Fields.java
src/main/java/org/assertj/core/internal/Properties.java
src/main/java/org/assertj/core/util/Introspection.java
src/main/java/org/assertj/core/api/AbstractMapAssert.java

Reasoning:
1. AbstractObjectAssert.java - Most likely contains the hasNoNullFieldsOrProperties() method implementation that's failing.
2. Fields.java - Handles field introspection which may be incorrectly treating Map methods as fields.
3. Properties.java - Manages property introspection.
~~~

分析：失败核心是 API facade 与 internal helper 的跨层跳转。Issue 写 `hasNoNullFieldsOrProperties()` 和 `Map` 委托实现，baseline 普遍把目标放在 `AbstractObjectAssert`、`AbstractMapAssert`、`Introspection` 或大量 internal 类上，但真实 patch 在 `PropertyOrFieldSupport.getSimpleValue`，逻辑是调整 property、field、map key 的尝试顺序。这里需要 Java API 调用链：assertion method -> property/field support -> map fallback，而不是只按类名检索。

#### 样本 `python__mypy-14569`：Python / `python/mypy`

Issue 真实问题：mypy 在 `mypy_primer` 项目 Tanjun 上出现 `Must not defer during final iteration` crash。Issue 给出了 Tanjun 仓库、相关 mypy PR 评论、触发 Tanjun commit，以及长 traceback。表层 traceback 指向 `mypy/build.py`、`mypy/semanal_main.py`、`mypy/semanal.py`，但真实修复点是 `mypy/types.py`。

URL 证据：
- https://github.com/FasterSpeeding/Tanjun
- https://github.com/python/mypy/pull/14238#issuecomment-1409828838
- https://github.com/FasterSpeeding/Tanjun/commit/942b8b47106dddee9129ec4a6be312fe3e5eeac9

Gold 文件：
- `mypy/types.py`

| Baseline | File REC@All | Top 预测文件 |
|---|---:|---|
| LocAgent | 0.00 | `mypy/semanal.py`, `mypy/semanal_main.py` |
| CoSIL | 0.00 | `mypy/semanal.py`, `mypy/semanal_main.py`, `mypy/build.py`, `mypy/semanal_shared.py`, `mypy/semanal_pass1.py` |
| GraphLocator | 0.00 | `mypy/semanal.py`, `mypy/semanal_main.py`, `mypy/nodes.py`, `mypy/build.py`, `github/workflows/mypy_primer.yml` |
| GALA | 0.00 | 空 |

LocAgent 输出片段：

~~~text
mypy/semanal.py
line: 862-864
function: SemanticAnalyzer.analyze_func_def

mypy/semanal.py
line: 5918
function: SemanticAnalyzer.defer

mypy/semanal_main.py
line: 294-295
function: process_top_level_function

mypy/semanal.py
line: 5990-6004
function: SemanticAnalyzer.process_placeholder
~~~

CoSIL 推理片段：

~~~text
Based on the bug report and traceback, the crash occurs during semantic analysis when attempting to defer in the final iteration. The error originates in mypy/semanal.py at the defer method, with the call chain involving mypy/semanal_main.py and mypy/build.py.

mypy/semanal.py
mypy/semanal_main.py
mypy/build.py
mypy/semanal_pass1.py
mypy/semanal_shared.py
~~~

分析：失败核心是 traceback 表层文件与真实语义修复点不一致。LocAgent/CoSIL/GraphLocator 都集中在 `mypy/semanal.py`、`semanal_main.py`、`build.py`，但 gold 是 `mypy/types.py`。这类 mypy crash 需要从错误栈中的 defer/final iteration 上升到类型对象和类型变量表达，而不是把最后抛错处当 patch target。

#### 样本 `tailwindlabs__tailwindcss-5470`：TypeScript / `tailwindlabs/tailwindcss`

Issue 真实问题：禁用某些 opacity plugin 后，使用 CSS custom property/function 定义的颜色失效。复现入口是 Tailwind Play；Issue 还给了一个历史 demo repo 和一个 GitHub blob 链接，指向旧的 `src/plugins/backgroundColor.js#L11`。真实修复点不是这个旧插件文件，而是当前仓库中的 `src/corePlugins.js`，需要在 opacity disabled 的早返回路径中正确调用 `toColorValue(value)`。

URL 证据：
- https://play.tailwindcss.com/YVjDQE13bj
- https://github.com/adamwathan/tailwind-css-variable-text-opacity-demo
- https://github.com/tailwindlabs/tailwindcss/blob/691ed02f6352da17048dd14f742f7c82919e1455/src/plugins/backgroundColor.js#L11

Gold 文件：
- `src/corePlugins.js`

| Baseline | File REC@All | Top 预测文件 |
|---|---:|---|
| LocAgent | 100.00 | `src/util/toColorValue.js`, `src/corePlugins.js` |
| CoSIL | 0.00 | `src/plugins/backgroundColor.js`, `src/plugins/textColor.js`, `src/plugins/ringColor.js`, `src/plugins/borderColor.js`, `src/plugins/divideColor.js` |
| GraphLocator | 0.00 | `integrations/tailwindcss-cli/src/index.css`, `tests/fixtures/tailwind-output-no-color-opacity.css`, `src/util/responsive.js`, `src/util/withAlphaVariable.js`, `github/workflows/nodejs.yml` |
| GALA | 100.00 | `src/util/withAlphaVariable.js`, `src/corePlugins.js`, `src/util/pluginUtils.js` |

LocAgent 输出片段：

~~~text
Problem Summary:
When an opacity plugin is disabled, the color plugins return value directly as the CSS property value. For colors defined as functions, this is a bug because value is the function itself, not a color string. The function is never invoked.

The fix is to replace bare value with toColorValue(value) in each early-return path. toColorValue handles function-based colors correctly by calling maybeFunction({}).

src/util/toColorValue.js
function: toColorValue
line: 1-3

src/corePlugins.js
function: backgroundColor
line: 1270-1287
function: textColor
line: 1537-1554
~~~

CoSIL 推理片段：

~~~text
The bug specifically mentions that plugins are not calling withAlphaVariable() when opacity plugins are disabled.

src/plugins/backgroundColor.js
src/plugins/textColor.js
src/plugins/borderColor.js
src/plugins/divideColor.js
src/plugins/ringColor.js

backgroundColor.js is directly mentioned in the bug report, and other color plugins follow similar patterns.
~~~

分析：这个样本体现 URL 角色混合：play.tailwindcss 是复现，GitHub blob 指向 `backgroundColor.js`，但 gold 在 `src/corePlugins.js`。CoSIL 被 blob URL 诱导到 `src/plugins/backgroundColor.js` 等旧路径；LocAgent/GALA 通过 opacity/custom property 语义扩展到 `corePlugins.js` 成功。这里需要判断 code URL 是历史实现/相关证据还是当前仓库 patch target。

#### 样本 `webpack__webpack-14782`：JavaScript / `webpack/webpack`

Issue 真实问题：Module Federation 在 `strictVersion` mismatch 时，错误消息没有说明冲突版本来自哪个 source/package。Issue 附了错误信息截图。真实修复点在 runtime 代码 `lib/sharing/ConsumeSharedRuntimeModule.js`，需要让 singleton strict version 的 invalid version message 也带上来源信息。

URL 证据：
- https://user-images.githubusercontent.com/1610882/112955615-4a96c600-9148-11eb-8d8d-7aa08ed995ac.png

图片证据：
- https://user-images.githubusercontent.com/1610882/112955615-4a96c600-9148-11eb-8d8d-7aa08ed995ac.png

Gold 文件：
- `lib/sharing/ConsumeSharedRuntimeModule.js`

| Baseline | File REC@All | Top 预测文件 |
|---|---:|---|
| LocAgent | 100.00 | `lib/sharing/ConsumeSharedRuntimeModule.js`, `lib/sharing/ShareRuntimeModule.js`, `lib/sharing/ConsumeSharedModule.js` |
| CoSIL | 0.00 | `lib/sharing/SharePlugin.js`, `lib/sharing/ConsumeSharedModule.js`, `lib/sharing/ProvideSharedModule.js` |
| GraphLocator | 0.00 | `test/configCases/asset-modules/http-url/errors.webpack.lock.data/...`, `test/statsCases/module-not-found-error/webpack.config.js`, `examples/code-splitted-require.context-amd/template.md`, `examples/code-splitted-require.context-amd/webpack.config.js`, `examples/code-splitted-require.context/template.md` |
| GALA | 100.00 | `lib/sharing/ConsumeSharedRuntimeModule.js`, `lib/sharing/ConsumeSharedPlugin.js`, `lib/sharing/utils.js`, `lib/sharing/ConsumeSharedModule.js`, `lib/container/ModuleFederationPlugin.js` |

LocAgent 输出片段：

~~~text
The from property is set in ShareRuntimeModule.js when a module is registered. It's already available as versions[key].from on each entry in the shared scope. The getInvalidVersionMessage already uses this to show Available versions with from info. The getInvalidSingletonVersionMessage does NOT include this information, which is the core of the issue.

Execution Flow:
1. A module requests a shared module with strictVersion: true and singleton: true
2. ConsumeSharedModule.codeGeneration() generates code calling loadStrictSingletonVersionCheck
3. At runtime, these call getStrictSingletonVersion()
4. If unsatisfied, it throws getInvalidSingletonVersionMessage(), which lacks source package info
~~~

CoSIL 推理片段：

~~~text
lib/sharing/SingletonVersionHelper.js
lib/sharing/ProvideSharedModule.js
lib/sharing/ConsumeSharedModule.js
lib/sharing/SharePlugin.js
lib/sharing/versionHelpers.js
~~~

分析：图片是错误信息截图，真正线索是 Module Federation、strictVersion mismatch、consume shared runtime。LocAgent/GALA 成功命中 `ConsumeSharedRuntimeModule.js`；CoSIL 停在 `SharePlugin/ConsumeSharedModule/ProvideSharedModule`，GraphLocator 偏到测试和示例文件。这里说明图片 OCR/错误消息抽取必须转成 runtime module 语义，而不是只加入“error message”文本。

### 6.7 对 022 文档结论的补充

SWE Clean15 的主要矛盾是图片/UI/渲染证据如何映射到组件、状态和渲染引擎；这个 Omni60 Mimo 包显示出的主要矛盾是跨语言 URL 与复现证据如何映射到代码结构。两者共同指向同一个框架需求：先做证据角色识别，再做语言路由和图检索。具体来说：

1. 对 URL 先分类：playground/repl、GitHub blob、issue/PR/commit、文档/API、图片 URL。不同 URL 不能统一当普通文本。

2. 对语言做 router：Java 走 facade/internal/helper 调用链；Python 走 traceback 到 semantic type/dataflow 的反向解释；TypeScript/Babel/Tailwind 走 parser/compiler/plugin pipeline；JavaScript/Webpack/Prettier 走 runtime/formatter/plugin pipeline。

3. 对图片做角色识别：SWE 里图片多是 UI/Canvas/PDF/Markdown 渲染症状；Omni 里图片少，多是错误输出截图。图片处理的目标不是生成描述，而是抽取可检索的错误文本、UI 状态、组件名、route、配置项。

4. 对 Agent 搜索增加 verifier：如果预测只命中 traceback 抛错文件、URL 直接指向文件或测试 fixture，应强制执行一次“证据文件是否 patch target”的检查，并沿调用链/数据流扩展到真正修改点。


## 7. 对现有表格的修正结论

旧表只看了 REC@All，容易得出“某类 URL/图片整体好或坏”的结论。加入 Mimo-v2.5 和真实轨迹后，应改成下面这组判断：

1. Mimo-v2.5 明显增强了语义理解，但不能自动解决证据角色问题。`Automattic__wp-calypso-21409` 中，模型理解了 email verification，却仍把证据 selector 当成 patch target。
2. URL 的价值取决于角色。直接 gold URL 是强入口；相关但非 gold 的代码 URL 是高风险干扰；历史讨论/PR 需要解析 diff、评论和文件提及；复现页面需要解析 route、输入代码和配置。
3. 图片的价值取决于能否转为可执行查询。Markdown/Canvas 更容易转成 token/API/grammar；Web UI 和 PDF 需要 route/component/layout engine 的跨层映射。
4. Baseline 的差异主要在证据利用方式：LocAgent 能通过工具搜索修正部分入口，但容易过宽；CoSIL 依赖一次性文件判断，容易被关键词牵引；GraphLocator 对初始种子敏感；GALA/BM25 在词面强的样本上稳定，但对业务流和视觉布局理解不足。

## 8. 后续框架设计建议

应把多模态证据先转换成结构化 evidence graph，再交给 Agent 搜索：

- URL resolver：区分 `gold-code-url`、`related-code-url`、`discussion-url`、`demo-url`、`docs-url`，输出 path/symbol/route/API/config，而不是只把 URL 当文本。
- Image resolver：将截图分为 UI、Canvas/chart、PDF/layout、Markdown/text-render，并输出可搜索实体，例如 route、component、event、layout primitive、grammar token。
- Evidence-to-target verifier：检查当前候选是证据入口还是 patch target，避免 `current-user/selectors.js` 这类证据文件压过真正修改链路。
- Patch closure：从命中的入口沿调用图、状态图、组件树、配置流扩展，覆盖多文件修改链。
- Failure-aware rerank：对 `相关代码但非 gold`、`Web UI`、`PDF/layout` 这些高风险类型提高验证强度，要求候选文件能解释 gold 行为改变，而不是只匹配关键词。
