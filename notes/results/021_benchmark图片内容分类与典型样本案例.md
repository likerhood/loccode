# Benchmark 图片内容分类与典型样本案例

本文基于当前仓库中已经准备好的 benchmark `samples.jsonl` 重新统计图片字段，并对典型图片做人工核对。重点回答三个问题：图片字段到底是什么格式、这些图片内容可以分成哪些定位证据类型、每类图片如何影响代码定位。

## 1. 结论摘要

- 当前 prepared 数据里的图片不是本地文件字段，而是 `image_urls` 中的远程图片 URL。SWE-bench Multimodal 还保留 `image_assets` 元信息，但定位输入仍主要来自 URL。

- SWE-bench Multimodal 的样本全部带图片；OmniGIRL full-candidates 只有一小部分带图片，大多数样本是网页 URL 或文本/链接证据。

- 图片本身不能简单等价为“强定位证据”。同样是图片 URL，可能是 UI 页面截图、图表渲染、错误输出，也可能只是 IssueHunt 徽章。Agent 需要先做图片角色判断，再决定是否把视觉证据转成搜索 query。

- 最有用的图片通常包含可抽取文本或结构：错误栈、expected/actual、playground 输入、CSS class、页面按钮、图表元素、PDF 渲染属性。最弱的图片是徽章、头像和奖励标识。

## 2. 图片字段真实性核对

| 数据集 | 样本数 | 仅图片 | 图片+网页URL | 仅网页URL | 纯文本 | 图片URL总数 | 主要图片域名 |
|---|---:|---:|---:|---:|---:|---:|---|
| SWE-bench Multimodal dev 全量 | 102 | 37 | 65 | 0 | 0 | 301 | raw.githubusercontent.com(147), user-images.githubusercontent.com(139), cldup.com(6), cloud.githubusercontent.com(5) |
| SWE-bench Multimodal 60 子集 | 60 | 27 | 33 | 0 | 0 | 203 | raw.githubusercontent.com(115), user-images.githubusercontent.com(78), cldup.com(5), cloud.githubusercontent.com(2) |
| OmniGIRL full-candidates | 631 | 16 | 32 | 583 | 0 | 79 | user-images.githubusercontent.com(59), img.shields.io(5), file.mo7.cc(2), github.com(2) |
| OmniGIRL unified60 子集 | 60 | 6 | 14 | 28 | 12 | 37 | user-images.githubusercontent.com(32), snipboard.io(2), i.imgur.com(2), cloud.githubusercontent.com(1) |

说明：这里的“图片+网页URL”表示同一个 issue 同时有 `image_urls` 和网页/代码/文档 URL。图片 URL 本身不计入网页 URL，避免重复计算。

## 3. 图片内容分类口径

| 类别 | 定位意义 |
|---|---|
| 产品/UI流程截图 | 截图展示产品页面、设置流程、提示条、按钮、空态或页面状态。它通常强烈约束“哪个业务页面/组件出错”，但不一定直接指向最终修改文件。 |
| 图表/Canvas可视化渲染 | 截图展示图表、canvas 或 SVG 渲染差异。它对定位图形元素、scale、legend、tooltip、layout 逻辑有用。 |
| PDF/排版渲染 | 截图展示 PDF/文档排版输出，常对应布局、边框、分页、字体、Yoga layout 等渲染路径。 |
| Markdown/富文本渲染 | 截图展示 Markdown 输入和渲染结果对照，通常需要抽取 markdown 语法、版本、renderer/parser 行为。 |
| 图形/几何/WebGL输出 | 截图展示几何图形、颜色、渐变、坐标或 WebGL/canvas 效果，通常要回到渲染 API、shader 或绘制状态。 |
| IDE/断言diff/测试失败视图 | 截图展示 IDE diff、assertion failure、测试失败堆栈。它往往直接暴露测试类、错误类型、expected/actual 文本。 |
| 编译器/Parser/Playground错误输出 | 截图展示 parser/compiler/prettier playground 的报错或格式化差异。关键证据是输入代码、parser、错误位置、配置。 |
| CSS/样式Playground输出 | 截图展示 Tailwind/CSS playground 输入、生成 CSS 和 preview。关键证据是 class token、variant、arbitrary value、prefix/config。 |
| 运行时/控制台/表格输出 | 截图展示终端、测试、表格、bundle 或运行输出。关键证据是错误消息、数值、版本、expected/actual。 |
| 动图/交互行为演示 | 动图展示动态过程，例如进度条刷新、UI 交互、动画。它的价值在于时间顺序和状态变化。 |
| 弱相关徽章/头像/奖励图 | 图片只是徽章、头像、奖励标识或装饰图。它是 image URL，但对定位几乎没有直接作用，应该降权。 |
| 其他截图 | 无法用规则稳定归类的截图，需要进一步人工或视觉模型分析。 |

分类方法：对代表图片进行人工核对，再结合 repo、issue 文本和 URL 规则对全量样本做规则分类。因此它适合做数据画像和方法设计，不应理解为逐张图片的人工标注金标准。

## 4. 各数据集图片内容分布

| 图片类别 | SWE dev 全量 | SWE60 | Omni full-candidates | Omni60 |
|---|---:|---:|---:|---:|
| 产品/UI流程截图 | 37 | 20 | 0 | 0 |
| 图表/Canvas可视化渲染 | 24 | 15 | 0 | 0 |
| PDF/排版渲染 | 11 | 7 | 0 | 0 |
| Markdown/富文本渲染 | 14 | 8 | 0 | 0 |
| 图形/几何/WebGL输出 | 16 | 10 | 0 | 0 |
| IDE/断言diff/测试失败视图 | 0 | 0 | 1 | 0 |
| 编译器/Parser/Playground错误输出 | 0 | 0 | 8 | 2 |
| CSS/样式Playground输出 | 0 | 0 | 13 | 11 |
| 运行时/控制台/表格输出 | 0 | 0 | 17 | 6 |
| 动图/交互行为演示 | 0 | 0 | 4 | 1 |
| 弱相关徽章/头像/奖励图 | 0 | 0 | 5 | 0 |

几个直接观察：

- SWE dev 全量的图片几乎覆盖全部样本，主要来自 WordPress UI、Chart.js 图表、react-pdf 排版、Marked 渲染和 p5.js 图形。它更像“视觉症状驱动”的 benchmark。

- Omni full-candidates 的图片只覆盖 48/631 个样本，但类型更杂：Java 的 IDE diff、JS/TS playground、Python 表格输出、webpack bundle 截图、tqdm GIF、Day.js 测试输出和弱相关徽章并存。

- Omni 中存在真实的 image URL 但定位价值很低的样本，例如 IssueHunt badge。这类图片如果不降权，会把多模态 Agent 引向无关网页或社交/奖励信息。

## 5. 典型样本案例

### 5.1 Automattic__wp-calypso-21409：产品/UI流程截图

- 数据来源：SWE-bench Multimodal dev 全量

- Repo：`Automattic/wp-calypso`

- Issue 标题/首行：Store: Signup Flow needs to require email verification

- 图片核对：PNG, 574 x 629；人工核对为购买后创建商店流程 UI 和邮箱验证提示截图。

- 图片 URL 数：2；网页 URL 数：2；Gold 文件数：10


图片 URL：

- https://user-images.githubusercontent.com/22080/34058152-cf2dccfa-e18e-11e7-99f6-8a6f1f7a2dc4.png
- https://user-images.githubusercontent.com/22080/34058228-0f78b5f4-e18f-11e7-8133-e57bceea7374.png

网页/代码/文档 URL：

- https://gi
- https://github.com/Automattic/wp-calypso/blob/master/client/state/current-user/selectors.js#L157

Gold 文件：

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

定位解释：


这类图片给出页面状态、按钮文案和业务流程。定位时应先抽取页面/组件/状态词，再沿路由、组件层级和状态 selector 扩展，而不是把截图或 issue 中出现的第一个代码 URL 直接当 gold target。


完整 issue 原文：

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

### 5.2 chartjs__Chart.js-10301：图表/Canvas可视化渲染

- 数据来源：SWE-bench Multimodal dev 全量

- Repo：`chartjs/Chart.js`

- Issue 标题/首行：Legend event onLeave

- 图片核对：PNG, 934 x 765；人工核对为 Chart.js 饼图/图例渲染截图。

- 图片 URL 数：3；网页 URL 数：2；Gold 文件数：1


图片 URL：

- https://user-images.githubusercontent.com/58777964/157239796-95ccabbb-7ac1-4e58-89ca-c902b1df0dfe.png
- https://user-images.githubusercontent.com/58777964/157240018-395c6e62-d8e3-431f-8926-7644d5441078.png
- https://user-images.githubusercontent.com/58777964/157241538-f55bf466-916f-4763-b0ea-ef78ef847127.png

网页/代码/文档 URL：

- https://codesandbox.io/s/react-chartjs-2-chart-js-issue-template-forked-3kw5p0?file=/src/App.tsx
- https://www.chartjs.org/docs/latest/samples/legend/events.html

Gold 文件：

- `src/plugins/plugin.legend.js`

定位解释：


这类图片的关键证据是视觉元素和图表配置，例如 legend、pie/doughnut、tooltip、scale、layout。定位时要把截图转成 chart type、element、option 名称和渲染阶段。


完整 issue 原文：

````text
[Original Issue]
[Original Issue]
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

Attached Images:
- https://user-images.githubusercontent.com/58777964/157239796-95ccabbb-7ac1-4e58-89ca-c902b1df0dfe.png
- https://user-images.githubusercontent.com/58777964/157240018-395c6e62-d8e3-431f-8926-7644d5441078.png
- https://user-images.githubusercontent.com/58777964/157241538-f55bf466-916f-4763-b0ea-ef78ef847127.png

