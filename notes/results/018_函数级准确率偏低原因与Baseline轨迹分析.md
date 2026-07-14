# 函数级准确率偏低原因与 Baseline 轨迹分析

本文分析为什么当前 baseline 在函数级定位上的准确率明显低于文件级定位。分析对象主要是 SWE-bench Multimodal dev 全量经过 Clean15 清洗后的 92 个样本，模型为 `qwen3-vl-8b`，并结合 LocAgent、CoSIL、GraphLocator、GALA、BM25-MMIR 的真实结果文件和日志轨迹。

核心结论是：**函数级准确率低不是单纯因为模型弱，而是因为现有方法大多停留在“找到相关文件或相关组件”的粒度，没有把 issue 证据进一步验证到具体函数的职责、调用链和 patch closure 上。** 在多模态、多 URL、多语言仓库中，这个问题会被放大。

## 1. 数据来源

本文使用的主要文件如下：

| 内容 | 路径 |
|---|---|
| LocAgent 定位输出 | `LocAgent/newtest/swebench_multimodal-full-dev/results/openai_qwen3-vl-8b/location/loc_trajs.jsonl` |
| CoSIL 文件级轨迹 | `CoSIL/newtest/swebench_multimodal-full-dev/results/openai_qwen3-vl-8b/file_level/localization_logs/*.log` |
| GraphLocator 逐样本评估 | `GraphLocator/newtest/swebench_multimodal-full-dev/results/openai_qwen3-vl-8b/eval_strict/per_instance_metrics_3level.csv` |
| GALA 中间图结果 | `GALA/mytest/swebench_multimodal-full-dev/results/qwen3-vl-8b/*/code_graph_*.json` |
| Clean15 逐样本指标 | `collected_results/qwen8b_mimo_compare_20260711_212220/.../per_instance_metrics_3level.csv` |

## 2. 现象：函数级 Acc@15 普遍低

Clean15 严格评估下，函数级 Acc@15 如下：

| Baseline | Function Acc@15 |
|---|---:|
| BM25-MMIR | 13.04 |
| GALA | 11.96 |
| LocAgent | 7.61 |
| CoSIL | 4.35 |
| GraphLocator | 3.26 |

这里的 Acc@15 是严格 full-coverage：只有 top-15 函数预测覆盖该样本所有 gold functions，才算 1。只命中其中一部分函数不会算 Acc@15 成功，只会体现在 recall/F1 中。

逐样本拆解后可以看到，函数级失败分为两类：

| Baseline | 样本数 | 文件完全未命中 | 文件命中但函数完全未命中 | 函数部分命中但未覆盖全量 | 函数全覆盖 |
|---|---:|---:|---:|---:|---:|
| LocAgent | 92 | 53 | 16 | 16 | 8 |
| CoSIL | 92 | 51 | 27 | 10 | 4 |
| GraphLocator | 92 | 63 | 16 | 10 | 3 |
| GALA | 92 | 34 | 26 | 21 | 11 |
| BM25-MMIR | 92 | 32 | 26 | 24 | 12 |

这说明函数级低分不是只有“文件没找到”导致的。即使文件命中，很多 baseline 也经常选错同文件内的函数，或者只命中一部分函数。

## 3. 为什么文件命中了，函数仍然失败

### 3.1 函数级评估要求的是“精确实体”，不是“相关代码区域”

文件级只要预测到 `src/plugins/plugin.legend.js` 就算命中文件；函数级则要求进一步命中类似：

```text
src/plugins/plugin.legend.js::handleEvent
src/plugins/plugin.legend.js::isListened
```

如果 baseline 预测了同一文件里的 `drawTitle`、`buildLabels`、`adjustHitBoxes`，它在语义上可能和 legend 相关，但函数级仍然失败。原因是这些函数不是 gold patch 实际修改的函数。

### 3.2 多模态证据通常描述 UI 症状，不直接指向函数

截图和 GIF 常常只能说明“哪个 UI 现象错了”，例如 legend、hover、click、tooltip、signup flow。它们能帮助定位到组件文件，但不能自动告诉我们具体应该改 `handleEvent`、`isListened`、`_draw` 还是 `calculateItemHeight`。

因此，函数级定位需要第二阶段：在候选文件内部做函数职责验证和修改点推断。当前 baseline 大多缺少这个阶段。

### 3.3 URL 可能是 evidence seed，不一定是 patch target

Issue 中的 GitHub URL 可能指向相关状态、复现入口、文档、配置或历史代码。它不一定就是要修改的位置。若 agent 把 URL 指向文件直接当作 target，就会导致整条搜索链偏移。

