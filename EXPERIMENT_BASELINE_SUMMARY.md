# Baseline 与实验结果汇总

生成时间：2026-07-04。

本文档汇总 `/home/like/locCode` 下目前已经完成的多模态 issue localization 实验结果。所有数值均重新核对自各方法输出目录中的 `metrics_3level.md` / `metrics_3level.json` / `loc_results.json`。

## 统计口径说明

本文档统计的是各 baseline 已经生成的三层评估指标，不是只统计 `baseline_run_logs` 中的终端日志。`baseline_run_logs` 目前主要保存 GALA 和 GraphLocator 的 60 样本运行日志，只能用于排查运行过程；最终数值以各项目结果目录中的 `eval/metrics_3level.md` / `metrics_3level.json` 为准。

需要特别注意：本文档不是“所有 baseline 都跑了全量 benchmark”的结果表。当前完整 full-candidates 结果只有 BM25-MMIR：

- SWE-bench Multimodal full-candidates：BM25-MMIR 评估了 102 条可评估 dev 样本；
- OmniGIRL full-candidates：BM25-MMIR 评估了 631 条当前本地可运行候选样本；
- LocAgent / CoSIL / GALA / GraphLocator 当前汇总的是 60 样本或部分 60 样本结果；
- E5-MMIR / Jina-Code-v2-MMIR / CodeSage-large-v2-MMIR / CodeRankEmbed-MMIR 当前还没有完整指标。

因此，本文档中的 60 样本主实验用于横向观察不同 baseline 的表现；full-candidates 部分目前只用于说明 BM25-MMIR 在更大候选集合上的非 agent 检索上限。

## 汇总范围

数据集：

- SWE-bench Multimodal 60
- OmniGIRL 60
- SWE-bench Multimodal full-candidates
- OmniGIRL full-candidates

已有完整或部分结果的方法：

- LocAgent
- CoSIL
- GALA
- GraphLocator
- BM25-MMIR

目前已经搭好或计划运行、但当前结果目录中尚未看到完整指标的方法：

- E5-MMIR
- Jina-Code-v2-MMIR
- CodeSage-large-v2-MMIR
- CodeRankEmbed-MMIR

说明：上述四个 Dense/Embedding MM-IR 方法已经作为后续检索 baseline 纳入计划，但当前还没有在 `SWE-bench Multimodal full-candidates` 和 `OmniGIRL full-candidates` 上形成完整、可汇总的 `metrics_3level` 结果。下一轮测评应按同一套三层 gold、同一套指标脚本运行，并补充到本文档中。

## 指标说明

排序指标：

- `Acc@K`：前 K 个预测中是否命中任意 gold 位置。
- `MRR@15`：第一个正确预测的倒数排名，最多看前 15 个预测。
- `MAP@15`：前 15 个预测的平均精度。
- `Empty`：该层级预测为空的样本比例。

集合指标：

- `SL`：严格成功率。只有当该层级的所有 gold 位置都被预测集合覆盖时才记为成功。
- `REC`：集合召回率。
- `PRE`：集合精确率。
- `F1`：集合精确率与召回率的调和平均。

本文档中的集合指标统一采用完整预测集合计算。这样可以更直接地比较不同方法最终输出候选集合的整体质量。

口径提示：LocAgent 论文中的 `Acc@K` 更严格，要求 top-K 预测覆盖该样本的所有 relevant locations 才算成功；LocAgent 项目原始 `evaluation/eval_metric.py` 中的 `acc_at_k` 也采用这种 full-coverage 口径。本文档为了展示排序召回曲线，将 `Acc@K` 统一定义为 hit-any，即 top-K 中命中任意 gold 即算成功；严格 full-coverage 成功率对应本文档中的 `SL`。

## 指标计算公式

本节公式参考 CoSIL 论文中用于 issue localization 的 `Top-N / MAP / MRR / Empty Rate` 指标，以及 GraphLocator 中用于集合定位质量的 `SuccLoc / Recall / Precision / F1` 指标。不同之处在于：本文档把这些指标统一扩展到三层定位，即 `File`、`Module`、`Function` 三个层级分别计算。

记评估样本集合为：

$$
D = \{1, 2, \ldots, N\}
$$

对任意样本 `i` 和任意定位层级 `l ∈ {file, module, function}`：

