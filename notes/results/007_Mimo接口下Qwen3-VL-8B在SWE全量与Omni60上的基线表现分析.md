# Mimo 接口下 Qwen3-VL-8B 在 SWE 全量与 Omni60 上的基线表现分析

本文分析两组已经完成的 `openai_qwen3-vl-8b` 结果：

- **SWE-bench Multimodal dev 全量**：102 个样本。
- **OmniGIRL unified60 子集**：60 个样本。

这里说的 “Mimo 测试” 指通过 OpenAI-compatible/Mimo 服务接口调用的 `Qwen3-VL-8B` 结果；实际结果目录名是 `openai_qwen3-vl-8b` 或 `qwen3-vl-8b`。本文不把 `mimo-v2.5` 结果混进来。

## 1. 数据源与评估口径

主要结果文件：

| 数据集 | Baseline | 结果目录 |
|---|---|---|
| SWE 全量 | LocAgent | `LocAgent/newtest/swebench_multimodal-full-dev/results/openai_qwen3-vl-8b` |
| SWE 全量 | CoSIL | `CoSIL/newtest/swebench_multimodal-full-dev/results/openai_qwen3-vl-8b` |
| SWE 全量 | GraphLocator | `GraphLocator/newtest/swebench_multimodal-full-dev/results/openai_qwen3-vl-8b` |
| SWE 全量 | GALA | `GALA/mytest/swebench_multimodal-full-dev/results/qwen3-vl-8b` |
| Omni60 | LocAgent | `LocAgent/newtest/omnigirl-unified60/results/openai_qwen3-vl-8b` |
| Omni60 | CoSIL | `CoSIL/newtest/omnigirl-unified60/results/openai_qwen3-vl-8b` |
| Omni60 | GraphLocator | `GraphLocator/newtest/omnigirl-unified60/results/openai_qwen3-vl-8b` |
| Omni60 | GALA | `GALA/mytest/omnigirl-unified60/results/qwen3-vl-8b` |
| Omni60 | BM25-MMIR | `MM-IR/results/omnigirl-unified60/bm25-mmir` |

指标使用 strict 三层评估：

- **File@K / Module@K / Function@K**：前 K 个预测必须覆盖该层全部 gold，才算成功。比如一个样本 gold file 有 3 个，top-8 只命中 2 个，File@8 仍然是 0。
- **MRR@15**：第一个正确目标出现得越靠前越高。它比 Acc@K 更宽松，能反映“是否至少靠近了答案”。
- **REC / PRE / F1**：集合级召回、精度和 F1。它允许部分命中，因此常常比严格 Acc 更能看出 baseline 是否“找到了部分相关位置”。
- **Empty**：预测为空的比例。Empty 高通常说明模型调用、解析或结果过滤阶段不稳定。

## 2. 两个数据集的定位难点差异

| 数据集 | 样本数 | 模态构成 | 主语言 | 图片均值 | 网页 URL 均值 | Gold 文件均值 | Hunk 均值 | Gold Function 均值 |
|---|---:|---|---|---:|---:|---:|---:|---:|
| SWE-bench Multimodal dev 全量 | 102 | 84 个图片+网页 URL，18 个仅图片 | 以 JavaScript/JSX 为主 | 2.95 | 2.02 | 3.87 | 9.35 | 5.46 |
| OmniGIRL unified60 | 60 | 26 个仅网页 URL，15 个纯文本，12 个仅图片，7 个图片+网页 URL | JavaScript、Java、Python、TypeScript 混合 | 0.57 | 0.65 | 1.13 | 1.58 | 1.12 |

这两个集合的难点不一样：

1. **SWE 全量更像前端多模态大型仓库定位**。它几乎每个样本都有图片，绝大多数还有网页 URL；但 gold patch 往往是多文件、多 hunk、多函数，尤其 `wp-calypso`、`p5.js`、`react-pdf` 这类仓库里，UI 现象和真实修改文件之间有较长的语义距离。
2. **Omni60 更像跨语言小补丁定位**。它文件数和 hunk 数都小很多，但语言更杂，Java/Python/TypeScript 的结构和命名风格差异更大。这里不是“多模态很多”导致难，而是“跨语言、跨仓库、同名 API 或工具类很多”导致错。
3. **函数级定位不是文件级定位的简单缩小版**。SWE 全量失败样本的平均 hunk 数明显更高；Omni60 虽然多是单文件，但仍有不少 gold function 无法映射或落在顶层代码、配置、测试数据区域。

## 3. 总体指标对比

