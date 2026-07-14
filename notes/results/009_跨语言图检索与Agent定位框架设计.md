# 跨语言图检索与 Agent 定位框架设计

本文基于清洗后的 `Three-level-clean@15` benchmark 重新分析多语言、多模态 Issue 定位问题，并把结论落到一个可实现的 Agent 框架设计上。

这里的“清洗后”指：每个样本在 file、module、function 三层都有非空 gold，并且每层 gold 数量都不超过 15。这样 `Acc@15` 才是在评估模型能否在 top15 内覆盖所有真实目标，而不是被 `gold > 15` 的样本天然卡死。清洗规则和样本分布见 `010_三层定位评估样本清洗与可评估性分析.md`。

## 1. Clean15 后的核心结论

Clean15 去掉了两类会扭曲主指标的样本：

- `gold > 15` 的长尾大补丁：例如 `diegomura__react-pdf-1285`、`Automattic__wp-calypso-25160`、`webpack__webpack-15579`。
- module/function 不可映射样本：例如很多 OmniGIRL 样本真实修改了文件，但修改行落在配置、顶层代码、测试数据、样式或结构抽取器无法识别的区域。

但清洗后，baseline 仍然有明显失败。这说明主要瓶颈不只是 benchmark 不公平，而是：

1. **Issue 证据没有被结构化使用**：图片、URL、报错、复现步骤、文档链接没有稳定转成代码搜索约束。
2. **跨语言实体图不统一**：JS/TS、Python、Java、CSS/MDX/JSON 的 import、调用、类型、配置关系差异很大，统一用文本搜索或单一调用图不够。
3. **Agent 搜索动作缺少状态约束**：日志中反复出现空 search terms、搜索预算耗尽、图缓存缺失后临时构图。
4. **仓库级长链路没有闭环**：UI 组件、状态 selector、工具函数、测试文件、配置文件之间存在 patch closure，单点 top-k 很容易命中入口但漏掉关联文件。

因此本文提出的方向不是“再堆一个更大的召回器”，而是一个 **跨语言证据图驱动的 Agent 定位框架**：让 Agent 在每一步搜索前明确语言、证据、图关系和停止条件。

## 2. Clean15 指标：需要关注 Acc@1 到 Acc@15 的完整曲线

下面的表都使用严格 full-coverage Acc：只有 top-k 预测覆盖该层所有 gold 目标时才记为 1。`MRR@15` 更关注第一个正确目标出现的位置，`MAP@15` 更关注 top15 内正确目标的排序质量。

### 2.1 SWE-bench Multimodal full-dev Clean15 / Mimo-v2.5

SWE full-dev Clean15 有 92 个样本。这个集合仍然保留多图、多 URL、多文件、多 hunk 的特征，但去掉了超大补丁和不可映射样本。

#### File 层

| 方法 | Acc@1 | Acc@3 | Acc@5 | Acc@8 | Acc@10 | Acc@12 | Acc@13 | Acc@15 | MRR@15 | MAP@15 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 25.00 | 40.22 | 41.30 | 41.30 | 42.39 | 42.39 | 42.39 | 42.39 | 73.24 | 53.02 |
| CoSIL | 15.22 | 23.91 | 26.09 | 26.09 | 26.09 | 26.09 | 26.09 | 26.09 | 58.79 | 37.07 |
| GraphLocator | 4.35 | 7.61 | 8.70 | 8.70 | 9.78 | 10.87 | 10.87 | 11.96 | 22.73 | 12.45 |
| GALA | 13.04 | 29.35 | 39.13 | 39.13 | 39.13 | 39.13 | 39.13 | 39.13 | 58.62 | 41.43 |
| BM25-MMIR | 5.43 | 11.96 | 17.39 | 21.74 | 27.17 | 29.35 | 29.35 | 30.43 | 35.09 | 21.32 |

#### Module 层

| 方法 | Acc@1 | Acc@3 | Acc@5 | Acc@8 | Acc@10 | Acc@12 | Acc@13 | Acc@15 | MRR@15 | MAP@15 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 9.78 | 18.48 | 23.91 | 30.43 | 33.70 | 40.22 | 41.30 | 43.48 | 31.18 | 24.71 |
| CoSIL | 9.78 | 22.83 | 23.91 | 25.00 | 25.00 | 25.00 | 25.00 | 25.00 | 34.48 | 24.43 |
| GraphLocator | 4.35 | 10.87 | 11.96 | 13.04 | 13.04 | 13.04 | 13.04 | 13.04 | 13.99 | 10.28 |
| GALA | 14.13 | 26.09 | 34.78 | 34.78 | 34.78 | 34.78 | 34.78 | 34.78 | 40.51 | 31.20 |
| BM25-MMIR | 5.43 | 18.48 | 20.65 | 25.00 | 29.35 | 33.70 | 35.87 | 40.22 | 26.48 | 20.56 |

