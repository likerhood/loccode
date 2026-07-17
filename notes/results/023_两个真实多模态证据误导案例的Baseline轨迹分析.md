# 两个真实多模态证据误导案例的 Baseline 轨迹分析

本文整理两个已经核对过的 SWE-bench Multimodal Clean15 案例，重点分析图片、URL、issue 文本如何影响定位，以及各 baseline 为什么会被带到错误层级。

数据来源：

- 样本原始数据：`GraphLocator/datasets/swebench_multimodal_full_dev.jsonl`
- Mimo-v2.5 SWE 全量结果解压目录：`unpacked_results/swefull_results_mimov2.5/swebench_multimodal_full_dev_mimo-v2.5_20260712_152753/repo`
- BM25-MMIR 结果：`MM-IR/results/swebench_multimodal-full-candidates/bm25-mmir`
- 评估口径：`eval_strict_clean15/per_instance_metrics_3level.csv`

需要先说明：这两个案例不是凭直觉编写，而是直接根据本地样本、真实 gold patch、真实预测文件和逐样本评估结果核对后整理。

## 1. 案例一：Reader Edit 链接错误，真实修复在 URL 生成函数

### 1.1 样本基本信息

样本：

```text
Automattic__wp-calypso-23915
```

仓库：

```text
Automattic/wp-calypso
```

Issue 标题：

```text
Reader: Broken Edit link in Reader for my own posts on Jetpack sites
```

用户复现步骤：

```text
1. Starting at URL: https://wordpress.com/read/list/goldsounds/amptest
2. Click on a post, e.g. https://wordpress.com/read/feeds/76552105/posts/1804969891
3. Notice Edit link below post; click it
4. Page enters a weird state where the top and side bars disappear,
   but the reader content is still displayed and we don't enter "edit" mode fully
```

多模态证据：

```text
图片：
https://user-images.githubusercontent.com/51896/37911883-0e6ddc30-30c6-11e8-8bb5-a28724d7945e.png

视频：
https://cloudup.com/cGHsI-1AaD8

运行 URL：
https://wordpress.com/read/list/goldsounds/amptest
https://wordpress.com/read/feeds/76552105/posts/1804969891
```

图片内容是 WordPress.com Reader 页面，文章下方有 `Edit / Share / Like` 三个操作按钮，红色箭头指向 `Edit` 按钮。图片证明的是：用户是在 Reader 页面点击 `Edit`，而不是在 post editor 页面内操作。

### 1.2 Issue 的关键语义

这个 issue 表面看起来像 UI 按钮或 Reader 页面跳转问题，但 `hints_text` 里给出了真正关键线索：

```text
I noticed that the URL for that Edit link in your video is this format:
https://wordpress.com/edit/{SITE_ADDRESS}/{POST_ID}

However, it should be:
https://wordpress.com/post/{SITE_ADDRESS}/{POST_ID}
(with post instead of edit in the URL).
```

所以问题不是 `Edit` 按钮没有显示，也不是 Reader 页面布局坏了，而是：

```text
Edit 按钮生成出来的 href/URL 路径错了。
```

错误 URL：

```text
https://wordpress.com/edit/{SITE_ADDRESS}/{POST_ID}
```

正确 URL：

```text
https://wordpress.com/post/{SITE_ADDRESS}/{POST_ID}
```

也就是说，真实定位目标应该从 `Reader UI` 继续追踪到：

```text
Edit button
  -> edit URL
  -> URL builder
  -> post.type
  -> default post type
```

### 1.3 真实 gold patch

真实修改文件只有一个：

```text
client/lib/posts/utils.js
```

真实修改函数：

```text
client/lib/posts/utils.js::getEditURL
```

真实 patch：