- `G_i^l` 表示该样本在层级 `l` 上的 gold location 集合；
- `P_i^l = [p_{i,1}^l, p_{i,2}^l, ..., p_{i,m}^l]` 表示模型在层级 `l` 上输出的有序预测列表；
- `P_{i,K}^l` 表示前 `K` 个预测；
- `S_{i,K}^l` 表示前 `K` 个预测去重后的集合；
- `S_i^l` 表示完整预测集合。

即：

$$
S_{i,K}^l = \mathrm{set}(P_{i,K}^l), \qquad S_i^l = \mathrm{set}(P_i^l)
$$

### Acc@K / Top-K

`Acc@K` 与 CoSIL 论文中的 `Top-N` 含义一致：只要前 `K` 个预测中命中任意一个 gold location，该样本就算成功。

$$
\mathrm{Acc@}K(l) =
\frac{1}{N}
\sum_{i=1}^{N}
\mathbf{1}\left[
G_i^l \cap S_{i,K}^l \neq \varnothing
\right]
$$

### MRR@15

`MRR@15` 衡量第一个正确预测出现得有多靠前。设：

$$
rank_i^l =
\min \left\{
r \mid 1 \le r \le 15,\ p_{i,r}^l \in G_i^l
\right\}
$$

如果前 15 个预测中没有命中，则该样本的 reciprocal rank 为 0。

$$
RR_{i,15}^l =
\begin{cases}
\frac{1}{rank_i^l}, & \text{if } rank_i^l \text{ exists} \\
0, & \text{otherwise}
\end{cases}
$$

$$
\mathrm{MRR@15}(l) =
\frac{1}{N}
\sum_{i=1}^{N}
RR_{i,15}^l
$$

### MAP@15

`MAP@15` 衡量多个 gold location 在排序列表中的整体命中质量。对样本 `i`，定义第 `r` 位是否命中：

$$
rel_i^l(r) =
\mathbf{1}\left[
p_{i,r}^l \in G_i^l
\right]
$$

前 `r` 位 precision 为：

$$
\mathrm{Precision}_{i,r}^l =
\frac{
\left|G_i^l \cap S_{i,r}^l\right|
}{r}
$$

则：

$$
AP_{i,15}^l =
\frac{1}{\left|G_i^l\right|}
\sum_{r=1}^{15}
\mathrm{Precision}_{i,r}^l \cdot rel_i^l(r)
$$

$$
\mathrm{MAP@15}(l) =
\frac{1}{N}
\sum_{i=1}^{N}
AP_{i,15}^l
$$

### Empty Rate

`Empty` 表示该层级没有任何预测的样本比例：

$$
\mathrm{Empty}(l) =
\frac{1}{N}
\sum_{i=1}^{N}
\mathbf{1}\left[
\left|P_i^l\right| = 0
\right]
$$

### 集合指标

### SL / SuccLoc

`SL` 是严格成功率。只有当该层级的所有 gold locations 都被预测集合覆盖时，样本才算成功：

$$
\mathrm{SL}(l) =
\frac{1}{N}
\sum_{i=1}^{N}
\mathbf{1}\left[
G_i^l \neq \varnothing
\ \land\
G_i^l \subseteq S_i^l
\right]
$$

### REC / Recall

$$
\mathrm{REC}_i^l =
\frac{
\left|G_i^l \cap S_i^l\right|
}{
\left|G_i^l\right|
}
$$

$$
\mathrm{REC}(l) =
\frac{1}{N}
\sum_{i=1}^{N}
\mathrm{REC}_i^l
$$

### PRE / Precision

$$
\mathrm{PRE}_i^l =
\frac{
\left|G_i^l \cap S_i^l\right|
}{
\left|S_i^l\right|
}
$$

如果 `S_i^l` 为空，则该样本 precision 记为 0。

$$
\mathrm{PRE}(l) =
\frac{1}{N}
\sum_{i=1}^{N}
\mathrm{PRE}_i^l
$$

### F1

$$
\mathrm{F1}_i^l =
\begin{cases}
\frac{
2 \cdot \mathrm{PRE}_i^l \cdot \mathrm{REC}_i^l
}{
\mathrm{PRE}_i^l + \mathrm{REC}_i^l
},
& \text{if } \mathrm{PRE}_i^l + \mathrm{REC}_i^l > 0 \\
0,
& \text{otherwise}
\end{cases}
$$

$$
\mathrm{F1}(l) =
\frac{1}{N}
\sum_{i=1}^{N}
\mathrm{F1}_i^l
$$

### 三层 gold 的构造口径

