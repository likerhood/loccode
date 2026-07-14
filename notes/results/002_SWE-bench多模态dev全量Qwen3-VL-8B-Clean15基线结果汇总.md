# SWE-bench 多模态 dev 全量 Qwen3-VL-8B Clean15 基线结果汇总

生成时间：2026-07-13

本文档是 `001_SWE-bench多模态dev全量Qwen3-VL-8B基线结果汇总.md` 的 Clean15 复评估版本。`001` 汇总的是原始 102 条 dev 全量结果；本文只在 `Three-level-clean@15` 样本上重新统计结果。

Clean15 的目的不是重新运行模型，而是对已经跑完的定位结果做筛选复评估：只保留 file、module、function 三层 gold 都非空，且三层 gold 数量都不超过 15 的样本。这样 `Acc@15` 才不会被“真实目标超过 15 个”天然卡死，也不会把 module/function 不可映射样本混入实体级主指标。

## 1. 实验范围

| 项目 | 内容 |
|---|---|
| 基准 | SWE-bench Multimodal |
| 数据划分 | dev |
| 原始样本数 | 102 |
| Clean15 样本数 | 92 |
| 被排除样本数 | 10 |
| LLM/VLM 基线模型 | `openai/qwen3-vl-8b` / `qwen3-vl-8b` |
| 原始运行日志 | `baseline_run_logs/swebench_multimodal_full_dev_parallel_20260708_182346/` |
| 规范化样本文件 | `LocAgent/newtest/swebench_multimodal-full-dev/data/samples.jsonl` |
| 规范化仓库结构 | `LocAgent/newtest/swebench_multimodal-full-dev/repo_structures/` |
| Clean15 说明文档 | `notes/results/010_三层定位评估样本清洗与可评估性分析.md` |

原始 102 条样本的仓库分布如下：

| 仓库 | 数量 |
|---|---:|
| Automattic/wp-calypso | 37 |
| chartjs/Chart.js | 24 |
| diegomura/react-pdf | 11 |
| markedjs/marked | 14 |
| processing/p5.js | 16 |

Clean15 主要排除了两类样本：

- 超大 patch：例如 `diegomura__react-pdf-1285`，真实修改 36 个文件、43 个 module、121 个 function，严格 `Acc@15` 理论上无法全覆盖。
- module/function 不可映射样本：例如真实修改行落在非函数区域或结构抽取器无法识别的位置。

## 2. 结果路径

| 基线 | Clean15 结果目录 |
|---|---|
| LocAgent | `collected_results/qwen8b_mimo_compare_20260711_212220/swebench_multimodal-full-dev/qwen3-vl-8b/locagent/metrics_clean15/` |
| CoSIL | `collected_results/qwen8b_mimo_compare_20260711_212220/swebench_multimodal-full-dev/qwen3-vl-8b/cosil/metrics_clean15/` |
| GraphLocator | `collected_results/qwen8b_mimo_compare_20260711_212220/swebench_multimodal-full-dev/qwen3-vl-8b/graphlocator/metrics_clean15/` |
| GALA | `collected_results/qwen8b_mimo_compare_20260711_212220/swebench_multimodal-full-dev/qwen3-vl-8b/gala/metrics_clean15/` |
| BM25-MMIR | `collected_results/qwen8b_mimo_compare_20260711_212220/swebench_multimodal-full-candidates/retrieval/mmir_bm25-mmir/metrics_clean15/` |

说明：

- BM25-MMIR 是非大模型检索基线，作为稀疏词法检索参照。
- 本文 Clean15 指标来自已完成定位结果的复评估，不是重新跑 baseline。
- 数值均为百分比。

## 3. 指标口径

本文继续沿用 `001` 的两套 Acc@K 口径：

- **宽松 Acc@K**：top-k 中命中任意一个 gold 即算成功。
- **严格 Acc@K**：top-k 必须覆盖该层级全部 gold 才算成功。

同时报告：

- `MRR@15`：第一个正确目标越靠前越高。
- `MAP@15`：top15 内多个正确目标的排序质量。
- `Empty`：该层预测为空的比例。
- `SL / REC / PRE / F1`：集合级成功、召回、精度和 F1。

Clean15 后，严格 `Acc@15` 的解释更清晰：如果模型失败，主要是定位和排序问题，而不是样本 gold 数量超过 top15 上限。

## 4. 宽松 Clean15 排名指标

### 文件级