```diff
export const getEditURL = function( post, site ) {
 	let basePath = '';
+	const postType = post.type || 'post';
 
-	if ( ! includes( [ 'post', 'page' ], post.type ) ) {
+	if ( ! includes( [ 'post', 'page' ], postType ) ) {
 		basePath = '/edit';
 	}
 
-	return `${ basePath }/${ post.type }/${ site.slug }/${ post.ID }`;
+	return `${ basePath }/${ postType }/${ site.slug }/${ post.ID }`;
};
```

修复逻辑是：当 `post.type` 为空或缺失时，默认当成普通文章 `post`。

旧逻辑：

```js
post.type === ''
includes( [ 'post', 'page' ], post.type ) === false
basePath = '/edit'
return `/edit/${ post.type }/${ site.slug }/${ post.ID }`
```

新逻辑：

```js
const postType = post.type || 'post'
includes( [ 'post', 'page' ], postType ) === true
basePath = ''
return `/post/${ site.slug }/${ post.ID }`
```

测试补丁也验证了这一点：

```js
test( 'should default to type=post if no post type is supplied', () => {
	const url = postUtils.getEditURL(
		{ ID: 123, type: '' },
		{ slug: 'en.blog.wordpress.com' }
	);
	expect( url ).toEqual( '/post/en.blog.wordpress.com/123' );
} );
```

### 1.4 Mimo-v2.5 Clean15 下的实际 baseline 结果

| Baseline | file_acc@15 | file_rec@all | module_rec@all | function_rec@all | 预测情况 |
|---|---:|---:|---:|---:|---|
| LocAgent | 1.00 | 1.00 | 命中 | 命中 | 第 2 位命中 `client/lib/posts/utils.js::getEditURL` |
| CoSIL | 0.00 | 0.00 | 0.00 | 0.00 | 停在 post edit button / reader actions / route |
| GraphLocator | 0.00 | 0.00 | 0.00 | 0.00 | 偏到 post type list 的 edit/share/view 菜单 |
| GALA | 0.00 | 0.00 | 0.00 | 0.00 | 偏到 layout focus、reader controller、post editor controller |
| BM25-MMIR | 0.00 | 0.00 | 0.00 | 0.00 | 偏到 media、sharing、guided tours 等词法相关文件 |

LocAgent 的真实预测：

```text
client/blocks/post-edit-button/index.jsx
client/lib/posts/utils.js
client/blocks/reader-post-actions/index.jsx
client/blocks/reader-full-post/index.jsx
client/my-sites/post-type-list/post-actions-ellipsis-menu/edit.jsx
```

LocAgent 的最终定位输出中包含真实函数：

```text
client/lib/posts/utils.js
function: getEditURL
line: 16-24
```

CoSIL 的真实预测：

```text
client/blocks/post-edit-button/index.jsx
client/blocks/reader-post-actions/index.jsx
client/blocks/reader-full-post/index.jsx
client/lib/route/index.js
client/state/reader/posts/actions.js
```

GraphLocator 的真实预测：

```text
client/my-sites/post-type-list/bulk-edit-bar.jsx
client/my-sites/post-type-list/post-actions-ellipsis-menu/edit.jsx
client/my-sites/post-type-list/post-actions-ellipsis-menu/share.jsx
client/my-sites/post-type-list/post-actions-ellipsis-menu/view.jsx
client/my-sites/site-settings/jetpack-dev-mode-notice.jsx
```

GALA 的真实预测：

```text
client/state/ui/layout-focus/actions.js
client/layout/index.jsx
client/blocks/reader-post-actions/index.jsx
client/reader/controller.js
client/post-editor/controller.js
```

BM25-MMIR 的真实预测：

```text
client/components/tinymce/plugins/media/plugin.jsx
client/my-sites/sharing/connections/service-examples.jsx
client/components/tinymce/i18n.js
assets/stylesheets/shared/functions/_z-index.scss
client/layout/guided-tours/tours/checklist-publish-post-tour.js
```

### 1.5 失败原因分析

这个样本的多模态证据强烈指向 `Reader UI`：