#### Function 层

| 方法 | Acc@1 | Acc@3 | Acc@5 | Acc@8 | Acc@10 | Acc@12 | Acc@13 | Acc@15 | MRR@15 | MAP@15 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 3.26 | 10.87 | 14.13 | 17.39 | 18.48 | 20.65 | 21.74 | 21.74 | 22.66 | 14.76 |
| CoSIL | 1.09 | 4.35 | 5.43 | 7.61 | 7.61 | 9.78 | 10.87 | 10.87 | 10.83 | 6.96 |
| GraphLocator | 1.09 | 2.17 | 3.26 | 3.26 | 3.26 | 3.26 | 3.26 | 3.26 | 6.96 | 3.59 |
| GALA | 1.09 | 2.17 | 5.43 | 9.78 | 10.87 | 11.96 | 13.04 | 13.04 | 12.70 | 7.30 |
| BM25-MMIR | 3.26 | 6.52 | 9.78 | 11.96 | 11.96 | 11.96 | 11.96 | 13.04 | 20.35 | 11.63 |

观察：

- LocAgent 在 file/module 层最好，但 function 层只到 21.74，说明“找到文件”后没有稳定落到真实函数。
- GALA 在 SWE 多模态场景有明显 file/module 优势，说明图和视觉/描述对齐有帮助；但 function 层仍明显掉下去。
- BM25 的 Acc@1 很低，但 Acc@15 接近强 baseline，说明词法召回可作为 seed，但不能单独做最终定位。
- GraphLocator 在 Clean15 下仍弱，说明其因果链图构造和搜索对实际多语言仓库的适配不足。

### 2.2 SWE-bench Multimodal full-dev Clean15 / Qwen3-VL-8B

同一 Clean15 集合下，Qwen3-VL-8B 的整体数值低于 Mimo-v2.5，但 failure pattern 一致：file 层明显高于 function 层。

#### File 层

| 方法 | Acc@1 | Acc@3 | Acc@5 | Acc@8 | Acc@10 | Acc@12 | Acc@13 | Acc@15 | MRR@15 | MAP@15 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 9.78 | 14.13 | 16.30 | 18.48 | 18.48 | 19.57 | 19.57 | 19.57 | 32.55 | 19.77 |
| CoSIL | 10.87 | 15.22 | 18.48 | 18.48 | 18.48 | 18.48 | 18.48 | 18.48 | 37.41 | 22.95 |
| GraphLocator | 6.52 | 7.61 | 7.61 | 7.61 | 7.61 | 7.61 | 7.61 | 7.61 | 25.36 | 12.61 |
| GALA | 9.78 | 18.48 | 25.00 | 25.00 | 25.00 | 25.00 | 25.00 | 25.00 | 47.84 | 30.43 |
| BM25-MMIR | 5.43 | 11.96 | 17.39 | 21.74 | 27.17 | 29.35 | 29.35 | 30.43 | 35.09 | 21.32 |

#### Module 层

| 方法 | Acc@1 | Acc@3 | Acc@5 | Acc@8 | Acc@10 | Acc@12 | Acc@13 | Acc@15 | MRR@15 | MAP@15 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 4.35 | 9.78 | 14.13 | 19.57 | 19.57 | 19.57 | 20.65 | 21.74 | 17.48 | 12.96 |
| CoSIL | 9.78 | 16.30 | 17.39 | 17.39 | 17.39 | 17.39 | 17.39 | 17.39 | 27.99 | 20.02 |
| GraphLocator | 5.43 | 9.78 | 9.78 | 9.78 | 9.78 | 9.78 | 9.78 | 9.78 | 19.11 | 12.49 |
| GALA | 13.04 | 21.74 | 25.00 | 25.00 | 25.00 | 25.00 | 25.00 | 25.00 | 39.24 | 28.84 |
| BM25-MMIR | 5.43 | 18.48 | 20.65 | 25.00 | 29.35 | 33.70 | 35.87 | 40.22 | 26.48 | 20.56 |

#### Function 层

