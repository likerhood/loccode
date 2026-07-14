# Automattic__wp-calypso-21409 证据 URL 误导与多 Baseline 轨迹分析

本文专门分析 SWE-bench Multimodal dev 全量样本 `Automattic__wp-calypso-21409`。这个样本很适合写论文动机，因为它不是“模型完全没有找到线索”，而是多个 baseline 都找到了 issue 里的强证据，却没有判断出这些证据在修复链路中的角色。

核心结论：**issue 里的 GitHub URL 指向 `isCurrentUserEmailVerified` selector，这是有效 evidence seed，但不是 patch target。真正需要定位的是 WooCommerce store signup/dashboard/address flow 的 patch closure。当前 baseline 普遍缺少“证据角色识别”和“从证据节点扩展到真实修改闭包”的机制。**

## 1. 真实数据来源

本文只使用本地真实存在的结果、日志和样本文件：

| 类型 | 真实路径 |
|---|---|
| 原始样本与 gold patch | `/home/like/locCode/GraphLocator/datasets/swebench_multimodal_full_dev.jsonl` |
| Qwen3-VL-8B LocAgent 预测和轨迹 | `/home/like/locCode/LocAgent/newtest/swebench_multimodal-full-dev/results/openai_qwen3-vl-8b/location/loc_outputs.jsonl`；`loc_trajs.jsonl` |
| Qwen3-VL-8B CoSIL 轨迹日志 | `/home/like/locCode/CoSIL/newtest/swebench_multimodal-full-dev/results/openai_qwen3-vl-8b/file_level/localization_logs/Automattic__wp-calypso-21409.log` |
| Qwen3-VL-8B 汇总结果 | `/home/like/locCode/collected_results/qwen8b_mimo_compare_20260711_212220/swebench_multimodal-full-dev/qwen3-vl-8b/` |
| Mimo-v2.5 解压结果根目录 | `/home/like/locCode/unpacked_results/swefull_results_mimov2.5/swebench_multimodal_full_dev_mimo-v2.5_20260712_152753/repo/` |
| Mimo-v2.5 LocAgent 轨迹 | `.../LocAgent/newtest/swebench_multimodal-full-dev/results/mimo-v2.5/location/loc_trajs.jsonl` |
| Mimo-v2.5 服务器运行日志 | `.../logs/server_swebench_multimodal_full_dev_20260712_121456/run_swebench_multimodal_full_dev.log` |
| BM25-MMIR 结果 | `/home/like/locCode/MM-IR/results/swebench_multimodal-full-candidates/bm25-mmir/loc_results.json` |

注意：BM25-MMIR 的本地结果目录命名是 `swebench_multimodal-full-candidates`，但样本集合对应 SWE-bench Multimodal dev 全量候选；本文按真实路径记录。

## 2. 样本内容和 Gold Patch

Issue 标题是：

```text
Store: Signup Flow needs to require email verification
```

Issue 包含两个截图：

```text
https://user-images.githubusercontent.com/22080/34058152-cf2dccfa-e18e-11e7-99f6-8a6f1f7a2dc4.png
https://user-images.githubusercontent.com/22080/34058228-0f78b5f4-e18f-11e7-8133-e57bceea7374.png
```

还包含一个代码 URL：

```text
https://github.com/Automattic/wp-calypso/blob/master/client/state/current-user/selectors.js#L157
```

这个 URL 指向的 selector 是：

```text
client/state/current-user/selectors.js
157: export const isCurrentUserEmailVerified = createCurrentUserSelector( 'email_verified', false );
```

但是 gold patch 真实修改文件是下面 10 个：

```text
client/extensions/woocommerce/app/dashboard/index.js
client/extensions/woocommerce/app/dashboard/required-plugins-install-view.js
client/extensions/woocommerce/app/dashboard/setup-footer.js
client/extensions/woocommerce/app/dashboard/store-location-setup-view.js
client/extensions/woocommerce/components/address-view/index.js
client/extensions/woocommerce/components/form-location-select/states.js
client/extensions/woocommerce/components/query-locations/index.js
client/extensions/woocommerce/lib/countries/index.js
client/extensions/woocommerce/state/sites/locations/selectors.js
client/extensions/woocommerce/state/sites/settings/actions.js
```

