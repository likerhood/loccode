# python__mypy-13481 删除类变量状态流定位失败分析

本文专门分析 OmniGIRL 中的 Python/mypy 样本 `python__mypy-13481`。这个样本非常适合说明：对于类型检查器、编译器、静态分析器这类仓库，定位不能只依赖错误文本、函数调用图或普通词法检索，而需要理解语言语义节点、声明类型、控制流状态和错误报告之间的关系。

分析只使用本地真实数据和结果，不补不存在的轨迹。

数据来源：

- 样本原始数据：`GraphLocator/datasets/omnigirl_full_candidates.jsonl`
- Qwen3-VL-8B / OmniGIRL full-candidates 结果：
  - `LocAgent/newtest/omnigirl-full-candidates/results/openai_qwen3-vl-8b/location/loc_outputs.jsonl`
  - `LocAgent/newtest/omnigirl-full-candidates/results/openai_qwen3-vl-8b/location/loc_trajs.jsonl`
  - `CoSIL/newtest/omnigirl-full-candidates/results/openai_qwen3-vl-8b/file_level/loc_outputs.jsonl`
  - `CoSIL/newtest/omnigirl-full-candidates/results/openai_qwen3-vl-8b/file_level/localization_logs/python__mypy-13481.log`
  - `MM-IR/results/omnigirl-full-candidates/bm25-mmir/loc_results.json`
- Qwen3-VL-8B / OmniGIRL unified60 结果：
  - `LocAgent/newtest/omnigirl-unified60/results/openai_qwen3-vl-8b/location/loc_outputs.jsonl`
  - `LocAgent/newtest/omnigirl-unified60/results/openai_qwen3-vl-8b/location/loc_trajs.jsonl`
  - `CoSIL/newtest/omnigirl-unified60/results/openai_qwen3-vl-8b/file_level/loc_outputs.jsonl`
  - `GraphLocator/newtest/omnigirl-unified60/results/openai_qwen3-vl-8b/loc_results.json`
  - `GALA/mytest/omnigirl-unified60/results/qwen3-vl-8b/loc_results.json`
- Mimo-v2.5 server Omni60 结果解压目录：
  - `unpacked_results/omnigirl_unified60_mimo-v2.5_20260716_155146/...`

需要说明：本地 Mimo-v2.5 逐样本评估 CSV 中能看到该样本的评估项，但对应预测文件中没有找到可验证的原始预测行。因此本文不编造 Mimo-v2.5 的具体推理轨迹，只说明已能验证的评估现象。

## 1. 样本基本信息

样本：

```text
python__mypy-13481
```

仓库：

```text
python/mypy
```

base commit：

```text
d89b28d973c3036ef154c9551b961d9119761380
```

Issue 标题：

```text
"Trying to read deleted variable" false negative when deleting class
```

Issue 核心复现代码：

```python
class Foo: ...
del Foo

print(Foo) # no error
```

Issue 中包含一个 mypy playground URL：

```text
https://mypy-play.net/?mypy=latest&python=3.10&flags=...&gist=1dea89d07b0f24e562595bf221e4f7d8
```

该样本没有图片：

```text
image_urls = []
```

URL 类型是：

```text
playground / reproduction URL
```

它不是 GitHub code URL，也不是直接 gold 文件线索。它的作用只是表示这段代码可以在 mypy playground 复现。

## 2. 真实 gold patch

真实 gold 文件：

```text
mypy/binder.py
```

真实 patch：

```diff
diff --git a/mypy/binder.py b/mypy/binder.py
--- a/mypy/binder.py
+++ b/mypy/binder.py
@@ -8,9 +8,28 @@
 from mypy.erasetype import remove_instance_last_known_values
 from mypy.join import join_simple
 from mypy.literals import Key, literal, literal_hash, subkeys
-from mypy.nodes import AssignmentExpr, Expression, IndexExpr, MemberExpr, NameExpr, RefExpr, Var
+from mypy.nodes import (
+    AssignmentExpr,
+    Expression,
+    IndexExpr,
+    MemberExpr,
+    NameExpr,
+    RefExpr,
+    TypeInfo,
+    Var,
+)
 from mypy.subtypes import is_same_type, is_subtype
-from mypy.types import AnyType, NoneType, PartialType, Type, TypeOfAny, UnionType, get_proper_type
+from mypy.types import (
+    AnyType,
+    NoneType,
+    PartialType,
+    Type,
+    TypeOfAny,
+    TypeType,
+    UnionType,
+    get_proper_type,
+)
+from mypy.typevars import fill_typevars_with_any
```

