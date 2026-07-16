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

```text
```
client/state/current-user/selectors.js
client/signup/config/flows.js
client/signup/steps/design-type-with-store/pressable-store/index.js
client/components/email-verification/index.js
client/signup/config/steps.js
```
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

```
src/elements/View.js
src/mixins/border.js
src/styles/stylesheet.js
src/utils/border.js
src/utils/shape.js
```
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

## 6. 对现有表格的修正结论

旧表只看了 REC@All，容易得出“某类 URL/图片整体好或坏”的结论。加入 Mimo-v2.5 和真实轨迹后，应改成下面这组判断：

1. Mimo-v2.5 明显增强了语义理解，但不能自动解决证据角色问题。`Automattic__wp-calypso-21409` 中，模型理解了 email verification，却仍把证据 selector 当成 patch target。
2. URL 的价值取决于角色。直接 gold URL 是强入口；相关但非 gold 的代码 URL 是高风险干扰；历史讨论/PR 需要解析 diff、评论和文件提及；复现页面需要解析 route、输入代码和配置。
3. 图片的价值取决于能否转为可执行查询。Markdown/Canvas 更容易转成 token/API/grammar；Web UI 和 PDF 需要 route/component/layout engine 的跨层映射。
4. Baseline 的差异主要在证据利用方式：LocAgent 能通过工具搜索修正部分入口，但容易过宽；CoSIL 依赖一次性文件判断，容易被关键词牵引；GraphLocator 对初始种子敏感；GALA/BM25 在词面强的样本上稳定，但对业务流和视觉布局理解不足。

## 7. 后续框架设计建议

应把多模态证据先转换成结构化 evidence graph，再交给 Agent 搜索：

- URL resolver：区分 `gold-code-url`、`related-code-url`、`discussion-url`、`demo-url`、`docs-url`，输出 path/symbol/route/API/config，而不是只把 URL 当文本。
- Image resolver：将截图分为 UI、Canvas/chart、PDF/layout、Markdown/text-render，并输出可搜索实体，例如 route、component、event、layout primitive、grammar token。
- Evidence-to-target verifier：检查当前候选是证据入口还是 patch target，避免 `current-user/selectors.js` 这类证据文件压过真正修改链路。
- Patch closure：从命中的入口沿调用图、状态图、组件树、配置流扩展，覆盖多文件修改链。
- Failure-aware rerank：对 `相关代码但非 gold`、`Web UI`、`PDF/layout` 这些高风险类型提高验证强度，要求候选文件能解释 gold 行为改变，而不是只匹配关键词。