### 3.4 patch closure 会跨越多个函数

很多修复不是改一个入口函数，而是同时修改：

- 事件监听函数；
- UI 尺寸计算函数；
- 数据转换 helper；
- 类型定义；
- runtime 解析函数；
- 状态 selector/action。

这种情况下，函数级 full-coverage 很难。只找到入口函数通常仍然不够。

## 4. 失败样本一：`chartjs__Chart.js-10157`

### 4.1 问题与 gold

该样本是 Chart.js bar chart 相关问题。真实 gold 文件是：

```text
src/controllers/controller.bar.js
```

真实 gold function 是：

```text
src/controllers/controller.bar.js::_calculateBarValuePixels
```

### 4.2 LocAgent 的真实输出

来源：

```text
LocAgent/newtest/swebench_multimodal-full-dev/results/openai_qwen3-vl-8b/location/loc_trajs.jsonl
```

LocAgent 最终输出片段：

```text
src/elements/element.bar.js
function: parseBorderRadius
line: 52
function: hasRadius
line: 112

src/controllers/controller.bar.js
function: computeFitCategoryTraits
line: 61
function: computeFlexCategoryTraits
line: 89
```

### 4.3 失败原因

LocAgent 找到了正确文件 `controller.bar.js`，说明它理解了问题属于 bar controller。但是它把注意力放在 bar 布局 trait 和 bar element 绘制 helper 上，没有落到真正控制 bar value pixel 的 `_calculateBarValuePixels`。

这类失败说明：**文件级语义相关不等于函数级修改点正确。** 对 bar chart 问题来说，`computeFitCategoryTraits`、`computeFlexCategoryTraits`、`_calculateBarValuePixels` 都在同一组件语义圈内；但只有后者是真实 patch target。

### 4.4 对框架设计的启发

需要在文件命中后进行函数级验证：

1. 读取候选文件内函数列表。
2. 根据 issue 关键词拆成机制问题，例如 value pixel、base line、bar length、border radius。
3. 对每个函数生成“职责解释”。
4. 让 agent 判断哪个函数直接计算错误变量，而不是只选相关组件函数。

## 5. 失败样本二：`chartjs__Chart.js-10301`

### 5.1 问题与 gold

该样本与 legend 的 `onLeave` 事件有关。真实 gold 文件：

```text
src/plugins/plugin.legend.js
```

真实 gold functions：

```text
src/plugins/plugin.legend.js::handleEvent
src/plugins/plugin.legend.js::isListened
```

### 5.2 LocAgent 的真实输出

来源：

```text
LocAgent/newtest/swebench_multimodal-full-dev/results/openai_qwen3-vl-8b/location/loc_trajs.jsonl
```

输出片段：

```text
src/plugins/plugin.legend.js
function: handleEvent
line: 518
function: drawTitle
line: 433

src/core/core.controller.js
function: determineLastEvent
line: 94
function: getElementsAtEventForMode
line: 805
```

LocAgent 命中了 `handleEvent`，但漏掉 `isListened`，并引入了 `drawTitle` 和 controller 事件函数。因此函数 recall 部分命中，但 strict full-coverage 不成功。

### 5.3 CoSIL 的真实日志

来源：

```text
CoSIL/newtest/swebench_multimodal-full-dev/results/openai_qwen3-vl-8b/file_level/localization_logs/chartjs__Chart.js-10301.log
```

CoSIL 日志中的定位线索偏文件级：

```text
Localization clues:
- Legend interaction events (`onHover`, `onLeave`)
- Likely Legend/Chart component and event dispatch logic
```

最终文件输出：

```text
src/plugins/legend.js
src/plugins/plugin.legend.js
```

### 5.4 GraphLocator 的函数偏移

GraphLocator 在该样本中也能定位到 `plugin.legend.js`，但函数预测集中在 legend 布局和构造相关函数：

```text
src/plugins/plugin.legend.js::getBoxSize
src/plugins/plugin.legend.js::itemsEqual
src/plugins/plugin.legend.js::Legend.constructor
src/plugins/plugin.legend.js::Legend.update
src/plugins/plugin.legend.js::Legend.setDimensions
src/plugins/plugin.legend.js::Legend.buildLabels
src/plugins/plugin.legend.js::Legend.fit
src/plugins/plugin.legend.js::Legend._fitRows
src/plugins/plugin.legend.js::Legend._fitCols
src/plugins/plugin.legend.js::Legend.adjustHitBoxes
```

这些函数都属于 legend 文件，但不是 `handleEvent` 和 `isListened`。