| 基线 | N | Acc@1 | Acc@3 | Acc@5 | Acc@8 | Acc@10 | Acc@12 | Acc@13 | Acc@15 | MRR@15 | MAP@15 | Empty |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 92 | 28.26 | 33.70 | 39.13 | 42.39 | 42.39 | 42.39 | 42.39 | 42.39 | 32.55 | 19.77 | 4.35 |
| CoSIL | 92 | 31.52 | 43.48 | 44.57 | 44.57 | 44.57 | 44.57 | 44.57 | 44.57 | 37.41 | 22.95 | 0.00 |
| GraphLocator | 92 | 22.83 | 27.17 | 29.35 | 30.43 | 30.43 | 30.43 | 30.43 | 30.43 | 25.36 | 12.61 | 0.00 |
| GALA | 92 | 35.87 | 58.70 | 63.04 | 63.04 | 63.04 | 63.04 | 63.04 | 63.04 | 47.84 | 30.43 | 0.00 |
| BM25-MMIR | 92 | 25.00 | 41.30 | 45.65 | 52.17 | 57.61 | 61.96 | 61.96 | 65.22 | 35.09 | 21.32 | 0.00 |

### 模块级

| 基线 | N | Acc@1 | Acc@3 | Acc@5 | Acc@8 | Acc@10 | Acc@12 | Acc@13 | Acc@15 | MRR@15 | MAP@15 | Empty |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 92 | 10.87 | 19.57 | 25.00 | 31.52 | 32.61 | 33.70 | 33.70 | 35.87 | 17.48 | 12.96 | 4.35 |
| CoSIL | 92 | 23.91 | 32.61 | 33.70 | 33.70 | 33.70 | 33.70 | 33.70 | 33.70 | 27.99 | 20.02 | 2.17 |
| GraphLocator | 92 | 15.22 | 22.83 | 25.00 | 25.00 | 25.00 | 25.00 | 26.09 | 26.09 | 19.11 | 12.49 | 7.61 |
| GALA | 92 | 30.43 | 45.65 | 53.26 | 54.35 | 54.35 | 54.35 | 54.35 | 54.35 | 39.24 | 28.84 | 1.09 |
| BM25-MMIR | 92 | 14.13 | 32.61 | 38.04 | 45.65 | 53.26 | 57.61 | 57.61 | 60.87 | 26.48 | 20.56 | 0.00 |

### 函数级

| 基线 | N | Acc@1 | Acc@3 | Acc@5 | Acc@8 | Acc@10 | Acc@12 | Acc@13 | Acc@15 | MRR@15 | MAP@15 | Empty |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 92 | 3.26 | 11.96 | 14.13 | 18.48 | 20.65 | 20.65 | 20.65 | 20.65 | 8.00 | 4.62 | 4.35 |
| CoSIL | 92 | 6.52 | 10.87 | 13.04 | 14.13 | 14.13 | 15.22 | 15.22 | 15.22 | 9.25 | 5.27 | 2.17 |
| GraphLocator | 92 | 5.43 | 9.78 | 11.96 | 13.04 | 13.04 | 13.04 | 13.04 | 14.13 | 7.79 | 4.52 | 8.70 |
| GALA | 92 | 5.43 | 7.61 | 15.22 | 27.17 | 29.35 | 33.70 | 34.78 | 34.78 | 10.43 | 5.75 | 1.09 |
| BM25-MMIR | 92 | 13.04 | 23.91 | 28.26 | 33.70 | 36.96 | 36.96 | 38.04 | 39.13 | 20.35 | 11.63 | 0.00 |

## 5. 严格 Clean15 排名指标

### 文件级

| 基线 | N | Acc@1 | Acc@3 | Acc@5 | Acc@8 | Acc@10 | Acc@12 | Acc@13 | Acc@15 | MRR@15 | MAP@15 | Empty |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 92 | 9.78 | 14.13 | 16.30 | 18.48 | 18.48 | 19.57 | 19.57 | 19.57 | 32.55 | 19.77 | 4.35 |
| CoSIL | 92 | 10.87 | 15.22 | 18.48 | 18.48 | 18.48 | 18.48 | 18.48 | 18.48 | 37.41 | 22.95 | 0.00 |
| GraphLocator | 92 | 6.52 | 7.61 | 7.61 | 7.61 | 7.61 | 7.61 | 7.61 | 7.61 | 25.36 | 12.61 | 0.00 |
| GALA | 92 | 9.78 | 18.48 | 25.00 | 25.00 | 25.00 | 25.00 | 25.00 | 25.00 | 47.84 | 30.43 | 0.00 |
| BM25-MMIR | 92 | 5.43 | 11.96 | 17.39 | 21.74 | 27.17 | 29.35 | 29.35 | 30.43 | 35.09 | 21.32 | 0.00 |