本文档中的三层 gold 采用统一构造方式：

1. **File gold**：来自样本中的 patch changed files 或 `files` 字段。
2. **Module gold**：根据 patch changed lines 与 `repo_structures` 中 class/module 实体的行号范围重叠得到。
3. **Function gold**：根据 patch changed lines 与 `repo_structures` 中 function/method 实体的行号范围重叠得到。

因此，所有 baseline 的三层评估都尽量共享同一套 gold construction 和 metric implementation。这样可以避免不同方法各用各的 module/function 定义，导致结果不可比。

## 关于 GALA 三层指标的核查

GALA 目录中确实生成了 `code_graph_*.json` 和 `repo_structure_*.json`，这些文件里包含候选代码图和仓库结构。但是当前用于评估的 `loc_results.json` 中：

- `final_files` 有最终文件级预测；
- `final_modules` / `final_functions` 已通过 GALA staged file candidates 与外部 `repo_structures` 派生生成；
- `gt_modules` / `gt_functions` 也通过 patch changed lines 与 `repo_structures` 的实体范围重叠得到。

因此 GALA 现在可以参与 module/function 的三层评估，但需要标注它的 module/function 不是原始 GALA 输出字段，而是由评估转换层根据 `edit_target -> matched -> code_seed -> snapshot_seed` 这些 staged file candidates 派生得到。这个口径与 CoSIL 的结构 fallback 类似，适合做三层定位能力分析，但不能解释为 GALA 原始 agent 直接输出了函数级定位。

## 60 样本主实验结果

### SWE-bench Multimodal 60：排序指标

| 方法 | 评估样本数 | File Acc@1 | File Acc@3 | File Acc@5 | File Acc@8 | File Acc@10 | File Acc@15 | Module Acc@1 | Module Acc@3 | Module Acc@5 | Module Acc@8 | Module Acc@10 | Module Acc@15 | Function Acc@1 | Function Acc@3 | Function Acc@5 | Function Acc@8 | Function Acc@10 | Function Acc@15 | File MRR@15 | Module MRR@15 | Function MRR@15 | 空预测率 File/Module/Function |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 60 | 35.00 | 51.67 | 55.00 | 58.33 | 60.00 | 61.67 | 18.33 | 30.00 | 35.00 | 41.67 | 43.33 | 48.33 | 10.00 | 18.33 | 20.00 | 25.00 | 25.00 | 28.33 | 44.40 | 25.21 | 14.98 | 3.33 / 3.33 / 3.33 |
| CoSIL | 60 | 26.67 | 45.00 | 50.00 | 50.00 | 50.00 | 50.00 | 21.67 | 30.00 | 36.67 | 38.33 | 38.33 | 38.33 | 3.33 | 8.33 | 11.67 | 15.00 | 18.33 | 23.33 | 35.33 | 27.29 | 7.52 | 3.33 / 10.00 / 10.00 |
| GALA | 60 | 40.00 | 60.00 | 61.67 | 61.67 | 61.67 | 61.67 | 8.33 | 16.67 | 21.67 | 21.67 | 21.67 | 21.67 | 3.33 | 8.33 | 10.00 | 10.00 | 11.67 | 13.33 | 46.81 | 13.39 | 6.19 | 0.00 / 0.00 / 13.33 |
| GraphLocator | 60 | 21.67 | 26.67 | 28.33 | 28.33 | 28.33 | 30.00 | 10.00 | 20.00 | 21.67 | 21.67 | 21.67 | 21.67 | 6.67 | 11.67 | 11.67 | 13.33 | 13.33 | 13.33 | 24.18 | 14.86 | 9.40 | 0.00 / 10.00 / 10.00 |
| BM25-MMIR | 60 | 25.00 | 43.33 | 48.33 | 58.33 | 60.00 | 66.67 | 15.00 | 33.33 | 40.00 | 51.67 | 60.00 | 65.00 | 11.67 | 20.00 | 28.33 | 36.67 | 38.33 | 43.33 | 36.36 | 27.96 | 19.41 | 0.00 / 0.00 / 0.00 |

### SWE-bench Multimodal 60：集合指标