### 3.1 SWE-bench Multimodal dev 全量

| Baseline | Eval | File@1 | File@8 | File@15 | File MRR | Empty | Module@8 | Function@8 | File REC@15 | File F1@15 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 102 | 9.80 | 17.65 | 18.63 | 30.78 | 4.90 | 17.65 | 6.86 | 24.94 | 14.30 |
| CoSIL | 102 | 10.78 | 18.63 | 18.63 | 37.01 | 0.00 | 15.69 | 4.90 | 27.59 | 18.59 |
| GraphLocator | 102 | 5.88 | 6.86 | 6.86 | 23.56 | 0.00 | 8.82 | 3.92 | 13.76 | 13.18 |
| GALA | 102 | 10.78 | 25.49 | 25.49 | 47.40 | 0.00 | 11.76 | 6.86 | 39.55 | 23.99 |

SWE 全量上，**GALA 的 file-level 最强**：File@8/15 达到 25.49，File MRR 也最高。它的图像检索和 seed file 机制对前端 UI 类问题更有帮助，至少能把候选拉到更相关的组件区域。CoSIL 的 File MRR 和 File F1 比 LocAgent 更高，说明它经常能给出较靠前、较集中的文件候选。LocAgent 的 module-level 不弱，但 file-level 在多文件 gold 上受 strict full-coverage 影响很大。GraphLocator 的结构图方法在 SWE 全量上召回不足，File@8 只有 6.86。

### 3.2 OmniGIRL unified60

| Baseline | Eval | File@1 | File@8 | File@15 | File MRR | Empty | Module@8 | Function@8 | File REC@15 | File F1@15 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 60 | 23.33 | 46.67 | 46.67 | 32.06 | 0.00 | 26.67 | 10.00 | 47.78 | 9.15 |
| CoSIL | 60 | 30.00 | 38.33 | 38.33 | 35.14 | 5.00 | 31.67 | 1.67 | 39.44 | 16.72 |
| GraphLocator | 60 | 16.67 | 30.00 | 31.67 | 23.36 | 0.00 | 11.67 | 10.00 | 32.78 | 20.49 |
| GALA | 60 | 6.67 | 20.00 | 20.00 | 12.83 | 43.33 | 6.67 | 3.33 | 21.39 | 7.67 |
| BM25-MMIR | 60 | 8.33 | 40.00 | 43.33 | 20.09 | 0.00 | 18.33 | 16.67 | 45.56 | 6.34 |

Omni60 上，**LocAgent 的 strict File@8 最高**，说明交互式搜索和工具调用对单文件、小补丁、跨语言问题比较有效。CoSIL 的 File@1 和 File MRR 高，说明它在第一候选上更果断，但 Function@8 很低，更多停在文件级。GraphLocator 的 File F1@15 最高，原因是它输出较收敛，精度相对更好，但 strict File@8 不如 LocAgent。GALA 在 Omni60 上 Empty 达到 43.33，说明这个配置或解析链路对 Omni60 并不稳定。BM25-MMIR 在 Omni60 上很有参考价值：它不看图、不调 LLM，却能达到 File@8 40.00，说明很多 Omni60 样本的文本线索和文件名/API 名非常强。

## 4. 成功与失败样本的结构差异

### 4.1 SWE 全量：失败主要和多文件、多 hunk、长链路 UI 相关

| Baseline | File@8 成功数 | 失败数 | 成功样本平均 Gold 文件 / 图片 / URL / Hunk | 失败样本平均 Gold 文件 / 图片 / URL / Hunk |
|---|---:|---:|---|---|
| LocAgent | 18 | 84 | 1.22 / 3.50 / 1.94 / 2.17 | 4.44 / 2.83 / 2.04 / 10.89 |
| CoSIL | 19 | 83 | 1.21 / 3.32 / 2.32 / 2.05 | 4.48 / 2.87 / 1.95 / 11.02 |
| GraphLocator | 7 | 95 | 1.00 / 2.57 / 2.71 / 1.71 | 4.08 / 2.98 / 1.97 / 9.92 |
| GALA | 26 | 76 | 1.27 / 2.65 / 2.27 / 2.27 | 4.76 / 3.05 / 1.93 / 11.78 |

这个对比非常清楚：SWE 全量里，所有 baseline 成功的样本都更接近“单文件、少 hunk”；失败样本的 gold 文件数和 hunk 数都明显更高。也就是说，模型不是完全看不懂多模态输入，而是很难从 UI 现象一路稳定展开到多个真实修改点。

### 4.2 Omni60：失败不一定是“大 patch”，更多是跨语言和命名歧义

