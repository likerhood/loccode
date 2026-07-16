# Benchmark 多模态字段真实性核对与典型样本案例

本文是对 `014_Clean15样本图片URL证据类型与多模态定位处理方案.md` 的补充核对。重点回答三个问题：

1. benchmark 里的图片到底是什么格式，是本地图片文件还是 URL；
2. SWE-bench Multimodal 与 OmniGIRL 的 URL 内容类型分别是什么；
3. 每种多模态类型给出可复核的真实样本，包含完整 issue 文本和全部多模态链接。

## 1. 图片字段到底是什么格式

结论：当前本地 prepared benchmark 中，图片不是本地图片文件路径，而是 **URL 字符串**。

| 数据集 | 图片字段 | 字段格式 | 说明 |
|---|---|---|---|
| SWE-bench Multimodal | `image_urls` | JSON list，元素是 `https://...png/jpg/gif/...` | 主字段，直接给图片 URL |
| SWE-bench Multimodal | `image_assets` | JSON object，键为 `problem_statement`/`patch`/`test_patch`，值为 URL list | 标明图片来自 issue 正文、patch 还是 test patch；本地样本里主要来自 `problem_statement` |
| OmniGIRL full-candidates | `image_urls` | JSON list，元素是 URL | 没有 `image_assets` 字段，图片多数是 GitHub user-images 或外部图片 URL |
| OmniGIRL unified60 | `image_urls` | JSON list，元素是 URL | 额外有 `num_images`、`modality` 等准备阶段统计字段 |

字段核对示例：`LocAgent/newtest/swebench_multimodal-full-dev/data/samples.jsonl` 第一条 `Automattic__wp-calypso-21409` 的 `image_urls` 是：

```json
[
  "https://user-images.githubusercontent.com/22080/34058152-cf2dccfa-e18e-11e7-99f6-8a6f1f7a2dc4.png",
  "https://user-images.githubusercontent.com/22080/34058228-0f78b5f4-e18f-11e7-8133-e57bceea7374.png"
]
```

因此后续所谓“图片处理”，实际首先要处理的是 **图片 URL 解析、下载/缓存、视觉内容理解、再转成代码搜索约束**。如果只把 URL 字符串交给 LLM，模型并没有真正看到图片。

## 2. Raw prepared 数据的多模态分布核对

下面表格直接从本地 `samples.jsonl` 统计。这里是 raw prepared 数据，不等同于 Clean15；Clean15 会进一步过滤 module/function 不可映射或 gold 数量超过 15 的样本。

| 数据集 | 样本数 | 图片+URL | 仅图片 | 仅URL | 纯文本 | image_urls 总数 | issue 正文额外图片 URL |
|---|---:|---:|---:|---:|---:|---:|---:|
| SWE-bench Multimodal dev 全量 raw 102 | 102 | 64 | 38 | 0 | 0 | 301 | 4 |
| SWE-bench Multimodal 60 raw 60 | 60 | 35 | 25 | 0 | 0 | 203 | 2 |
| OmniGIRL full-candidates raw 631 | 631 | 32 | 16 | 583 | 0 | 79 | 0 |
| OmniGIRL unified60 raw 60 | 60 | 14 | 6 | 28 | 12 | 37 | 0 |

解释：

- `图片+URL`：`image_urls` 非空，同时存在非图片 URL，例如 GitHub、playground、文档或外部网页。

- `仅图片`：只有 `image_urls`，没有非图片 URL。

- `仅URL`：没有图片，但有网页/代码/文档/PR 等 URL。

- `纯文本`：既没有图片字段，也没有可抽取网页 URL。

- `issue 正文额外图片 URL`：正文里出现但没有写入 `image_urls` 字段的图片 URL，用于检查字段抽取是否遗漏。

## 3. URL 内容类型核对

| 数据集 | 图片URL | GitHub代码文件 | GitHub issue/PR | GitHub commit/compare | 复现/Playground/Demo | 文档/API/规范 | 问答/讨论 | GitHub其他 | 外部网页/其他 | 截断/异常 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SWE-bench Multimodal dev 全量 raw 102 | 304 | 11 | 14 | 2 | 24 | 5 | 0 | 7 | 72 | 2 |
| SWE-bench Multimodal 60 raw 60 | 204 | 3 | 5 | 0 | 13 | 3 | 0 | 3 | 42 | 1 |
| OmniGIRL full-candidates raw 631 | 79 | 181 | 166 | 14 | 362 | 122 | 42 | 230 | 273 | 0 |
| OmniGIRL unified60 raw 60 | 37 | 10 | 8 | 1 | 43 | 8 | 0 | 15 | 5 | 0 |

需要注意：同一个样本可能包含多个 URL，所以 URL 类型数量之和会大于样本数。SWE 里 `raw.githubusercontent.com`、`user-images.githubusercontent.com` 大量出现，主要是图片；Omni 里 `github.com`、`prettier.io`、`play.tailwindcss.com`、`mypy.readthedocs.io` 等更多，说明 Omni 更偏 URL 证据驱动。

## 4. 典型样本案例：完整 issue 与全部多模态链接

以下案例全部来自本地 `samples.jsonl`。为了可复核，每个案例都列出字段中的 `image_urls`、`web_urls`/`website_links`，以及从完整 issue 文本中额外抽取到的 URL。

### 4.1 SWE 图片 + GitHub 代码 URL：证据入口不等于 patch target

- 数据集：`SWE-bench Multimodal dev 全量 raw 102`
- 样本：`Automattic__wp-calypso-21409`
- 仓库：`Automattic/wp-calypso`
- 语言：`未显式标注`
- 模态组合：`图片 + URL`
- URL 类型计数：`{'图片 URL': 2, '截断/异常 URL': 1, 'GitHub 代码文件 URL': 1}`
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

字段 `image_urls`：