| 方法 | File SL | File REC | File PRE | File F1 | Module SL | Module REC | Module PRE | Module F1 | Function SL | Function REC | Function PRE | Function F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 23.33 | 35.93 | 12.76 | 13.25 | 31.67 | 41.62 | 8.36 | 10.60 | 13.33 | 22.29 | 2.90 | 4.02 |
| CoSIL | 13.33 | 24.44 | 15.47 | 15.42 | 6.67 | 18.04 | 16.71 | 14.92 | 6.67 | 12.15 | 2.85 | 3.87 |
| GALA | 20.00 | 35.19 | 18.28 | 20.37 | 10.00 | 15.14 | 7.68 | 9.40 | 6.67 | 9.50 | 3.77 | 4.84 |
| GraphLocator | 8.33 | 13.75 | 20.08 | 13.62 | 10.00 | 13.47 | 12.14 | 11.45 | 3.33 | 6.62 | 5.13 | 4.89 |
| BM25-MMIR | 30.00 | 46.02 | 8.78 | 12.97 | 43.33 | 51.19 | 6.92 | 11.36 | 15.00 | 22.72 | 4.62 | 6.26 |

### OmniGIRL 60：排序指标

| 方法 | 评估样本数 | File Acc@1 | File Acc@3 | File Acc@5 | File Acc@8 | File Acc@10 | File Acc@15 | Module Acc@1 | Module Acc@3 | Module Acc@5 | Module Acc@8 | Module Acc@10 | Module Acc@15 | Function Acc@1 | Function Acc@3 | Function Acc@5 | Function Acc@8 | Function Acc@10 | Function Acc@15 | File MRR@15 | Module MRR@15 | Function MRR@15 | 空预测率 File/Module/Function |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 48 | 20.83 | 35.42 | 39.58 | 45.83 | 47.92 | 47.92 | 10.42 | 22.92 | 29.17 | 35.42 | 37.50 | 43.75 | 2.08 | 6.25 | 8.33 | 8.33 | 12.50 | 14.58 | 28.77 | 19.10 | 4.83 | 0.00 / 0.00 / 0.00 |
| CoSIL | 60 | 28.33 | 38.33 | 40.00 | 40.00 | 40.00 | 40.00 | 13.33 | 23.33 | 23.33 | 30.00 | 30.00 | 30.00 | 0.00 | 0.00 | 1.67 | 5.00 | 5.00 | 5.00 | 33.47 | 18.25 | 0.93 | 6.67 / 8.33 / 8.33 |
| GALA JS/TS | 17 | 23.53 | 47.06 | 52.94 | 52.94 | 52.94 | 52.94 | 0.00 | 17.65 | 17.65 | 17.65 | 17.65 | 17.65 | 0.00 | 0.00 | 5.88 | 5.88 | 5.88 | 5.88 | 33.82 | 7.84 | 1.47 | 0.00 / 0.00 / 0.00 |
| GraphLocator | 48 | 12.50 | 16.67 | 18.75 | 22.92 | 22.92 | 25.00 | 6.25 | 8.33 | 8.33 | 8.33 | 8.33 | 8.33 | 4.17 | 6.25 | 8.33 | 8.33 | 8.33 | 8.33 | 15.83 | 7.29 | 5.73 | 0.00 / 22.92 / 25.00 |
| BM25-MMIR | 48 | 6.25 | 16.67 | 25.00 | 35.42 | 41.67 | 47.92 | 2.08 | 8.33 | 14.58 | 16.67 | 18.75 | 25.00 | 6.25 | 12.50 | 12.50 | 16.67 | 18.75 | 20.83 | 15.28 | 7.32 | 9.95 | 0.00 / 0.00 / 0.00 |

### OmniGIRL 60：集合指标

| 方法 | File SL | File REC | File PRE | File F1 | Module SL | Module REC | Module PRE | Module F1 | Function SL | Function REC | Function PRE | Function F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LocAgent | 52.08 | 52.08 | 5.14 | 9.19 | 41.67 | 43.96 | 3.25 | 5.74 | 14.58 | 18.06 | 0.78 | 1.44 |
| CoSIL | 38.33 | 39.44 | 11.14 | 16.44 | 28.33 | 29.05 | 8.85 | 12.53 | 1.67 | 3.06 | 0.74 | 1.02 |
| GALA JS/TS | 41.18 | 46.08 | 11.37 | 17.86 | 17.65 | 17.65 | 4.61 | 7.25 | 5.88 | 5.88 | 0.53 | 0.98 |
| GraphLocator | 22.92 | 24.31 | 13.09 | 14.31 | 8.33 | 8.33 | 6.25 | 6.94 | 6.25 | 7.29 | 1.15 | 1.94 |
| BM25-MMIR | 41.67 | 44.44 | 3.47 | 6.36 | 18.75 | 21.88 | 2.25 | 3.72 | 16.67 | 18.06 | 2.48 | 4.07 |