Related URLs:
- https://codesandbox.io/s/react-chartjs-2-chart-js-issue-template-forked-3kw5p0?file=/src/App.tsx
- https://www.chartjs.org/docs/latest/samples/legend/events.html

[adapter_fallback=ModuleNotFoundError]

[Multimodal Context - Compact]
[Visual Evidence] Image 1: https://user-images.githubusercontent.com/58777964/157239796-95ccabbb-7ac1-4e58-89ca-c902b1df0dfe.png **Raw Visual Description** A pie chart with six colored segments (Red, Blue, Yellow, Green, Purple, Orange) and a legend above. The mouse cursor is positioned near the top-left corner, outside the chart area. The "Red" segment remains visually highlighted despite the cursor being outside the chart, indicating a UI state mismatch. **Issue-Relevant Analysis** The `onLeave` event handler for the legend is not consistently firing when the mouse exits the chart area. This causes chart elements (e.g., the "Red" segment) to remain highlighted even when the cursor is outside the chart, violating expected behavior. The issue appears sporadic and may relate to event propagation or timing in Chart.js v3.7.1. **Localization Clues** - Legend interaction events (`onHover`, `onLeave`) are involved. - Chart.js v3.7.1, likely in the `Legend` or `Chart` component. - Event listener attachment/cleanup may be problematic. - Mouse position relative to chart boundaries is critical. Image 2: https://user-images.githubusercontent.com/58777964/157240018-395c6e62-d8e3-431f-8926-7644d5441078.png **Raw Visual Description** A console log output showing alternating "enter" and "leave" events for a legend hover interaction. The last event is "enter" with a cursor icon, indicating the mouse is currently inside the legend area. The pattern suggests inconsistent event firing — "leave" events are not reliably triggered when the mouse exits the legend. **Issue-Relevant Analysis** The `onLeave` event is not consistently fired when the mouse exits the legend area, causing legend items to remain highlighted even when the cursor is outside. This results in visual inconsistency where hovered elements stay active despite the mouse leaving the legend. The event sequence shows "leave" events are sometimes missed, leading to stale state. **Localization Clues** - Event handlers: `onHover`, `onLeave` - Component: Chart.js Legend - Trigger: Mouse exit from legend area - Expected: `onLeave` fires reliably on mouse exit - Actual: `onLeave` occasionally skipped, causing stale highlight state - Likely code component: Legend interaction handler in Chart.js core or plugin Image 3: https://user-images.githubusercontent.com/58777964/157241538-f55bf466-916f-4763-b0ea-ef78ef847127.png **Raw Visual Description** Code editor shows React + chart.js code with `onHover`/`onLeave` handlers...

[Adapter Note]
Use the multimodal context only as auxiliary evidence for code localization.

[Multimodal Context - Compact]
[Visual Evidence] Image 1: https://user-images.githubusercontent.com/58777964/157239796-95ccabbb-7ac1-4e58-89ca-c902b1df0dfe.png **Raw Visual Description** A pie chart with six colored segments (Red, Blue, Yellow, Green, Purple, Orange) and a legend above. The mouse cursor is positioned near the top-left corner, outside the chart area. The "Red" segment remains visually highlighted despite the cursor being outside the chart, indicating a UI state mismatch. **Issue-Relevant Analysis** The `onLeave` event handler for the legend is not consistently firing when the mouse exits the chart area. This causes chart elements (e.g., the "Red" segment) to remain highlighted even when the cursor is outside the chart, violating expected behavior. The issue appears sporadic and may relate to event propagation or timing in Chart.js v3.7.1. **Localization Clues** - Legend interaction events (`onHover`, `onLeave`) are involved. - Chart.js v3.7.1, likely in the `Legend` or `Chart` component. - Event listener attachment/cleanup may be problematic. - Mouse position relative to chart boundaries is critical. Image 2: https://user-images.githubusercontent.com/58777964/157240018-395c6e62-d8e3-431f-8926-7644d5441078.png **Raw Visual Description** A console log output showing alternating "enter" and "leave" events for a legend hover interaction. The last event is "enter" with a cursor icon, indicating the mouse is currently inside the legend area. The pattern suggests inconsistent event firing — "leave" events are not reliably triggered when the mouse exits the legend. **Issue-Relevant Analysis** The `onLeave` event is not consistently fired when the mouse exits the legend area, causing legend items to remain highlighted even when the cursor is outside. This results in visual inconsistency where hovered elements stay active despite the mouse leaving the legend. The event sequence shows "leave" events are sometimes missed, leading to stale state. **Localization Clues** - Event handlers: `onHover`, `onLeave` - Component: Chart.js Legend - Trigger: Mouse exit from legend area - Expected: `onLeave` fires reliably on mouse exit - Actual: `onLeave` occasionally skipped, causing stale highlight state - Likely code component: Legend interaction handler in Chart.js core or plugin Image 3: https://user-images.githubusercontent.com/58777964/157241538-f55bf466-916f-4763-b0ea-ef78ef847127.png **Raw Visual Description** Code editor shows React + chart.js code with `onHover`/`onLeave` handlers...

[Adapter Note]
Use the multimodal context only as auxiliary evidence for code localization.

[Multimodal Context - Compact]
[Visual Evidence] Image 1: https://user-images.githubusercontent.com/58777964/157239796-95ccabbb-7ac1-4e58-89ca-c902b1df0dfe.png **Raw Visual Description** A pie chart with six colored segments (Red, Blue, Yellow, Green, Purple, Orange) and a legend above. The mouse cursor is positioned near the top-left corner, outside the chart area. The "Red" segment remains visually highlighted despite the cursor being outside the chart, indicating a UI state mismatch. **Issue-Relevant Analysis** The `onLeave` event handler for the legend is not consistently firing when the mouse exits the chart area. This causes chart elements (e.g., the "Red" segment) to remain highlighted even when the cursor is outside the chart, violating expected behavior. The issue appears sporadic and may relate to event propagation or timing in Chart.js v3.7.1. **Localization Clues** - Legend interaction events (`onHover`, `onLeave`) are involved. - Chart.js v3.7.1, likely in the `Legend` or `Chart` component. - Event listener attachment/cleanup may be problematic. - Mouse position relative to chart boundaries is critical. Image 2: https://user-images.githubusercontent.com/58777964/157240018-395c6e62-d8e3-431f-8926-7644d5441078.png **Raw Visual Description** A console log output showing alternating "enter" and "leave" events for a legend hover interaction. The last event is "enter" with a cursor icon, indicating the mouse is currently inside the legend area. The pattern suggests inconsistent event firing — "leave" events are not reliably triggered when the mouse exits the legend. **Issue-Relevant Analysis** The `onLeave` event is not consistently fired when the mouse exits the legend area, causing legend items to remain highlighted even when the cursor is outside. This results in visual inconsistency where hovered elements stay active despite the mouse leaving the legend. The event sequence shows "leave" events are sometimes missed, leading to stale state. **Localization Clues** - Event handlers: `onHover`, `onLeave` - Component: Chart.js Legend - Trigger: Mouse exit from legend area - Expected: `onLeave` fires reliably on mouse exit - Actual: `onLeave` occasionally skipped, causing stale highlight state - Likely code component: Legend interaction handler in Chart.js core or plugin Image 3: https://user-images.githubusercontent.com/58777964/157241538-f55bf466-916f-4763-b0ea-ef78ef847127.png **Raw Visual Description** Code editor shows React + chart.js code with `onHover`/`onLeave` handlers...

[Adapter Note]
Use the multimodal context only as auxiliary evidence for code localization.
````

### 5.3 diegomura__react-pdf-433：PDF/排版渲染

- 数据来源：SWE-bench Multimodal dev 全量

- Repo：`diegomura/react-pdf`

- Issue 标题/首行：Setting a border on a rounded <View> causes unexpected results

- 图片核对：PNG, 1838 x 1097；人工核对为 react-pdf REPL，左侧代码、右侧 PDF 渲染结果。

- 图片 URL 数：4；网页 URL 数：0；Gold 文件数：5


图片 URL：

- https://user-images.githubusercontent.com/4199296/49249306-b037e380-f3d0-11e8-96cd-29eee986683b.png
- https://user-images.githubusercontent.com/4199296/49249354-c5ad0d80-f3d0-11e8-8e2d-393dee2530e1.png
- https://user-images.githubusercontent.com/4199296/49249430-f42ae880-f3d0-11e8-9272-cefd5bca1b0d.png
- https://user-images.githubusercontent.com/4199296/49249444-fb51f680-f3d0-11e8-8f24-49d22bc27962.png

Gold 文件：

- `src/dom.js`
- `src/elements/Base.js`
- `src/elements/Image.js`
- `src/mixins/borders.js`
- `src/mixins/clipping.js`

定位解释：


这类图片暴露的是布局输出差异。定位时需要把视觉属性映射到 layout/style/render pipeline，例如 border、padding、page、view、stylesheet、Yoga 节点。


完整 issue 原文：

````text
[Original Issue]
[Original Issue]
[Original Issue]
Setting a border on a rounded <View> causes unexpected results

**OS:**
macOS 10.13 High Sierra

**React-pdf version:**
@react-pdf/renderer@^1.0.0-alpha.25

**Description:**
I am attempting to draw a circle with a border by rounding a `<View />` and adding a border. 

```
const Quixote = () => (
  <Document>
    <Page style={styles.body}>
      <View style={styles.circle}></View>
    </Page>
  </Document>
);

const styles = StyleSheet.create({
  body: {
    paddingTop: 35,
    paddingBottom: 65,
    paddingHorizontal: 35,
  },
  circle: {
    width: 50,
    height: 50,
    backgroundColor: 'green',
    borderRadius: 50,
    border: '2 solid red'
  }

});

ReactPDF.render(<Quixote />);
```