| 方法 | Acc@1 | Acc@3 | Acc@5 | Acc@8 | Acc@10 | Acc@12 | Acc@13 | Acc@15 | MRR@15 | MAP@15 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 0.00 | 5.43 | 6.52 | 7.61 | 7.61 | 7.61 | 7.61 | 7.61 | 8.00 | 4.62 |
| CoSIL | 3.26 | 3.26 | 4.35 | 4.35 | 4.35 | 4.35 | 4.35 | 4.35 | 9.25 | 5.27 |
| GraphLocator | 2.17 | 3.26 | 3.26 | 3.26 | 3.26 | 3.26 | 3.26 | 3.26 | 7.79 | 4.52 |
| GALA | 1.09 | 1.09 | 4.35 | 9.78 | 10.87 | 10.87 | 11.96 | 11.96 | 10.43 | 5.75 |
| BM25-MMIR | 3.26 | 6.52 | 9.78 | 11.96 | 11.96 | 11.96 | 11.96 | 13.04 | 20.35 | 11.63 |

观察：

- Qwen3-VL-8B 下，BM25 在 module/function 的 Acc@15 反而强于多轮 Agent，说明很多失败不是“没有语义能力”，而是 Agent 搜索策略没有把简单词法 seed 稳定扩展到正确实体。
- GALA 在 file/module 层强于 LocAgent，但 function 层仍低，说明图对齐能帮忙找区域，不能自动解决函数级实体闭环。

### 2.3 OmniGIRL unified60 Clean15 / Qwen3-VL-8B

Omni60 Clean15 只有 40 个样本。它比 SWE 小得多，图片少，URL 更重要，仓库语言更分散，包括 Java、Python、JavaScript/TypeScript 等。

#### File 层

| 方法 | Acc@1 | Acc@3 | Acc@5 | Acc@8 | Acc@10 | Acc@12 | Acc@13 | Acc@15 | MRR@15 | MAP@15 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 30.00 | 42.50 | 45.00 | 60.00 | 60.00 | 60.00 | 60.00 | 60.00 | 41.84 | 40.52 |
| CoSIL | 40.00 | 47.50 | 50.00 | 50.00 | 50.00 | 50.00 | 50.00 | 50.00 | 46.46 | 45.35 |
| GraphLocator | 20.00 | 25.00 | 27.50 | 30.00 | 30.00 | 30.00 | 30.00 | 32.50 | 23.71 | 23.71 |
| GALA | 7.50 | 10.00 | 12.50 | 12.50 | 12.50 | 12.50 | 12.50 | 12.50 | 10.71 | 9.88 |
| BM25-MMIR | 12.50 | 25.00 | 37.50 | 40.00 | 42.50 | 42.50 | 42.50 | 42.50 | 25.04 | 23.77 |

#### Module 层

| 方法 | Acc@1 | Acc@3 | Acc@5 | Acc@8 | Acc@10 | Acc@12 | Acc@13 | Acc@15 | MRR@15 | MAP@15 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 22.50 | 35.00 | 40.00 | 40.00 | 42.50 | 45.00 | 47.50 | 47.50 | 34.73 | 32.60 |
| CoSIL | 12.50 | 22.50 | 27.50 | 35.00 | 35.00 | 35.00 | 35.00 | 35.00 | 22.29 | 21.84 |
| GraphLocator | 12.50 | 25.00 | 25.00 | 25.00 | 25.00 | 25.00 | 25.00 | 25.00 | 20.92 | 19.42 |
| GALA | 2.50 | 7.50 | 10.00 | 10.00 | 10.00 | 10.00 | 10.00 | 10.00 | 5.21 | 5.21 |
| BM25-MMIR | 10.00 | 17.50 | 27.50 | 27.50 | 27.50 | 32.50 | 32.50 | 32.50 | 18.85 | 17.80 |

#### Function 层

| 方法 | Acc@1 | Acc@3 | Acc@5 | Acc@8 | Acc@10 | Acc@12 | Acc@13 | Acc@15 | MRR@15 | MAP@15 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 2.50 | 7.50 | 15.00 | 15.00 | 17.50 | 17.50 | 17.50 | 17.50 | 12.94 | 10.02 |
| CoSIL | 0.00 | 2.50 | 2.50 | 2.50 | 2.50 | 2.50 | 2.50 | 2.50 | 3.33 | 2.08 |
| GraphLocator | 2.50 | 17.50 | 17.50 | 17.50 | 17.50 | 17.50 | 17.50 | 17.50 | 14.58 | 12.92 |
| GALA | 0.00 | 2.50 | 2.50 | 2.50 | 7.50 | 7.50 | 7.50 | 7.50 | 1.36 | 1.47 |
| BM25-MMIR | 7.50 | 15.00 | 17.50 | 25.00 | 30.00 | 32.50 | 32.50 | 32.50 | 18.24 | 17.02 |

观察：

- Omni60 Clean15 上 BM25 function Acc@15 最高，说明跨语言场景下，函数名、类名、错误词、API 名称的词法线索很强。
- LocAgent file/module 层强，但 function 层弱，说明其多轮搜索能找对文件区域，但缺少语言特定的函数候选约束和验证。
- GALA 在 Omni60 明显弱，说明面向多模态/图对齐的策略迁移到跨语言仓库时不稳定。