### 模块级

| 基线 | N | Acc@1 | Acc@3 | Acc@5 | Acc@8 | Acc@10 | Acc@12 | Acc@13 | Acc@15 | MRR@15 | MAP@15 | Empty |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 92 | 4.35 | 9.78 | 14.13 | 19.57 | 19.57 | 19.57 | 20.65 | 21.74 | 17.48 | 12.96 | 4.35 |
| CoSIL | 92 | 9.78 | 16.30 | 17.39 | 17.39 | 17.39 | 17.39 | 17.39 | 17.39 | 27.99 | 20.02 | 2.17 |
| GraphLocator | 92 | 5.43 | 9.78 | 9.78 | 9.78 | 9.78 | 9.78 | 9.78 | 9.78 | 19.11 | 12.49 | 7.61 |
| GALA | 92 | 13.04 | 21.74 | 25.00 | 25.00 | 25.00 | 25.00 | 25.00 | 25.00 | 39.24 | 28.84 | 1.09 |
| BM25-MMIR | 92 | 5.43 | 18.48 | 20.65 | 25.00 | 29.35 | 33.70 | 35.87 | 40.22 | 26.48 | 20.56 | 0.00 |

### 函数级

| 基线 | N | Acc@1 | Acc@3 | Acc@5 | Acc@8 | Acc@10 | Acc@12 | Acc@13 | Acc@15 | MRR@15 | MAP@15 | Empty |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 92 | 0.00 | 5.43 | 6.52 | 7.61 | 7.61 | 7.61 | 7.61 | 7.61 | 8.00 | 4.62 | 4.35 |
| CoSIL | 92 | 3.26 | 3.26 | 4.35 | 4.35 | 4.35 | 4.35 | 4.35 | 4.35 | 9.25 | 5.27 | 2.17 |
| GraphLocator | 92 | 2.17 | 3.26 | 3.26 | 3.26 | 3.26 | 3.26 | 3.26 | 3.26 | 7.79 | 4.52 | 8.70 |
| GALA | 92 | 1.09 | 1.09 | 4.35 | 9.78 | 10.87 | 10.87 | 11.96 | 11.96 | 10.43 | 5.75 | 1.09 |
| BM25-MMIR | 92 | 3.26 | 6.52 | 9.78 | 11.96 | 11.96 | 11.96 | 11.96 | 13.04 | 20.35 | 11.63 | 0.00 |

## 6. Raw 全量与 Clean15 严格 Acc@15 对比

| 基线 | Raw N | Clean N | Raw File@15 | Clean File@15 | Raw Module@15 | Clean Module@15 | Raw Function@15 | Clean Function@15 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 102 | 92 | 18.63 | 19.57 | 19.61 | 21.74 | 6.86 | 7.61 |
| CoSIL | 102 | 92 | 18.63 | 18.48 | 15.69 | 17.39 | 4.90 | 4.35 |
| GraphLocator | 102 | 92 | 6.86 | 7.61 | 8.82 | 9.78 | 3.92 | 3.26 |
| GALA | 102 | 92 | 25.49 | 25.00 | 11.76 | 25.00 | 7.84 | 11.96 |
| BM25-MMIR | 102 | 92 | 31.37 | 30.43 | 36.27 | 40.22 | 11.76 | 13.04 |

清洗后的变化可以这样理解：

- LocAgent 清洗后略升，说明它在被排除的大 patch 和不可映射样本上确实吃亏，但主问题仍然存在。
- CoSIL file 层基本不变，module 层略升，function 层略降，说明它的问题不是主要来自超大样本，而是函数级实体排序能力不足。
- GraphLocator 清洗后 file/module 略升，但 function 略降，说明它的因果链图在 Clean15 中仍没有稳定命中函数。
- GALA 的 module/function 明显提升，说明原始全集中的不可映射或长尾样本会压低它的三层表现；Clean15 更能体现其在可映射样本上的图对齐能力。
- BM25-MMIR 在 module/function 的 Clean15 表现更强，说明词法 seed 对可映射实体有较高召回价值，但 precision 和闭包仍不足。

## 7. 集合指标 @All