核心行为修改在 `get_declaration`：

```diff
 def get_declaration(expr: BindableExpression) -> Type | None:
-    if isinstance(expr, RefExpr) and isinstance(expr.node, Var):
-        type = expr.node.type
-        if not isinstance(get_proper_type(type), PartialType):
-            return type
+    if isinstance(expr, RefExpr):
+        if isinstance(expr.node, Var):
+            type = expr.node.type
+            if not isinstance(get_proper_type(type), PartialType):
+                return type
+        elif isinstance(expr.node, TypeInfo):
+            return TypeType(fill_typevars_with_any(expr.node))
     return None
```

测试补丁：

```diff
+[case testDelStmtWithTypeInfo]
+class Foo: ...
+del Foo
+Foo + 1  # E: Trying to read deleted variable "Foo"
```

## 3. 这个 bug 实际是什么

`Foo` 是一个类名。mypy 内部里，类名对应的语义节点不是普通变量 `Var`，而是 `TypeInfo`。

旧逻辑中，`binder.get_declaration()` 只处理：

```python
expr.node is Var
```

也就是说，如果是普通变量：

```python
x = 1
del x
print(x)
```

`x` 的节点更可能是 `Var`，binder 可以找到声明类型。

但这个样本是：

```python
class Foo: ...
del Foo
Foo + 1
```

这里 `Foo` 对应的是类定义产生的 `TypeInfo`。旧版 `get_declaration` 没有处理 `TypeInfo`，导致 binder 无法把这个类名声明变成可跟踪的类型。

新逻辑增加：

```python
elif isinstance(expr.node, TypeInfo):
    return TypeType(fill_typevars_with_any(expr.node))
```

含义是：

```text
如果被删除/读取的是类名 Foo，就把 TypeInfo 转换成 TypeType[Foo] 形式，
让 binder 可以像处理普通变量声明一样处理类名声明。
```

因此，这个 bug 的真实机制是：

```text
del Foo 删除类名后，后续读取 Foo 应该报 deleted variable。
但 binder 旧逻辑只认识 Var，不认识 TypeInfo。
因此 TypeInfo 声明没有进入 binder 的删除状态追踪。
```

这不是简单的错误消息问题，也不是普通 type inference 问题，而是：

```text
TypeInfo -> TypeType -> binder declaration tracking
```

这条内部语义链没有打通。

## 4. Playground URL 的作用与局限

Issue 中的 URL：

```text
https://mypy-play.net/?mypy=latest&python=3.10&flags=...&gist=1dea89d07b0f24e562595bf221e4f7d8
```

本地多模态 adapter 提取到的网页摘要是：

```text
mypy Playground The mypy Playground is a web service that receives a Python program with type hints,
runs mypy inside a sandbox, then returns the output.
```

这个摘要没有解析出最重要的复现结构：

```python
class Foo: ...
del Foo
print(Foo)
```

也没有进一步抽象成：

```text
RefExpr(Foo)
expr.node = TypeInfo
del statement
read after deletion
binder declaration tracking
```

所以这个 URL 对 baseline 的实际帮助有限。它只是证明问题可复现，但没有直接提供：

```text
mypy/binder.py
get_declaration
TypeInfo
TypeType
fill_typevars_with_any
```

这些真正的修复线索。

## 5. 各 baseline 实际预测与评估

### 5.1 LocAgent / Qwen3-VL-8B

full-candidates 预测：

```text
mypy/dmypy/client.py
mypyc/subtype.py
mypyc/sametype.py
mypy/main.py
mypyc/transform/refcount.py
mypyc/irbuild/expression.py
scripts/find_type.py
mypy/checker.py
```

unified60 预测：

```text
mypy/checker.py
mypy/checkmember.py
mypy/types.py
```

严格评估：

```text
file_rec@all = 0.0
module_rec@all = 0.0
function_rec@all = 0.0
```

LocAgent 轨迹中，模型其实理解到了问题的大方向：

```text
The problem describes a false negative in mypy's type checking when attempting to read a deleted class variable.
Specifically, `del Foo` deletes the class `Foo`, but mypy does not detect an error when subsequently trying to access `Foo`.

1. Handling `del` statements and tracking deleted names.
2. Checking references to deleted names during type checking.
```