## 3. Clean15 后仍失败的具体样本

### 3.1 SWE Clean15 / LocAgent Mimo 代表失败样本

这些样本都已经通过 Clean15，不存在 `gold > 15` 或实体不可映射问题。失败说明模型/Agent 本身没有把证据转换成正确的仓库路径和实体。

| 样本 | 仓库 | Gold文件数 | Gold函数数 | File REC@All | Function REC@All | Gold文件示例 | 预测文件示例 |
|---|---|---:|---:|---:|---:|---|---|
| `Automattic__wp-calypso-33948` | `Automattic/wp-calypso` | 10 | 10 | 0.0 | 0.0 | `CREDITS.md; client/lib/browser-storage/README.md; client/lib/browser-storage/bypass.ts ...` | `client/lib/localforage/index.js; client/lib/localforage/localforage-bypass.js` |
| `Automattic__wp-calypso-34820` | `Automattic/wp-calypso` | 3 | 4 | 0.0 | 0.0 | `client/lib/user/shared-utils.js; client/lib/user/user.js; server/user-bootstrap/index.js` | `client/signup/config/flows-pure.js; client/signup/steps/site-type/index.jsx; client/signup/main.jsx ...` |
| `Automattic__wp-calypso-21635` | `Automattic/wp-calypso` | 3 | 3 | 0.0 | 0.0 | `client/lib/credit-card-details/ebanx.js; client/lib/credit-card-details/masking.js; package.json` | `client/blocks/reader-subscription-list-item/index.jsx; client/blocks/reader-subscription-list-item/connected.jsx; client/blocks/reader-subscription-list-item/docs/example.jsx ...` |
| `diegomura__react-pdf-2400` | `diegomura/react-pdf` | 2 | 5 | 0.0 | 0.0 | `changeset/mighty-birds-eat.md; packages/layout/src/node/shouldBreak.js` | `packages/layout/src/steps/resolvePagination.js` |
| `Automattic__wp-calypso-25725` | `Automattic/wp-calypso` | 2 | 4 | 0.0 | 0.0 | `client/my-sites/site-settings/manage-connection/site-ownership.jsx; client/state/data-layer/wpcom/sites/plan-transfer/index.js` | `client/me/purchases/manage-purchase/purchase-meta.jsx; client/state/purchases/actions.js; client/state/purchases/reducer.js ...` |
| `processing__p5.js-3680` | `processing/p5.js` | 2 | 4 | 0.0 | 0.0 | `src/core/shape/vertex.js; src/webgl/p5.RendererGL.Immediate.js` | `utils/sample-linter.js; src/app.js; docs/preprocessor.js ...` |
| `chartjs__Chart.js-8710` | `chartjs/Chart.js` | 2 | 2 | 0.0 | 0.0 | `src/scales/scale.linearbase.js; src/scales/scale.logarithmic.js` | `src/core/core.ticks.js; src/helpers/helpers.intl.js; src/core/core.defaults.js` |
| `Automattic__wp-calypso-21492` | `Automattic/wp-calypso` | 2 | 1 | 0.0 | 0.0 | `client/jetpack-connect/authorize.js; client/jetpack-connect/utils.js` | `client/jetpack-connect/example-components/jetpack-install.jsx; client/jetpack-connect/example-components/jetpack-connect.jsx; client/jetpack-connect/example-components/jetpack-activate.jsx ...` |

这些失败可以归为四类：

- **同领域路径干扰**：`jetpack-connect` 预测到 example-components，但 gold 在 authorize/utils。Agent 找到了 feature 目录，却没有验证真实执行链。
- **同仓库邻近功能误导**：`wp-calypso` 中 `purchases`、`signup`、`browser-storage` 等目录词义接近，路径名检索容易跑偏。
- **视觉/URL 证据未转成代码约束**：Chart.js、p5.js、React-PDF 的 issue 往往包含图片或可视化链接，但 baseline 多数只把它们当文本描述。
- **patch closure 缺失**：真实修复常同时改工具函数、状态层、配置或文档；预测只命中一个入口或完全命中相邻入口。

### 3.2 Omni60 Clean15 / LocAgent Qwen 代表失败样本