集合指标在宽松和严格口径下相同，因为它不依赖排序 Acc 的 full-coverage/any-hit 区分，而是直接比较预测集合和 gold 集合。

### 宽松 Clean15

| 基线 | 文件 SL | 文件 REC | 文件 PRE | 文件 F1 | 模块 SL | 模块 REC | 模块 PRE | 模块 F1 | 函数 SL | 函数 REC | 函数 PRE | 函数 F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 19.57 | 26.45 | 17.19 | 15.45 | 26.09 | 32.83 | 7.95 | 10.62 | 8.70 | 15.32 | 2.76 | 3.76 |
| CoSIL | 18.48 | 28.10 | 17.86 | 19.36 | 17.39 | 24.33 | 18.02 | 18.76 | 4.35 | 8.59 | 2.52 | 3.22 |
| GraphLocator | 7.61 | 15.46 | 20.40 | 14.19 | 9.78 | 16.56 | 15.51 | 14.56 | 3.26 | 7.77 | 2.90 | 3.68 |
| GALA | 25.00 | 40.32 | 20.62 | 23.97 | 25.00 | 38.46 | 24.47 | 26.34 | 11.96 | 19.65 | 4.19 | 6.28 |
| BM25-MMIR | 30.43 | 45.41 | 6.81 | 11.11 | 40.22 | 48.51 | 5.81 | 10.06 | 13.04 | 22.08 | 3.98 | 6.09 |

### 严格 Clean15

| 基线 | 文件 SL | 文件 REC | 文件 PRE | 文件 F1 | 模块 SL | 模块 REC | 模块 PRE | 模块 F1 | 函数 SL | 函数 REC | 函数 PRE | 函数 F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 19.57 | 26.45 | 17.19 | 15.45 | 26.09 | 32.83 | 7.95 | 10.62 | 8.70 | 15.32 | 2.76 | 3.76 |
| CoSIL | 18.48 | 28.10 | 17.86 | 19.36 | 17.39 | 24.33 | 18.02 | 18.76 | 4.35 | 8.59 | 2.52 | 3.22 |
| GraphLocator | 7.61 | 15.46 | 20.40 | 14.19 | 9.78 | 16.56 | 15.51 | 14.56 | 3.26 | 7.77 | 2.90 | 3.68 |
| GALA | 25.00 | 40.32 | 20.62 | 23.97 | 25.00 | 38.46 | 24.47 | 26.34 | 11.96 | 19.65 | 4.19 | 6.28 |
| BM25-MMIR | 30.43 | 45.41 | 6.81 | 11.11 | 40.22 | 48.51 | 5.81 | 10.06 | 13.04 | 22.08 | 3.98 | 6.09 |

## 8. 代表失败样本

这些样本已经通过 Clean15，因此失败不能归因于 `gold > 15` 或 module/function 不可映射。它们更能反映 baseline 的真实定位问题。

### LocAgent 严格 Clean15 代表失败样本

| 样本 | 仓库 | Gold文件 | Gold模块 | Gold函数 | File REC@All | Module REC@All | Function REC@All | Gold文件示例 | 预测文件示例 |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| `Automattic__wp-calypso-27090` | `Automattic/wp-calypso` | 13 | 3 | 6 | 0.0 | 0.0 | 0.0 | `client/components/data/query-stats-recent-post-views/README.md; client/components/data/query-stats-recent-post-views/index.jsx; client/my-sites/post-type-list/index.jsx ...` | `client/extensions/woocommerce/woocommerce-services/views/shipping-label/label-purchase-modal/packages-step/package-info.js; client/extensions/woocommerce/woocommerce-services/views/shipping-label/label-purchase-modal/address-step/fields.js; client/components/tinymce/plugins/wpcom-view/views/embed/index.js ...` |
| `Automattic__wp-calypso-21409` | `Automattic/wp-calypso` | 10 | 5 | 10 | 0.0 | 0.0 | 0.0 | `client/extensions/woocommerce/app/dashboard/index.js; client/extensions/woocommerce/app/dashboard/required-plugins-install-view.js; client/extensions/woocommerce/app/dashboard/setup-footer.js ...` | `client/state/current-user/selectors.js; client/state/themes/selectors.js; client/state/ui/selectors.js ...` |
| `Automattic__wp-calypso-33948` | `Automattic/wp-calypso` | 10 | 3 | 10 | 0.0 | 0.0 | 0.0 | `CREDITS.md; client/lib/browser-storage/README.md; client/lib/browser-storage/bypass.ts ...` | `` |
| `Automattic__wp-calypso-23991` | `Automattic/wp-calypso` | 10 | 5 | 5 | 0.0 | 0.0 | 0.0 | `client/lib/posts/post-edit-store.js; client/post-editor/controller.js; client/post-editor/editor-drawer/featured-image.jsx ...` | `client/state/posts/utils.js; client/state/site-settings/exporter/selectors.js; client/state/site-settings/exporter/actions.js ...` |
| `Automattic__wp-calypso-22026` | `Automattic/wp-calypso` | 8 | 7 | 6 | 0.0 | 0.0 | 0.0 | `client/extensions/woocommerce/app/dashboard/setup-tasks.js; client/extensions/woocommerce/app/settings/email/mailchimp/sync_tab.js; client/extensions/woocommerce/app/settings/payments/style.scss ...` | `client/state/themes/utils.js; client/state/utils.js; client/state/ui/editor/image-editor/actions.js ...` |
| `Automattic__wp-calypso-21648` | `Automattic/wp-calypso` | 7 | 4 | 8 | 0.0 | 0.0 | 0.0 | `client/extensions/woocommerce/app/settings/email/email-settings/components/customer-notification.js; client/extensions/woocommerce/app/settings/email/email-settings/components/internal-notification.js; client/extensions/woocommerce/app/settings/email/email-settings/components/notifications-origin.js ...` | `client/extensions/woocommerce/app/settings/email/mailchimp/setup-steps/store-info.js; client/state/notices/account-recovery/index.js; client/state/account-recovery/settings/selectors.js ...` |