### 5.5 失败原因

这个样本体现的是“同文件高干扰函数”问题。`plugin.legend.js` 内部既有布局、绘制、label 构造，也有事件处理。Issue 说的是 `onLeave`，所以真正应该重点检查事件监听入口和监听判断函数。

当前 baseline 的问题是：它们容易把 `Legend` 这个组件整体相关函数都列出来，但没有进一步问：**这个 issue 的触发条件是事件是否被监听，还是 label 如何绘制？**

## 6. 失败样本三：`chartjs__Chart.js-11352`

### 6.1 问题与 gold

该样本涉及多行 legend label 的点击/布局问题。真实 gold 文件：

```text
src/plugins/plugin.legend.js
```

真实 gold functions：

```text
src/plugins/plugin.legend.js::_draw
src/plugins/plugin.legend.js::calculateItemHeight
src/plugins/plugin.legend.js::calculateItemWidth
src/plugins/plugin.legend.js::calculateLegendItemHeight
```

### 6.2 CoSIL 的真实日志

来源：

```text
CoSIL/newtest/swebench_multimodal-full-dev/results/openai_qwen3-vl-8b/file_level/localization_logs/chartjs__Chart.js-11352.log
```

日志中的线索：

```text
Localization clues:
- Legend event handling
- multi-line text bounding box calculation
- right-positioned legend label hit boxes
```

最终文件输出：

```text
src/plugins/legend.js
src/plugins/plugin.legend.js
```

### 6.3 LocAgent 的真实输出

来源：

```text
LocAgent/newtest/swebench_multimodal-full-dev/results/openai_qwen3-vl-8b/location/loc_trajs.jsonl
```

LocAgent 输出：

```text
src/plugins/plugin.legend.js
function: adjustHitBoxes
line: 230
function: itemsEqual
line: 39

src/plugins/plugin.tooltip.js
function: splitNewlines
line: 106
function: getBeforeAfterBodyLines
line: 337
```

### 6.4 失败原因

该样本中，截图/GIF 能明显提示 legend 和 multi-line text，但真正 patch target 是 item width/height 计算和 `_draw`。LocAgent 和 CoSIL 都抓住了 legend，但 LocAgent 转向 hitbox 和 tooltip newline helper；CoSIL 只输出文件级结果。

这说明多模态证据需要被转成更具体的内部机制：

```text
多行 label 显示/点击区域错误
=> legend item height/width 计算错误
=> hitbox 和 draw 使用的尺寸不一致
=> calculateItemHeight / calculateItemWidth / _draw
```

如果没有这个“症状到机制”的转换，函数级定位会停在视觉相关组件层。

## 7. 失败样本四：`diegomura__react-pdf-1306`

### 7.1 问题与 gold

该样本是 React-PDF 图片 source 类型与运行时解析不一致的问题。Issue 和截图容易把注意力引到类型定义文件。真实 gold files：

```text
packages/layout/src/image/fetchImage.js
packages/layout/src/image/getSource.js
packages/layout/src/image/resolveSource.js
packages/types/image.d.ts
```

真实 gold functions：

```text
packages/layout/src/image/fetchImage.js::fetchImage
packages/layout/src/image/fetchImage.js::resolveSrc
packages/layout/src/image/getSource.js::getSource
```

注意：`packages/types/image.d.ts` 是 gold file，但它不贡献函数级 gold。函数级目标在 runtime layout image 解析代码中。

### 7.2 LocAgent 的真实输出

来源：

```text
LocAgent/newtest/swebench_multimodal-full-dev/results/openai_qwen3-vl-8b/location/loc_trajs.jsonl
```

输出片段：

```text
packages/types/image.d.ts

packages/renderer/index.d.ts
class: Note
line: 214
function: usePDF
line: 469

packages/renderer/src/index.js
function: updateContainer
line: 29
function: callOnRender
line: 52
```

### 7.3 CoSIL 的真实日志

来源：

```text
CoSIL/newtest/swebench_multimodal-full-dev/results/openai_qwen3-vl-8b/file_level/localization_logs/diegomura__react-pdf-1306.log
```

CoSIL 输出文件列表：

```text
@react-pdf/types/image.d.ts
packages/image/src/index.ts
packages/renderer/src/index.ts
packages/pdfkit/src/image/index.ts
packages/types/index.ts
packages/types/image.d.ts
packages/image/src/index.js
packages/renderer/src/index.js
packages/pdfkit/src/image/png.js
packages/types/index.d.ts
```

### 7.4 失败原因