| Baseline | File@8 成功数 | 失败数 | 成功样本平均 Gold 文件 / 图片 / URL / Hunk | 失败样本平均 Gold 文件 / 图片 / URL / Hunk |
|---|---:|---:|---|---|
| LocAgent | 28 | 32 | 1.04 / 0.50 / 0.46 / 1.43 | 1.22 / 0.62 / 0.81 / 1.72 |
| CoSIL | 23 | 37 | 1.00 / 0.13 / 0.48 / 1.30 | 1.22 / 0.84 / 0.76 / 1.76 |
| GraphLocator | 18 | 42 | 1.00 / 0.17 / 0.44 / 1.33 | 1.19 / 0.74 / 0.74 / 1.69 |
| GALA | 12 | 48 | 1.00 / 1.00 / 1.08 / 1.17 | 1.17 / 0.46 / 0.54 / 1.69 |

Omni60 的成功和失败在 gold 文件数、hunk 数上差异不大。这说明它的主要难点不是 patch 大，而是：

- Java、Python、TypeScript、JavaScript 的代码组织方式差异大；
- issue 文本里经常出现抽象 API、测试名、报错名，容易把模型引到邻近但不正确的工具类或测试文件；
- 有些样本的 gold module/function 为 0，说明真实修改落在顶层、配置或结构解析不到的实体里，函数级指标天然更难解释。

## 5. Baseline 逐项分析

### 5.1 LocAgent

LocAgent 在 Omni60 上最强，File@8 达到 46.67。它的优势来自交互式工具搜索：当样本是单文件、小 hunk，且 issue 文本里有足够的类名、函数名、错误信息时，LocAgent 能通过 repository search 找到正确区域。

但在 SWE 全量上，LocAgent 的 File@8 只有 17.65。失败样本常见两个模式：

1. **多文件 gold 无法完整覆盖**。SWE strict 指标要求 top-k 覆盖全部 gold 文件；如果 gold 有 7 到 10 个文件，LocAgent 即使命中一部分，也会被算作 File@K 失败。
2. **搜索扩散到通用 state/selectors/utils 文件**。在 `wp-calypso` 这种仓库中，很多 UI 问题都会经过 `state`、`selectors`、`utils`，LocAgent 容易把这些共享层误认为主要修改点。

因此 LocAgent 更适合 Omni60 这种“小而准”的定位；面对 SWE 全量多文件 UI 补丁时，需要更强的候选聚类和多文件扩展策略。

### 5.2 CoSIL

CoSIL 在 SWE 全量的 File MRR 最高的非 GALA baseline，File@1 也略高于 LocAgent。它的输出更像“文件级候选列表”，通常较集中，Empty 也较低。SWE 全量里 CoSIL `found_files` 非空率为 100%，说明运行链路比较稳定。

不足是 module/function 级明显弱。Omni60 上 CoSIL File@1 是 30.00，但 Function@8 只有 1.67。这说明 CoSIL 经常能找到一个语义相关文件，但没有稳定下钻到具体函数或方法。对跨语言数据集来说，CoSIL 的文件级定位可作为候选召回，但实体级分析还需要另一个结构化阶段。

### 5.3 GraphLocator

GraphLocator 的特点是输出更收敛，Omni60 的 File F1@15 最高，说明它在少量候选场景下精度不错。但 SWE 全量 File@8 只有 6.86，主要问题是图遍历召回不足。

从日志看，GraphLocator 在 SWE 全量中出现过 `Max turn reached, stopping.`，并且会在一些 p5.js 样本里反复围绕 `friendly_errors` 等图节点探索。这说明它有时能抓住一个合理的语义簇，但没有足够预算或策略跳到真正修改的多个文件。对于多 hunk、多组件问题，图遍历的局部性会变成限制。

### 5.4 GALA

GALA 在 SWE 全量上 file-level 最强，File@8/15 是 25.49，File MRR 是 47.40。它对 SWE 这种前端多模态集合更有优势，原因大概率是图像检索、seed file 和代码候选融合能更早把搜索拉到 UI 相关文件。

但 GALA 在 Omni60 上表现很不稳定，Empty 达到 43.33。这不是 Omni60 本身更难，而是 GALA 当前配置更偏多模态前端场景；遇到 Java/Python/纯文本样本时，图像检索或种子生成阶段可能给不出有效候选。GALA 更适合作为 SWE 多模态前端基线，暂时不适合作为 Omni60 跨语言稳定基线。

### 5.5 BM25-MMIR