| 样本 | 仓库 | Gold文件数 | Gold函数数 | File REC@All | Function REC@All | Gold文件示例 | 预测文件示例 |
|---|---|---:|---:|---:|---:|---|---|
| `tailwindlabs__tailwindcss-7588` | `tailwindlabs/tailwindcss` | 3 | 1 | 0.0 | 0.0 | `src/lib/expandApplyAtRules.js; src/lib/resolveDefaultsAtRules.js; src/util/cloneNodes.js` | `integrations/webpack-5/src/index.css; integrations/webpack-4/src/index.css; integrations/tailwindcss-cli/src/index.html ...` |
| `prettier__prettier-12177` | `prettier/prettier` | 2 | 1 | 0.0 | 0.0 | `src/language-js/comments.js; src/language-js/printer-estree.js` | `src/language-js/print/statement.js` |
| `netty__netty-13209` | `netty/netty` | 1 | 3 | 0.0 | 0.0 | `codec/src/main/java/io/netty/handler/codec/DefaultHeaders.java` | `codec-http2/src/main/java/io/netty/handler/codec/http2/ReadOnlyHttp2Headers.java; codec-http/src/main/java/io/netty/handler/codec/http/ReadOnlyHttpHeaders.java; codec-http/src/main/java/io/netty/handler/codec/http/HttpRequestDecoder.java ...` |
| `assertj__assertj-225` | `assertj/assertj` | 1 | 2 | 0.0 | 0.0 | `src/main/java/org/assertj/core/internal/Diff.java` | `src/main/java/org/assertj/core/util/Files.java; src/main/java/org/assertj/core/util/introspection/FieldUtils.java; src/main/java/org/assertj/core/util/introspection/FieldSupport.java ...` |
| `prettier__prettier-11900` | `prettier/prettier` | 1 | 2 | 0.0 | 0.0 | `src/language-handlebars/utils.js` | `website/playground/PrettierFormat.js; website/playground/codeSamples.js; website/playground/buttons.js ...` |
| `python__mypy-13481` | `python/mypy` | 1 | 2 | 0.0 | 0.0 | `mypy/binder.py` | `mypy/checker.py; mypy/messages.py; mypy/types.py ...` |
| `python__mypy-14821` | `python/mypy` | 1 | 2 | 0.0 | 0.0 | `mypy/checker.py` | `mypyc/irbuild/classdef.py; mypyc/codegen/emitclass.py; mypy/typevars.py ...` |
| `python__mypy-14926` | `python/mypy` | 1 | 2 | 0.0 | 0.0 | `mypy/nodes.py` | `mypyc/irbuild/statement.py; mypy/subtypes.py; mypy/checker.py ...` |

Omni 的失败更能体现跨语言问题：

- Java 仓库里，类名、包名、接口名、实现类之间的关系比普通文本相似度更重要。例如 Netty 的 `DefaultHeaders` 与多个 HTTP header 类词面相似，但真正入口在 codec generic header。
- Python 仓库里，类型检查器、binder、checker、nodes 的调用链复杂，错误文本常出现多个核心模块名，Agent 需要数据流/类型流约束，而不是只搜高频词。
- Prettier/Tailwind 中，语言子目录、插件目录、playground 目录、integration 目录容易造成“功能相近但层级错误”的误判。

## 4. 运行日志暴露的系统性问题

| 模式 | 代表日志 | 次数 | 含义 |
|---|---|---:|---|
| missing graph/cache | `baseline_run_logs/omnigirl_full_parallel_20260709_100049/locagent.log` | 3262 | 图缓存缺失后临时构图，容易导致耗时巨大或中断。 |
| max turn | `baseline_run_logs/swebench_multimodal_full_dev_parallel_20260708_182346/graphlocator.log` | 2 | Agent/图搜索预算耗尽，说明局部搜索没有及时收敛或反证。 |
| fallback graph | `baseline_run_logs/omnigirl_full_parallel_20260709_100049/locagent.log` | 1170 | 原始图不可用时启用多语言 fallback，说明跨语言结构索引需要一等公民化。 |
| git clone failure | `baseline_run_logs/omnigirl_full_parallel_20260709_100049/locagent.log` | 2 | 仓库准备不稳定，影响复现实验和长仓库构图。 |
| search empty terms | `baseline_run_logs/omnigirl_full_parallel_20260709_100049/locagent.log` | 6546 | Agent 工具调用 query 不完整，说明搜索动作缺少约束和状态校验。 |

日志问题和指标问题是对应的：

- `search empty terms` 对应 Agent 没有把 issue 证据转成可执行查询。
- `fallback graph` 对应跨语言结构图没有统一缓存和 schema。
- `max turn` 对应搜索过程缺少反证机制：搜错方向后继续扩展，直到预算耗尽。
- `missing graph/cache` 对应图构建太重，不适合每个 issue 临时做全仓库图。

## 5. 现有 baseline 在 Clean15 后的不足

### 5.1 LocAgent

LocAgent 的优势是多轮工具调用和仓库操作能力，Clean15 下 file/module 层表现强。但它的主要问题是：