### 2.1 这个 issue 到底要求修什么

这个 issue 的核心不是“`isCurrentUserEmailVerified` selector 有 bug”，也不是“当前用户 state 取值不对”。真正的问题是：**WooCommerce Store signup 流程只提示用户验证邮箱，但没有在必要场景下阻止用户继续进入后续 setup / `wp-admin`。**

Issue 背景里说得比较绕，可以拆成下面这条业务链：

1. 新用户购买或开通 Store 后，会进入 Store signup / setup flow。
2. 页面会提示用户去验证邮箱，但这个提示只是 notice，不是强制步骤。
3. 对于美国、加拿大这种 Calypso 里支持 Store management 的国家，用户可以继续留在 Calypso dashboard checklist 里完成后续 setup。
4. 对于不支持的国家，流程会把用户送到 WooCommerce 的 `wp-admin` setup 页面。
5. 但是如果用户还没有验证邮箱，当前 WPCOM session 不能有效通过 `wp-admin` 认证。
6. 所以，在用户进入 `wp-admin` 前，必须增加一个 email verification gate：未验证就不要继续跳转，已验证才允许进入后续 setup。

两张截图分别对应这个链路中的两个关键点：

| 证据 | 截图展示的内容 | 对定位的真实含义 |
|---|---|---|
| 第一张截图 | 用户购买 Business Plan 后看到 “Thank you for your purchase!” / “Create your store!” 按钮，同时顶部有 “Please check your email to confirm your address.” 的提示条 | 现有问题：系统已经知道邮箱未验证，也已经给了提示，但用户仍然可以继续点按钮进入后续流程 |
| 第二张截图 | “Store Location” 地址页，要求用户输入店铺地址和国家/地区 | 新逻辑的分叉点：只有用户填完地址后，系统才知道国家是不是 US/CA，从而决定继续 Calypso dashboard，还是进入 `wp-admin` 前先强制邮箱验证 |

Issue 里的 GitHub URL 指向：

```text
client/state/current-user/selectors.js
157: export const isCurrentUserEmailVerified = createCurrentUserSelector( 'email_verified', false );
```

这个 URL 是有效证据，但它的角色是 **helper / evidence seed**，不是 **patch target**。也就是说，修复确实需要使用“当前用户邮箱是否已验证”这个状态，但不需要修改这个 selector 本身。真正需要改的是 WooCommerce store setup 流程如何读取这个状态、如何结合国家信息分叉、如何阻止或允许跳转。

可以把真实修复逻辑理解成下面的伪代码：

```text
用户进入 Store Location 地址页
  -> 加载国家/州列表
  -> 用户填写店铺地址和国家
  -> 保存 store address / settings
  -> 判断国家是否支持 Calypso 内管理
       如果是 US/CA：
         继续显示 Calypso dashboard setup checklist
       如果不是 US/CA：
         检查 isCurrentUserEmailVerified(state)
           如果已验证：
             redirect 到 site.options.admin_url，也就是 wp-admin / WC setup
           如果未验证：
             停在验证步骤，显示 busy/disabled 状态或提示用户完成验证
```

因此，gold patch 涉及 10 个文件是合理的。它不是单点 bug，而是一个跨 UI、国家数据、地址表单、settings 保存、redirect 控制的流程级改动：