BM25-MMIR 只在 Omni60 这里作为参考。它不使用 LLM，也不使用图片，但 File@8 达到 40.00，说明 Omni60 里很多问题有强词面线索。它的问题是 precision 很低，File F1@15 只有 6.34，因为 BM25 往往给出很多相似 API、测试文件或同名工具类。

一个合理用法是：把 BM25 作为低成本候选召回器，再交给 LocAgent/CoSIL/GALA 做重排和解释；不要直接把 BM25 当最终定位器。

## 6. 具体失败样本复盘

### 6.1 SWE: `Automattic__wp-calypso-21409`

样本特征：图片+网页 URL，JavaScript，gold file=10，gold function=10，hunk=37。所有 baseline 的 File@8 都失败。

真实修改集中在 WooCommerce dashboard/location/settings 相关文件：

- `client/extensions/woocommerce/app/dashboard/index.js`
- `client/extensions/woocommerce/app/dashboard/store-location-setup-view.js`
- `client/extensions/woocommerce/components/form-location-select/states.js`
- `client/extensions/woocommerce/lib/countries/index.js`
- `client/extensions/woocommerce/state/sites/settings/actions.js`

各 baseline 的主要偏移：

- LocAgent 预测到 `client/state/current-user/selectors.js`、`client/state/themes/selectors.js`、`client/state/ui/selectors.js` 等通用 state/selectors。
- CoSIL 预测到 `client/signup/steps/site/index.jsx`、`design-type-with-store`、`plans` 等注册/开店流程。
- GraphLocator 预测到 `client/jetpack-connect/signup.js`。
- GALA 也偏到 signup/design/plans 相关文件。

这个例子说明：**多模态 UI 线索能提示“店铺、站点、设置”这一类概念，但在 `wp-calypso` 里 WooCommerce、Jetpack、signup、plans 都有相近词汇，baseline 很容易被产品语义相似性带偏。**

### 6.2 SWE: `Automattic__wp-calypso-21492`

样本特征：图片+网页 URL，gold file=2，hunk=5。看起来比上一个简单，但所有 baseline 仍失败。

真实文件：

- `client/jetpack-connect/authorize.js`
- `client/jetpack-connect/utils.js`

预测偏移：

- LocAgent 预测到 `jetpack-connect/plans*.jsx` 和 `state/sites/selectors.js`。
- CoSIL 预测到 `jetpack-connect/index.js`、`jetpack-new-site`、`state/jetpack/connection/reducer.js`。
- GraphLocator 预测到 `state/jetpack-connect/reducer/*`。
- GALA 预测到 `site-url-input.jsx`、`plans.jsx`、`install-step.jsx`、`signup.js`。

这不是完全“找错仓库区域”，而是**找到了 Jetpack 相关区域但没找到 authorize/utils 的精确文件**。这类样本说明：File@K strict 对“同一功能簇内的精确文件选择”非常敏感。

### 6.3 SWE: `Automattic__wp-calypso-22026`

样本特征：仅图片，无网页 URL，gold file=8，hunk=22。真实修改横跨 WooCommerce 设置、税费、支付、shipping、dashboard 和样式文件。

几个 baseline 都偏向单一组件或通用 UI：

- LocAgent 进入 `state/themes/utils.js`、`state/ui/editor/image-editor/actions.js` 等通用路径。
- CoSIL 预测到 `async-load`、`spinner`、`form-fieldset`。
- GraphLocator 只给出 `woocommerce/app/settings/shipping/shipping-origin.js`。
- GALA 预测到 `store-address`、`form-dimensions-input` 等 WooCommerce 组件。

GALA 和 GraphLocator 至少靠近 WooCommerce 设置区域，但 strict File@8 仍失败，因为 gold 是多文件、多 hunk。这个例子体现了 **“仅图片 + 多文件 UI 重构”** 对所有 baseline 都很难。

### 6.4 Omni60: `prettier__prettier-12177`

样本特征：图片+网页 URL，JavaScript，gold file=2，hunk=4。真实文件：

- `src/language-js/comments.js`
- `src/language-js/printer-estree.js`

预测偏移：

- LocAgent 只预测到 `src/language-js/print/statement.js`。
- CoSIL 预测到 `print/jsx.js`、`parse/postprocess/index.js`、`main/core.js`。
- GraphLocator 偏向测试和内部 eslint rule。
- GALA 预测到 `print/block.js`、`print/comment.js`、`print/statement.js`、`print/misc.js`。
- BM25 受到 website、tests、parser-api 等词面干扰。