- 搜索 action 没有强制携带 `语言、实体类型、证据来源、期望命中`。
- 找到 feature 目录后缺少 patch closure 验证，容易只停在同目录邻近文件。
- 对跨语言 repo 的图关系依赖 fallback，不能稳定表达 Java package、Python import/type、JS route/component/state、CSS/MDX/config 等异构关系。

### 5.2 CoSIL

CoSIL 的 file-level 能力相对稳定，但 function-level 明显弱。原因是它更像“文件候选生成 + 反思”，对真实函数、类、方法边界的利用不足。它适合做候选召回，不适合作为最终实体排序器。

### 5.3 GraphLocator

GraphLocator 理论上强调因果链，但在多语言、多仓库场景中容易遇到两类问题：

- 图构建成本高，缓存缺失时无法稳定运行。
- 因果链如果建立在错误 seed 上，会扩展到大量相似但错误的邻近模块。

它需要从“全仓库大图”改成“证据 seed 驱动的局部动态图”。

### 5.4 GALA

GALA 在 SWE 多模态场景 file/module 层有效，说明视觉/文本/代码图对齐是有价值的。但它在 Omni60 跨语言场景明显弱，说明其图对齐方式对 JS/TS UI 仓库更友好，对 Java/Python 后端库、编译器、类型系统不够稳。

### 5.5 BM25-MMIR

BM25 的 Acc@1 低，但 Acc@15 和 MAP 在多个场景不差。它说明词法 seed 仍是跨语言定位的强基础，但缺少：

- 语言特定的实体解释。
- 图扩展和闭包补全。
- 对图片/URL/堆栈/文档证据的结构化解析。

## 6. 框架设计：PolyGraph-Agent

### 6.1 设计目标

PolyGraph-Agent 的目标不是替代所有 baseline，而是把它们各自有效的部分组织成一个受约束的搜索框架：

- 用 BM25/Dense 做初始 seed。
- 用语言适配器解析 seed 的语义。
- 用局部异构图扩展候选。
- 用 Agent 做证据验证、反证和闭包补全。
- 用 Clean15 主集和 long-tail 诊断集分别评估。

### 6.2 总体流程

```text
Issue 文本 / 图片 / URL / 日志
        |
        v
证据帧 Evidence Frame
        |
        v
语言与任务路由 Language-Task Router
        |
        v
多路召回 BM25 + Dense + Symbol + URL/Image Seed
        |
        v
局部异构图扩展 Local PolyGraph Expansion
        |
        v
Agent 证据验证与反证
        |
        v
Patch Closure 补全
        |
        v
File / Module / Function 排序输出
```

### 6.3 Evidence Frame：先把 Issue 变成结构化证据

每个样本先抽取如下字段：

| 字段 | 例子 | 作用 |
|---|---|---|
| 视觉证据 | chart 截图、UI 组件异常、PDF 渲染图 | 生成视觉关键词、布局对象、组件名候选 |
| URL 证据 | 文档链接、playground、issue 引用、commit 链接 | 抽取 API 名、页面路径、配置项、复现代码 |
| 报错证据 | stack trace、assertion diff、type error | 定位语言、包、类、函数、测试入口 |
| 行为证据 | “hover 后 tooltip 错位”、“parser 输出错误” | 区分 UI、parser、formatter、state、rendering |
| 约束证据 | repo、语言、修改文件类型、测试文件 | 限制搜索空间，避免全仓库漂移 |

关键点：URL 不能只当普通文本。对 URL 要做三类解析：

- 文档 URL：抽取 API/配置名。
- playground/repro URL：抽取最小复现代码、组件名、参数。
- issue/commit URL：抽取关联文件、堆栈、讨论中的实体名。

### 6.4 Language-Task Router：按语言和任务类型决定图 schema

不同语言的“有用边”不同，不能全部塞进一个简单 call graph。

| 语言/文件类型 | 关键实体 | 关键边 |
|---|---|---|
| JavaScript/TypeScript | function、component、hook、selector、action、route、config | import/export、component-use、state-flow、test-to-impl、route-to-component |
| Python | module、class、function、type、fixture、decorator | import、call、inheritance、type-flow、test-to-target |
| Java | package、class、interface、method、annotation、test class | package dependency、override/implement、method call、assertion API、test-to-class |
| CSS/SCSS/MDX/JSON | selector、token、doc page、config key | style-to-component、doc-to-code、config-to-runtime |

Router 输出不是一个标签，而是一组搜索策略。例如：

```json
{
  "language": "Java",
  "task": "assertion-api",
  "primary_entities": ["class", "method"],
  "seed_edges": ["package", "test-to-class", "method-call", "override"],
  "avoid": ["same-name utility classes without test evidence"]
}
```