这个样本不是“完全没找到主题”。多个 baseline 都知道问题和 image source 类型有关，也能找到 `packages/types/image.d.ts`。失败在于它们没有继续追踪：

```text
类型定义 SourceObject
=> runtime 如何读取 source
=> getSource / resolveSource / fetchImage
=> Promise 或函数返回值如何被解析
```

这属于跨文件 patch closure：类型定义是 evidence/接口，真正函数修改在 runtime layout image pipeline。现有 baseline 容易把类型文件当作终点，而不是把它作为入口继续做调用链和数据流扩展。

## 8. 失败样本五：`Automattic__wp-calypso-21409`

### 8.1 问题与 gold

该样本 issue 提供了两个 UI 截图，并给出代码 URL：

```text
https://github.com/Automattic/wp-calypso/blob/master/client/state/current-user/selectors.js#L157
```

该 URL 指向：

```text
client/state/current-user/selectors.js
157: export const isCurrentUserEmailVerified = createCurrentUserSelector( 'email_verified', false );
```

但真实修改集中在 WooCommerce dashboard / address / store location setup flow：

```text
client/extensions/woocommerce/app/dashboard/index.js
client/extensions/woocommerce/app/dashboard/setup-footer.js
client/extensions/woocommerce/app/dashboard/store-location-setup-view.js
client/extensions/woocommerce/components/address-view/index.js
client/extensions/woocommerce/components/form-location-select/states.js
client/extensions/woocommerce/lib/countries/index.js
client/extensions/woocommerce/state/sites/locations/selectors.js
client/extensions/woocommerce/state/sites/settings/actions.js
```

### 8.2 LocAgent 的真实输出

来源：

```text
LocAgent/newtest/swebench_multimodal-full-dev/results/openai_qwen3-vl-8b/location/loc_trajs.jsonl
```

输出片段：

```text
client/state/current-user/selectors.js
function: createCurrentUserSelector
line: 45
function: getCurrentUserSiteCount
line: 72

client/state/themes/selectors.js
function: isDownloadableFromWpcom
line: 676
function: getThemePurchaseUrl
line: 419

client/state/ui/selectors.js
function: isPreviewShowing
line: 125
function: hasSidebar
line: 129
```

### 8.3 GraphLocator 的偏移

GraphLocator 在该样本上预测到 signup/Jetpack connect 相关文件：

```text
client/jetpack-connect/signup.js
function: componentWillMount
function: componentDidMount
function: render
```

这些文件和 signup 流程相关，但不在 WooCommerce dashboard/address setup 的 gold patch 中。

### 8.4 失败原因

URL 是有效证据，但只是“email verified 状态来源”。真正需要修改的是 WooCommerce flow 如何使用这个状态、如何阻断 dashboard/address setup。当前 baseline 普遍没有区分：

```text
evidence seed: current-user selector
patch target: WooCommerce dashboard/address setup flow
```

因此搜索从 selector 和 signup 泛化入口开始，最终没有进入真实的 WooCommerce patch closure。

## 9. 成功反例：`Automattic__wp-calypso-26008`

该样本说明函数级定位不是不可做，而是需要强证据和正确的机制链。

Gold 中包含：

```text
client/lib/post-normalizer/rule-content-detect-polls.js::detectPolls
```

CoSIL、GALA、GraphLocator 都能命中 `detectPolls`。原因是 issue 语义和函数名高度对应，文件名也直接表达职责：

```text
rule-content-detect-polls.js
detectPolls
```

这个反例说明：当函数名、文件名、issue 语义有稳定映射时，现有 baseline 可以成功。它们失败最多的地方，是“症状和函数职责之间需要跨文件、跨图或跨模态推理”的样本。

## 10. 各 baseline 的函数级短板

### 10.1 LocAgent

LocAgent 的强项是能用 LLM 搜索代码、解释 issue、给出文件和函数候选。问题是它经常在文件级或组件级停止，最终函数列表来自“相关函数枚举”，而不是“修改点验证”。

典型表现：

- `chartjs__Chart.js-10157`：找到 bar controller，但选了 category trait 函数，漏掉 `_calculateBarValuePixels`。
- `chartjs__Chart.js-10301`：命中 `handleEvent`，但漏掉 `isListened`。
- `diegomura__react-pdf-1306`：被 `types/image.d.ts` 牵引，没有沿数据流进入 layout image runtime。

改进方向：LocAgent 需要在候选文件内增加函数级 verifier，要求每个预测函数都回答“它修改了哪个变量/状态/事件条件，为什么能解释 issue”。

### 10.2 CoSIL