### GALA 严格 Clean15 代表失败样本

| 样本 | 仓库 | Gold文件 | Gold模块 | Gold函数 | File REC@All | Module REC@All | Function REC@All | Gold文件示例 | 预测文件示例 |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| `Automattic__wp-calypso-27090` | `Automattic/wp-calypso` | 13 | 3 | 6 | 0.0 | 0.0 | 0.0 | `client/components/data/query-stats-recent-post-views/README.md; client/components/data/query-stats-recent-post-views/index.jsx; client/my-sites/post-type-list/index.jsx ...` | `client/my-sites/posts/index.js; client/my-sites/posts/main.jsx; client/my-sites/posts/post-total-views.jsx ...` |
| `Automattic__wp-calypso-21409` | `Automattic/wp-calypso` | 10 | 5 | 10 | 0.0 | 0.0 | 0.0 | `client/extensions/woocommerce/app/dashboard/index.js; client/extensions/woocommerce/app/dashboard/required-plugins-install-view.js; client/extensions/woocommerce/app/dashboard/setup-footer.js ...` | `client/signup/steps/site-or-domain/index.jsx; client/signup/steps/design-type-with-store/index.jsx; client/signup/steps/design-type-with-atomic-store/index.jsx ...` |
| `Automattic__wp-calypso-33948` | `Automattic/wp-calypso` | 10 | 3 | 10 | 0.0 | 0.0 | 0.0 | `CREDITS.md; client/lib/browser-storage/README.md; client/lib/browser-storage/bypass.ts ...` | `apps/wpcom-block-editor/webpack.config.js; apps/wpcom-block-editor/package.json; apps/full-site-editing/package.json ...` |
| `Automattic__wp-calypso-22026` | `Automattic/wp-calypso` | 8 | 7 | 6 | 0.0 | 0.0 | 0.0 | `client/extensions/woocommerce/app/dashboard/setup-tasks.js; client/extensions/woocommerce/app/settings/email/mailchimp/sync_tab.js; client/extensions/woocommerce/app/settings/payments/style.scss ...` | `client/extensions/woocommerce/components/store-address/index.js; client/extensions/woocommerce/components/store-address/style.scss; client/extensions/woocommerce/components/form-dimensions-input/index.jsx ...` |
| `Automattic__wp-calypso-21648` | `Automattic/wp-calypso` | 7 | 4 | 8 | 0.0 | 0.0 | 0.0 | `client/extensions/woocommerce/app/settings/email/email-settings/components/customer-notification.js; client/extensions/woocommerce/app/settings/email/email-settings/components/internal-notification.js; client/extensions/woocommerce/app/settings/email/email-settings/components/notifications-origin.js ...` | `client/state/site-settings/actions.js; client/lib/formatting/decode-entities/browser.js; client/state/site-settings/selectors.js ...` |
| `Automattic__wp-calypso-21977` | `Automattic/wp-calypso` | 5 | 3 | 12 | 0.0 | 0.0 | 0.0 | `client/extensions/woocommerce/app/settings/payments/stripe/payment-method-stripe-connected-dialog.js; client/extensions/woocommerce/state/action-types.js; client/extensions/woocommerce/state/sites/settings/stripe-connect-account/actions.js ...` | `client/jetpack-connect/index.js` |