| Gold 文件 | 在修复中的作用 |
|---|---|
| `app/dashboard/index.js` | dashboard 层拿到 `adminURL`，接收 redirect 请求，决定什么时候跳转到 `wp-admin` |
| `app/dashboard/store-location-setup-view.js` | 核心流程文件：连接地址表单、国家判断、邮箱验证状态和 redirect |
| `components/address-view/index.js` | 地址页表单展示和提交逻辑 |
| `components/form-location-select/states.js` | 国家/州选择相关逻辑 |
| `components/query-locations/index.js` | 新增 location 数据查询组件，保证国家/州数据可用 |
| `lib/countries/index.js` | 新增 `isStoreManagementSupportedInCalypsoForCountry`，定义 US/CA 支持判断 |
| `state/sites/locations/selectors.js` | 判断 locations 是否加载、读取国家/州数据 |
| `state/sites/settings/actions.js` | 保存 store address / site settings |
| `app/dashboard/setup-footer.js` | footer button 增加 `busy` 状态，避免验证/跳转过程中继续点击 |
| `app/dashboard/required-plugins-install-view.js` | 调整文案，不再把流程描述绑定到 US/CA 的旧逻辑 |

这也是为什么这个样本会误导 baseline：issue 里最显眼的代码 URL 是 selector，但真正 patch target 是 selector 的“使用场景”和“业务闭包”。好的定位系统需要先判断 URL 是证据入口还是修改目标，再沿着 WooCommerce Store setup flow 扩展。

### 2.2 Gold Patch 的关键含义

真实 patch 不是只加一个 email selector 判断，而是重构 WooCommerce store setup 的完整流程：

```diff
diff --git a/client/extensions/woocommerce/app/dashboard/store-location-setup-view.js b/client/extensions/woocommerce/app/dashboard/store-location-setup-view.js
@@ -20,16 +20,22 @@ import {
+import { bumpStat } from 'state/analytics/actions';
-import { getCountryData, getCountries } from 'woocommerce/lib/countries';
+import {
+	areLocationsLoaded,
+	getCountriesWithStates,
+} from 'woocommerce/state/sites/locations/selectors';
+import { isStoreManagementSupportedInCalypsoForCountry } from 'woocommerce/lib/countries';
+import QueryLocations from 'woocommerce/components/query-locations';
@@ -58,6 +64,8 @@ class StoreLocationSetupView extends Component {
+		adminURL: PropTypes.string.isRequired,
+		onRequestRedirect: PropTypes.func.isRequired,
```

`store-location-setup-view.js` 是最核心的入口：它连接 address form、country 判断、email verification selector、redirect 到 `wp-admin`。

```diff
diff --git a/client/extensions/woocommerce/app/dashboard/setup-footer.js b/client/extensions/woocommerce/app/dashboard/setup-footer.js
@@ -12,10 +12,10 @@ import PropTypes from 'prop-types';
-const SetupFooter = ( { disabled, label, onClick, primary } ) => {
+const SetupFooter = ( { busy, disabled, label, onClick, primary } ) => {
-			<Button disabled={ disabled } onClick={ onClick } primary={ primary }>
+			<Button busy={ busy } disabled={ disabled } onClick={ onClick } primary={ primary }>
```

`setup-footer.js` 说明 patch 还要处理按钮 busy/disabled 状态，不只是 selector。

```diff
diff --git a/client/extensions/woocommerce/lib/countries/index.js b/client/extensions/woocommerce/lib/countries/index.js
@@ -32,6 +32,16 @@ export const getCountryData = country => {
+/**
+ * Whether or not we support store management in calypso for
+ * the passed country
+ */
+export const isStoreManagementSupportedInCalypsoForCountry = country => {
+	return includes( [ 'US', 'CA' ], country );
+};
```

`countries/index.js` 是 supported/non-supported country 分支逻辑。

```diff
diff --git a/client/extensions/woocommerce/components/query-locations/index.js b/client/extensions/woocommerce/components/query-locations/index.js
--- /dev/null
+++ b/client/extensions/woocommerce/components/query-locations/index.js
@@ -0,0 +1,35 @@
+import { fetchLocations } from 'woocommerce/state/sites/locations/actions';
```

`query-locations/index.js` 是新文件，说明真实修复还涉及位置数据加载。

因此这个样本的定位目标是一个跨文件闭包：