这些预测并非完全无关，都围绕 JavaScript printer/comment 生态，但没有覆盖真实的 `comments.js` 和 `printer-estree.js`。这说明 Omni60 里即使 patch 很小，**同一语言子系统里的相邻文件也足够多，精确文件定位仍然困难。**

### 6.5 Omni60: `babel__babel-16377`

样本特征：仅网页 URL，TypeScript，gold file=1，function gold=0。真实文件：

- `packages/babel-traverse/src/scope/index.ts`

预测偏移：

- LocAgent 偏到 `babel-types` builders/validators/definitions。
- CoSIL 偏到 `transform-typescript`、`transform-classes`、`parser/typescript`。
- GraphLocator 偏到 `helper-create-class-features-plugin` 和 `babel-types` TypeScript definitions。
- GALA 偏到 generator/classes/methods 和 transform-typescript。

这个例子典型地说明跨语言/跨包命名歧义：issue 线索里只要出现 TypeScript、scope、class、type，Babel 仓库里就有很多非常相似的包路径。真实文件在 `babel-traverse/src/scope`，但模型容易被 `babel-types` 或 `transform-typescript` 吸走。

### 6.6 Omni60: `assertj__assertj-225`

样本特征：纯文本，Java，gold file=1。真实文件：

- `src/main/java/org/assertj/core/internal/Diff.java`

预测偏移：

- LocAgent 预测到 `Files.java`、`FieldUtils.java`、`Assertions.java`、`Strings.java`。
- CoSIL 预测到 `AbstractFileAssert.java`、`CharSequenceAssert.java` 等 API 层文件。
- GraphLocator 预测到 `Assertions.java`、error 类、测试文件。
- GALA 输出为空。
- BM25 预测到 diff 相关测试、file content 测试和工具类。

这里 BM25 的失败很有代表性：它能抓到 `diff`、`file`、`content` 这些词，但容易优先返回测试文件和工具类，而不是 `internal/Diff.java`。LLM baseline 则倾向于把用户可见 API 层当成修改点。

## 7. 结论与改进方向

### 7.1 对 SWE 全量

SWE 全量的核心问题不是“有没有图片”，而是**图片和网页 URL 指向的是 UI 现象，真实 patch 经常分散在多个组件、state、utils、样式和业务逻辑文件里**。失败样本平均 gold 文件数和 hunk 数显著更高，说明多文件扩展能力是瓶颈。

建议：

- 用 GALA 或图像检索先找 UI 相关候选，再用 LocAgent/CoSIL 做代码搜索和多文件扩展。
- 对 `wp-calypso` 这类大型前端仓库增加产品域 disambiguation，比如 WooCommerce、Jetpack、signup、plans、settings 不应只靠关键词相似度。
- strict Acc 之外要同时报告 partial recall/F1，因为多文件样本中“命中部分文件”也有分析价值。

### 7.2 对 Omni60

Omni60 更适合测试跨语言泛化。LocAgent 在这里最稳定，但 BM25-MMIR 也能达到很高 file recall，说明文本线索很强。真正的问题在于精确文件和实体选择。

建议：

- 把 BM25/MMIR 当第一阶段候选召回，再做 LLM 重排。
- 对 Java/Python/TypeScript 分别加语言特定的结构提示，比如 package/module/class/function 的路径关系。
- 对 gold module/function 为 0 的样本单独标注，避免把“不可映射实体”误解释成函数级定位失败。

### 7.3 对各 baseline 的使用建议

| Baseline | 更适合 | 主要短板 | 建议角色 |
|---|---|---|---|
| LocAgent | Omni60 小补丁、跨语言工具搜索 | SWE 多文件 UI 补丁容易扩散 | 交互式精定位和二阶段验证 |
| CoSIL | 文件级候选、较集中预测 | 函数级下钻弱 | 文件候选生成器 |
| GraphLocator | 结构明确、候选少的场景 | 图遍历召回不足，长链路会卡在局部 | 精度型结构补充 |
| GALA | SWE 前端多模态场景 | Omni60 Empty 高，跨语言不稳 | 多模态 seed / UI 候选生成 |
| BM25-MMIR | 文本线索强、API 名明显 | 不看图，候选多，precision 低 | 低成本召回器 |

整体判断：**SWE 全量更需要多模态 UI 证据与多文件扩展结合；Omni60 更需要跨语言结构理解与精确重排。** 当前没有一个 baseline 同时稳定覆盖这两类能力，后续更值得做的是“检索召回 + 多模态 seed + 工具式验证”的组合式定位流程。