### BM25-MMIR 严格 Clean15 代表失败样本

| 样本 | 仓库 | Gold文件 | Gold模块 | Gold函数 | File REC@All | Module REC@All | Function REC@All | Gold文件示例 | 预测文件示例 |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| `Automattic__wp-calypso-27090` | `Automattic/wp-calypso` | 13 | 3 | 6 | 0.0 | 0.0 | 0.0 | `client/components/data/query-stats-recent-post-views/README.md; client/components/data/query-stats-recent-post-views/index.jsx; client/my-sites/post-type-list/index.jsx ...` | `client/blocks/inline-help/contextual-help.js; client/components/tinymce/plugins/media/plugin.jsx; client/lib/analytics/index.js ...` |
| `Automattic__wp-calypso-22026` | `Automattic/wp-calypso` | 8 | 7 | 6 | 0.0 | 0.0 | 0.0 | `client/extensions/woocommerce/app/dashboard/setup-tasks.js; client/extensions/woocommerce/app/settings/email/mailchimp/sync_tab.js; client/extensions/woocommerce/app/settings/payments/style.scss ...` | `assets/stylesheets/directly.scss; client/components/tinymce/plugins/media/plugin.jsx; client/extensions/woocommerce/state/sites/settings/actions.js ...` |
| `Automattic__wp-calypso-21648` | `Automattic/wp-calypso` | 7 | 4 | 8 | 0.0 | 0.0 | 0.0 | `client/extensions/woocommerce/app/settings/email/email-settings/components/customer-notification.js; client/extensions/woocommerce/app/settings/email/email-settings/components/internal-notification.js; client/extensions/woocommerce/app/settings/email/email-settings/components/notifications-origin.js ...` | `client/components/title-format-editor/parser.js; client/components/tinymce/plugins/media/plugin.jsx; client/lib/post-normalizer/utils.js ...` |
| `Automattic__wp-calypso-32764` | `Automattic/wp-calypso` | 7 | 4 | 5 | 0.0 | 0.0 | 0.0 | `client/me/billing-history/controller.js; client/me/billing-history/main.jsx; client/me/billing-history/style.scss ...` | `client/state/plans/test/fixture/index.js; client/lib/discounts/active-discounts.js; client/components/tinymce/plugins/media/plugin.jsx ...` |
| `Automattic__wp-calypso-22621` | `Automattic/wp-calypso` | 7 | 3 | 3 | 0.0 | 0.0 | 0.0 | `client/jetpack-onboarding/constants.js; client/jetpack-onboarding/controller.js; client/jetpack-onboarding/main.jsx ...` | `client/layout/guided-tours/tours/checklist-publish-post-tour.js; client/jetpack-connect/authorize.js; client/layout/guided-tours/tours/checklist-about-page-tour.js ...` |
| `diegomura__react-pdf-1363` | `diegomura/react-pdf` | 6 | 4 | 5 | 0.0 | 25.0 | 0.0 | `packages/layout/src/text/getAttributedString.js; packages/render/src/index.js; packages/render/src/primitives/renderBackground.js ...` | `packages/renderer/index.d.ts; packages/pdfkit/src/image/png.js; packages/fontkit/src/opentype/GSUBProcessor.js ...` |

## 9. 日志模式摘要

| 模式 | 次数 | 代表日志 | 解释 |
|---|---:|---|---|
| 空响应/接口异常 | 0 | 无 | 本次 qwen3-vl-8b 原始完成日志中没有明显 API 空响应模式。 |
| 搜索预算耗尽 | 2 | `baseline_run_logs/swebench_multimodal_full_dev_parallel_20260708_182346/graphlocator.log` | GraphLocator 部分样本没有在搜索预算内收敛，说明图搜索可能进入局部错误链。 |
| 图缓存/构图问题 | 148 | `baseline_run_logs/swebench_multimodal_full_dev_parallel_20260708_182346/graphlocator.log` | 图缓存、构图和图扩展相关日志较多，说明全仓图/局部图构造成本是稳定性瓶颈。 |
| 定位失败/异常关键词 | 106 | `baseline_run_logs/swebench_multimodal_full_dev_parallel_20260708_182346/gala.log`, `baseline_run_logs/swebench_multimodal_full_dev_parallel_20260708_182346/graphlocator.log` | 多数是样本级失败、警告、图搜索失败或候选为空，不等同于整轮实验失败。 |