- `https://user-images.githubusercontent.com/22080/34058152-cf2dccfa-e18e-11e7-99f6-8a6f1f7a2dc4.png`
- `https://user-images.githubusercontent.com/22080/34058228-0f78b5f4-e18f-11e7-8133-e57bceea7374.png`

字段 `web_urls` / `website_links`：

- `https://gi`
- `https://github.com/Automattic/wp-calypso/blob/master/client/state/current-user/selectors.js#L157`

issue 正文额外抽取 URL：

- 无

完整 issue 文本：

````text
[Original Issue]
[Original Issue]
[Original Issue]
Store: Signup Flow needs to require email verification
Background p90Yrv-sE-p2

In order to allow for countries that are not supported by Store on wpcom to flow properly through the signup -> AT site/wp-admin, new user's email addresses must be verified for their WPCOM session to be valid to auth against their `wp-admin`.

There is one notice shown during the signup flow that prompts the user to verify their email address, but it does not prevent them from proceeding prior to doing so:

![notice-verify](https://user-images.githubusercontent.com/22080/34058152-cf2dccfa-e18e-11e7-99f6-8a6f1f7a2dc4.png)

__Current Thinking__
The idea right now is to create a new verification step after the user completes the Address Page form:

![address-page](https://user-images.githubusercontent.com/22080/34058228-0f78b5f4-e18f-11e7-8133-e57bceea7374.png)

Based on the user input here, we will have a fork in the flow:

_Supported Countries ( US, CA )_
If the store address entered is a supported country, the next step will be the current flow - showing the dashboard setup checklist.

_Non-Supported Countries_
These users will need to have a verified email address before proceeding/being directed to the WC setup page in `wp-admin`. Looks like we should be able to leverage [`isCurrentUserEmailVerified`](https://github.com/Automattic/wp-calypso/blob/master/client/state/current-user/selectors.js#L157) to quickly sniff this out - but we might have to do some polling, or add a button for the user to say "Yes I have verified my email".

Maybe we could even use that cool fake browser frame to show them what the email subject line looks like @allendav!

TODO: Need a design for this portion of the signup flow.

Attached Images:
- https://user-images.githubusercontent.com/22080/34058152-cf2dccfa-e18e-11e7-99f6-8a6f1f7a2dc4.png
- https://user-images.githubusercontent.com/22080/34058228-0f78b5f4-e18f-11e7-8133-e57bceea7374.png

Related URLs:
- https://github.com/Automattic/wp-calypso/blob/master/client/state/current-user/selectors.js#L157

[adapter_fallback=ModuleNotFoundError]

[Multimodal Context - Compact]
[Visual Evidence] Image 1: https://user-images.githubusercontent.com/22080/34058152-cf2dccfa-e18e-11e7-99f6-8a6f1f7a2dc4.png **Raw Visual Description** A purple confirmation card shows “Business Plan $299.00” and “Thank you for your purchase!” with a “Create your store!” button. Above it, a dark notice bar (with redacted email) says: “We’ve sent a message to [redacted]@gmail.com. Please check your email to confirm your address.” The notice has a yellow warning icon but no visible blocking mechanism. **Issue-Relevant Analysis** The UI displays an email verification notice but does not enforce it — users can proceed to store setup without verifying. The flow needs to block non-supported country users until email verification is complete, using `isCurrentUserEmailVerified` or a manual confirmation. No design for this verification step is provided. **Localization Clues** - Text: “We’ve sent a message to [redacted]@gmail.com. Please check your email to confirm your address.” - Button: “Create your store!” - Context: Email verification is required for non-supported countries before proceeding to wp-admin. - Likely code component: A notice/alert component with conditional blocking logic based on country and email verification status. Image 2: https://user-images.githubusercontent.com/22080/34058228-0f78b5f4-e18f-11e7-8133-e57bceea7374.png **Raw Visual Description** A signup flow screen titled “Store Location” with a central illustration of a person holding a clipboard. Below the illustration, text reads: “Howdy! Ready to start selling? First we need to know where you are in the world.” A “Street address” input field is partially visible at the bottom, showing “60696 River Bend Drive.” **Issue-Relevant Analysis** The current signup flow does not enforce email verification for users in unsupported countries. While a notice prompts email verification, it does not block progression. The proposed fix adds a verification step after the address form: for supported countries (US, CA), proceed to dashboard setup; for unsupported countries, require email verification before proceeding to wp-admin. **Localization Clues** - Text: “Howdy! Ready to start selling?” and “First we need to know where you are in the world.” - UI element: “Street address” input field. - Context: Email verification required for non-supported countries before proceeding to wp-admin. - Code hint: `isCurrentUserEmailVerified` selector for checking verification status. [Web Evidence] URL 1: https://gi...

[Adapter Note]
Use the multimodal context only as auxiliary evidence for code localization.

[Multimodal Context - Compact]
[Visual Evidence] Image 1: https://user-images.githubusercontent.com/22080/34058152-cf2dccfa-e18e-11e7-99f6-8a6f1f7a2dc4.png **Raw Visual Description** A purple confirmation card shows “Business Plan $299.00” and “Thank you for your purchase!” with a “Create your store!” button. Above it, a dark notice bar (with redacted email) says: “We’ve sent a message to [redacted]@gmail.com. Please check your email to confirm your address.” The notice has a yellow warning icon but no visible blocking mechanism. **Issue-Relevant Analysis** The UI displays an email verification notice but does not enforce it — users can proceed to store setup without verifying. The flow needs to block non-supported country users until email verification is complete, using `isCurrentUserEmailVerified` or a manual confirmation. No design for this verification step is provided. **Localization Clues** - Text: “We’ve sent a message to [redacted]@gmail.com. Please check your email to confirm your address.” - Button: “Create your store!” - Context: Email verification is required for non-supported countries before proceeding to wp-admin. - Likely code component: A notice/alert component with conditional blocking logic based on country and email verification status. Image 2: https://user-images.githubusercontent.com/22080/34058228-0f78b5f4-e18f-11e7-8133-e57bceea7374.png **Raw Visual Description** A signup flow screen titled “Store Location” with a central illustration of a person holding a clipboard. Below the illustration, text reads: “Howdy! Ready to start selling? First we need to know where you are in the world.” A “Street address” input field is partially visible at the bottom, showing “60696 River Bend Drive.” **Issue-Relevant Analysis** The current signup flow does not enforce email verification for users in unsupported countries. While a notice prompts email verification, it does not block progression. The proposed fix adds a verification step after the address form: for supported countries (US, CA), proceed to dashboard setup; for unsupported countries, require email verification before proceeding to wp-admin. **Localization Clues** - Text: “Howdy! Ready to start selling?” and “First we need to know where you are in the world.” - UI element: “Street address” input field. - Context: Email verification required for non-supported countries before proceeding to wp-admin. - Code hint: `isCurrentUserEmailVerified` selector for checking verification status. [Web Evidence] URL 1: https://gi...

[Adapter Note]
Use the multimodal context only as auxiliary evidence for code localization.

[Multimodal Context - Compact]
[Visual Evidence] Image 1: https://user-images.githubusercontent.com/22080/34058152-cf2dccfa-e18e-11e7-99f6-8a6f1f7a2dc4.png **Raw Visual Description** A purple confirmation card shows “Business Plan $299.00” and “Thank you for your purchase!” with a “Create your store!” button. Above it, a dark notice bar (with redacted email) says: “We’ve sent a message to [redacted]@gmail.com. Please check your email to confirm your address.” The notice has a yellow warning icon but no visible blocking mechanism. **Issue-Relevant Analysis** The UI displays an email verification notice but does not enforce it — users can proceed to store setup without verifying. The flow needs to block non-supported country users until email verification is complete, using `isCurrentUserEmailVerified` or a manual confirmation. No design for this verification step is provided. **Localization Clues** - Text: “We’ve sent a message to [redacted]@gmail.com. Please check your email to confirm your address.” - Button: “Create your store!” - Context: Email verification is required for non-supported countries before proceeding to wp-admin. - Likely code component: A notice/alert component with conditional blocking logic based on country and email verification status. Image 2: https://user-images.githubusercontent.com/22080/34058228-0f78b5f4-e18f-11e7-8133-e57bceea7374.png **Raw Visual Description** A signup flow screen titled “Store Location” with a central illustration of a person holding a clipboard. Below the illustration, text reads: “Howdy! Ready to start selling? First we need to know where you are in the world.” A “Street address” input field is partially visible at the bottom, showing “60696 River Bend Drive.” **Issue-Relevant Analysis** The current signup flow does not enforce email verification for users in unsupported countries. While a notice prompts email verification, it does not block progression. The proposed fix adds a verification step after the address form: for supported countries (US, CA), proceed to dashboard setup; for unsupported countries, require email verification before proceeding to wp-admin. **Localization Clues** - Text: “Howdy! Ready to start selling?” and “First we need to know where you are in the world.” - UI element: “Street address” input field. - Context: Email verification required for non-supported countries before proceeding to wp-admin. - Code hint: `isCurrentUserEmailVerified` selector for checking verification status. [Web Evidence] URL 1: https://gi...

[Adapter Note]
Use the multimodal context only as auxiliary evidence for code localization.
````

定位意义：

- 这是典型的 `图片 + GitHub 代码 URL` 样本。URL 指向 email verification selector，但 gold 文件在 WooCommerce dashboard/address flow。它说明代码 URL 可能只是 evidence seed，不一定是 patch target。

### 4.2 SWE 仅图片：截图是主要复现证据

- 数据集：`SWE-bench Multimodal 60 raw 60`
- 样本：`Automattic__wp-calypso-21492`
- 仓库：`Automattic/wp-calypso`
- 语言：`未显式标注`
- 模态组合：`图片 + URL`
- URL 类型计数：`{'图片 URL': 1, '外部网页/其他 URL': 1}`
- Gold 文件：
- `client/jetpack-connect/authorize.js`
- `client/jetpack-connect/utils.js`

字段 `image_urls`：

- `https://cldup.com/A0Nsu9q2Uw.png`

字段 `web_urls` / `website_links`：

- 无

issue 正文额外抽取 URL：

- `http://www.yoursite.com`

完整 issue 文本：

````text
[Original Issue]
Jetpack Connect: Plans page inadvertently shows site entry screen for subscribers
It seems that when a non-admin user attempts to connect their site, initiating the flow in Jetpack, after connection, they're directed to `/jetpack/connect/plans`, but they see the JPC initial site entry screen instead of the plans page.

#### Steps to reproduce
* Connect a Jetpack site with your Jetpack site admin user.
* Login in WP.com with another user.
* Create a non-admin (subscriber) user with the same email that you use for the .com account in the last step.
* Login to your Jetpack site with the new subscriber user.
* Connect the site for the subscriber user, starting from wp-admin.
* Approve the connection in the JPC flow.
* Witness a short redirect loop in the URL bar.
* You're presented with the JPC initial site entry step, rather than the plans page (but the URL is `/jetpack/connect/plans`).

#### What I expected
To be redirected back to wp-admin.

#### What happened instead
I was presented with the JPC plans page URL, but it displayed the JPC initial site entry step.

#### Screenshot / Video
![](https://cldup.com/A0Nsu9q2Uw.png)

#### Context / Source
Found while manually testing Jetpack 5.5beta3

#manual-testing

[Multimodal Context - Compact]
[Visual Evidence] Image 1: https://cldup.com/A0Nsu9q2Uw.png **Raw Visual Description** A Jetpack Connect page titled “Connect a self-hosted WordPress” shows a form for entering a site address (default: `http://www.yoursite.com`). Below it, a note states, “By connecting your site you agree to our fascinating Terms of Service.” A “Connect Now” button is present. The URL in the browser bar is `/jetpack/connect/plans`, but the content is the initial site entry screen, not the plans page. **Issue-Relevant Analysis** The UI displays the site connection form instead of the expected plans page, despite the URL indicating the plans page. This suggests a routing or state management bug: the system correctly loads the plans page URL but fails to render the correct content, possibly due to session/user context not being properly handled after connection approval. The redirect loop implies a state inconsistency. **Localization Clues** The text “By connecting your site you agree to our fascinating Terms of Service.” contains a likely localization string (`Terms of Service`) that may be inconsistently rendered or misaligned with the user’s locale or context. The phrase “fascinating” is also a potential localization point, possibly a placeholder or hardcoded text that should be dynamic.

[Adapter Note]
Use the multimodal context only as auxiliary evidence for code localization.
````

定位意义：

- 这是典型的 SWE 仅图片样本。图片展示 Jetpack Connect flow 的异常页面，定位需要从视觉/流程描述转到 `jetpack-connect/authorize.js` 和 `utils.js`。

### 4.3 SWE 图片 + Playground/Demo URL：视觉交互复现

- 数据集：`SWE-bench Multimodal 60 raw 60`
- 样本：`chartjs__Chart.js-10301`
- 仓库：`chartjs/Chart.js`
- 语言：`未显式标注`
- 模态组合：`图片 + URL`
- URL 类型计数：`{'图片 URL': 3, '复现/Playground/Demo URL': 1, '外部网页/其他 URL': 1}`
- Gold 文件：
- `src/plugins/plugin.legend.js`

字段 `image_urls`：

- `https://user-images.githubusercontent.com/58777964/157239796-95ccabbb-7ac1-4e58-89ca-c902b1df0dfe.png`
- `https://user-images.githubusercontent.com/58777964/157240018-395c6e62-d8e3-431f-8926-7644d5441078.png`
- `https://user-images.githubusercontent.com/58777964/157241538-f55bf466-916f-4763-b0ea-ef78ef847127.png`

字段 `web_urls` / `website_links`：

- `https://codesandbox.io/s/react-chartjs-2-chart-js-issue-template-forked-3kw5p0?file=/src/App.tsx`
- `https://www.chartjs.org/docs/latest/samples/legend/events.html`

issue 正文额外抽取 URL：

- 无

完整 issue 文本：

````text
[Original Issue]
Legend event onLeave
### Expected behavior

When I place the mouse outside the legend I expect the onLeave event to be called all the time.

### Current behavior

In the example at https://www.chartjs.org/docs/latest/samples/legend/events.html you can hover over a legend. If you quickly place the mouse outside the chart, content sometimes are highlight anyway due to onLeave isn't called.

On this image you can see that red are still highlighted, although the cursor are outside:
![image](https://user-images.githubusercontent.com/58777964/157239796-95ccabbb-7ac1-4e58-89ca-c902b1df0dfe.png)

I added a console.log to the onHover and onLeave handler in the example and received this when the cursor is outside the the chart but the color are still highlighted:
![image](https://user-images.githubusercontent.com/58777964/157240018-395c6e62-d8e3-431f-8926-7644d5441078.png)

### Reproducible sample

https://codesandbox.io/s/react-chartjs-2-chart-js-issue-template-forked-3kw5p0?file=/src/App.tsx

### Optional extra steps/info to reproduce

Drag the mouse between one of the legends and then up to the next. The problem occurs perhaps 1/10 times

![image](https://user-images.githubusercontent.com/58777964/157241538-f55bf466-916f-4763-b0ea-ef78ef847127.png)


### Possible solution

While trying to find a fix for this, I played around with attaching a mouseout event, it worked better but I had problem cleaning up the eventlistener.

### Context

_No response_

### chart.js version

v3.7.1

### Browser name and version

_No response_

### Link to your project

_No response_

[Multimodal Context - Compact]
[Visual Evidence] Image 1: https://user-images.githubusercontent.com/58777964/157239796-95ccabbb-7ac1-4e58-89ca-c902b1df0dfe.png **Raw Visual Description** A pie chart with six colored segments (Red, Blue, Yellow, Green, Purple, Orange) and a legend above. The mouse cursor is positioned near the top-left corner, outside the chart area. The "Red" segment remains visually highlighted despite the cursor being outside the chart, indicating a UI state mismatch. **Issue-Relevant Analysis** The `onLeave` event handler for the legend is not consistently firing when the mouse exits the chart area. This causes chart elements (e.g., the "Red" segment) to remain highlighted even when the cursor is outside the chart, violating expected behavior. The issue appears sporadic and may relate to event propagation or timing in Chart.js v3.7.1. **Localization Clues** - Legend interaction events (`onHover`, `onLeave`) are involved. - Chart.js v3.7.1, likely in the `Legend` or `Chart` component. - Event listener attachment/cleanup may be problematic. - Mouse position relative to chart boundaries is critical. Image 2: https://user-images.githubusercontent.com/58777964/157240018-395c6e62-d8e3-431f-8926-7644d5441078.png **Raw Visual Description** A console log output showing alternating "enter" and "leave" events for a legend hover interaction. The last event is "enter" with a cursor icon, indicating the mouse is currently inside the legend area. The pattern suggests inconsistent event firing — "leave" events are not reliably triggered when the mouse exits the legend. **Issue-Relevant Analysis** The `onLeave` event is not consistently fired when the mouse exits the legend area, causing legend items to remain highlighted even when the cursor is outside. This results in visual inconsistency where hovered elements stay active despite the mouse leaving the legend. The event sequence shows "leave" events are sometimes missed, leading to stale state. **Localization Clues** - Event handlers: `onHover`, `onLeave` - Component: Chart.js Legend - Trigger: Mouse exit from legend area - Expected: `onLeave` fires reliably on mouse exit - Actual: `onLeave` occasionally skipped, causing stale highlight state - Likely code component: Legend interaction handler in Chart.js core or plugin Image 3: https://user-images.githubusercontent.com/58777964/157241538-f55bf466-916f-4763-b0ea-ef78ef847127.png **Raw Visual Description** Code editor shows React + chart.js code with `onHover`/`onLeave` handlers...

[Adapter Note]
Use the multimodal context only as auxiliary evidence for code localization.
````

定位意义：

- 这是典型的 `图片 + playground/demo URL` 样本。CodeSandbox 和 Chart.js 文档链接提供复现入口，图片提供交互/图例症状，定位应落到 legend/event 相关函数。

### 4.4 SWE 图片 + GitHub issue/代码 URL：历史讨论和代码指针混合

- 数据集：`SWE-bench Multimodal 60 raw 60`
- 样本：`Automattic__wp-calypso-26008`
- 仓库：`Automattic/wp-calypso`
- 语言：`未显式标注`
- 模态组合：`图片 + URL`
- URL 类型计数：`{'图片 URL': 3, 'GitHub 代码文件 URL': 1, 'GitHub issue/PR URL': 2, '外部网页/其他 URL': 1}`
- Gold 文件：
- `client/lib/post-normalizer/index.js`
- `client/lib/post-normalizer/rule-content-detect-polls.js`
- `client/lib/post-normalizer/rule-content-detect-surveys.js`
- `client/state/reader/posts/normalization-rules.js`

字段 `image_urls`：

- `https://cloud.githubusercontent.com/assets/7233112/22263721/630de9e2-e243-11e6-8476-b425d8ac5a77.png`
- `https://cloud.githubusercontent.com/assets/7233112/22263743/7876fcf6-e243-11e6-931f-62451d55512c.png`
- `https://user-images.githubusercontent.com/17325/42547087-72d982f8-8514-11e8-8fcb-48a78a6b0401.png`

字段 `web_urls` / `website_links`：

- `https://github.com/Automattic/wp-calypso/blob/master/client/lib/post-normalizer/rule-content-detect-polls.js`
- `https://github.com/Automattic/wp-calypso/issues/10866`
- `https://github.com/wordpress-mobile/WordPress-iOS/issues/4306`
- `https://wordpress.com/read/feeds/84820645/posts/1921317670`

issue 正文额外抽取 URL：

- 无

完整 issue 文本：

````text
[Original Issue]
Reader: embedded Crowdsignal surveys do not display


#### Steps to reproduce
Open a Reader full post with a ~Polldaddy~ Crowdsignal survey embedded. For example:

https://wordpress.com/read/feeds/84820645/posts/1921317670

#### What I expected

Link to ~Polldaddy~ Crowdsignal survey is shown.

#### What happened instead

Survey was not displayed at all:

<img width="656" alt="screen shot 2018-07-11 at 14 11 18" src="https://user-images.githubusercontent.com/17325/42547087-72d982f8-8514-11e8-8fcb-48a78a6b0401.png">

~Polldaddy~ Crowdsignal polls work fine.

#### Context / Source






We detect ~Polldaddy~ Crowdsignal polls like this:

https://github.com/Automattic/wp-calypso/blob/master/client/lib/post-normalizer/rule-content-detect-polls.js

We need another similar rule to detect surveys, which embed differently.
Reader: Polldaddy embeds aren't being displayed
#### Steps to reproduce
1. Create a post with a link to a PollDaddy survey
2. View said post in the Reader

#### What I expected
To see some representation of the poll in the display

#### What happened instead
There's nothing there.  If the poll is the only thing in the post that leaves you with a completely empty post:
![screen shot 2017-01-24 at 2 42 42 pm](https://cloud.githubusercontent.com/assets/7233112/22263721/630de9e2-e243-11e6-8476-b425d8ac5a77.png)

As opposed to in the post itself:
![screen shot 2017-01-24 at 2 43 18 pm](https://cloud.githubusercontent.com/assets/7233112/22263743/7876fcf6-e243-11e6-931f-62451d55512c.png)

See also:
https://github.com/wordpress-mobile/WordPress-iOS/issues/4306
https://github.com/Automattic/wp-calypso/issues/10866

#### Browser / OS version
Any

#### Context / Source
#manual-testing

[Multimodal Context - Compact]
[Visual Evidence] Image 1: https://cloud.githubusercontent.com/assets/7233112/22263721/630de9e2-e243-11e6-8476-b425d8ac5a77.png **Raw Visual Description** A Reader post titled "Poll" (posted 8m ago) shows a placeholder for a survey with options "A" and "B". Below, a comment section invites users to add the first comment. No actual survey content or embedded widget is visible. The UI includes "Edit", "Share", "Comment", and "Like" actions. **Issue-Relevant Analysis** The embedded Crowdsignal (formerly Polldaddy) survey is not rendering in the Reader. The UI shows only a minimal poll structure ("A" and "B") without interactive elements or survey content. This contrasts with the expected behavior where the survey should be displayed. The issue stems from missing detection logic in the Reader’s post normalizer for Crowdsignal survey embeds. **Localization Clues** - Text: "Poll", "8m ago", "MORE IN A TEST SITE WITH DOMAIN", "NO COMMENTS - Add the first!", "Enter your comment here..." - UI Elements: "Edit", "Share", "Comment", "Like" buttons, comment input field, poll options "A" and "B" - Likely Code Components: Post normalizer rules for poll detection, embedded content renderer, survey-specific detection logic (e.g., `rule-content-detect-polls.js`) Image 2: https://cloud.githubusercontent.com/assets/7233112/22263743/7876fcf6-e243-11e6-931f-62451d55512c.png **Raw Visual Description** A survey interface titled "Poll" with two questions: Q.1 (Free text input) and Q.2 (Multiple Choice with options 1 and 2). A "Finish Survey" button is at the bottom. The UI is minimal, with no visible branding or embedded iframe. **Issue-Relevant Analysis** The embedded Crowdsignal survey fails to render in the Reader view. While the survey appears correctly in the post itself, it is missing entirely in Reader, leaving the post visually empty. This suggests the Reader’s content parser does not recognize or handle Crowdsignal survey embeds, unlike Polldaddy polls which are already supported. **Localization Clues** The issue involves detecting and rendering embedded survey content. The key clue is the need for a new content detection rule in the Reader’s post-normalizer (similar to the existing Polldaddy poll rule). The survey’s HTML structure (likely an iframe or script tag) must be identified and rendered differently than standard polls. Image 3: https://user-images.githubusercontent.com/17325/42547087-72d982f8-8514-11e8-8fcb-48a78a6b0401.png **Raw Visual Description** Text snip...

[Adapter Note]
Use the multimodal context only as auxiliary evidence for code localization.
````

定位意义：

- 这是 `图片 + GitHub issue/代码 URL` 混合样本。链接提供历史讨论和相关代码文件，但真正定位需要判断代码指针是否直接对应 gold。

### 4.5 Omni 仅图片：图片 URL 是问题展示本体

- 数据集：`OmniGIRL full-candidates raw 631`
- 样本：`assertj__assertj-1332`
- 仓库：`assertj/assertj`
- 语言：`Java`
- 模态组合：`仅图片`
- URL 类型计数：`{'图片 URL': 1}`
- Gold 文件：
- `src/main/java/org/assertj/core/internal/Strings.java`

字段 `image_urls`：

- `https://user-images.githubusercontent.com/2374036/46114945-98d85080-c1fd-11e8-87a2-9cc52e0eed3e.png`

字段 `web_urls` / `website_links`：

- 无

issue 正文额外抽取 URL：

- 无

完整 issue 文本：

````text
[Original Issue]
Throw AssertionFailedError instead of AssertionError in non-strict string assertions
#### Summary
Throwing AssertionFailedError from opentest4j facilitates test failure analysis in IDE providing handy "diff" view.
AssertJ already uses AssertionFailedError (if available on the classpath) but not in non-strict string assertions (from AbstractCharSequenceAssert), specifically:
* isEqualToIgnoringNewLines
* isEqualToIgnoringWhitespace
* isEqualToIgnoringNewLines

Given that two of them mention new lines it is rather common to use them to compare long multi-line strings, and IDE's "diff" feature would be very helpful to nitpick some single-letter difference in big texts (possibly coming from files).

#### Example

```java
String generatedText = sut.generateText();
assertThat(generatedText).isEqualToNormalizingNewlines(loadText("expected.txt"));
```
![image](https://user-images.githubusercontent.com/2374036/46114945-98d85080-c1fd-11e8-87a2-9cc52e0eed3e.png)

[Multimodal Context - Compact]
[Visual Evidence] Image 1: https://user-images.githubusercontent.com/2374036/46114945-98d85080-c1fd-11e8-87a2-9cc52e0eed3e.png **Raw Visual Description** IDE screenshot showing a test failure in `ChangeSetGeneratorIntegrationTest`. A comparison failure dialog highlights a single difference: the word “hecking” is misspelled as “hecking” in the “Actual” output. The error message shows `org.opentest4j.AssertionFailedError` with expected vs. actual string content, and a “Click to see difference” link. The test code uses `assertThat(...).isEqualTo(...)`. **Issue-Relevant Analysis** The test fails because `isEqualTo(...)` (or a similar non-strict string assertion) produced an `AssertionFailedError` with a plain string diff, not a structured `AssertionFailedError` with a diff view. The IDE’s diff view is not activated, making it hard to spot subtle differences in large strings. The issue targets non-strict string assertions like `isEqualToIgnoringNewLines` or `isEqualToIgnoringWhitespace` to use `AssertionFailedError` for better IDE diff support. **Localization Clues** - Class: `org.opentest4j.AssertionFailedError` - Method: `isEqualTo(...)` or related non-strict string assertions (e.g., `isEqualToIgnoringNewLines`) - File: `ChangeSetGeneratorIntegrationTest.java` - IDE: Likely IntelliJ IDEA (based on UI) - Key text: “hecking” vs. “hecking” (typo in actual output) - Error message: “but was not. <Click to see difference>”

[Adapter Note]
Use the multimodal context only as auxiliary evidence for code localization.
````

定位意义：

- 这是 Omni 中仅图片的 Java 样本。图片是 IDE diff/断言展示相关证据，定位仍要回到 AssertJ 字符串断言内部实现。

### 4.6 Omni 仅 URL：GitHub 代码文件 + StackOverflow 语义线索

- 数据集：`OmniGIRL full-candidates raw 631`
- 样本：`assertj__assertj-2200`
- 仓库：`assertj/assertj`
- 语言：`Java`
- 模态组合：`仅 URL`
- URL 类型计数：`{'GitHub 代码文件 URL': 1, '问答/讨论 URL': 1}`
- Gold 文件：
- `src/main/java/org/assertj/core/api/Descriptable.java`
- `src/main/java/org/assertj/core/error/ShouldBeEqual.java`
- `src/main/java/org/assertj/core/error/ShouldBeEqualIgnoringCase.java`

字段 `image_urls`：

- 无

字段 `web_urls` / `website_links`：

- `https://github.com/assertj/assertj-core/blob/main/src/main/java/org/assertj/core/error/ShouldBeEqual.java#L44`
- `https://stackoverflow.com/questions/10934743/formatting-output-so-that-intellij-idea-shows-diffs-for-two-texts`

issue 正文额外抽取 URL：

- 无

完整 issue 文本：

````text
[Original Issue]
Remove space in default error message for ShouldBeEqual to help IntelliJ diff detection
Referencing this StackOverflow ticket: https://stackoverflow.com/questions/10934743/formatting-output-so-that-intellij-idea-shows-diffs-for-two-texts

It seems that IntelliJ expects assertion errors to be in this format in order to have nicely rendered diffs:

`expected: xxx but was: yyy`

But AssertJ would format this with an extra space after the `was`:

`expected: xxx but was : yyy`

Which would cause it to fail the regex, and IntelliJ defaults to just printing the error string. I tried patching my AssertJ `ShouldBeEqual` locally without that extra space, and IntelliJ was then able to detect it properly.

Would it be possible to remove the extraneous space after the `was` so that the test output can automatically be detected as a diff?

Thanks!

Link to message: https://github.com/assertj/assertj-core/blob/main/src/main/java/org/assertj/core/error/ShouldBeEqual.java#L44

[Multimodal Context - Compact]
[Web Evidence] URL 1: https://github.com/assertj/assertj-core/blob/main/src/main/java/org/assertj/core/error/ShouldBeEqual.java#L44 Web processing failed; use URL only. Error: HTTP Error 404: Not Found URL 2: https://stackoverflow.com/questions/10934743/formatting-output-so-that-intellij-idea-shows-diffs-for-two-texts Summary: Formatting output so that Intellij Idea shows diffs for two texts - Stack Overflow I would like to be able to print in the logs a message for which intellij idea would present a nice way of comparing two objects (strings). This happens automatically for the error message logged b... Formatting output so that Intellij Idea shows diffs for two texts - Stack Overflow Skip to main content About Products Stack Internal Stack Internal Implement a knowledge platform layer to power your enterprise and AI tools. Stack Data Licensing Get access to top-class technical expertise with trusted & attributed content. Stack Ads Connect your brand to the world’s most trusted technologist communities. Relea...

[Adapter Note]
Use the multimodal context only as auxiliary evidence for code localization.
````

定位意义：

- 这是 Omni 中 `GitHub 代码文件 + StackOverflow` 的 URL-only 样本。代码 URL 给出候选实现位置，StackOverflow 给出 IDE diff 输出格式语义。

### 4.7 Omni 图片 + Playground URL：图片需要和复现 URL 绑定解析

- 数据集：`OmniGIRL unified60 raw 60`
- 样本：`babel__babel-15134`
- 仓库：`babel/babel`
- 语言：`TypeScript`
- 模态组合：`图片 + URL`
- URL 类型计数：`{'图片 URL': 1, '复现/Playground/Demo URL': 1}`
- Gold 文件：
- `packages/babel-parser/src/parser/expression.ts`

字段 `image_urls`：

- `https://user-images.githubusercontent.com/68288688/200038280-5710d26b-d188-433c-b675-e83a27e5ef13.png`

字段 `web_urls` / `website_links`：

- `https://babeljs.io/repl#?browsers=since%202015&build=&builtIns=false&corejs=3.21&spec=false&loose=false&code_lz=GYewTgFAhg7lCWAXABCYyDaBGANAJhwGYBdASmWQG9kBjEAOwGcQAbAUwDoWQBzaOJOQC-AKCA&debug=false&forceAllTransforms=false&shippedProposals=false&circleciRepo=&evaluate=false&fileSize=false&timeTravel=false&sourceType=script&lineWrap=true&presets=env%2Creact%2Cstage-2&prettier=false&targets=&version=7.20.1&externalPlugins=&assumptions=%7B%7D`

issue 正文额外抽取 URL：

- 无

完整 issue 文本：

````text
[Bug]: Babel crashes when using `await` as an identifier in ForInOfHead
### 💻

- [ ] Would you like to work on a fix?

### How are you using Babel?

Other (Next.js, Gatsby, vue-cli, ...)

### Input code

```js
for( await of [1, 2, 3] )  { console.log(await) }
```

### Configuration file name

_No response_

### Configuration

_No response_

### Current and expected behavior

Hello,

The input code prints `1`, `2` and `3`:
```console
$ node --version
v18.11.0
$ node input.js
1
2
3
```
However, Babel fails to transpile the input code:
<img width="446" alt="image" src="https://user-images.githubusercontent.com/68288688/200038280-5710d26b-d188-433c-b675-e83a27e5ef13.png">


### Environment

[Reproduction on Babel's own REPL](https://babeljs.io/repl#?browsers=since%202015&build=&builtIns=false&corejs=3.21&spec=false&loose=false&code_lz=GYewTgFAhg7lCWAXABCYyDaBGANAJhwGYBdASmWQG9kBjEAOwGcQAbAUwDoWQBzaOJOQC-AKCA&debug=false&forceAllTransforms=false&shippedProposals=false&circleciRepo=&evaluate=false&fileSize=false&timeTravel=false&sourceType=script&lineWrap=true&presets=env%2Creact%2Cstage-2&prettier=false&targets=&version=7.20.1&externalPlugins=&assumptions=%7B%7D)

### Possible solution

_No response_

### Additional context

_No response_

Attached Images:
- https://user-images.githubusercontent.com/68288688/200038280-5710d26b-d188-433c-b675-e83a27e5ef13.png

Related URLs:
- https://babeljs.io/repl#?browsers=since%202015&build=&builtIns=false&corejs=3.21&spec=false&loose=false&code_lz=GYewTgFAhg7lCWAXABCYyDaBGANAJhwGYBdASmWQG9kBjEAOwGcQAbAUwDoWQBzaOJOQC-AKCA&debug=false&forceAllTransforms=false&shippedProposals=false&circleciRepo=&evaluate=false&fileSize=false&timeTravel=false&sourceType=script&lineWrap=true&presets=env%2Creact%2Cstage-2&prettier=false&targets=&version=7.20.1&externalPlugins=&assumptions=%7B%7D

[adapter_fallback=ModuleNotFoundError]
````

定位意义：

- 这是 Omni 中 `图片 + Babel playground` 样本。playground URL 编码了复现代码和配置，图片通常只是复现输出展示；处理时应先解析 playground，再用图片确认行为。

### 4.8 Omni 仅 URL：文档/API URL 驱动定位

- 数据集：`OmniGIRL full-candidates raw 631`
- 样本：`redis__redis-py-2745`
- 仓库：`redis/redis-py`
- 语言：`Python`
- 模态组合：`仅 URL`
- URL 类型计数：`{'文档/API/规范 URL': 1}`
- Gold 文件：
- `redis/commands/core.py`

字段 `image_urls`：

- 无

字段 `web_urls` / `website_links`：

- `https://redis.io/commands/CLIENT-NO-TOUCH`

issue 正文额外抽取 URL：

- 无

完整 issue 文本：

````text
[Original Issue]
Add support for new redis command CLIENT NO-TOUCH
7.2.0 adds support for the new redis command CLIENT NO-TOUCH. We need to add support, documented [here](https://redis.io/commands/CLIENT-NO-TOUCH).

[Multimodal Context - Compact]
[Web Evidence] URL 1: https://redis.io/commands/CLIENT-NO-TOUCH Summary: CLIENT NO-TOUCH | Docs Controls whether commands sent by the client affect the LRU/LFU of accessed keys. CLIENT NO-TOUCH | Docs {"acl_categories":["@slow","@connection"],"arguments":[{"arguments":[{"display_text":"on","name":"on","token":"ON","type":"pure-token"},{"display_text":"off","name":"off","token":"OFF","type":"pure-token"}],"name":"enabled","type":"oneof"}],"arity":3,"categories":["docs","develop","stack","oss","rs","rc","oss","kubernetes","clients"],"command_flags":["noscript","loading","stale"],"complexity":"O(1)","description":"Controls whether commands sent by the client affect the LRU/LFU of accessed keys.","duplicateOf":"head:data-ai-metadata","group":"connection","location...

[Adapter Note]
Use the multimodal context only as auxiliary evidence for code localization.
````

定位意义：

- 这是 Omni 中文档/API URL 驱动样本。Redis 命令文档是行为规范，不是代码目标；定位应从 API 命令语义映射到 redis-py 对应 command 实现。

### 4.9 Omni 纯文本：没有图片和网页 URL，仍是合法样本

- 数据集：`OmniGIRL unified60 raw 60`
- 样本：`assertj__assertj-1587`
- 仓库：`assertj/assertj`
- 语言：`Java`
- 模态组合：`纯文本`
- URL 类型计数：`{}`
- Gold 文件：
- `src/main/java/org/assertj/core/internal/Strings.java`

字段 `image_urls`：

- 无

字段 `web_urls` / `website_links`：

- 无

issue 正文额外抽取 URL：

- 无

完整 issue 文本：

````text
The assertion assertThat().HasSizeBetween() does not work with strings
#### Summary

The assertion assertThat().hasSizeBetween() with strings does not work, assertj-core seems to confuse string lengths between actual, min and max.

#### Example

```java
assertThat("Test1").hasSizeBetween(4, 11);
```
throws a confusing exception :
java.lang.IllegalArgumentException: The higher boundary <4> must be greater than the lower boundary <5>.

Tested on assertj_core 3.13.2 and AdoptOpenJDK 11

[adapter_fallback=ModuleNotFoundError]
````

定位意义：

- 这是 Omni60 中纯文本样本，没有图片也没有网页 URL。它提醒我们：多模态框架仍要保留纯文本 issue 的普通代码定位能力。

## 5. 对 014 文档的修正和使用建议

1. `图片类型` 不应表述成已经人工看过图片；当前统计主要基于 URL host/path 和 issue/repo 语义推断。更严谨的说法是“图片 URL 来源/可能内容类型”。

2. SWE-bench Multimodal 的图片字段较完整，`image_assets` 能说明图片来自 issue 正文；OmniGIRL 没有同等粒度字段，主要依靠 `image_urls`。

3. URL 类型必须和 URL 角色分开。`GitHub 代码文件 URL` 可能是真实 patch target，也可能只是 evidence-only。`Automattic__wp-calypso-21409` 就是 evidence-only 的反例。

4. 对 Omni 来说，URL 处理比图片处理更核心。大量 URL 是 playground、docs/API、GitHub PR/issue/code、StackOverflow，这些都应该走不同 resolver。

5. 多模态 Agent 不能只把图片 URL 和网页 URL 拼到 prompt 里。正确流程应该是：URL/图片下载或解析 -> 证据类型识别 -> 证据角色判断 -> 转换成 route/component/function/API/config 搜索约束 -> 进入 repo graph 扩展。

## 6. 可复核的数据路径

- SWE-bench Multimodal dev 全量 raw 102: `/home/like/locCode/LocAgent/newtest/swebench_multimodal-full-dev/data/samples.jsonl`
- SWE-bench Multimodal 60 raw 60: `/home/like/locCode/LocAgent/newtest/swebench_multimodal-60/data/samples.jsonl`
- OmniGIRL full-candidates raw 631: `/home/like/locCode/MM-IR/data/omnigirl-full-candidates/samples.jsonl`
- OmniGIRL unified60 raw 60: `/home/like/locCode/LocAgent/newtest/omnigirl-unified60/data/samples.jsonl`


本文生成时使用的统计口径：直接读取上述 `samples.jsonl`，用 `image_urls` 判断图片字段，用 `web_urls` / `website_links` 加 issue 正文正则抽取判断网页 URL。