但后续定位仍偏向：

```text
mypy/checker.py
mypy/checkmember.py
mypy/types.py
```

失败点是：LocAgent 把“读取删除变量未报错”理解成 checker/error-message 问题，但没有继续追踪 mypy 内部的状态绑定组件：

```text
del statement
  -> binder frame
  -> get_declaration
  -> TypeInfo / Var
```

### 5.2 CoSIL / Qwen3-VL-8B

full-candidates 预测：

```text
mypy/checker.py
mypy/checkmember.py
mypy/scope.py
mypy/types.py
mypy/checkexpr.py
```

unified60 预测：

```text
mypy/checker.py
mypy/semanal.py
mypy/scope.py
mypy/typeanal.py
mypy/checkexpr.py
```

严格评估：

```text
file_rec@all = 0.0
module_rec@all = 0.0
function_rec@all = 0.0
```

CoSIL 日志中可以看到，prompt 的 candidate file tree 里其实包含：

```text
mypy/binder.py
```

但最终输出是：

```text
mypy/checker.py
mypy/checkexpr.py
mypy/checkmember.py
mypy/scope.py
mypy/types.py
```

或者 unified60 中：

```text
mypy/checker.py
mypy/semanal.py
mypy/scope.py
mypy/typeanal.py
mypy/checkexpr.py
```

这说明 CoSIL 不是看不到 `binder.py`，而是排序和语义判断失败。它把 issue 中的强词：

```text
Trying to read deleted variable
false negative
class
type checking
```

映射到了更常见的核心模块：

```text
checker.py
checkexpr.py
checkmember.py
types.py
```

但没有识别出 `binder.py` 是 mypy 中维护条件类型、表达式绑定状态和删除状态的组件。

### 5.3 GraphLocator / Qwen3-VL-8B

unified60 预测：

```text
mypy/types.py
mypy/treetransform.py
mypy/nodes.py
mypy/stubgen.py
mypy/test/teststubtest.py
mypy/binder.py
mypy/checker.py
mypy/checkmember.py
mypy/fastparse.py
mypy/fscache.py
mypy/ipc.py
mypy/main.py
```

严格评估：

```text
file_rec@all = 1.0
module_rec@all = 1.0
function_rec@all = 0.0
```

GraphLocator 是这个样本里表现相对好的一个。它找到了：

```text
mypy/binder.py
```

但排名在第 6 位，前面有：

```text
mypy/types.py
mypy/treetransform.py
mypy/nodes.py
mypy/stubgen.py
mypy/test/teststubtest.py
```

这说明图扩展或关联推理能把候选扩展到 binder，但没有把 binder 排到最高，也没有命中真实函数：

```text
mypy/binder.py::get_declaration
mypy/binder.py::top_frame_context
```

它的缺口是缺少 mypy 领域内的职责判断：

```text
types.py: 定义 TypeType / Type 等类型结构
nodes.py: 定义 RefExpr / TypeInfo 等 AST/语义节点
checker.py: 触发类型检查和报错
binder.py: 维护表达式当前绑定类型和删除状态
```

对于本 bug，真正 patch target 是最后一个。

### 5.4 GALA / Qwen3-VL-8B

unified60 结果：

```text
gt_files = ['mypy/binder.py']
gt_modules = ['mypy/binder.py']
gt_functions = [
  'mypy/binder.py::get_declaration',
  'mypy/binder.py::top_frame_context'
]

snapshot_seed_files = []
code_seed_files = []
matched_files = []
edit_target_files = []
final_files = []
final_modules = []
final_functions = []
```

严格评估：

```text
file_rec@all = 0.0
module_rec@all = 0.0
function_rec@all = 0.0
```

这个样本没有图片，URL 又只是 playground，所以 GALA 没有获得有效视觉 seed 或代码 seed，最终输出为空。它说明对于纯文本/Playground URL 的 Python 语义 bug，视觉代码对齐类方法如果缺少语言语义图，很容易完全没有候选。

### 5.5 BM25-MMIR

full-candidates top 文件：

```text
mypy/options.py
mypy/messages.py
mypy/main.py
mypy/errorcodes.py
mypy/semanal.py
mypy/checker.py
mypy/typeanal.py
mypy/test/testcheck.py
mypy/nodes.py
mypy/fastparse.py
mypy/message_registry.py
mypy/suggestions.py
```