```text
email verified selector
  -> StoreLocationSetupView
  -> AddressView / FormStateSelect
  -> countries supported-country logic
  -> locations selectors / QueryLocations
  -> settings actions / dashboard redirect / setup footer
```

## 3. Clean15 评估结果对比

### 3.1 Qwen3-VL-8B Clean15

| Baseline | file_rec@all | module_rec@all | function_rec@all | 真实预测倾向 |
|---|---:|---:|---:|---|
| LocAgent | 0.00 | 0.00 | 0.00 | `current-user/selectors.js`、theme/ui state、server loader |
| CoSIL | 0.00 | 0.00 | 0.00 | signup step 文件 + `current-user/selectors.js` |
| GraphLocator | 0.00 | 0.00 | 0.00 | `client/jetpack-connect/signup.js` |
| GALA | 0.00 | 0.00 | 0.00 | signup step / plans 文件 |

Qwen3-VL-8B 的共同问题是：强跟随 issue 中的 `wp-admin`、`signup`、`isCurrentUserEmailVerified`、截图 URL，未能转到 WooCommerce dashboard/address flow。

### 3.2 Mimo-v2.5 Clean15

| Baseline | file_rec@all | module_rec@all | function_rec@all | 真实预测倾向 |
|---|---:|---:|---:|---|
| LocAgent | 0.10 | 0.20 | 0.10 | 命中 `store-location-setup-view.js`，但漏掉 9/10 gold 文件 |
| CoSIL | 0.00 | 0.00 | 0.00 | `current-user/selectors.js`、signup config、email-verification |
| GraphLocator | 0.00 | 0.00 | 0.00 | current-user/email verification、signup、Mailchimp setup |
| GALA | 0.10 | 0.20 | 0.30 | 命中 `countries/index.js`，但主闭包不完整 |
| BM25-MMIR | 0.10 | 0.20 | 0.10 | 命中 `store-location-setup-view.js`，但排序后续发散 |

Mimo-v2.5 比 Qwen3-VL-8B 更容易把 “Store Location” 图像文本和 WooCommerce dashboard 关联起来，但仍然没有把单个命中扩展成完整 patch closure。

## 4. Baseline 真实轨迹与失败分析

### 4.1 Qwen3-VL-8B LocAgent：被 issue 上下文自动补词牵引

真实日志：

```text
/home/like/locCode/baseline_run_logs/swebench_multimodal_full_dev_parallel_20260707_231510/locagent.log
```

轨迹片段：

```text
2026-07-07 23:20:44 auto_search_main.py INFO Executing code:
print(search_code_snippets(**{}))

OBSERVATION:
search_code_snippets was called without search_terms or line_nums.
Auto-filled search_terms from the issue context:
['wp-admin', 'isCurrentUserEmailVerified', '/wp-admin',
 '//user-images.githubusercontent.com/22080/34058152-cf2dccfa-e18e-11e7-99f6-8a6f1f7a2dc4.png',
 'user-images.githubusercontent.com', '22080',
 '34058152-cf2dccfa-e18e-11e7-99f6-8a6f1f7a2dc4.png',
 '//user-images.githubusercontent.com/22080/34058228-0f78b5f4-e18f-11e7-8133-e57bceea7374.png'].
Using multi-language default file pattern '**/*'.
```

这个片段非常关键：LocAgent 没有先做证据角色判断，而是把 issue 里的 URL、图片 URL、`wp-admin`、selector 名称直接作为搜索词。结果第一轮搜索被低层 selector、server route、UI state 等泛化文件牵引。

最终输出：

```text
client/state/current-user/selectors.js
client/state/themes/selectors.js
client/state/ui/selectors.js
client/state/themes/utils.js
client/state/ui/guided-tours/contexts.js
client/state/utils.js
client/state/ui/editor/image-editor/actions.js
server/pages/index.js
server/bundler/loader.js
```

失败原因：

1. `isCurrentUserEmailVerified` 被当成 target，而不是 evidence。
2. `wp-admin` 被映射到 server route/loader，而不是 WooCommerce redirect behavior。
3. 图片 URL 被当成搜索 token，没有转成稳定 UI 语义：`Store Location`、`Street address`、`Create your store`、`non-supported country fork`。