- 图片：Reader 页面里的 `Edit` 按钮；
- URL：`/read/list/...` 和 `/read/feeds/.../posts/...`；
- 文本：`Reader`、`Edit link`、`top and side bars disappear`。

因此，大多数 baseline 会优先搜索：

```text
reader action
reader full post
post edit button
post editor controller
layout focus
```

但真实修复点不是“按钮在哪里渲染”，而是“按钮跳转 URL 如何生成”。这个样本要求 agent 继续追踪行为链：

```text
Reader post page
  -> Edit link element
  -> href / target URL
  -> post metadata
  -> getEditURL(post, site)
  -> post.type 缺失时应默认为 post
```

LocAgent 之所以能命中，是因为它最终把 `Edit link` 和 `URL` 线索推进到了 `getEditURL`。但 CoSIL、GraphLocator、GALA、BM25 都停在 UI/action/route 层。

### 1.6 对方法设计的启发

这个案例适合归类为：

```text
外部运行 URL + 截图指向用户行为入口，真实修复在内部 URL builder / dataflow。
```

agent 不应该把 URL 和截图直接转成目标文件，而应该先标注证据角色：

| 证据 | 角色 | 应该如何使用 |
|---|---|---|
| Reader 页面截图 | UI symptom | 定位用户点击的是哪个 action |
| `/read/list/...` | route evidence | 识别入口页面和产品模块 |
| `/read/feeds/.../posts/...` | route/data evidence | 识别 post 对象和 Reader feed |
| `https://wordpress.com/edit/{SITE}/{POST_ID}` | wrong generated URL | 追踪 URL builder |
| `https://wordpress.com/post/{SITE}/{POST_ID}` | expected URL | 推断 `post.type` 应为 `post` |

因此，框架需要支持：

```text
用户层复现步骤
  -> UI action
  -> 运行时 URL
  -> URL builder
  -> 数据字段归一化
  -> patch target
```

## 2. 案例二：`margin: auto` 视觉 diff，真实修复在 stylesheet 语义层

### 2.1 样本基本信息

样本：

```text
diegomura__react-pdf-1178
```

仓库：

```text
diegomura/react-pdf
```

Issue 标题：

```text
margin auto is broken in v2
```

Issue 原文核心内容：

```text
Run a some snapshot tests with react-pdf examples for v1/v2
and seems like margin auto doesn't work
```

多模态证据：

```text
示例 URL：
https://github.com/diegomura/react-pdf/blob/master/packages/examples/src/knobs/
https://github.com/diegomura/react-pdf/blob/master/packages/examples/src/knobs/index.js#L20

图片：
https://user-images.githubusercontent.com/6726016/113850039-b8736b00-97a2-11eb-857d-50470f1d52c2.png
```

图片内容是 v1 和 v2 的渲染 diff：左侧 v1 间距正常，v2 的进度条挤在一起，说明 `margin: auto` 没有产生正确布局效果。

### 2.2 URL 和图片真正表达的含义

这个样本里，URL 指向：

```text
packages/examples/src/knobs/index.js
```

但它只是复现 example，不是修复文件。它的作用是告诉 agent：

```text
这个例子里有 margin auto 的复现输入。
```

图片的作用也不是直接告诉 agent 去改 renderer，而是说明：

```text
视觉症状 = margin auto 布局语义没有生效。
```

所以正确推理应该是：

```text
margin: auto 失效
  -> CSS-like style semantic bug
  -> style shorthand / box model expansion
  -> stylesheet resolve pipeline
  -> packages/stylesheet/src/expand.js
  -> packages/stylesheet/src/resolve.js
```

而不是：

```text
图片有渲染差异
  -> renderer
  -> image
  -> yoga
```

也不是：

```text
URL 指向 example
  -> packages/examples/src/knobs/index.js
```

### 2.3 真实 gold patch

真实修改文件：