When I set the `borderRadius` to 1, the border drawn mostly goes around the view. 
![screen shot 2018-11-29 at 12 14 46 pm](https://user-images.githubusercontent.com/4199296/49249306-b037e380-f3d0-11e8-96cd-29eee986683b.png)

When I set `borderRadius` to 3, the border drawn already starts to have issues.
![screen shot 2018-11-29 at 12 14 51 pm](https://user-images.githubusercontent.com/4199296/49249354-c5ad0d80-f3d0-11e8-8e2d-393dee2530e1.png)

As I increase the borderRadius to make the view more circular the rendering gets really strange.
`borderRadius @ 20`
![screen shot 2018-11-29 at 12 14 58 pm](https://user-images.githubusercontent.com/4199296/49249430-f42ae880-f3d0-11e8-9272-cefd5bca1b0d.png)

`borderRadius @ 30`
![screen shot 2018-11-29 at 12 15 02 pm](https://user-images.githubusercontent.com/4199296/49249444-fb51f680-f3d0-11e8-8f24-49d22bc27962.png)

I would love the border implementation to better support rounded views! Thanks a bunch!

Attached Images:
- https://user-images.githubusercontent.com/4199296/49249306-b037e380-f3d0-11e8-96cd-29eee986683b.png
- https://user-images.githubusercontent.com/4199296/49249354-c5ad0d80-f3d0-11e8-8e2d-393dee2530e1.png
- https://user-images.githubusercontent.com/4199296/49249430-f42ae880-f3d0-11e8-9272-cefd5bca1b0d.png
- https://user-images.githubusercontent.com/4199296/49249444-fb51f680-f3d0-11e8-8f24-49d22bc27962.png

[adapter_fallback=ModuleNotFoundError]

[Multimodal Context - Compact]
[Visual Evidence] Image 1: https://user-images.githubusercontent.com/4199296/49249306-b037e380-f3d0-11e8-96cd-29eee986683b.png **Raw Visual Description** Split-screen view: left side shows React code in a dark editor, right side shows rendered PDF output. Code defines a green square `<View>` with `borderRadius: 1` and `border: '2 solid red'`. Rendered output shows a green square with a red border, but the border is visibly misaligned and clipped at the corners, especially as `borderRadius` increases. **Issue-Relevant Analysis** The `borderRadius` property on a `<View>` in React-PDF does not render the border correctly around rounded corners. At low values (e.g., 1), the border is mostly intact but clipped. As `borderRadius` increases (e.g., 20, 30), the border becomes distorted, appearing to "melt" or be cut off at the corners, indicating a rendering bug in how borders are applied to rounded elements. **Localization Clues** - Code snippet: `borderRadius: 1` and `border: '2 solid red'` in `styles.circle` - Rendered output: green square with red border, visibly misaligned and clipped at corners - React-PDF version: `@react-pdf/renderer@^1.0.0-alpha.25` - Issue occurs on macOS 10.13 High Sierra - Expected: border should fully encircle the rounded view - Actual: border is clipped or distorted as `borderRadius` increases Image 2: https://user-images.githubusercontent.com/4199296/49249354-c5ad0d80-f3d0-11e8-8e2d-393dee2530e1.png **Raw Visual Description** Split-screen view: left side shows React code in a dark editor, right side shows rendered PDF output. Code defines a green `<View>` with `borderRadius: 3` and `border: '2 solid red'`. Rendered output shows a green square with a red border, not a circle. The border appears clipped or misaligned, especially at corners, indicating rendering artifacts. **Issue-Relevant Analysis** The `<View>` with `borderRadius` and `border` is not rendering a proper circular border. At `borderRadius: 3`, the border is visibly clipped or distorted, suggesting the PDF renderer does not correctly handle rounded corners with borders. The issue escalates with higher `borderRadius` values, implying a rendering engine limitation or bug in how borders are applied to rounded shapes. **Localization Clues** - Code snippet: `borderRadius: 3`, `border: '2 solid red'` in `styles.circle` - Rendered output: green square with red border, not a circle - React-PDF version: `@react-pdf/renderer@^1.0.0-alpha.25` - OS: macOS 10.13 High Sierra - Issu...

[Adapter Note]
Use the multimodal context only as auxiliary evidence for code localization.

[Multimodal Context - Compact]
[Visual Evidence] Image 1: https://user-images.githubusercontent.com/4199296/49249306-b037e380-f3d0-11e8-96cd-29eee986683b.png **Raw Visual Description** Split-screen view: left side shows React code in a dark editor, right side shows rendered PDF output. Code defines a green square `<View>` with `borderRadius: 1` and `border: '2 solid red'`. Rendered output shows a green square with a red border, but the border is visibly misaligned and clipped at the corners, especially as `borderRadius` increases. **Issue-Relevant Analysis** The `borderRadius` property on a `<View>` in React-PDF does not render the border correctly around rounded corners. At low values (e.g., 1), the border is mostly intact but clipped. As `borderRadius` increases (e.g., 20, 30), the border becomes distorted, appearing to "melt" or be cut off at the corners, indicating a rendering bug in how borders are applied to rounded elements. **Localization Clues** - Code snippet: `borderRadius: 1` and `border: '2 solid red'` in `styles.circle` - Rendered output: green square with red border, visibly misaligned and clipped at corners - React-PDF version: `@react-pdf/renderer@^1.0.0-alpha.25` - Issue occurs on macOS 10.13 High Sierra - Expected: border should fully encircle the rounded view - Actual: border is clipped or distorted as `borderRadius` increases Image 2: https://user-images.githubusercontent.com/4199296/49249354-c5ad0d80-f3d0-11e8-8e2d-393dee2530e1.png **Raw Visual Description** Split-screen view: left side shows React code in a dark editor, right side shows rendered PDF output. Code defines a green `<View>` with `borderRadius: 3` and `border: '2 solid red'`. Rendered output shows a green square with a red border, not a circle. The border appears clipped or misaligned, especially at corners, indicating rendering artifacts. **Issue-Relevant Analysis** The `<View>` with `borderRadius` and `border` is not rendering a proper circular border. At `borderRadius: 3`, the border is visibly clipped or distorted, suggesting the PDF renderer does not correctly handle rounded corners with borders. The issue escalates with higher `borderRadius` values, implying a rendering engine limitation or bug in how borders are applied to rounded shapes. **Localization Clues** - Code snippet: `borderRadius: 3`, `border: '2 solid red'` in `styles.circle` - Rendered output: green square with red border, not a circle - React-PDF version: `@react-pdf/renderer@^1.0.0-alpha.25` - OS: macOS 10.13 High Sierra - Issu...

[Adapter Note]
Use the multimodal context only as auxiliary evidence for code localization.

[Multimodal Context - Compact]
[Visual Evidence] Image 1: https://user-images.githubusercontent.com/4199296/49249306-b037e380-f3d0-11e8-96cd-29eee986683b.png **Raw Visual Description** Split-screen view: left side shows React code in a dark editor, right side shows rendered PDF output. Code defines a green square `<View>` with `borderRadius: 1` and `border: '2 solid red'`. Rendered output shows a green square with a red border, but the border is visibly misaligned and clipped at the corners, especially as `borderRadius` increases. **Issue-Relevant Analysis** The `borderRadius` property on a `<View>` in React-PDF does not render the border correctly around rounded corners. At low values (e.g., 1), the border is mostly intact but clipped. As `borderRadius` increases (e.g., 20, 30), the border becomes distorted, appearing to "melt" or be cut off at the corners, indicating a rendering bug in how borders are applied to rounded elements. **Localization Clues** - Code snippet: `borderRadius: 1` and `border: '2 solid red'` in `styles.circle` - Rendered output: green square with red border, visibly misaligned and clipped at corners - React-PDF version: `@react-pdf/renderer@^1.0.0-alpha.25` - Issue occurs on macOS 10.13 High Sierra - Expected: border should fully encircle the rounded view - Actual: border is clipped or distorted as `borderRadius` increases Image 2: https://user-images.githubusercontent.com/4199296/49249354-c5ad0d80-f3d0-11e8-8e2d-393dee2530e1.png **Raw Visual Description** Split-screen view: left side shows React code in a dark editor, right side shows rendered PDF output. Code defines a green `<View>` with `borderRadius: 3` and `border: '2 solid red'`. Rendered output shows a green square with a red border, not a circle. The border appears clipped or misaligned, especially at corners, indicating rendering artifacts. **Issue-Relevant Analysis** The `<View>` with `borderRadius` and `border` is not rendering a proper circular border. At `borderRadius: 3`, the border is visibly clipped or distorted, suggesting the PDF renderer does not correctly handle rounded corners with borders. The issue escalates with higher `borderRadius` values, implying a rendering engine limitation or bug in how borders are applied to rounded shapes. **Localization Clues** - Code snippet: `borderRadius: 3`, `border: '2 solid red'` in `styles.circle` - Rendered output: green square with red border, not a circle - React-PDF version: `@react-pdf/renderer@^1.0.0-alpha.25` - OS: macOS 10.13 High Sierra - Issu...

[Adapter Note]
Use the multimodal context only as auxiliary evidence for code localization.
````

### 5.4 markedjs__marked-1435：Markdown/富文本渲染

- 数据来源：SWE-bench Multimodal dev 全量

- Repo：`markedjs/marked`

- Issue 标题/首行：[Bug] We have to use '\' to add the '('

- 图片核对：PNG, 1299 x 205；人工核对为 Marked Demo 中 Markdown 输入和 HTML preview 对照。

- 图片 URL 数：1；网页 URL 数：7；Gold 文件数：1


图片 URL：

- https://user-images.githubusercontent.com/40081831/53847026-28263300-3fea-11e9-8c93-9acc880bde90.png

网页/代码/文档 URL：

- https://github.com/markedjs/marked/files/2933754/Sample.txt
- https://github.com/nodejs/nodejs.org/issues/2119
- https://liebdich.com
- https://t
- https://twitter.com/matteocollina
- https://twitter.com/pracucci
- https://voxnest.com

Gold 文件：

- `lib/marked.js`

定位解释：


这类图片通常同时包含输入 Markdown 和预览结果。定位时要抽取语法 token、链接/HTML/escape 行为、版本信息，然后检索 lexer/parser/renderer。


完整 issue 原文：

````text
[Original Issue]
[Original Issue]
[Original Issue]
[Bug] We have to use '\' to add the '('
![image](https://user-images.githubusercontent.com/40081831/53847026-28263300-3fea-11e9-8c93-9acc880bde90.png)

Notice that we have to add '\' in front of "(", otherwises this won't be analyzed out.

The original words are in the attached sample:
[Sample.txt](https://github.com/markedjs/marked/files/2933754/Sample.txt).

For more，please refer to：https://github.com/nodejs/nodejs.org/issues/2119

Attached Images:
- https://user-images.githubusercontent.com/40081831/53847026-28263300-3fea-11e9-8c93-9acc880bde90.png

Related URLs:
- https://github.com/markedjs/marked/files/2933754/Sample.txt
- https://github.com/nodejs/nodejs.org/issues/2119

[adapter_fallback=ModuleNotFoundError]

[Multimodal Context - Compact]
[Visual Evidence] Image 1: https://user-images.githubusercontent.com/40081831/53847026-28263300-3fea-11e9-8c93-9acc880bde90.png **Raw Visual Description** A Markdown previewer UI shows a text input field and its rendered output. In the input, URLs are wrapped in `[text](url)` syntax, but the `(` in the URL is escaped with a backslash (`\`). The preview correctly renders the links as clickable text. The UI includes version selection, clear button, and performance metrics. **Issue-Relevant Analysis** The Markdown parser incorrectly treats unescaped parentheses `(` in URLs as literal characters rather than part of link syntax. This breaks link rendering unless the `(` is escaped with a backslash (`\`). The parser should recognize `(` within URLs as part of the link syntax without requiring escaping. **Localization Clues** - The issue occurs in the Markdown parser’s link syntax handling. - The parser must correctly parse `(` within URLs without requiring `\` escaping. - The issue is likely in the link regex or tokenization logic in the `marked` library. [Web Evidence] URL 1: https://github.com/markedjs/marked/files/2933754/Sample.txt Summary: CVE-2018-12121 originally reported by Jan Maybach ([liebdich.com](https://liebdich.com)), keep-alive variant reported by [Marco Pracucci](https://twitter.com/pracucci) \([Voxnest](https://voxnest.com)), fixed by [Matteo Collina](https://twitter.com/matteocollina). URL 2: https://github.com/nodejs/nodejs.org/issues/2119 Summary: Markdown parsing problem · Issue #2119 · nodejs/nodejs.org · GitHub CVE-2018-12121 originally reported by Jan Maybach ([liebdich.com](https://liebdich.com)), keep-alive variant reported by [Marco Pracucci](https://twitter.com/pracucci) ([Voxnest](https://voxnest.com)), fixed by [Matteo Collina](https://t... Markdown parsing problem · Issue #2119 · nodejs/nodejs.org · GitHub Skip to content Navigation Menu Toggle navigation Sign in Appearance settings Platform AI CODE CREATION GitHub Copilot Write better code with AI GitHub Copilot app Direct agents from issue to merge MCP Registry New Integrate external tools DEVELOPER WORKFLOWS Actions Automate any workflow Codespaces Instant dev environ...

[Adapter Note]
Use the multimodal context only as auxiliary evidence for code localization.

[Multimodal Context - Compact]
[Visual Evidence] Image 1: https://user-images.githubusercontent.com/40081831/53847026-28263300-3fea-11e9-8c93-9acc880bde90.png **Raw Visual Description** A Markdown previewer UI shows a text input field and its rendered output. In the input, URLs are wrapped in `[text](url)` syntax, but the `(` in the URL is escaped with a backslash (`\`). The preview correctly renders the links as clickable text. The UI includes version selection, clear button, and performance metrics. **Issue-Relevant Analysis** The Markdown parser incorrectly treats unescaped parentheses `(` in URLs as literal characters rather than part of link syntax. This breaks link rendering unless the `(` is escaped with a backslash (`\`). The parser should recognize `(` within URLs as part of the link syntax without requiring escaping. **Localization Clues** - The issue occurs in the Markdown parser’s link syntax handling. - The parser must correctly parse `(` within URLs without requiring `\` escaping. - The issue is likely in the link regex or tokenization logic in the `marked` library. [Web Evidence] URL 1: https://github.com/markedjs/marked/files/2933754/Sample.txt Summary: CVE-2018-12121 originally reported by Jan Maybach ([liebdich.com](https://liebdich.com)), keep-alive variant reported by [Marco Pracucci](https://twitter.com/pracucci) \([Voxnest](https://voxnest.com)), fixed by [Matteo Collina](https://twitter.com/matteocollina). URL 2: https://github.com/nodejs/nodejs.org/issues/2119 Summary: Markdown parsing problem · Issue #2119 · nodejs/nodejs.org · GitHub CVE-2018-12121 originally reported by Jan Maybach ([liebdich.com](https://liebdich.com)), keep-alive variant reported by [Marco Pracucci](https://twitter.com/pracucci) ([Voxnest](https://voxnest.com)), fixed by [Matteo Collina](https://t... Markdown parsing problem · Issue #2119 · nodejs/nodejs.org · GitHub Skip to content Navigation Menu Toggle navigation Sign in Appearance settings Platform AI CODE CREATION GitHub Copilot Write better code with AI GitHub Copilot app Direct agents from issue to merge MCP Registry New Integrate external tools DEVELOPER WORKFLOWS Actions Automate any workflow Codespaces Instant dev environ... URL 3: https://liebdich.com Summary: URL 4: https://t Web processing failed; use URL only. Error: <urlopen error [Errno -3] Temporary failure in name resolution> URL 5: https://twitter.com/matteocollina Summary: Matteo Collina (@matteocollina) / X @platformatic Co-Founder & CTO, @nodejs TSC Chair, Lead maint...

[Adapter Note]
Use the multimodal context only as auxiliary evidence for code localization.

[Multimodal Context - Compact]
[Visual Evidence] Image 1: https://user-images.githubusercontent.com/40081831/53847026-28263300-3fea-11e9-8c93-9acc880bde90.png **Raw Visual Description** A Markdown previewer UI shows a text input field and its rendered output. In the input, URLs are wrapped in `[text](url)` syntax, but the `(` in the URL is escaped with a backslash (`\`). The preview correctly renders the links as clickable text. The UI includes version selection, clear button, and performance metrics. **Issue-Relevant Analysis** The Markdown parser incorrectly treats unescaped parentheses `(` in URLs as literal characters rather than part of link syntax. This breaks link rendering unless the `(` is escaped with a backslash (`\`). The parser should recognize `(` within URLs as part of the link syntax without requiring escaping. **Localization Clues** - The issue occurs in the Markdown parser’s link syntax handling. - The parser must correctly parse `(` within URLs without requiring `\` escaping. - The issue is likely in the link regex or tokenization logic in the `marked` library. [Web Evidence] URL 1: https://github.com/markedjs/marked/files/2933754/Sample.txt Summary: CVE-2018-12121 originally reported by Jan Maybach ([liebdich.com](https://liebdich.com)), keep-alive variant reported by [Marco Pracucci](https://twitter.com/pracucci) \([Voxnest](https://voxnest.com)), fixed by [Matteo Collina](https://twitter.com/matteocollina). URL 2: https://github.com/nodejs/nodejs.org/issues/2119 Summary: Markdown parsing problem · Issue #2119 · nodejs/nodejs.org · GitHub CVE-2018-12121 originally reported by Jan Maybach ([liebdich.com](https://liebdich.com)), keep-alive variant reported by [Marco Pracucci](https://twitter.com/pracucci) ([Voxnest](https://voxnest.com)), fixed by [Matteo Collina](https://t... Markdown parsing problem · Issue #2119 · nodejs/nodejs.org · GitHub Skip to content Navigation Menu Toggle navigation Sign in Appearance settings Platform AI CODE CREATION GitHub Copilot Write better code with AI GitHub Copilot app Direct agents from issue to merge MCP Registry New Integrate external tools DEVELOPER WORKFLOWS Actions Automate any workflow Codespaces Instant dev environ... URL 3: https://liebdich.com Summary: URL 4: https://t Web processing failed; use URL only. Error: <urlopen error [Errno -3] Temporary failure in name resolution> URL 5: https://twitter.com/matteocollina Summary: Matteo Collina (@matteocollina) / X @platformatic Co-Founder & CTO, @nodejs TSC Chair, Lead maint...

[Adapter Note]
Use the multimodal context only as auxiliary evidence for code localization.
````

### 5.5 processing__p5.js-4147：图形/几何/WebGL输出

- 数据来源：SWE-bench Multimodal dev 全量

- Repo：`processing/p5.js`

- Issue 标题/首行：WEBGL vertex color no longer working as expected in 0.8.0

- 图片核对：PNG, 466 x 456；人工核对为 p5.js/canvas 图形输出截图。

- 图片 URL 数：2；网页 URL 数：2；Gold 文件数：12


图片 URL：

- https://user-images.githubusercontent.com/9550197/68548929-8b2a5e00-03f2-11ea-9992-02cb1b185d81.png
- https://user-images.githubusercontent.com/9550197/68548937-ae550d80-03f2-11ea-9570-682b42bbd7e0.png

网页/代码/文档 URL：

- https://editor.p5js.org/haschdl/sketches/LNpN29qY4
- https://editor.p5js.org/haschdl/sketches/tlmBNIdjR

Gold 文件：

- `src/app.js`
- `src/core/constants.js`
- `src/core/shape/vertex.js`
- `src/webgl/3d_primitives.js`
- `src/webgl/material.js`
- `src/webgl/p5.Geometry.js`
- `src/webgl/p5.RenderBuffer.js`
- `src/webgl/p5.RendererGL.Immediate.js`
- `src/webgl/p5.RendererGL.Retained.js`
- `src/webgl/p5.RendererGL.js`
- `src/webgl/p5.Shader.js`
- `src/webgl/text.js`

定位解释：


这类图片展示几何或渲染状态。定位时要抽取颜色、坐标、形状、渐变、透明度、WebGL/canvas API，再映射到绘制函数或 shader/renderer。


完整 issue 原文：

````text
[Original Issue]
[Original Issue]
[Original Issue]
WEBGL vertex color no longer working as expected in 0.8.0
I read multiple issues related to WEBGL but I could not find this one. It seems something broke between 0.8.0 and 0.9.0. 

#### Nature of issue?

- [x] Found a bug
- [ ] Existing feature enhancement
- [ ] New feature request

#### Most appropriate sub-area of p5.js?

- [x] Color
- [ ] Core/Environment/Rendering
- [ ] Data
- [ ] Events
- [ ] Image
- [ ] IO
- [ ] Math
- [ ] Typography
- [ ] Utilities
- [x] WebGL
- [ ] Other (specify if possible)

#### Which platform were you using when you encountered this?

- [ ] Mobile/Tablet (touch devices)
- [x] Desktop/Laptop
- [ ] Others (specify if possible)

#### Details about the bug: 

- p5.js version: 0.9.0
- Web browser and version: 78.0.3904.97
- Operating System: Windows 10
- Steps to reproduce this:

1) Using the p4js editor, create a new sketch, and make sure the HTML has a reference to p5js version 0.9.0
2) Paste the following code to the editor and hit play. A live version is available [here](https://editor.p5js.org/haschdl/sketches/tlmBNIdjR)

```javascript
function setup() {
  createCanvas(500, 500, WEBGL);
}

function draw() {
  beginShape();
  fill(100,100,20);
  vertex(-150, -150);
  fill(250);
  vertex(150, -150);
  fill(200);
  vertex(150, 150);
  fill(100,50, 100);
  vertex(-150, 150);
  endShape(CLOSE);
}
```
3) The output will be as follows (using p5.js version 0.9.0):
![image](https://user-images.githubusercontent.com/9550197/68548929-8b2a5e00-03f2-11ea-9992-02cb1b185d81.png)

Changing the `sketch.hmtl` to use the version **0.8.0**, we get the expected output. A live version is available [here](https://editor.p5js.org/haschdl/sketches/LNpN29qY4). Note the code in `sketch.js` is the same, but the reference inside `sketch.html` is to p5js 0.8.0
![image](https://user-images.githubusercontent.com/9550197/68548937-ae550d80-03f2-11ea-9570-682b42bbd7e0.png)




#### Feature enhancement details:



#### New feature details:

Attached Images:
- https://user-images.githubusercontent.com/9550197/68548929-8b2a5e00-03f2-11ea-9992-02cb1b185d81.png
- https://user-images.githubusercontent.com/9550197/68548937-ae550d80-03f2-11ea-9570-682b42bbd7e0.png

Related URLs:
- https://editor.p5js.org/haschdl/sketches/LNpN29qY4
- https://editor.p5js.org/haschdl/sketches/tlmBNIdjR

[adapter_fallback=ModuleNotFoundError]

[Multimodal Context - Compact]
[Visual Evidence] Image 1: https://user-images.githubusercontent.com/9550197/68548929-8b2a5e00-03f2-11ea-9992-02cb1b185d81.png **Raw Visual Description** A square canvas divided diagonally into two triangles. The top-left triangle is a gradient from light gray to olive green. The bottom-right triangle is solid dark purple. The diagonal line is sharp and clean. **Issue-Relevant Analysis** The WebGL vertex coloring in p5.js 0.9.0 is not applying per-vertex colors as expected. In 0.8.0, each `vertex()` call with a preceding `fill()` correctly sets the color for that vertex. In 0.9.0, the colors are not being applied per-vertex, resulting in a uniform color across the entire shape (or defaulting to the last fill color). **Localization Clues** - WebGL rendering pipeline - Vertex color assignment logic - `fill()` and `vertex()` interaction in WebGL mode - p5.js version 0.9.0 WebGL color bug - Likely in WebGL renderer or vertex attribute setup code Image 2: https://user-images.githubusercontent.com/9550197/68548937-ae550d80-03f2-11ea-9570-682b42bbd7e0.png **Raw Visual Description** A square WebGL canvas displaying a smooth gradient transitioning from olive-green/mustard at the top-left to a muted purple/magenta at the bottom-left, fading to near-white at the top-right and right edge. The gradient appears uniform and lacks sharp edges or distinct color blocks. **Issue-Relevant Analysis** The WebGL vertex coloring behavior regressed between p5.js 0.8.0 and 0.9.0. The expected output (visible in 0.8.0) should show distinct colored triangles defined by `fill()` calls before each `vertex()`. Instead, 0.9.0 renders a blended gradient across the entire shape, indicating a change in how vertex colors are applied or interpolated in WebGL rendering. **Localization Clues** - Code component: `fill()` and `vertex()` calls within `draw()` function in WebGL mode. - Likely affected module: WebGL rendering pipeline or vertex attribute handling. - Version-specific regression: Behavior differs between p5.js 0.8.0 and 0.9.0. - Expected vs actual: Discrete colored vertices vs blended gradient. [Web Evidence] URL 1: https://editor.p5js.org/haschdl/sketches/LNpN29qY4 Summary: Github-issue-4141-v-080 by haschdl -p5.js Web Editor A web editor for p5.js, a JavaScript library with the goal of making coding accessible to artists, designers, educators, and beginners. Github-issue-4141-v-080 by haschdl -p5.js Web Editor URL 2: https://editor.p5js.org/haschdl/sketches/tlmBNIdjR Summary: Git...

[Adapter Note]
Use the multimodal context only as auxiliary evidence for code localization.

[Multimodal Context - Compact]
[Visual Evidence] Image 1: https://user-images.githubusercontent.com/9550197/68548929-8b2a5e00-03f2-11ea-9992-02cb1b185d81.png **Raw Visual Description** A square canvas divided diagonally into two triangles. The top-left triangle is a gradient from light gray to olive green. The bottom-right triangle is solid dark purple. The diagonal line is sharp and clean. **Issue-Relevant Analysis** The WebGL vertex coloring in p5.js 0.9.0 is not applying per-vertex colors as expected. In 0.8.0, each `vertex()` call with a preceding `fill()` correctly sets the color for that vertex. In 0.9.0, the colors are not being applied per-vertex, resulting in a uniform color across the entire shape (or defaulting to the last fill color). **Localization Clues** - WebGL rendering pipeline - Vertex color assignment logic - `fill()` and `vertex()` interaction in WebGL mode - p5.js version 0.9.0 WebGL color bug - Likely in WebGL renderer or vertex attribute setup code Image 2: https://user-images.githubusercontent.com/9550197/68548937-ae550d80-03f2-11ea-9570-682b42bbd7e0.png **Raw Visual Description** A square WebGL canvas displaying a smooth gradient transitioning from olive-green/mustard at the top-left to a muted purple/magenta at the bottom-left, fading to near-white at the top-right and right edge. The gradient appears uniform and lacks sharp edges or distinct color blocks. **Issue-Relevant Analysis** The WebGL vertex coloring behavior regressed between p5.js 0.8.0 and 0.9.0. The expected output (visible in 0.8.0) should show distinct colored triangles defined by `fill()` calls before each `vertex()`. Instead, 0.9.0 renders a blended gradient across the entire shape, indicating a change in how vertex colors are applied or interpolated in WebGL rendering. **Localization Clues** - Code component: `fill()` and `vertex()` calls within `draw()` function in WebGL mode. - Likely affected module: WebGL rendering pipeline or vertex attribute handling. - Version-specific regression: Behavior differs between p5.js 0.8.0 and 0.9.0. - Expected vs actual: Discrete colored vertices vs blended gradient. [Web Evidence] URL 1: https://editor.p5js.org/haschdl/sketches/LNpN29qY4 Summary: Github-issue-4141-v-080 by haschdl -p5.js Web Editor A web editor for p5.js, a JavaScript library with the goal of making coding accessible to artists, designers, educators, and beginners. Github-issue-4141-v-080 by haschdl -p5.js Web Editor URL 2: https://editor.p5js.org/haschdl/sketches/tlmBNIdjR Summary: Git...

[Adapter Note]
Use the multimodal context only as auxiliary evidence for code localization.

[Multimodal Context - Compact]
[Visual Evidence] Image 1: https://user-images.githubusercontent.com/9550197/68548929-8b2a5e00-03f2-11ea-9992-02cb1b185d81.png **Raw Visual Description** A square canvas divided diagonally into two triangles. The top-left triangle is a gradient from light gray to olive green. The bottom-right triangle is solid dark purple. The diagonal line is sharp and clean. **Issue-Relevant Analysis** The WebGL vertex coloring in p5.js 0.9.0 is not applying per-vertex colors as expected. In 0.8.0, each `vertex()` call with a preceding `fill()` correctly sets the color for that vertex. In 0.9.0, the colors are not being applied per-vertex, resulting in a uniform color across the entire shape (or defaulting to the last fill color). **Localization Clues** - WebGL rendering pipeline - Vertex color assignment logic - `fill()` and `vertex()` interaction in WebGL mode - p5.js version 0.9.0 WebGL color bug - Likely in WebGL renderer or vertex attribute setup code Image 2: https://user-images.githubusercontent.com/9550197/68548937-ae550d80-03f2-11ea-9570-682b42bbd7e0.png **Raw Visual Description** A square WebGL canvas displaying a smooth gradient transitioning from olive-green/mustard at the top-left to a muted purple/magenta at the bottom-left, fading to near-white at the top-right and right edge. The gradient appears uniform and lacks sharp edges or distinct color blocks. **Issue-Relevant Analysis** The WebGL vertex coloring behavior regressed between p5.js 0.8.0 and 0.9.0. The expected output (visible in 0.8.0) should show distinct colored triangles defined by `fill()` calls before each `vertex()`. Instead, 0.9.0 renders a blended gradient across the entire shape, indicating a change in how vertex colors are applied or interpolated in WebGL rendering. **Localization Clues** - Code component: `fill()` and `vertex()` calls within `draw()` function in WebGL mode. - Likely affected module: WebGL rendering pipeline or vertex attribute handling. - Version-specific regression: Behavior differs between p5.js 0.8.0 and 0.9.0. - Expected vs actual: Discrete colored vertices vs blended gradient. [Web Evidence] URL 1: https://editor.p5js.org/haschdl/sketches/LNpN29qY4 Summary: Github-issue-4141-v-080 by haschdl -p5.js Web Editor A web editor for p5.js, a JavaScript library with the goal of making coding accessible to artists, designers, educators, and beginners. Github-issue-4141-v-080 by haschdl -p5.js Web Editor URL 2: https://editor.p5js.org/haschdl/sketches/tlmBNIdjR Summary: Git...

[Adapter Note]
Use the multimodal context only as auxiliary evidence for code localization.
````

### 5.6 assertj__assertj-1332：IDE/断言diff/测试失败视图

- 数据来源：OmniGIRL full-candidates

- Repo：`assertj/assertj`

- 主语言：`Java`

- Issue 标题/首行：Throw AssertionFailedError instead of AssertionError in non-strict string assertions

- 图片核对：PNG, 1796 x 853；人工核对为 IntelliJ/JUnit assertion diff 和测试失败输出。

- 图片 URL 数：1；网页 URL 数：0；Gold 文件数：1


图片 URL：

- https://user-images.githubusercontent.com/2374036/46114945-98d85080-c1fd-11e8-87a2-9cc52e0eed3e.png

Gold 文件：

- `src/main/java/org/assertj/core/internal/Strings.java`

定位解释：


这类图片包含高价值文本证据：测试类、失败类型、expected/actual。定位时应 OCR/文本化后优先检索错误类、测试名和断言构造路径。


完整 issue 原文：

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

### 5.7 babel__babel-15134：编译器/Parser/Playground错误输出

- 数据来源：OmniGIRL full-candidates

- Repo：`babel/babel`

- 主语言：`TypeScript`

- Issue 标题/首行：[Bug]: Babel crashes when using `await` as an identifier in ForInOfHead

- 图片核对：PNG, 892 x 234；人工核对为 Babel parser 错误输出截图。

- 图片 URL 数：1；网页 URL 数：2；Gold 文件数：1


图片 URL：

- https://user-images.githubusercontent.com/68288688/200038280-5710d26b-d188-433c-b675-e83a27e5ef13.png

网页/代码/文档 URL：

- https://babeljs.io/repl#?browsers=since%202015&build=&builtIns=false&corejs=3.21&spec=false&loose=false&code_lz=GYewTgFAhg7lCWAXABCYyDaBGANAJhwGYBdASmWQG9kBjEAOwGcQAbAUwDoWQBzaOJOQC-AKCA&debug=false&forceAllTransforms=false&shippedProposals=false&circleciRepo=&evaluate=false&fileSize=false&timeTravel=false&sourceType=script&lineWrap=true&presets=env%2Creact%2Cstage-2&prettier=false&targets=&version=7.20.1&externalPlugins=&assumptions=%7B%7D
- https://babeljs.io/repl#?browsers=since%202015&build=&builtIns=false&corejs=3.21&spec=false&loose=false&code_lz=GYewTgFAhg7lCWAXABCYyDaBGANAJhwGYBdASmWQG9kBjEAOwGcQAbAUwDoWQBzaOJOQC-AKCA&debug=false&forceAllTransforms=false&shippedProposals=false&circleciRepo=&evaluate=false&fileSize=false&timeTravel=false&sourceType=script&lineWrap=true&presets=env%2Creact%2Cstage-2&prettier=false&targets=&version=7.20.1&externalPlugins=&assumptions=%7B%7D

Gold 文件：

- `packages/babel-parser/src/parser/expression.ts`

定位解释：


这类图片的核心是输入代码、parser/plugin、错误位置和报错短语。定位时应将图片和 URL hash 中的代码/config 合并成结构化 repro。


完整 issue 原文：

````text
[Original Issue]
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

[Multimodal Context - Compact]
[Visual Evidence] Image 1: https://user-images.githubusercontent.com/68288688/200038280-5710d26b-d188-433c-b675-e83a27e5ef13.png Visual processing failed; use the URL and issue text only. Error: HTTP Error 500: Internal Server Error [Web Evidence] URL 1: https://babeljs.io/repl#?browsers=since%202015&build=&builtIns=false&corejs=3.21&spec=false&loose=false&code_lz=GYewTgFAhg7lCWAXABCYyDaBGANAJhwGYBdASmWQG9kBjEAOwGcQAbAUwDoWQBzaOJOQC-AKCA&debug=false&forceAllTransforms=false&shippedProposals=false&circleciRepo=&evaluate=false&fileSize=false&timeTravel=false&sourceType=script&lineWrap=true&presets=env%2Creact%2Cstage-2&prettier=false&targets=&version=7.20.1&externalPlugins=&assumptions=%7B%7D Summary: Babel Babel Skip to main content Docs Setup Try it out Videos Blog Search Donate Team GitHub

[Adapter Note]
Use the multimodal context only as auxiliary evidence for code localization.
````

### 5.8 tailwindlabs__tailwindcss-10212：CSS/样式Playground输出

- 数据来源：OmniGIRL full-candidates

- Repo：`tailwindlabs/tailwindcss`

- 主语言：`TypeScript`

- Issue 标题/首行：Div content with brackets `[]` prevents arbitrary class from being generated

- 图片核对：PNG, 1620 x 930；人工核对为 Tailwind playground，HTML/CSS 和 preview 并列。

- 图片 URL 数：2；网页 URL 数：4；Gold 文件数：1


图片 URL：

- https://user-images.githubusercontent.com/111561/209682078-7e43a107-52ff-4006-8c37-ec44414abe12.png
- https://user-images.githubusercontent.com/111561/209682172-de1dcaaa-6e69-429b-907f-840691e35ceb.png

网页/代码/文档 URL：

- https://play.tailwindcss.com/0VLICQ8oUW
- https://play.tailwindcss.com/5KJf7xDKv6
- https://play.tailwindcss.com/0VLICQ8oUW
- https://play.tailwindcss.com/5KJf7xDKv6

Gold 文件：

- `src/lib/defaultExtractor.js`

定位解释：


这类图片的核心是 HTML class token、生成 CSS 和 preview 差异。定位时应抽取 class、variant、arbitrary value、prefix/config，再检索 candidate generation 和 parser。


完整 issue 原文：

````text
[Original Issue]
Div content with brackets `[]` prevents arbitrary class from being generated
## This works: https://play.tailwindcss.com/0VLICQ8oUW

<img width="810" alt="image" src="https://user-images.githubusercontent.com/111561/209682078-7e43a107-52ff-4006-8c37-ec44414abe12.png">

## This does not work: https://play.tailwindcss.com/5KJf7xDKv6
<img width="821" alt="image" src="https://user-images.githubusercontent.com/111561/209682172-de1dcaaa-6e69-429b-907f-840691e35ceb.png">

[Multimodal Context - Compact]
[Visual Evidence] Image 1: https://user-images.githubusercontent.com/111561/209682078-7e43a107-52ff-4006-8c37-ec44414abe12.png Visual processing failed; use the URL and issue text only. Error: HTTP Error 500: Internal Server Error Image 2: https://user-images.githubusercontent.com/111561/209682172-de1dcaaa-6e69-429b-907f-840691e35ceb.png Visual processing failed; use the URL and issue text only. Error: HTTP Error 500: Internal Server Error [Web Evidence] URL 1: https://play.tailwindcss.com/0VLICQ8oUW Summary: Tailwind Play An advanced online playground for Tailwind CSS that lets you use all of Tailwind's build-time features directly in the browser. Tailwind Play Share Loading Copied! ... /0VLICQ8oUW v3.4.19 Switch to vertical split layout Switch to horizontal split layout Switch to preview-only layout Toggle responsive design mode URL 2: https://play.tailwindcss.com/5KJf7xDKv6 Summary: Tailwind Play An advanced online playground for Tailwind CSS that lets you use all of Tailwind's build-time features directly in the browser. Tailwind Play Share Loading Copied! ... /5KJf7xDKv6 v3.4.19 Switch to vertical split layout Switch to horizontal split layout Switch to preview-only layout Toggle responsive design mode

[Adapter Note]
Use the multimodal context only as auxiliary evidence for code localization.
````

### 5.9 iamkun__dayjs-581：弱相关徽章/头像/奖励图

- 数据来源：OmniGIRL full-candidates

- Repo：`iamkun/dayjs`

- 主语言：`JavaScript`

- Issue 标题/首行：Please fix formatting months in russian

- 图片核对：SVG；人工核对为 IssueHunt reward badge，不是行为截图。

- 图片 URL 数：1；网页 URL 数：10；Gold 文件数：2


图片 URL：

- https://img.shields.io/badge/IssueHunt-%2450%20Rewarded-%237E24E3.svg

网页/代码/文档 URL：

- https://avatars0.githubusercontent.com/u/17680888?v=4
- https://avatars3.githubusercontent.com/u/44827199?v=4
- https://issuehunt.io/membership/members
- https://issuehunt.io/r/iamkun/dayjs/
- https://issuehunt.io/r/iamkun/dayjs/issues/577
- https://issuehunt.io/r/iamkun/dayjs/pull/581
- https://issuehunt.io/r/new
- https://issuehunt.io/u/iamkun
- https://issuehunt.io/u/issuehunt
- https://runkit.com/bagmutva/5cbc390d7da00600130f419c

Gold 文件：

- `src/index.js`
- `src/locale/ru.js`

定位解释：


这类图片本身几乎不携带定位信息。Agent 应识别为弱证据并降权，只保留 issue 正文和真正的复现/代码/文档 URL。


完整 issue 原文：

````text
[Original Issue]
Please fix formatting months in russian
<!-- Issuehunt Badges -->
[<img alt="Issuehunt badges" src="https://img.shields.io/badge/IssueHunt-%2450%20Rewarded-%237E24E3.svg" />](https://issuehunt.io/r/iamkun/dayjs/issues/577)
<!-- /Issuehunt Badges -->


**Describe the bug**
Long description of months (MMMM) are showing not correctly.

**Expected behavior**
I created comparison, so you can see what it should look like. Also I've included possible fix (different months field in object fixedRuLocale) - https://runkit.com/bagmutva/5cbc390d7da00600130f419c
For now in my work project we're using dayjs and moment. Unfortunately because of this bug we using moment for formatting long dates. But we want to use only one library - dayjs. So please fix this.

**Information**
 - Day.js Version 1.8.12
 - OS: MacOS Mojave 10.14.4
 - Browser: Google Chrome 73.0.3683.86


<!-- Issuehunt content -->

---

<details>
<summary>
<b>IssueHunt Summary</b>
</summary>

#### [<img src='https://avatars0.githubusercontent.com/u/17680888?v=4' alt='iamkun' width=24 height=24> iamkun](https://issuehunt.io/u/iamkun) has been rewarded.

### Backers (Total: $50.00)

- [<img src='https://avatars3.githubusercontent.com/u/44827199?v=4' alt='issuehunt' width=24 height=24> issuehunt](https://issuehunt.io/u/issuehunt) ($50.00)
### Submitted pull Requests
- [#581 fix: Update locale month to support both array and function](https://issuehunt.io/r/iamkun/dayjs/pull/581)
---

### Tips

- Checkout the [Issuehunt explorer](https://issuehunt.io/r/iamkun/dayjs/) to discover more funded issues.
- Need some help from other developers? [Add your repositories](https://issuehunt.io/r/new) on IssueHunt to raise funds.
---
IssueHunt has been backed by the following sponsors. [Become a sponsor](https://issuehunt.io/membership/members)
</details>
<!-- /Issuehunt content-->

[Multimodal Context - Compact]
[Visual Evidence] Image 1: https://img.shields.io/badge/IssueHunt-%2450%20Rewarded-%237E24E3.svg Visual processing failed; use the URL and issue text only. Error: HTTP Error 400: Bad Request [Web Evidence] URL 1: https://avatars0.githubusercontent.com/u/17680888?v=4 Web processing failed; use URL only. Error: unsupported content-type: image/png URL 2: https://avatars3.githubusercontent.com/u/44827199?v=4 Web processing failed; use URL only. Error: unsupported content-type: image/png URL 3: https://issuehunt.io/membership/members Summary: Issuehunt Vulnerability Disclosure and Bounty Programs Issuehunt Vulnerability Disclosure and Bounty Programs You need to enable JavaScript to run this app. URL 4: https://issuehunt.io/r/iamkun/dayjs/ Summary: iamkun/dayjs (Raised $1,326.00) - Issuehunt IssueHunt 🦉 = OSS Development ⚒ + Bounty Program 💰. IssueHunt is an issue-based bounty platform for open source projects. Anyone can put a bounty on not only a bug but also on OSS feature requests listed on IssueHunt. Collected funds will be distributed to project owners and contributors. iamkun/dayjs (Raised $1,326.00) - Issuehunt IssueHunt Bug Bounty ( New! ) Browse Sign in with GitHub ← Back iamkun / dayjs ⏰ Day.js 2KB immutable date library alternative to Moment.js with the same modern API Owners: Follow $ 1,326.00 USD raised Recent activities iamkun cancelled funding $ 1.00 for iamkun/ dayjs#865 about 6 years ago iamkun was rewarded for iam... URL 5: https://issuehunt.io/r/iamkun/dayjs/issues/577 Summary: Issuehunt IssueHunt 🦉 = OSS Development ⚒ + Bounty Program 💰. IssueHunt is an issue-based bounty platform for open source projects. Anyone can put a bounty on not only a bug but also on OSS feature requests listed on IssueHunt. Collected funds will be distributed to project owners and contributors. Issuehunt IssueHunt Bug Bounty ( New! ) Browse Sign in with GitHub iamkun / dayjs The issue has been solved Please fix formatting months in russian # 577 VBagmut posted on GitHub Loading interface... Update comments Loading interface... Loading interface... Loading interface... Loading interface... Fund this Issue $ 50.00 Rewarded issuehunt ( 32,559 ) $ 50.00 Rewarded pull request fix: Update l... URL 6: https://issuehunt.io/r/iamkun/dayjs/pull/581 Skipped detailed fetch: Possible patch/PR/commit link; kept as URL only to avoid answer leakage. URL 7: https://issuehunt.io/r/new Summary: Issuehunt IssueHunt 🦉 = OSS Development ⚒ + Bounty Program 💰. IssueHunt is an issue-ba...

[Adapter Note]
Use the multimodal context only as auxiliary evidence for code localization.
````

### 5.10 iamkun__dayjs-1101：运行时/控制台/表格输出

- 数据来源：OmniGIRL full-candidates

- Repo：`iamkun/dayjs`

- 主语言：`JavaScript`

- Issue 标题/首行：wrong day in my timezone (UTC+3)

- 图片核对：PNG, 594 x 287；人工核对为 JavaScript 测试失败输出，展示 UTC 日期期望值和实际值。

- 图片 URL 数：1；网页 URL 数：0；Gold 文件数：2


图片 URL：

- https://user-images.githubusercontent.com/130606/94871507-d0b0a900-0452-11eb-8cbf-2d72c9ea184f.png

Gold 文件：

- `src/plugin/localeData/index.js`
- `src/plugin/localizedFormat/index.js`

定位解释：


这类图片主要提供错误输出或运行结果，应优先抽取可搜索文本、数值、expected/actual、文件名、类名和配置。


完整 issue 原文：

````text
[Original Issue]
wrong day in my timezone (UTC+3)
**Describe the bug**
I noticed a utc test failing after midnight at my timezone.

**Expected behavior**
Run tests.

**Information**
 - Day.js dev branch
 - OS: macos
 - Node v14.11.0
 - Time zone:(UTC+3)

![Screenshot 2020-10-02 at 1 55 43](https://user-images.githubusercontent.com/130606/94871507-d0b0a900-0452-11eb-8cbf-2d72c9ea184f.png)

```
 FAIL  test/plugin/objectSupport.test.js
  ● Constructor from Object UTC

    expect(received).toBe(expected) // Object.is equality
    
    Expected value to be:
      "2020-10-02 15:25:50.125"
    Received:
      "2020-10-01 15:25:50.125"

      121 |   for (let i = 0; i < tests.length; i += 1) {
      122 |     expect(dayjs.utc(tests[i][0]).format(fmt)).toBe(tests[i][1])
    > 123 |     expect(moment.utc(tests[i][0]).format(fmt)).toBe(tests[i][1])
      124 |   }
      125 | })
      126 | it('Set from Object', () => {
      
      at Object.<anonymous> (test/plugin/objectSupport.test.js:123:49)


Test Suites: 1 failed, 58 passed, 59 total
Tests:       1 failed, 569 passed, 570 total
Snapshots:   0 total
Time:        3.982s
Ran all test suites.
```

[Multimodal Context - Compact]
[Visual Evidence] Image 1: https://user-images.githubusercontent.com/130606/94871507-d0b0a900-0452-11eb-8cbf-2d72c9ea184f.png **Raw Visual Description** A test failure in `test/plugin/objectSupport.test.js` shows `dayjs.utc()` and `moment.utc()` both returning `"2020-10-01 15:25:50.125"` instead of the expected `"2020-10-02 15:25:50.125"`. The test runs in UTC+3 timezone, and the failure occurs at line 123. The test compares parsed UTC timestamps against expected strings. **Issue-Relevant Analysis** The test expects UTC-aware parsing to correctly interpret a timestamp (likely from a local time zone) as UTC, but `dayjs.utc()` is producing a date one day earlier than expected. This suggests a timezone or parsing bug in `dayjs` when handling timestamps that cross midnight in a non-UTC timezone. **Localization Clues** - Test file: `test/plugin/objectSupport.test.js` - Line: 123 - Function: `dayjs.utc()` - Expected: `"2020-10-02 15:25:50.125"` - Actual: `"2020-10-01 15:25:50.125"` - Context: Timezone UTC+3, test runs in local time.

[Adapter Note]
Use the multimodal context only as auxiliary evidence for code localization.
````

### 5.11 statsmodels__statsmodels-7748：运行时/控制台/表格输出

- 数据来源：OmniGIRL full-candidates

- Repo：`statsmodels/statsmodels`

- 主语言：`Python`

- Issue 标题/首行：summary.as_latex() output missing 1 row

- 图片核对：PNG, 670 x 317；人工核对为 statsmodels summary/LaTeX 表格输出截图。

- 图片 URL 数：2；网页 URL 数：0；Gold 文件数：1


图片 URL：

- https://github.com/BecksIsAlreadyTaken/Troubleshooting/blob/main/Screenshot%20from%202021-09-23%2023-31-14.png
- https://github.com/BecksIsAlreadyTaken/Troubleshooting/blob/main/Screenshot%20from%202021-09-23%2023-31-35.png

Gold 文件：

- `statsmodels/iolib/summary.py`

定位解释：


这类图片主要提供错误输出或运行结果，应优先抽取可搜索文本、数值、expected/actual、文件名、类名和配置。


完整 issue 原文：

````text
[Original Issue]
summary.as_latex() output missing 1 row
#### Describe the bug

i compared the console output summary() and summary.as_latex(), found that the last row of result table gone missing.

#### Code Sample, a copy-pastable example if possible


```python
print(logit.summary().as_latex())
print(logit.summary())
```
<details>

**Note**: As you can see, there are many issues on our GitHub tracker, so it is very possible that your issue has been posted before. Please check first before submitting so that we do not have to handle and close duplicates.

**Note**: Please be sure you are using the latest released version of `statsmodels`, or a recent build of `main`. If your problem has been fixed in an unreleased version, you might be able to use `main` until a new release occurs. 

**Note**: If you are using a released version, have you verified that the bug exists in the main branch of this repository? It helps the limited resources if we know problems exist in the current main branch so that they do not need to check whether the code sample produces a bug in the next release.

[summary() output](https://github.com/BecksIsAlreadyTaken/Troubleshooting/blob/main/Screenshot%20from%202021-09-23%2023-31-14.png)

[summary().as_latex() output](https://github.com/BecksIsAlreadyTaken/Troubleshooting/blob/main/Screenshot%20from%202021-09-23%2023-31-35.png)

Here the row containing "Covariance Type:" and "LLR p-value" went missing.
</details>


If the issue has not been resolved, please file it in the issue tracker.

#### Expected Output

A full result table.

#### Output of ``import statsmodels.api as sm; sm.show_versions()``

<details>

[paste the output of ``import statsmodels.api as sm; sm.show_versions()`` here below this line]
INSTALLED VERSIONS
------------------
Python: 3.9.0.final.0
OS: Linux 5.4.0-86-generic #97-Ubuntu SMP Fri Sep 17 19:19:40 UTC 2021 x86_64
byteorder: little
LC_ALL: None
LANG: en_US.UTF-8

statsmodels
===========

Installed: 0.12.2 (/home/beck/anaconda3/envs/main/lib/python3.9/site-packages/statsmodels)

Required Dependencies
=====================

cython: Not installed
numpy: 1.21.2 (/home/beck/anaconda3/envs/main/lib/python3.9/site-packages/numpy)
scipy: 1.7.1 (/home/beck/anaconda3/envs/main/lib/python3.9/site-packages/scipy)
pandas: 1.3.3 (/home/beck/anaconda3/envs/main/lib/python3.9/site-packages/pandas)
    dateutil: 2.8.2 (/home/beck/anaconda3/envs/main/lib/python3.9/site-packages/dateutil)
patsy: 0.5.1 (/home/beck/anaconda3/envs/main/lib/python3.9/site-packages/patsy)

Optional Dependencies
=====================

matplotlib: 3.4.3 (/home/beck/anaconda3/envs/main/lib/python3.9/site-packages/matplotlib)
    backend: TkAgg 
cvxopt: Not installed
joblib: 1.0.1 (/home/beck/anaconda3/envs/main/lib/python3.9/site-packages/joblib)

Developer Tools
================

IPython: Not installed
    jinja2: Not installed
sphinx: Not installed
    pygments: Not installed
pytest: Not installed
virtualenv: Not installed

</details>

[Multimodal Context - Compact]
[Visual Evidence] Image 1: https://github.com/BecksIsAlreadyTaken/Troubleshooting/blob/main/Screenshot%20from%202021-09-23%2023-31-14.png Visual processing failed; use the URL and issue text only. Error: HTTP Error 400: Bad Request Image 2: https://github.com/BecksIsAlreadyTaken/Troubleshooting/blob/main/Screenshot%20from%202021-09-23%2023-31-35.png Visual processing failed; use the URL and issue text only. Error: HTTP Error 400: Bad Request

[Adapter Note]
Use the multimodal context only as auxiliary evidence for code localization.
````

### 5.12 webpack__webpack-14782：运行时/控制台/表格输出

- 数据来源：OmniGIRL full-candidates

- Repo：`webpack/webpack`

- 主语言：`JavaScript`

- Issue 标题/首行：Module Federation deps strictVersion mismatch source in error message

- 图片核对：PNG, 2479 x 773；人工核对为 webpack bundle/error 信息中的模块联邦版本检查片段。

- 图片 URL 数：1；网页 URL 数：0；Gold 文件数：1


图片 URL：

- https://user-images.githubusercontent.com/1610882/112955615-4a96c600-9148-11eb-8d8d-7aa08ed995ac.png

Gold 文件：

- `lib/sharing/ConsumeSharedRuntimeModule.js`

定位解释：


这类图片主要提供错误输出或运行结果，应优先抽取可搜索文本、数值、expected/actual、文件名、类名和配置。


完整 issue 原文：

````text
[Original Issue]
Module Federation deps strictVersion mismatch source in error message
<!-- Please don't delete this template or we'll close your issue -->

## Feature request

<!-- Issues that contain questions or support requests will be closed. -->
<!-- Before creating an issue please make sure you are using the latest version of webpack. -->
<!-- Check if this feature needs to be implemented in a plugin or loader instead -->
<!-- If yes: file the issue on the plugin/loader repo -->
<!-- Features related to the development server should be filed on this repo instead -->

**What is the expected behavior?**
`getStrictSingletonVersion` throws more detailed error.
Also will be great get all errors at once (not one per step)

This dramatically decrease spent time on module federation integration process.


**What is motivation or use case for adding/changing the behavior?**
Adding module federation to huge porject i'm facing following problem:
I'm unable do determine package, which declare mismatched strict version dependency, because only clue i've get is 
```
Unsatisfied version 11.0.3 of shared singleton module @angular/core (required ^10.0.0)
```

Digging deeper i've found this (but it still don't help me):
![image](https://user-images.githubusercontent.com/1610882/112955615-4a96c600-9148-11eb-8d8d-7aa08ed995ac.png)
There are is a lot of older angular dependencies version, but - i can't determine which package bring them there.

**How should this be implemented in your opinion?**

This:
```
Unsatisfied version 11.0.3 of shared singleton module @angular/core (required ^10.0.0)
```

Will be good to expanded to this:
```
Unsatisfied versions detected:
@angular/core (current 11.0.3)
   10.0.0 (by @ngrx/core)
   6.0.3 (by ngx-quicklinks)
```
**Are you willing to work on this yourself?**
I'm not sure i can handle it, but i can try, if you give me few design clues.

[Multimodal Context - Compact]
[Visual Evidence] Image 1: https://user-images.githubusercontent.com/1610882/112955615-4a96c600-9148-11eb-8d8d-7aa08ed995ac.png Visual processing failed; use the URL and issue text only. Error: HTTP Error 500: Internal Server Error

[Adapter Note]
Use the multimodal context only as auxiliary evidence for code localization.
````

### 5.13 tqdm__tqdm-1040：动图/交互行为演示

- 数据来源：OmniGIRL full-candidates

- Repo：`tqdm/tqdm`

- 主语言：`Python`

- Issue 标题/首行：Colored Progress Bars

- 图片核对：GIF, 1192 x 600；人工核对为 tqdm 彩色进度条行为演示动图。

- 图片 URL 数：1；网页 URL 数：0；Gold 文件数：2


图片 URL：

- https://user-images.githubusercontent.com/17583740/30978247-5925ad1e-a450-11e7-9f05-7ea07a46413b.gif

Gold 文件：

- `tqdm/notebook.py`
- `tqdm/std.py`

定位解释：


这类图片表达时间过程。定位时应抽取动态行为描述，例如刷新、进度条、多进程显示、宽字符对齐，而不是只看首帧。


完整 issue 原文：

````text
[Original Issue]
Colored Progress Bars
With a few tweaks in the code I managed to add a color argument to tqdm.

![newgif1](https://user-images.githubusercontent.com/17583740/30978247-5925ad1e-a450-11e7-9f05-7ea07a46413b.gif)

Is this already an implemented feature ? Anyone likes it ?

[Multimodal Context - Compact]
[Visual Evidence] Image 1: https://user-images.githubusercontent.com/17583740/30978247-5925ad1e-a450-11e7-9f05-7ea07a46413b.gif Visual processing failed; use the URL and issue text only. Error: HTTP Error 500: Internal Server Error

[Adapter Note]
Use the multimodal context only as auxiliary evidence for code localization.
````

## 6. 对多模态 Agent 的直接要求

1. **先做图片角色识别，再做检索。** 图片 URL 需要先分类成 UI、图表、错误输出、Playground、弱徽章等角色，不能统一当普通文本 URL。

2. **强文本图片要 OCR/结构化。** IDE diff、Babel 报错、Tailwind playground、statsmodels 表格输出都含有可直接检索的文本；如果不 OCR，会丢掉最强证据。

3. **视觉症状要映射到代码概念。** Chart.js 的饼图截图要变成 `doughnut/pie + legend + arc/layout`；react-pdf 的边框截图要变成 `border/padding/view/style/layout`。

4. **弱图片必须降权。** IssueHunt badge、头像、奖励图是 image URL 但不是定位证据。它们应该进入 evidence blacklist 或 low-confidence pool。

5. **图片与 URL 需要联合解释。** Playground URL 往往包含可复现代码和配置，图片只是输出结果；GitHub code URL 可能只是 evidence seed。Agent 应区分 evidence、repro、target 三种角色。


## 7. 后续建议

- 为每个样本生成 `visual_evidence.json`：保存图片角色、OCR 文本、可见 UI/图表/错误元素、证据强度。

- 在检索前生成多路 query：`issue_text_query`、`visual_symptom_query`、`url_repro_query`、`symbol_query`。不同图片类型使用不同模板。

- 在 rerank 阶段加入证据一致性检查：候选文件是否能解释图片中出现的 UI 状态、错误类型、图表元素或 playground 配置。