### 4.2 Mimo-v2.5 LocAgent：找到核心入口，但没有闭包扩展

真实日志：

```text
/home/like/locCode/unpacked_results/swefull_results_mimov2.5/swebench_multimodal_full_dev_mimo-v2.5_20260712_152753/repo/logs/server_swebench_multimodal_full_dev_20260712_121456/run_swebench_multimodal_full_dev.log
```

Mimo 版本的 LocAgent 先加载多语言 fallback：

```text
[locagent] Graph index for Automattic__wp-calypso-21409 has no file nodes; using multilingual graph fallback.
[locagent] Loaded repo structure index for Automattic__wp-calypso-21409: files=7023 symbols=15584
```

它明确搜索了 selector 和 email verification：

```text
print(search_code_snippets(**{
  'search_terms': ['isCurrentUserEmailVerified', 'email verified', 'emailVerified'],
  'file_path_or_pattern': '**/*'
}))
```

这次搜索命中了真实 gold 文件之一：

```text
Found code snippet in file `client/extensions/woocommerce/app/dashboard/store-location-setup-view.js`.

213 | <AddressView
217 |   onChange={ this.onChange }
219 | <SetupFooter
220 |   disabled={ submitDisabled }
221 |   onClick={ this.onNext }
229 | closeVerifyEmailDialog = () => {
231 |   // Re-fetch the user to see if they actually took care of things
266 | const currentUserEmailVerified = isCurrentUserEmailVerified( state );
```

又命中了该文件顶部的真实依赖：

```text
Found code snippet in file `client/extensions/woocommerce/app/dashboard/store-location-setup-view.js`.

17 | import AddressView from 'woocommerce/components/address-view';
25 | import { getCountryData, getCountries } from 'woocommerce/lib/countries';
26 | import { isCurrentUserEmailVerified } from 'state/current-user/selectors';
27 | import { setSetStoreAddressDuringInitialSetup } from 'woocommerce/state/sites/setup-choices/actions';
28 | import SetupFooter from './setup-footer';
29 | import SetupHeader from './setup-header';
30 | import SetupNotices from './setup-notices';
```

后续搜索路径也有明显方向：

```text
search_terms=["onNext", "doInitialSetup", "isSupportedCountry", "getCountryData"],
file_path_or_pattern="client/extensions/woocommerce/**/*"

search_terms=["getCountries", "getCountryData", "supported", "US", "CA"],
file_path_or_pattern="client/extensions/woocommerce/lib/countries.js"
```

最终输出：

```text
client/extensions/woocommerce/app/dashboard/store-location-setup-view.js
line: 133-189
class: StoreLocationSetupView
function: onNext

client/extensions/woocommerce/app/dashboard/store-location-setup-view.js
line: 39-48
class: StoreLocationSetupView

client/extensions/woocommerce/lib/countries/index.js
line: 23-25
function: getCountries

client/extensions/woocommerce/app/dashboard/setup-notices.js
line: 26-51
class: SetupNotices
function: possiblyRenderEmailWarning

client/state/current-user/selectors.js
function: isCurrentUserEmailVerified
```

分析：

Mimo LocAgent 已经解决了“找不到入口”的问题，但没有解决“闭包覆盖”的问题。它找到了 `store-location-setup-view.js`，也触达 `countries/index.js` 和 `setup-notices.js`，但没有继续扩展到：

```text
dashboard/index.js
required-plugins-install-view.js
setup-footer.js
address-view/index.js
form-location-select/states.js
query-locations/index.js
state/sites/locations/selectors.js
state/sites/settings/actions.js
```

这说明 agent 需要一个 explicit patch closure step：当定位到 `StoreLocationSetupView` 后，不能立即 finish，应沿着 import、render child、Redux selector/action、new file requirement 继续展开一轮。

### 4.3 CoSIL：单轮 top-5 文件定位被 signup 词汇主导