```text
packages/stylesheet/src/expand.js
packages/stylesheet/src/resolve.js
```

真实修改函数：

```text
packages/stylesheet/src/expand.js::processBoxModel
packages/stylesheet/src/resolve.js::resolveStyles
```

关键 patch 在 `expand.js`：

```diff
const processBoxModel = (key, value) => {
+  if (value === 'auto') return value;
+
  const match = matchBoxModel(value);
```

这表示：如果 box model 相关属性值是 `'auto'`，不要继续当成普通数值或 shorthand 去解析，而是直接保留。

`resolve.js` 的 patch 是删除调试注释：

```diff
-    // R.tap(console.log),
```

从行为角度看，关键修复是 `expand.js` 的 `processBoxModel`；但评估会把 patch 涉及的 `resolve.js::resolveStyles` 也算作 gold function。

测试补丁直接说明修复目标：

```js
test('should keep auto margins', () => {
  const top = expandStyles({ marginTop: 'auto' });
  const right = expandStyles({ marginRight: 'auto' });
  const bottom = expandStyles({ marginBottom: 'auto' });
  const left = expandStyles({ marginLeft: 'auto' });

  expect(top.marginTop).toBe('auto');
  expect(right.marginRight).toBe('auto');
  expect(bottom.marginBottom).toBe('auto');
  expect(left.marginLeft).toBe('auto');
});
```

以及：

```js
test('should transform margin auto shortcut correctly', () => {
  const styles = resolve({}, { margin: 'auto' });

  expect(styles).toEqual({
    marginRight: 'auto',
    marginLeft: 'auto',
    marginTop: 'auto',
    marginBottom: 'auto',
  });
});
```

### 2.4 Mimo-v2.5 Clean15 下的实际 baseline 结果

| Baseline | file_acc@15 | file_rec@all | module_rec@all | function_rec@all | 预测情况 |
|---|---:|---:|---:|---:|---|
| LocAgent | 0.00 | 0.50 | 0.50 | 0.50 | 命中 `expand.js`，但漏掉 `resolve.js` |
| CoSIL | 0.00 | 0.00 | 0.00 | 0.00 | 偏到 layout steps 和 URL utils |
| GraphLocator | 0.00 | 0.00 | 0.00 | 0.00 | 偏到 examples、image、renderer、yoga |
| GALA | 0.00 | 0.00 | 0.00 | 0.00 | 偏到 layout node margin setter |
| BM25-MMIR | 0.00 | 0.00 | 0.50 | 0.00 | 命中部分 module 语义，但没有命中源码文件 |

LocAgent 的真实预测：

```text
packages/examples/src/knobs/index.js
packages/stylesheet/src/expand.js
packages/layout/src/node/setYogaValue.js
```

CoSIL 的真实预测：

```text
packages/layout/src/node/splitNode.js
packages/layout/src/steps/resolveOrigins.js
packages/layout/src/steps/resolveSvg.js
packages/layout/src/utils/url.js
```

GraphLocator 的真实预测：

```text
packages/examples/src
packages/image/src/index.js
packages/image/src/png.js
packages/image/tests/cache.test.js
packages/image/tests/resolve.test.js
packages/primitives/tests/index.test.js
packages/renderer/tests/node.test.js
packages/yoga/tests/index.test.js
packages/renderer/src/index.js
packages/font/src/index.js
```

GALA 的真实预测：

```text
packages/layout/src/node/setMargin.js
packages/layout/src/node/getMargin.js
packages/layout/src/steps/resolveStyles.js
packages/layout/src/node/setDimension.js
packages/layout/src/node/getDimension.js
```

BM25-MMIR 的真实预测：

```text
packages/renderer/index.d.ts
github/no-response.yml
packages/renderer/src/dom.js
packages/renderer/src/node.js
packages/renderer/package.json
packages/yoga/package.json
package.json
packages/image/tests/resolve.test.js
packages/stylesheet/tests/resolve.test.js
```