运行状态文件显示本轮四个大模型 baseline 都以状态码 0 结束：

| 文件 | 状态 |
|---|---:|
| `baseline_run_logs/swebench_multimodal_full_dev_parallel_20260708_182346/locagent.status` | 0 |
| `baseline_run_logs/swebench_multimodal_full_dev_parallel_20260708_182346/cosil.status` | 0 |
| `baseline_run_logs/swebench_multimodal_full_dev_parallel_20260708_182346/graphlocator.status` | 0 |
| `baseline_run_logs/swebench_multimodal_full_dev_parallel_20260708_182346/gala.status` | 0 |

因此这里的重点不是“脚本没跑完”，而是“跑完之后仍然有大量 clean 样本无法定位”。

## 10. 结果分析

### 10.1 Clean15 后主结论没有改变：函数级仍是最难层级

严格 Clean15 下，最强函数级 `Acc@15` 是 BM25-MMIR 的 13.04，其次是 GALA 的 11.96。LocAgent 只有 7.61，CoSIL 4.35，GraphLocator 3.26。

这说明即使去掉超大 patch 和不可映射样本，function-level 仍然没有被现有 baseline 解决。主要原因是：

- file-level 候选不等于 function-level 精确定位；
- 多文件 patch 中存在工具函数、状态层、UI 层、测试/配置闭包；
- Qwen3-VL-8B 在长上下文仓库中容易给出相关但不精确的文件；
- 当前评估需要覆盖全部 gold function，不是只命中一个函数。

### 10.2 GALA 在 Clean15 后更能体现多模态图对齐优势

GALA 在宽松文件级 `Acc@15` 达到 63.04，严格文件级 `Acc@15` 达到 25.00，在大模型 baseline 中最好。它的模块级严格 `Acc@15` 也从 raw 的 11.76 提升到 clean 的 25.00。

这说明原始全集中的不可映射或极端长尾样本会压低 GALA 的三层指标。Clean15 更能体现它在多模态前端类样本上的优势。

但 GALA 函数级严格 `Acc@15` 仍只有 11.96，说明视觉/图对齐可以帮助找到文件或模块区域，但不足以完成函数级闭包定位。

### 10.3 BM25-MMIR 是强召回基线，但精度和解释性不足

BM25-MMIR 在宽松文件级 `Acc@15` 最高，为 65.22；严格模块级 `Acc@15` 最高，为 40.22；严格函数级 `Acc@15` 也最高，为 13.04。

这说明 SWE-bench Multimodal 里很多 issue 仍然包含强词法线索，比如组件名、API 名、文件路径、错误文本、文档链接等。

但 BM25 的集合指标暴露了精度问题：

- 文件 PRE@All 只有 6.81。
- 模块 PRE@All 只有 5.81。
- 函数 PRE@All 只有 3.98。

也就是说，BM25 能把 gold 放进较大的候选集合，但同时带来很多噪声。它适合作为第一阶段 seed，不适合作为最终定位器。

### 10.4 LocAgent 找文件能力中等，但搜索链容易漂移

LocAgent 严格文件级 `Acc@15` 是 19.57，模块级 21.74，函数级 7.61。失败样本里大量集中在 `Automattic/wp-calypso`，例如：

- `Automattic__wp-calypso-21409`
- `Automattic__wp-calypso-22026`
- `Automattic__wp-calypso-27090`
- `Automattic__wp-calypso-33948`

这些样本的共同特点是仓库大、前端目录多、功能域交叉强。LocAgent 常常能进入相近功能域，但会被 `state/selectors`、`woocommerce`、`jetpack`、`signup`、`billing` 等相邻目录吸走。

后续改进重点不是单纯增加 top-k，而是让 Agent 每一步搜索都带有：

- 证据来源：来自图片、URL、报错、还是 issue 文本；
- 目标实体：文件、组件、selector、action、工具函数；
- 反证条件：为什么相邻目录不是目标；
- patch closure：入口文件、状态层、工具函数、样式/配置是否需要一起补齐。

### 10.5 GraphLocator 的主要瓶颈是图构建和图搜索收敛

GraphLocator 在 Clean15 后仍整体偏低，严格文件级 `Acc@15` 只有 7.61，函数级只有 3.26。日志中图缓存/构图相关模式出现较多，并有搜索预算耗尽记录。