### 6.5 Local PolyGraph：不要一开始构全仓库大图

日志显示图缓存缺失和 fallback graph 很频繁。更现实的做法是：

1. 用 BM25/Dense/Symbol 取 top-N 文件作为 seed。
2. 只围绕 seed 构建局部图。
3. 图扩展半径按证据强度控制：强 seed 扩 2 跳，弱 seed 先要求更多证据。
4. 每次扩展都记录为什么扩展：import、test、URL、视觉组件、同目录、类型继承。

这样可以避免全仓库图过重，也避免 GraphLocator 类方法在错误 seed 上大规模扩散。

### 6.6 Agent 搜索动作必须有契约

当前日志里的 `search empty terms` 表明 Agent 工具调用缺少最低约束。新的 Agent action 应该使用结构化 schema：

```json
{
  "query": "DefaultHeaders value validation",
  "language": "Java",
  "entity_type": ["class", "method"],
  "evidence_source": ["error_message", "url_discussion"],
  "expected_hit": "generic header implementation, not HTTP-specific wrapper",
  "negative_constraints": ["ReadOnlyHttpHeaders unless stack trace mentions http"]
}
```

每次搜索后，Agent 需要写入 belief state：

```json
{
  "candidate": "codec/src/main/java/io/netty/handler/codec/DefaultHeaders.java",
  "supporting_evidence": ["class name matches issue", "generic header API used by wrappers"],
  "contradicting_evidence": [],
  "next_action": "inspect methods that validate header names/values"
}
```

这能解决两个问题：

- 防止空 query 或泛 query。
- 防止 Agent 找到同目录相似文件后不做反证。

### 6.7 Patch Closure：从入口文件补齐真实修改闭包

Clean15 失败样本中，很多不是完全找不到方向，而是漏掉工具函数、状态层、配置、测试或文档。Patch Closure 应该显式建模：

| 入口类型 | 应补齐的闭包 |
|---|---|
| UI 组件 | state selector、action、utility、style、test |
| Parser/formatter | AST node、printer、comment handler、fixture |
| Java API | interface、implementation、test assertion、utility |
| Python type checker | checker、binder、nodes、types、messages |
| Config/docs | config schema、runtime reader、docs/test |

输出时不只给 top-k 文件，还要给 closure group：

```text
Group A: symptom entry
- src/language-js/printer-estree.js

Group B: supporting utility
- src/language-js/comments.js

Group C: tests/fixtures
- tests/format/js/...
```

## 7. 结合失败样本的改进示例

### 7.1 `Automattic__wp-calypso-21492`

失败表现：预测在 `client/jetpack-connect/example-components/*`，gold 在 `authorize.js` 和 `utils.js`。

原因：

- 文本和目录都指向 `jetpack-connect`，但 baseline 没区分 demo component 和真实授权流程。
- 缺少 route/action/utils 的执行链验证。

改进：

- Router 判断为 JS/React + auth workflow。
- Local graph 从 component seed 扩展到 route/action，再沿 import 找 `authorize` 和 `utils`。
- Verifier 要求候选能解释“授权状态/连接流程”，example component 如果只展示 UI 应被降权。

### 7.2 `chartjs__Chart.js-8710`

失败表现：gold 在 linear/log scale，预测到 ticks/defaults/helper。

原因：

- 图表库中 ticks、scale、defaults 词面高度相关。
- 图片/URL 中的视觉异常应先转成 scale 类型约束，但 baseline 没有稳定使用。

改进：

- 视觉证据抽取轴、刻度、log/linear 语义。
- Router 判断为 JS chart scale task。
- 图扩展优先 `src/scales/*`，再通过 scale registry 和 tests 验证。

### 7.3 `tailwindlabs__tailwindcss-7588`

失败表现：gold 在 apply/defaults/cloneNodes，预测到 integrations 和 CSS demo。

原因：

- Tailwind issue 常包含 CSS 片段，词法搜索容易命中 integration fixture。
- 真正修改点在 PostCSS AST transform 工具链。

改进：

- Router 判断为 CSS syntax + JS transform。
- CSS 证据不是直接定位 `.css` 文件，而是映射到 transform pipeline：parse -> expand rules -> clone nodes -> defaults。
- Patch closure 补齐 utility，而不是只返回入口。

### 7.4 `netty__netty-13209`

失败表现：gold 在 `DefaultHeaders.java`，预测到 HTTP/2/HTTP wrapper headers。

原因：

- Java 包名和类名相似，词法搜索会偏向更具体的 HTTP 类。
- 缺少 generic implementation 与 wrapper implementation 的层级判断。

改进：