Qwen3-VL-8B CoSIL 真实日志：

```text
/home/like/locCode/CoSIL/newtest/swebench_multimodal-full-dev/results/openai_qwen3-vl-8b/file_level/localization_logs/Automattic__wp-calypso-21409.log
```

日志中 prompt 已经包含视觉证据：

```text
[Visual Evidence] Image 1:
... “Business Plan $299.00” ... “Create your store!” ...
“We’ve sent a message to [redacted]@gmail.com. Please check your email to confirm your address.”

[Visual Evidence] Image 2:
... A signup flow screen titled “Store Location” ...
“Howdy! Ready to start selling? First we need to know where you are in the world.”
```

但 CoSIL 输出是：

```text
client/signup/steps/site.js
client/signup/steps/plans.js
client/signup/steps/design-type-with-store.js
client/signup/steps/site-or-domain.js
client/state/current-user/selectors.js
```

规范化后实际预测：

```text
client/signup/steps/site/index.jsx
client/signup/steps/design-type-with-store/index.jsx
client/signup/steps/site-or-domain/index.jsx
client/signup/steps/plans/index.jsx
client/state/current-user/selectors.js
```

Mimo-v2.5 CoSIL 输出：

```text
client/state/current-user/selectors.js
client/signup/config/flows.js
client/signup/config/steps.js
client/signup/steps/design-type-with-store/pressable-store/index.jsx
client/components/email-verification/index.js
```

失败原因：

CoSIL 是 file-level top-5，一次性读 issue + repo tree 后输出文件。它没有交互式验证，也没有“证据 seed -> target closure”的过程。因此它会优先选择词面更近的 `signup`、`email-verification` 和 `current-user`，而不是 WooCommerce dashboard/address 子系统。

### 4.4 GraphLocator：因果链启动正确，但图搜索粒度和 seed 转换失败

Qwen3-VL-8B GraphLocator 真实日志：

```text
/home/like/locCode/baseline_run_logs/swebench_multimodal_full_dev_parallel_20260707_231510/graphlocator.log
```

起始 search tool call：

```text
<name=search_node>
<arguments>
<node_type>FILE</node_type>
<node_name>isCurrentUserEmailVerified</node_name>
</arguments>
</name>
```

下一轮：

```text
<name=search_node>
<arguments>
<node_type>FILE</node_type>
<node_name>signup</node_name>
</arguments>
</name>
```

Qwen3-VL-8B GraphLocator 最终预测：

```text
client/jetpack-connect/signup.js
```

Mimo-v2.5 GraphLocator 日志里推理起点其实是合理的：

```text
I'll help you localize the relevant code for this email verification issue in the Store signup flow.

Analysis:
1. The issue is about adding email verification requirement in the Store signup flow for non-supported countries
2. Key elements mentioned:
   - Address Page form component
   - Fork in flow based on country support (US, CA vs others)
   - `isCurrentUserEmailVerified` selector from `client/state/current-user/selectors.js`
   - Need to check email verification before proceeding for non-supported countries
```

但是 Mimo-v2.5 GraphLocator 最终预测仍偏向：

```text
client/state/current-user/selectors.js
client/extensions/woocommerce/app/settings/email/mailchimp/setup-steps/key-input.js
client/signup/steps/design-type-with-atomic-store/new-site-image.jsx
client/signup/steps/design-type-with-store/new-site-image.jsx
client/state/current-user/email-verification/actions.js
...
```

失败原因：

GraphLocator 的因果文字分析识别了 “Address Page + country fork + email verification”，但 graph search 的 query 仍落在 `isCurrentUserEmailVerified` 和 `signup` 这类证据词上。它没有把 `Address Page` 翻译成 `StoreLocationSetupView -> AddressView`，也没有把 `supported countries US/CA` 翻译成 `countries/index.js` 和 `locations/selectors.js`。

### 4.5 GALA：图种子质量随模型变化，但仍缺少 edit-target 闭包

Qwen3-VL-8B GALA 结果：