### 2.5 失败原因分析

这个样本的主要误导来自两个地方。

第一，URL 指向 example：

```text
packages/examples/src/knobs/index.js
```

很多方法会把这个复现文件当成强目标，优先搜索 example 目录。但 example 只是触发 bug 的输入，不是 bug 的实现位置。

第二，图片是渲染 diff：

```text
v1 正常
v2 间距/布局错误
```

这会诱导模型去找：

```text
renderer
layout
yoga
image
font
node margin setter
```

但真实修复点在更早的样式语义层：

```text
stylesheet expand / resolve
```

这说明 agent 不能只把图片转成“渲染错误”，而应该进一步识别视觉症状对应的语义类型：

```text
margin auto 失效
  -> box model shorthand / auto value preservation
  -> stylesheet expansion
```

GALA 的失败尤其有代表性。它找到了：

```text
packages/layout/src/node/setMargin.js
packages/layout/src/node/getMargin.js
```

这说明它确实理解到问题和 `margin` 有关，但它停在 layout node setter，没有继续向上游追踪：

```text
margin 值从哪里来？
margin: auto 在进入 layout 前是否已经被 stylesheet 层处理坏了？
```

LocAgent 只命中一半 gold，也说明它能从 `margin auto` 推到 `expand.js`，但没有完整覆盖 `resolve.js`。

### 2.6 对方法设计的启发

这个案例适合归类为：

```text
复现 URL + 视觉 diff 指向表层现象，真实修复在底层语义转换层。
```

对于 PDF/layout/renderer 类样本，agent 需要先做症状归类：

| 视觉/文本症状 | 应优先映射的语义层 |
|---|---|
| `margin: auto`、`padding`、box model | stylesheet expand / resolve |
| `px`、`pt`、百分比、单位异常 | unit transform |
| flex、wrap、stretch、basis | layout engine / yoga interface |
| color alpha、hex、rgb | color transform |
| text wrapping、line height | text layout / font measurement |
| image missing、jpeg/png | image resolver / renderer |

对这个样本，合理的搜索优先级应该是：

```text
packages/stylesheet/src/expand.js
packages/stylesheet/src/resolve.js
packages/layout/src/steps/resolveStyles.js
packages/layout/src/node/setMargin.js
packages/examples/src/knobs/index.js
```

而不是把 `examples` 或 `renderer` 放到最前。

## 3. 两个案例的共同结论

这两个案例共同说明：多模态证据通常不是直接 patch target，而是不同角色的 evidence。

| 案例 | 图片/URL 表面指向 | 真实修复层 | 常见误判 |
|---|---|---|---|
| `Automattic__wp-calypso-23915` | Reader 页面、Edit 按钮、运行 URL | URL builder / post type normalization | 停在 Reader UI、post editor、layout focus |
| `diegomura__react-pdf-1178` | example URL、渲染 diff | stylesheet expand / resolve | 停在 examples、renderer、layout node、yoga |

这说明多模态定位框架需要先判断证据角色：

```text
图片 = symptom evidence
运行 URL = route/reproduction evidence
GitHub example URL = reproduction code evidence
错误 URL = generated-output evidence
真实 patch = internal semantic layer
```

然后再做从证据到代码的推理链：

```text
Evidence
  -> behavior / semantic abstraction
  -> internal pipeline stage
  -> candidate file/function
```

如果直接把图片描述和 URL 文本投入普通检索，baseline 很容易被带到表层文件：

```text
UI component
example file
renderer
route controller
```

而真正需要的是进一步追踪：

```text
UI action -> URL builder -> data normalization
visual layout symptom -> stylesheet semantic transform -> layout engine
```

这也是后续框架创新可以重点强调的地方：**多模态信息不是简单增加输入，而是需要被解析成不同角色的 evidence，并连接到仓库内部的语义处理链。**