这说明对 SWE 这种前端多文件、多路径、多图片 benchmark，仅靠因果链图并不稳定。图构建如果基于错误 seed，会把模型带进错误局部区域；如果构图过重，又会造成运行成本和缓存问题。

更合理的方向是局部异构图：先从 BM25/视觉/URL seed 取 top-N，再围绕 seed 构建小图，并用证据 verifier 做反证。

### 10.6 CoSIL 的文件级稳定，但函数级下降明显

CoSIL 宽松文件级 `Acc@15` 为 44.57，严格文件级为 18.48，说明文件级候选仍有一定稳定性。但严格函数级只有 4.35。

这说明 CoSIL 更适合作为文件候选生成器，而不是完整三层定位器。它需要接一个实体级 reranker，尤其要利用 repo structure 的函数起止行、调用关系、测试关系和 patch hunk 映射。

## 11. 对后续框架设计的直接启发

Clean15 后的结果更适合指导框架创新，因为它排除了样本上限问题。当前最直接的设计结论是：

1. **主召回应该保留 BM25 seed**：BM25 在 Clean15 下仍然很强，说明词法线索不能丢。
2. **多模态信息要变成约束，不是只拼进 prompt**：GALA 的表现说明图片/视觉线索有价值，但需要进一步映射到组件、图表 scale、渲染路径、样式文件。
3. **Agent 搜索需要结构化动作契约**：搜索动作必须说明语言、实体类型、证据来源、期望命中和反证目标。
4. **需要 patch closure 机制**：很多 clean 样本不是单文件问题，入口文件、工具函数、状态层、配置/样式需要成组输出。
5. **图应该局部构建**：GraphLocator 的日志说明全仓图/重图构建成本高，应该从 seed 出发构建局部跨语言图。

一个更合理的 pipeline 是：

```text
Issue 文本 / 图片 / URL
  -> 证据抽取
  -> BM25 + Dense + Symbol seed
  -> 语言/任务 router
  -> 局部异构图扩展
  -> Agent 反证与 patch closure
  -> file/module/function 三层排序
```

## 12. 源文件

| 基线 | 宽松 Clean15 | 严格 Clean15 |
|---|---|---|
| LocAgent | `collected_results/qwen8b_mimo_compare_20260711_212220/swebench_multimodal-full-dev/qwen3-vl-8b/locagent/metrics_clean15/eval_clean15/metrics_3level.json` | `collected_results/qwen8b_mimo_compare_20260711_212220/swebench_multimodal-full-dev/qwen3-vl-8b/locagent/metrics_clean15/eval_strict_clean15/metrics_3level.json` |
| CoSIL | `collected_results/qwen8b_mimo_compare_20260711_212220/swebench_multimodal-full-dev/qwen3-vl-8b/cosil/metrics_clean15/eval_clean15/metrics_3level.json` | `collected_results/qwen8b_mimo_compare_20260711_212220/swebench_multimodal-full-dev/qwen3-vl-8b/cosil/metrics_clean15/eval_strict_clean15/metrics_3level.json` |
| GraphLocator | `collected_results/qwen8b_mimo_compare_20260711_212220/swebench_multimodal-full-dev/qwen3-vl-8b/graphlocator/metrics_clean15/eval_clean15/metrics_3level.json` | `collected_results/qwen8b_mimo_compare_20260711_212220/swebench_multimodal-full-dev/qwen3-vl-8b/graphlocator/metrics_clean15/eval_strict_clean15/metrics_3level.json` |
| GALA | `collected_results/qwen8b_mimo_compare_20260711_212220/swebench_multimodal-full-dev/qwen3-vl-8b/gala/metrics_clean15/eval_clean15/metrics_3level.json` | `collected_results/qwen8b_mimo_compare_20260711_212220/swebench_multimodal-full-dev/qwen3-vl-8b/gala/metrics_clean15/eval_strict_clean15/metrics_3level.json` |
| BM25-MMIR | `collected_results/qwen8b_mimo_compare_20260711_212220/swebench_multimodal-full-candidates/retrieval/mmir_bm25-mmir/metrics_clean15/eval_clean15/metrics_3level.json` | `collected_results/qwen8b_mimo_compare_20260711_212220/swebench_multimodal-full-candidates/retrieval/mmir_bm25-mmir/metrics_clean15/eval_strict_clean15/metrics_3level.json` |