## BM25-MMIR 全量候选结果

这里的结果使用所有可评估候选样本，而不是 60 样本子集。

### BM25-MMIR 全量候选：排序指标

| 数据集 | 评估样本数 | File Acc@1 | File Acc@3 | File Acc@5 | File Acc@8 | File Acc@10 | File Acc@15 | Module Acc@1 | Module Acc@3 | Module Acc@5 | Module Acc@8 | Module Acc@10 | Module Acc@15 | Function Acc@1 | Function Acc@3 | Function Acc@5 | Function Acc@8 | Function Acc@10 | Function Acc@15 | File MRR@15 | Module MRR@15 | Function MRR@15 | 空预测率 File/Module/Function |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SWE-bench Multimodal full-candidates | 102 | 26.47 | 41.18 | 46.08 | 52.94 | 58.82 | 65.69 | 13.73 | 30.39 | 37.25 | 44.12 | 50.00 | 56.86 | 11.76 | 21.57 | 26.47 | 32.35 | 35.29 | 39.22 | 36.07 | 25.16 | 18.88 | 0.00 / 0.00 / 0.00 |
| OmniGIRL full-candidates | 631 | 14.26 | 28.53 | 35.66 | 42.47 | 46.91 | 51.82 | 7.77 | 16.64 | 22.03 | 29.16 | 32.33 | 38.19 | 6.66 | 12.36 | 16.96 | 20.60 | 22.66 | 25.36 | 23.83 | 14.62 | 11.10 | 0.00 / 0.00 / 0.00 |

### BM25-MMIR 全量候选：集合指标

| 数据集 | File SL | File REC | File PRE | File F1 | Module SL | Module REC | Module PRE | Module F1 | Function SL | Function REC | Function PRE | Function F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SWE-bench Multimodal full-candidates | 31.37 | 45.69 | 7.39 | 11.38 | 36.27 | 44.36 | 5.69 | 9.57 | 11.76 | 20.07 | 3.99 | 5.70 |
| OmniGIRL full-candidates | 34.07 | 42.00 | 4.65 | 7.84 | 20.76 | 28.45 | 4.24 | 6.87 | 9.51 | 14.60 | 3.29 | 4.58 |

## 主要观察

1. BM25-MMIR 是一个很强的非 agent 检索 baseline。
   - 在 SWE-bench Multimodal 60 上，BM25-MMIR 的 File Acc@15 为 `66.67`，高于 LocAgent 的 `61.67`、GALA 的 `61.67`。
   - BM25-MMIR 在 SWE-bench Multimodal 60 上 Module Acc@15 为 `65.00`，Function Acc@15 为 `43.33`。
   - 这说明 issue text 与 multimodal compact context 中包含大量可被词法检索利用的定位线索。

2. 在已完成的 agent 类系统中，LocAgent 在 SWE-bench Multimodal 60 的三层指标上整体最强。
   - File Acc@10 为 `60.00`，Module Acc@10 为 `43.33`，Function Acc@10 为 `25.00`。
   - File Acc@15 为 `61.67`，Module Acc@15 为 `48.33`，Function Acc@15 为 `28.33`。
   - 空预测率较低，三个层级均为 `3.33`。

3. 当前 GALA 已经可以做派生三层评估，但强项仍主要在文件级定位。
   - SWE-bench Multimodal 60 上文件级排序较强，File Acc@10/15 均为 `61.67`。
   - 复评后，Module Acc@15 为 `21.67`，Function Acc@15 为 `13.33`。
   - 这些 module/function 是由 staged file candidates 和 `repo_structures` 派生得到，不是 GALA 原始 agent 直接输出，因此表中应保留这一说明。

4. GraphLocator 在这些多模态、多语言 benchmark 上稳定性和效率都比较弱。
   - SWE-bench Multimodal 60 上 File Acc@10 为 `28.33`，File Acc@15 为 `30.00`，Function Acc@10/15 均为 `13.33`。
   - OmniGIRL 60 上经过结构补评后 File 空预测率降为 `0.00`，但 Module/Function 空预测率仍为 `22.92` / `25.00`，说明旧 run 的实体级定位仍不稳定。