CoSIL 的日志主要是文件级定位。它经常能输出正确文件，但缺少函数级交互式确认。

典型表现：

- `chartjs__Chart.js-10301`：日志明确提到 legend interaction events，并输出 `plugin.legend.js`，但函数级仍然不足。
- `chartjs__Chart.js-11352`：日志抓到 multi-line text bounding box，但只停留在文件列表。
- `diegomura__react-pdf-1306`：类型文件和 image package 被列出，但没有识别 runtime layout image functions。

改进方向：CoSIL 需要把 file-level localization 扩展成 file-to-function localization：对每个候选文件抽取函数列表，再根据 issue 机制排序。

### 10.3 GraphLocator

GraphLocator 的图和因果链能帮助扩展相关实体，但如果初始 seed 偏了，图扩展会扩大偏移；如果初始文件正确，也容易选同文件内中心性更强或邻近更多的函数，而不是 patch 修改函数。

典型表现：

- `chartjs__Chart.js-10301`：同在 `plugin.legend.js`，但预测大量布局/构造函数，漏掉 `handleEvent/isListened`。
- `chartjs__Chart.js-11352`：能部分命中 `_draw`，但不能覆盖所有尺寸计算函数。
- `Automattic__wp-calypso-21409`：从 signup/Jetpack connect 扩展，未进入 WooCommerce dashboard/address flow。

改进方向：图扩展不能只按结构邻近，需要加入 issue 机制类型。例如事件问题优先 event listener/filter 函数，布局问题优先 size/measure/draw 函数，数据解析问题优先 parser/normalizer/resolve 函数。

### 10.4 GALA

GALA 在 Clean15 下文件级表现相对更好，说明视觉/代码图对齐有价值。但函数级仍然低，原因是视觉证据通常只能给到组件级，而函数级需要更细的内部职责映射。

典型表现：

- Chart.js legend 相关样本能进入 legend 文件，但容易在 draw、layout、event、label helper 之间混淆。
- 对 React-PDF 类型/图片问题，视觉和文本证据能指向 image/type，但不一定能推到 runtime resolve/fetch functions。

改进方向：GALA 需要把视觉区域转换成机制标签，例如 `legend-hitbox`、`legend-text-size`、`bar-value-pixel`，再用机制标签约束函数排序。

### 10.5 BM25-MMIR

BM25-MMIR 的优势是 lexical recall，能命中不少显式关键词相关文件。但函数级准确率仍不高，因为 BM25 不理解函数职责，只是按词项相似度排序。

典型表现：

- 当函数名直接匹配 issue，如 `detectPolls`，表现较好。
- 当 issue 只描述 UI 现象或类型错误，BM25 会返回大量词面相关文件，函数级噪声很高。

改进方向：BM25 适合作为第一阶段召回，不适合作为最终函数级排序器。后面必须接结构化 rerank 和 verifier。

## 11. 对新框架的直接启发

函数级准确率低说明我们需要一个“文件命中之后”的专门阶段，而不是只做更强召回。建议框架分成以下步骤：

1. **证据角色识别**：区分截图、网页 URL、代码 URL、文档 URL、错误栈、复现入口分别是 evidence seed 还是 patch target。
2. **症状到机制转换**：把 UI/URL/text 证据转换成机制标签，如 event listener、hitbox、layout size、state selector、runtime resolver、normalizer。
3. **候选文件内部函数抽取**：读取候选文件中的函数、类、起止行和 docstring/comment。
4. **函数职责解释**：为每个候选函数生成简短职责描述，避免只按函数名或图邻近排序。
5. **patch closure 扩展**：从入口函数沿调用链、数据流、类型接口扩展到 helper/runtime 函数。
6. **函数级 verifier**：要求每个预测函数回答三个问题：
   - 它和 issue 症状之间的机制关系是什么？
   - 它修改后会影响哪个状态、事件、布局或数据流？
   - 它是否只是 evidence seed，而不是真正 patch target？

## 12. 总结

当前 baseline 函数级准确率低，主要暴露出三个问题：

1. **定位粒度不足**：很多方法能找到相关文件，但不能在文件内部选出真实修改函数。
2. **证据角色混淆**：URL、截图、类型文件经常被当成 patch target，而不是 evidence seed。
3. **缺少 patch closure 推理**：真实修复常跨入口函数、helper、类型定义和 runtime 解析函数，现有方法很少系统追踪这条链。

因此后续方法创新不应只强调“更多模态输入”或“更大的代码图”，而应强调：**多模态证据驱动的函数级机制验证与 patch closure 推理**。这才直接对应当前实验中函数级指标低的问题。