```text
snapshot_seed_files:
client/signup/steps/site-or-domain/index.jsx
client/signup/steps/design-type-with-store/index.jsx
client/signup/steps/design-type-with-atomic-store/index.jsx
client/signup/steps/plans/index.jsx
client/signup/steps/plans-without-free/index.jsx

matched_files: []
edit_target_files: []
final_files:
client/signup/steps/site-or-domain/index.jsx
client/signup/steps/design-type-with-store/index.jsx
client/signup/steps/design-type-with-atomic-store/index.jsx
client/signup/steps/plans/index.jsx
client/signup/steps/plans-without-free/index.jsx
```

Mimo-v2.5 GALA 结果：

```text
snapshot_seed_files:
client/extensions/woocommerce/components/store-address/index.js
client/extensions/woocommerce/lib/countries/index.js
client/state/current-user/selectors.js
client/signup/config/flows.js
client/signup/config/steps.js

edit_target_files:
client/signup/config/flows.js
client/state/current-user/selectors.js

final_files:
client/signup/config/flows.js
client/state/current-user/selectors.js
client/extensions/woocommerce/components/store-address/index.js
client/extensions/woocommerce/lib/countries/index.js
client/signup/config/steps.js
```

Mimo GALA 比 Qwen GALA 更好，至少命中 `countries/index.js`，但仍然没有把 `store-address` 转换为真实 gold 的 `address-view/index.js`、`store-location-setup-view.js`、`dashboard/index.js` 和 Redux locations/settings 文件。

失败原因：

GALA 的 seed 机制更依赖“图像文本和代码文件名对齐”。当图像里出现 `Store Location`、`Street address`，它能靠语义找到 `store-address` 和 `countries`，但缺少对当前仓库真实组件结构的验证：真实 patch 的 address UI 是 `woocommerce/components/address-view/index.js`，流程入口是 `dashboard/store-location-setup-view.js`，不是 `store-address/index.js`。

### 4.6 BM25-MMIR：词面召回命中核心文件，但排序和闭包不够

真实路径：

```text
/home/like/locCode/MM-IR/results/swebench_multimodal-full-candidates/bm25-mmir/loc_results.json
```

BM25-MMIR 的 top files：

```text
client/extensions/woocommerce/app/dashboard/store-location-setup-view.js
client/blocks/eligibility-warnings/hold-list.jsx
client/signup/steps/design-type-with-atomic-store/index.jsx
client/components/tinymce/plugins/simple-payments/dialog/form.jsx
client/signup/processing-screen/index.jsx
client/me/help/help-contact/index.jsx
client/components/domains/transfer-domain-step/transfer-domain-precheck.jsx
client/extensions/wp-job-manager/components/setup/page-setup/index.jsx
client/components/tinymce/plugins/media/plugin.jsx
client/state/plans/test/fixture/index.js
client/my-sites/plans-features-main/index.jsx
client/jetpack-connect/sso.jsx
assets/stylesheets/shared/functions/_z-index.scss
client/my-sites/domains/domain-management/edit-contact-info/form-card.jsx
client/signup/config/flows.js
```

Clean15 指标：

```text
file_rec@15 = 0.1
module_rec@15 = 0.2
function_rec@15 = 0.1
```

失败原因：

BM25 对 `Store Location`、`email verified`、`Address Page` 这类词面很敏感，所以能把 `store-location-setup-view.js` 排到第一。但它没有代码语义推理能力，不能从 `store-location-setup-view.js` 扩展到 `SetupFooter`、`AddressView`、`QueryLocations`、`locations selectors`、`settings actions` 等配套文件。

## 5. 这个样本暴露的共同问题

### 5.1 URL 是 evidence，不一定是 target

这个样本的 URL 是：

```text
client/state/current-user/selectors.js#L157
```

它提供了 “如何判断 email verified” 的证据，但真实修改不在这个 selector。所有失败 baseline 都不同程度地把这个 URL 当成 target anchor。

正确处理应该是：