5. OmniGIRL 更难，而且不同 baseline 之间并不完全可直接比较。
   - LocAgent、GraphLocator、BM25-MMIR 在 60 样本实验中实际评估了 48 个样本。
   - CoSIL 评估了 60 个样本。
   - GALA JS/TS 版本只评估了 17 个 JS/TS 风格样本。
   - BM25-MMIR 的 OmniGIRL full-candidates 结果评估了 631 个样本。

6. 对输出候选较多的方法，集合精确率通常偏低。
   - 当方法输出较宽的候选列表时，`PRE` 和 `F1` 会被明显拉低。
   - 对定位搜索行为而言，`Acc@K`、`MRR` 这类排序指标通常更稳定。
   - 严格 `SL` 很有价值，但也更苛刻：必须覆盖该层级的所有 gold 位置才算成功。
   - 本文档中的集合指标统一采用完整预测集合口径，表示方法最终输出候选集合的整体质量。

## 待补测评

以下 Embedding/Dense 检索 baseline 已纳入 MM-IR 后续测评计划，但当前没有完整结果可汇总：

| 方法 | 当前状态 | 下一步 |
|---|---|---|
| E5-MMIR | 检索后端已规划接入，尚未形成完整三层指标 | 在 SWE-bench Multimodal full-candidates 与 OmniGIRL full-candidates 上运行并生成 `metrics_3level` |
| Jina-Code-v2-MMIR | 检索后端已规划接入，尚未形成完整三层指标 | 同上 |
| CodeSage-large-v2-MMIR | 检索后端已规划接入，尚未形成完整三层指标 | 同上 |
| CodeRankEmbed-MMIR | 检索后端已规划接入，尚未形成完整三层指标 | 同上 |

这些方法补测时应继续使用本文档中的统一三层 gold 构造和指标脚本。尤其需要注意：排序表中的 `Acc@K` 是 hit-any 口径；如果要和 LocAgent 论文原始表格严格对齐，还需要额外报告 full-coverage `Acc@K` 或使用本文档中的 `SL` 作为严格成功率参考。

## 结果文件索引

| 方法 | 数据集 | 指标文件 |
|---|---|---|
| LocAgent | SWE-bench Multimodal 60 | `/home/like/locCode/LocAgent/newtest/swebench_multimodal-60/results/openai_qwen3-vl-8b/eval/metrics_3level.md` |
| LocAgent | OmniGIRL 60 | `/home/like/locCode/LocAgent/newtest/omnigirl-60/results/openai_qwen3-vl-8b/eval/metrics_3level.md` |
| CoSIL | SWE-bench Multimodal 60 | `/home/like/locCode/CoSIL/newtest/swebench_multimodal-60/results/openai_qwen3-vl-8b/eval/metrics_3level.md` |
| CoSIL | OmniGIRL 60 | `/home/like/locCode/CoSIL/newtest/omnigirl-60/results/openai_qwen3-vl-8b/eval/metrics_3level.md` |
| GALA | SWE-bench Multimodal 60 | `/home/like/locCode/GALA/mytest/swebench-multimodal-60/results/qwen3-vl-8b/eval/metrics_3level.md` |
| GALA | OmniGIRL JS/TS 60 | `/home/like/locCode/GALA/mytest/omnigirl-js-ts-multimodal-60/results/qwen3-vl-8b/eval/metrics_3level.md` |
| GraphLocator | SWE-bench Multimodal 60 | `/home/like/locCode/GraphLocator/newtest/swebench_multimodal-60/results/openai_qwen3-vl-8b/eval/metrics_3level.md` |
| GraphLocator | OmniGIRL 60 | `/home/like/locCode/GraphLocator/newtest/omnigirl-60/results/openai_qwen3-vl-8b/eval/metrics_3level.md` |
| BM25-MMIR | SWE-bench Multimodal 60 | `/home/like/locCode/MM-IR/results/swebench_multimodal-60/bm25-mmir/eval/metrics_3level.md` |
| BM25-MMIR | OmniGIRL 60 | `/home/like/locCode/MM-IR/results/omnigirl-60/bm25-mmir/eval/metrics_3level.md` |
| BM25-MMIR | SWE-bench Multimodal full-candidates | `/home/like/locCode/MM-IR/results/swebench_multimodal-full-candidates/bm25-mmir/eval/metrics_3level.md` |
| BM25-MMIR | OmniGIRL full-candidates | `/home/like/locCode/MM-IR/results/omnigirl-full-candidates/bm25-mmir/eval/metrics_3level.md` |