- Java adapter 建立 interface/implementation/wrapper 关系。
- 如果 issue 描述是通用 header 行为，generic base class 权重大于协议 wrapper。
- test-to-class 和 method override 边用于二次验证。

### 7.5 `python__mypy-13481`

失败表现：gold 在 `mypy/binder.py`，预测到 checker/messages/types。

原因：

- Mypy 类型错误文本天然会出现 checker、types 等核心模块，词法召回容易过宽。
- binder 的作用是控制流下的类型约束，普通调用图很难体现。

改进：

- Python adapter 增加 type-flow/control-flow 语义边。
- 查询中识别 “narrowing / binder / assignment / branch” 类概念。
- Verifier 检查候选是否能解释类型状态更新，而不是只看是否包含错误词。

## 8. 最终创新点

### 8.1 从“统一图”转向“语言适配的异构局部图”

LocAgent 的全量调用图、CoSIL 的动态调用图、GraphLocator 的因果链、GALA 的图对齐都有价值，但它们都容易把多语言仓库压成单一结构。我们的创新是：图 schema 由语言和任务共同决定，且只围绕证据 seed 局部构建。

### 8.2 从“LLM 自由搜索”转向“带契约的 Agent 搜索”

Agent 每次工具调用必须声明：

- 搜什么。
- 为什么搜。
- 属于哪种语言/实体。
- 期望命中什么。
- 哪些相似结果应被排除。

这直接针对日志中的空 search terms、max turn、同目录漂移问题。

### 8.3 从“文件排序”转向“patch closure 排序”

真实修复往往不是一个文件，而是一组因果相关文件。Clean15 后仍失败的样本说明，即便 gold 数量不超过 15，闭包关系仍难。框架应该输出候选组，并解释组内关系，而不是只输出孤立列表。

### 8.4 从“多模态输入”转向“多模态证据约束”

图片和 URL 不是附加上下文，而是搜索约束来源。视觉异常应该变成组件/状态/渲染/布局约束；URL 应该变成 API、文档、复现代码、关联 issue 或 commit 约束。

### 8.5 从“单主表”转向“Clean 主评估 + 诊断评估”

Clean15 主表评估公平的 file/module/function 定位能力；long-tail 和 unmappable 集合评估真实世界复杂性。框架设计要同时优化这两类：

- Clean15：看 Acc@1/3/5/8/10/12/13/15、MRR@15、MAP@15。
- Long-tail：看 Recall@All、Set Metrics@All、是否找到入口和闭包。
- Unmappable：看 file-level 和结构抽取覆盖，而不是强行看 function。

## 9. 实现路线

1. **离线索引层**
   - 为每个 repo 构建文件、实体、import、test、URL/doc、视觉关键词索引。
   - 为 JS/TS、Python、Java、CSS/MDX/JSON 分别实现 adapter。

2. **证据抽取层**
   - Issue 文本抽取 API、错误、堆栈、复现步骤。
   - URL 抽取页面类型、代码片段、文档标题、实体名。
   - 图片抽取视觉对象、布局、组件候选、图表/坐标/文本。

3. **Agent 搜索层**
   - 使用结构化 action schema。
   - 每步更新 belief state。
   - 强制反证：同名/同目录/同 API 候选必须比较为什么不是 gold。

4. **图扩展层**
   - 从 top seed 构局部图。
   - 根据语言和任务选择边类型。
   - 用 patch closure 规则补齐候选组。

5. **评估层**
   - 默认输出原始全集、Clean15、long-tail、unmappable 四套结果。
   - Clean15 表必须包含 Acc@1、Acc@3、Acc@5、Acc@8、Acc@10、Acc@12、Acc@13、Acc@15、MRR@15、MAP@15。

## 10. 当前可验证假设

下一步最值得做的 ablation：

| 实验 | 目的 |
|---|---|
| BM25 seed + language adapter rerank | 验证跨语言实体解释能否提升 function MAP |
| URL parser on/off | 验证网页证据是否能减少同目录漂移 |
| Image evidence as constraints vs plain text | 验证视觉证据是否能提升 SWE 图表/UI 样本 |
| Local graph vs full graph | 验证局部图能否降低构图成本并减少错误扩散 |
| Patch closure on/off | 验证多文件补全能否提升 Acc@8/10/15 |
| Action contract on/off | 验证是否减少 empty query、max turn 和错误搜索链 |

如果这些 ablation 成立，框架的核心贡献可以概括为：

> 面向多模态跨语言 Issue 定位，单纯扩大召回或让 LLM 自由搜索并不能稳定解决问题。更有效的范式是：先把 issue 中的文本、图片和 URL 转成结构化证据，再由语言/任务路由选择局部异构图和搜索动作，最后用证据验证与 patch closure 输出三层定位结果。