```text
code-url/evidence-only:
  client/state/current-user/selectors.js#isCurrentUserEmailVerified

patch-target candidates:
  modules that call this selector inside the Store Location / WooCommerce dashboard flow
```

### 5.2 图片是 UI 症状和页面入口，不是文件名搜索词

两张图片分别提供：

```text
Image 1: email verification notice is shown but non-blocking
Image 2: Store Location address page, before wp-admin redirect
```

这些信息应该被转成结构化 UI event：

```text
notice shown but not blocking
address form submitted
country branch US/CA vs others
redirect to wp-admin
```

而不是把图片 URL 当成 BM25 token。

### 5.3 单点命中不等于完整定位

Mimo LocAgent 和 BM25 都命中 `store-location-setup-view.js`，但 Clean15 file_rec@all 仍只有 0.10。这说明这个样本不是 top-1 retrieval 问题，而是 patch closure 问题。

真正的 closure 至少包含：

```text
entry component:
  store-location-setup-view.js

child UI:
  setup-footer.js
  address-view/index.js
  form-location-select/states.js

data loading:
  query-locations/index.js
  locations/selectors.js

business rule:
  countries/index.js

side effects / redirect:
  dashboard/index.js
  settings/actions.js
  required-plugins-install-view.js
```

## 6. 对框架设计的直接启发

### 6.1 证据角色识别

在 agent 搜索前，先把 issue 证据分类：

| 证据 | 角色 | 对搜索的使用方式 |
|---|---|---|
| `current-user/selectors.js#L157` | `code-url/evidence-only` | 找调用者、不要直接作为 target |
| `isCurrentUserEmailVerified` | `state-selector` | 沿引用链找 flow 使用点 |
| 图片 1 notice | `ui-symptom` | 找 notice/blocking behavior |
| 图片 2 Store Location | `page-entry` | 找页面 component 和 submit handler |
| `US, CA` | `business-rule` | 找 country support helper |
| `wp-admin` | `redirect-target` | 找 redirect/admin URL 处理，不直接找 server route |

### 6.2 多模态 query reformulation

应从图片和 URL 生成多路 query：

```text
UI query:
  "Store Location", "Howdy! Ready to start selling?", "Street address"

State query:
  isCurrentUserEmailVerified, email_verified

Business query:
  supported countries, US, CA, country support

Flow query:
  onNext, doInitialSetup, redirectURL, adminURL, wp-admin
```

然后要求 agent 对每路 query 产生的文件做角色标注：

```text
selector file: evidence
flow component: candidate target
child component: closure target
business helper: closure target
redux selector/action: closure target
```

### 6.3 Patch closure verifier

当一个文件被认为是核心入口，例如：

```text
client/extensions/woocommerce/app/dashboard/store-location-setup-view.js
```

verifier 应主动追问：

1. 这个 component render 了哪些 child component？
2. submit handler 调用了哪些 action？
3. 新的 branch 条件依赖哪些 selector/helper？
4. 需要新增 query/data loader 吗？
5. redirect 行为在哪个父组件完成？

这个过程可以把 Mimo LocAgent 的 `0.10/0.20/0.10` 进一步扩展到更完整的 gold closure。

## 7. 论文动机可用表述

这个样本说明，真实多模态 issue 定位不是简单的“图片 + 文本检索”。Issue 里的 URL、截图和函数名经常是 evidence seed，而不是最终 patch target。现有 baseline 的主要问题不是完全看不懂 issue，而是缺少 evidence role classification 和 patch closure expansion：它们要么把 code URL 当成目标文件，要么命中核心入口后提前停止。

因此，我们的方法可以围绕下面的故事展开：

> 对多模态跨语言 Issue，agent 首先需要把视觉证据、URL 证据、代码符号证据解析成带角色的 evidence graph；然后沿调用、渲染、Redux state/action、业务规则和页面跳转关系扩展候选；最后由 verifier 判断候选集合是否覆盖完整 patch closure，而不是只返回最像 issue 文本的 top-k 文件。