unified60 top 文件：

```text
mypy/options.py
mypy/messages.py
mypy/main.py
mypy/errorcodes.py
mypy/semanal.py
mypy/checker.py
mypy/fastparse.py
mypy/test/testcheck.py
mypy/typeanal.py
mypy/build.py
mypy/nodes.py
mypy/stubgen.py
```

BM25 被词法信号带偏：

```text
Trying to read deleted variable
error
strict flags
mypy options
messages
errorcodes
checker
testcheck
```

由于 issue 文本没有出现：

```text
binder
get_declaration
TypeInfo
TypeType
fill_typevars_with_any
```

BM25 很难靠词面召回真实文件。

### 5.6 Mimo-v2.5 结果说明

本地解压的 Mimo-v2.5 server Omni60 结果中，逐样本评估 CSV 能看到该样本，并显示各 baseline 在 Clean15 评估下均未命中：

```text
LocAgent file_rec@all = 0.0
CoSIL file_rec@all = 0.0
GraphLocator file_rec@all = 0.0
GALA file_rec@all = 0.0
```

但在对应 `loc_outputs.jsonl` / `loc_results.json` 预测文件中，没有找到该 instance 的可验证预测行。因此本文不提供 Mimo-v2.5 的具体预测列表或推理轨迹，避免把评估结果之外的信息写成事实。

## 6. 失败原因总结

这个样本的失败不是因为 issue 太长或 URL 太复杂，而是因为真实修复点在 mypy 的中间语义层。

表面层：

```text
Trying to read deleted variable
false negative
class Foo
del Foo
print(Foo)
```

baseline 常见映射：

```text
checker.py
messages.py
types.py
errorcodes.py
checkexpr.py
checkmember.py
```

真实机制：

```text
class Foo
  -> TypeInfo
  -> RefExpr.node
  -> binder.get_declaration()
  -> TypeType(fill_typevars_with_any(TypeInfo))
  -> deleted variable state tracking
```

所以准确定位需要理解：

```text
类名 Foo 不是 Var，而是 TypeInfo。
del/read-after-delete 的状态不是只在 checker 里处理，而是在 binder 中维护。
错误文本只是最终输出，不是根因位置。
```

## 7. 对多语言仓库图和 Agent 框架的启发

这个案例说明，Python/mypy 这类仓库不能只建普通函数调用图。需要建更贴近语言语义的图。

建议增加以下边：

```text
ClassDef -> TypeInfo
NameExpr / RefExpr -> node kind
RefExpr -> Var
RefExpr -> TypeInfo
TypeInfo -> TypeType
DelStmt -> binder state update
BindableExpression -> get_declaration
get_declaration -> ConditionalTypeBinder frame
deleted variable error -> binder declaration tracking
```

Agent 搜索时也不应该只生成词法 query：

```text
Trying to read deleted variable
deleted variable
checker
error message
```

还应该生成语义 query：

```text
binder deleted variable
get_declaration RefExpr TypeInfo
del stmt binder declaration
TypeInfo TypeType fill_typevars_with_any
```

合理的推理链应该是：

```text
Issue: del Foo 后 Foo 读取未报错
  -> 这是 deleted variable state tracking
  -> Foo 是类名，对应 TypeInfo
  -> 旧逻辑可能只处理普通变量 Var
  -> mypy 的状态绑定组件是 binder
  -> 检查 binder.get_declaration 是否支持 TypeInfo
  -> 定位到 mypy/binder.py
```

## 8. 论文动机价值

这个样本可以作为“跨语言/语言语义图不足”的典型案例。

它与前端 UI / PDF layout 案例不同，问题不在图片或视觉信息，而在：

```text
语言语义节点和类型系统内部状态流。
```

因此可以说明我们的框架需要同时支持：

```text
多模态证据图：图片、URL、网页、复现链接；
多语言语义图：AST node、symbol、type、binder/control-flow state；
多关系仓库图：call、dataflow、state-flow、config、test、documentation。
```

一句话总结：

```text
python__mypy-13481 不是“错误消息定位”问题，而是“类名删除后的 TypeInfo declaration 如何进入 binder 状态流”的问题。现有 baseline 大多能理解 del/read-after-delete 的表面语义，但缺少 mypy 内部 TypeInfo -> TypeType -> binder declaration tracking 的跨层语义图，因此容易失败。
```

