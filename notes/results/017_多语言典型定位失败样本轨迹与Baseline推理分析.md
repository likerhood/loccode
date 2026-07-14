# 多语言典型定位失败样本轨迹与 Baseline 推理分析

本文补充此前偏 JS/TS 的失败案例分析，专门分析 OmniGIRL 中的 Python 与 Java 样本。分析只使用本地真实存在的结果、日志和轨迹文件；没有本地可验证轨迹的 baseline 不做虚构。

## 1. 数据与可验证范围

本次实际使用的文件如下：

- Qwen3-VL-8B / OmniGIRL full-candidates：
  - `LocAgent/newtest/omnigirl-full-candidates/results/openai_qwen3-vl-8b/location/loc_outputs.jsonl`
  - `LocAgent/newtest/omnigirl-full-candidates/results/openai_qwen3-vl-8b/location/loc_trajs.jsonl`
  - `LocAgent/newtest/omnigirl-full-candidates/results/openai_qwen3-vl-8b/eval_strict/per_instance_metrics_3level.csv`
  - `CoSIL/newtest/omnigirl-full-candidates/results/openai_qwen3-vl-8b/file_level/loc_outputs.jsonl`
  - `CoSIL/newtest/omnigirl-full-candidates/results/openai_qwen3-vl-8b/eval_strict/per_instance_metrics_3level.csv`
  - `MM-IR/results/omnigirl-full-candidates/bm25-mmir/loc_results.json`
  - `MM-IR/results/omnigirl-full-candidates/bm25-mmir/eval_strict/per_instance_metrics_3level.csv`
- 运行日志：
  - `baseline_run_logs/omnigirl_full_parallel_20260709_100049/locagent.log`
  - `baseline_run_logs/omnigirl_full_parallel_20260710_102728/{locagent,cosil,graphlocator}.log`

需要说明：当前本地没有发现 Mimo-v2.5 的 OmniGIRL Python/Java 结果包。Mimo-v2.5 当前可验证的完整包主要是 SWE-bench Multimodal full-dev，而该 benchmark 基本是 JS/TS 前端仓库。因此本文的非 JS 失败案例主要来自 Qwen3-VL-8B 在 OmniGIRL full-candidates 上的真实轨迹；Mimo-v2.5 不补不存在的非 JS 轨迹。

## 2. 案例一：Python / mypy 的变量删除生命周期定位失败

### 2.1 样本与真实答案

样本：`python__mypy-13481`

仓库：`python/mypy`

Issue 摘要：`del Foo` 删除类之后，`print(Foo)` 没有报 “Trying to read deleted variable” 之类的错误。

Issue 中包含一个 mypy playground URL：

```text
https://mypy-play.net/?mypy=latest&python=3.10&flags=...&gist=1dea89d07b0f24e562595bf221e4f7d8
```

真实 gold 文件：

```text
mypy/binder.py
```

真实 patch 关键点是 `binder.py` 中对声明读取和删除状态的处理，涉及 `TypeInfo`、`TypeType`、`fill_typevars_with_any`，以及 `get_declaration` / `top_frame_context` 相关逻辑。

### 2.2 各 baseline 的结果

| Baseline | file_rec@all | module_rec@all | function_rec@all | 预测倾向 |
|---|---:|---:|---:|---|
| LocAgent / Qwen8B | 0.00 | 0.00 | 0.00 | `mypy/checker.py`、`mypy/main.py`、`mypyc/*`、CLI/错误消息方向 |
| CoSIL / Qwen8B | 0.00 | 0.00 | 0.00 | `mypy/checker.py`、`checkmember.py`、`scope.py`、`types.py` |
| BM25-MMIR | 0.00 | 0.00 | 0.00 | `options.py`、`messages.py`、`main.py`、`semanal.py`、`checker.py` |
| GraphLocator / Qwen8B unified60 | 命中 file，但不完整 | 部分偏移 | 部分偏移 | 在 unified60 中找到 `binder.py`，但 top 排名混入 `types.py`、`nodes.py`、`stubgen.py` 等 |

LocAgent 最终输出片段：

```text
mypy/dmypy/client.py
class: AugmentedHelpFormatter

mypyc/subtype.py
function: is_subtype

mypyc/sametype.py
function: is_same_type

mypy/main.py
function: read_types_packages_to_install

mypyc/transform/refcount.py
function: is_maybe_undefined

mypy/checker.py
function: handle_cannot_determine_type
```

CoSIL 输出：

```text
mypy/checker.py
mypy/checkmember.py
mypy/scope.py
mypy/types.py
mypy/checkexpr.py
```

BM25-MMIR top 文件：

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
```

### 2.3 LocAgent 真实轨迹片段

LocAgent 的初始分析是合理的，但没有进入 `binder.py`：

```text
The problem describes a false negative in mypy's type checking when attempting to read a deleted class variable.
Specifically, `del Foo` deletes the class `Foo`, but mypy does not detect an error when subsequently trying to access `Foo`.
...
1. Handling `del` statements and tracking deleted names.
2. Checking references to deleted names during type checking.
```

随后搜索工具自动填充的 terms 被 playground URL 和复现代码牵引：

```text
OBSERVATION: search_code_snippets was called without search_terms or line_nums.
Auto-filled search_terms from the issue context:
['py\r\nclass Foo: ...\r\ndel Foo\r\n\r\nprint(Foo) # no error',
 '//mypy-play.net/', 'mypy-play.net', 'mypy-play', 'mypy', 'play',
 'show-error-context', 'show']
Using multi-language default file pattern '**/*.py'.
```

后续推理转向 `checker.py`：

```text
The search results indicate that the core logic for handling deleted names and type checking resides in `mypy/checker.py`,
which is responsible for type checking and validation.
...
This involves:
1. Tracking deleted names during AST processing.
2. Checking references to deleted names.
```

### 2.4 失败原因

这个样本不是简单的“查找 del 语句处理器”。真实修复在 `binder.py`，因为 mypy 中变量状态、类型窄化和删除后的声明读取属于 binder 的责任边界。baseline 的失败有三层：

1. **URL 角色识别不足**：mypy playground URL 是复现环境，不是代码位置。它提供了输入现象，但不应主导文件检索。
2. **Python 语义图缺失**：`del Foo` 后 `print(Foo)` 的错误不是普通 name lookup，而是符号生命周期状态变化。需要追踪 `NameExpr -> TypeInfo -> TypeType -> binder declaration`。
3. **搜索 query 过宽**：`deleted name`、`type checking`、`mypy-play` 会召回 checker/main/messages，而不是 binder 的 declaration frame。

### 2.5 对框架设计的启发

针对 Python 需要增加“符号生命周期图”：

```text
NameExpr / RefExpr
  -> SymbolTableNode / TypeInfo
  -> Binder frame
  -> declaration state
  -> read-after-delete diagnostic
```

Agent 不能只问“哪个文件负责 type checking”，而要把问题转换成更细的语言语义查询：

```text
Python class object deletion -> symbol table binding -> binder declaration lookup -> deleted variable diagnostic
```

## 3. 案例二：Python / cryptography 的跨接口传参链闭包失败

### 3.1 样本与真实答案

样本：`pyca__cryptography-7520`

仓库：`pyca/cryptography`

Issue 摘要：为 OpenSSH private key encryption 增加 `kdf_rounds` 参数，使其能像 `ssh-keygen -a` 一样控制 KDF rounds。

Issue URL：

```text
https://github.com/ansible-collections/community.crypto/issues/449
```

真实 gold 文件：

```text
src/cryptography/hazmat/backends/openssl/backend.py
src/cryptography/hazmat/primitives/_serialization.py
src/cryptography/hazmat/primitives/serialization/__init__.py
src/cryptography/hazmat/primitives/serialization/ssh.py
```

真实修改不是单点，而是跨接口链：

```text
BestAvailableEncryption / _KeySerializationEncryption
  -> backend._private_key_bytes
  -> OpenSSH serialization
  -> ssh._serialize_ssh_private_key
  -> kdf_rounds 参数落地
```

### 3.2 各 baseline 的结果

| Baseline | file_rec@all | module_rec@all | function_rec@all | 预测倾向 |
|---|---:|---:|---:|---|
| LocAgent / Qwen8B | 0.00 | 0.00 | 0.00 | 偏到 `keywrap.py`、`x509/*`、twofactor、证书相关文件 |
| CoSIL / Qwen8B | 0.25 | 0.25 | 0.00 | 命中 `serialization/ssh.py`，但漏掉 backend 与 public interface |
| BM25-MMIR | 0.75 | 0.20 | 0.00 | 命中 3/4 文件，但 function 层完全不准 |

LocAgent 输出：

```text
src/cryptography/hazmat/primitives/keywrap.py
function: aes_key_wrap_with_padding

src/cryptography/utils.py
class: InterfaceNotImplemented

src/cryptography/hazmat/primitives/twofactor/hotp.py
function: _generate_uri

src/cryptography/x509/ocsp.py
function: issuer_key_hash

src/cryptography/x509/name.py
function: get_attributes_for_oid
```

CoSIL 输出：

```text
src/cryptography/hazmat/primitives/serialization/ssh.py
src/cryptography/hazmat/primitives/kdf/pbkdf2.py
src/cryptography/hazmat/primitives/kdf/hkdf.py
src/cryptography/hazmat/primitives/kdf/scrypt.py
src/cryptography/hazmat/primitives/kdf/__init__.py
```

BM25-MMIR top 文件：

```text
src/_cffi_src/build_openssl.py
src/cryptography/hazmat/primitives/serialization/ssh.py
src/cryptography/hazmat/primitives/kdf/kbkdf.py
src/cryptography/hazmat/bindings/openssl/binding.py
src/cryptography/hazmat/primitives/_serialization.py
src/cryptography/hazmat/backends/openssl/backend.py
src/cryptography/hazmat/primitives/asymmetric/rsa.py
```

### 3.3 LocAgent 真实轨迹片段

LocAgent 一开始抓住了关键 token：

```text
assistant:
<function=search_code_snippets>
<parameter>search_terms</parameter>
<parameter>["BestAvailableEncryption", "kdf_rounds"]</parameter>
```

但搜索工具实际自动填充时被 issue 的长文本和泛 KDF 词牵引：

```text
OBSERVATION: search_code_snippets was called without search_terms or line_nums.
Auto-filled search_terms from the issue context:
['kdf_rounds', 'ssh-keygen', 'flag. This PR permits the same parameterization through the',
 'class.\r\n\r\n### Open Questions\r\n- [] Should this parameter be passed through',
 'where it is generally not applicable or should another data structure e.g.',
 'be created and passed through', 'at the level of', 'because it is only applied in the']
```

之后出现了明显的实体定位偏移：

```text
assistant:
<function=get_entity_contents>
<parameter>entity_names</parameter>
<parameter>['src/cryptography/hazmat/primitives/keywrap.py:BestAvailableEncryption']</parameter>
```

这里 `BestAvailableEncryption` 并不在 `keywrap.py`，说明工具返回、实体解析或 LLM 组合 entity name 时已经发生跨文件拼接错误。

### 3.4 失败原因

这个样本暴露出跨接口改动的典型难点：

1. **词法召回能接近，但无法闭包**：BM25 能命中 `ssh.py`、`_serialization.py`、`backend.py`，但不知道需要同时修改 public API、backend dispatch 和 OpenSSH serializer。
2. **LocAgent 的实体拼接不稳定**：`keywrap.py:BestAvailableEncryption` 是错误组合，说明 agent 没有强校验 symbol 所属文件。
3. **CoSIL 停在局部实现层**：只看到 SSH/KDF 层，漏掉 `BestAvailableEncryption` 对外接口和 backend 对 format/encryption_algorithm 的转发。

### 3.5 对框架设计的启发

需要显式做“接口传播闭包”：

```text
参数新增 kdf_rounds
  -> public constructor / interface
  -> internal serialization object
  -> backend dispatch
  -> format-specific serializer
  -> tests / docs
```

这类样本不能只依赖 top-k 文件排序；需要在候选文件之间建参数流图，验证新参数是否从 API 入口传到最终实现。

## 4. 案例三：Java / Gson 的匿名类序列化策略定位失败

### 4.1 样本与真实答案

样本：`google__gson-2498`

仓库：`google/gson`

Issue 摘要：Gson 应允许匿名类 serialization。当前 Guava `Sets.union(...)` 返回匿名类，`gson.toJsonTree(...)` 得到 `null`。

Issue URL 很多，包括 Gson issue、Javalin issue、StackOverflow：

```text
https://github.com/google/gson/issues/298
https://github.com/google/gson/issues/762
https://github.com/tipsy/javalin/issues/288
https://stackoverflow.com/questions/10746278/serializing-anonymous-classes-with-gson
https://stackoverflow.com/questions/26791752/convert-anonymous-java-object-types-to-json-using-gson
https://stackoverflow.com/questions/55622921/custom-gson-serializer-for-anonymous-classes
```

真实 gold 文件：

```text
gson/src/main/java/com/google/gson/internal/Excluder.java
gson/src/main/java/com/google/gson/internal/bind/ReflectiveTypeAdapterFactory.java
gson/src/main/java/com/google/gson/internal/reflect/ReflectionHelper.java
```

真实修复核心：匿名类不是在 `toJsonTree` 输出层修，而是在 class exclusion 和 reflective adapter 逻辑里处理。

### 4.2 各 baseline 的结果

| Baseline | file_rec@all | module_rec@all | function_rec@all | 预测倾向 |
|---|---:|---:|---:|---|
| LocAgent / Qwen8B | 0.00 | 0.00 | 0.00 | `JsonTreeWriter`、`JsonWriter`、`JsonElement`、`TypeAdapter`、`GsonBuilder` |
| CoSIL / Qwen8B | 0.00 | 0.00 | 0.00 | `TypeAdapterRuntimeTypeWrapper.java` |
| BM25-MMIR | 0.00 | 0.00 | 0.00 | `Gson.java`、`TypeToken.java`、`ConstructorConstructor.java`、`GsonBuilder.java` |

LocAgent 输出：

```text
gson/src/main/java/com/google/gson/internal/NonNullElementWrapperList.java
gson/src/main/java/com/google/gson/internal/bind/JsonTreeWriter.java
gson/src/main/java/com/google/gson/stream/JsonWriter.java
gson/src/main/java/com/google/gson/JsonElement.java
gson/src/main/java/com/google/gson/internal/bind/JsonTreeReader.java
gson/src/main/java/com/google/gson/stream/JsonReader.java
gson/src/main/java/com/google/gson/TypeAdapter.java
gson/src/main/java/com/google/gson/GsonBuilder.java
```

CoSIL 输出：

```text
gson/src/main/java/com/google/gson/internal/bind/TypeAdapterRuntimeTypeWrapper.java
```

BM25-MMIR top 文件：

```text
gson/src/main/java/com/google/gson/Gson.java
gson/src/main/java/com/google/gson/reflect/TypeToken.java
gson/src/main/java/com/google/gson/internal/ConstructorConstructor.java
gson/src/main/java/com/google/gson/GsonBuilder.java
gson/src/main/java/com/google/gson/ReflectionAccessFilter.java
gson/src/main/java/com/google/gson/TypeAdapterFactory.java
```

### 4.3 LocAgent 真实轨迹片段

LocAgent 的初始 query 是表层 API：

```text
assistant:
<function=search_code_snippets>
<parameter>search_terms</parameter>
<parameter>["Gson", "toJson", "toJsonTree", "anonymous class", "serialize", "serialization"]</parameter>
```

工具自动填充时，URL 与示例输出占据大量 query token：

```text
OBSERVATION: search_code_snippets was called without search_terms or line_nums.
Auto-filled search_terms from the issue context:
['["a", "b"]',
 'But actually, that code prints',
 ', totally unexpected to a user that is not familiar with the implementation of',
 'null',
 'gson.toJsonTree(union, TypeToken<Set<String>>(){}.getType());.',
 'ImmutableMap.of(...',
 '//github.com/google/gson/issues/298', 'github.com']
```

随后读取的是输出/adapter API 文件：

```text
assistant:
<function=get_entity_contents>
<parameter>entity_names</parameter>
<parameter>[
 'gson/src/main/java/com/google/gson/TypeAdapter.java',
 'gson/src/main/java/com/google/gson/internal/bind/JsonTreeWriter.java',
 'gson/src/main/java/com/google/gson/internal/bind/JsonTreeReader.java',
 'gson/src/main/java/com/google/gson/GsonBuilder.java',
 'gson/src/main/java/com/google/gson/JsonElement.java'
]</parameter>
```

### 4.4 失败原因

这个样本的问题是“现象 API”和“策略判断点”不在同一个文件：

```text
用户看到：gson.toJsonTree(...) -> null
真实原因：Excluder 认为 anonymous/local class 应被排除
修复位置：Excluder + ReflectiveTypeAdapterFactory + ReflectionHelper
```

Baseline 普遍被 `toJsonTree`、`JsonTreeWriter`、`TypeAdapter` 牵引，缺少从“输出为 null”反推“类被 exclusion 策略过滤”的因果边。

### 4.5 对框架设计的启发

Java 定位需要内置“框架策略点”搜索：

```text
serialization output anomaly
  -> adapter selection
  -> type exclusion / reflection access filter
  -> anonymous/local class predicate
  -> reflective adapter construction
```

Agent 需要把 URL 和 StackOverflow 链接识别为“用户困惑证据”，而不是直接把其中的 API 名当作 patch target。

## 5. 案例四：Java / Netty 的类名强牵引与共享缓冲区语义丢失

### 5.1 样本与真实答案

样本：`netty__netty-14086`

仓库：`netty/netty`

Issue 摘要：`SslHandler` 不支持 input `ByteBuf` 被多个线程共享的场景。Pulsar 曾通过 `.copy()` 缓解，但带来其他问题。

Issue URL：

```text
https://github.com/apache/pulsar/issues/22601#issuecomment-2122642708
https://github.com/apache/pulsar/issues/2401
https://github.com/apache/pulsar/pull/22760
https://github.com/apache/pulsar/pull/2464
```

真实 gold 文件：

```text
handler/src/main/java/io/netty/handler/ssl/SslHandlerCoalescingBufferQueue.java
transport/src/main/java/io/netty/channel/AbstractCoalescingBufferQueue.java
```

真实修复位置不是 `SslHandler.java` 本体，而是 coalescing buffer queue 的 compose / retain / copy 策略。

### 5.2 各 baseline 的结果

| Baseline | file_rec@all | module_rec@all | function_rec@all | 预测倾向 |
|---|---:|---:|---:|---|
| LocAgent / Qwen8B | 0.00 | 0.00 | 0.00 | `SslHandler.java`、`SpdySessionHandler.java` |
| CoSIL / Qwen8B | 0.00 | 0.00 | 0.00 | `SslHandler.java`、`AbstractSniHandler.java` |
| BM25-MMIR | 0.00 | 0.00 | 0.00 | CI workflow、`SslHandler.java`、`NativeLibraryLoader`、channel classes |

LocAgent 输出：

```text
codec-http/src/main/java/io/netty/handler/codec/spdy/SpdySessionHandler.java
function: issueSessionError

handler/src/main/java/io/netty/handler/ssl/SslHandler.java
function: channelReadComplete
function: channelReadComplete0
```

CoSIL 输出：

```text
handler/src/main/java/io/netty/handler/ssl/SslHandler.java
handler/src/main/java/io/netty/handler/ssl/AbstractSniHandler.java
```

BM25-MMIR top 文件：

```text
github/workflows/ci-pr.yml
github/workflows/ci-release-5.yml
github/workflows/ci-release.yml
microbench/src/main/resources/io/netty/microbench/search/netty-io-news.html
handler/src/main/java/io/netty/handler/ssl/SslHandler.java
common/src/main/java/io/netty/util/internal/NativeLibraryLoader.java
transport/src/main/java/io/netty/channel/nio/AbstractNioByteChannel.java
```

### 5.3 LocAgent 真实轨迹片段

LocAgent query 直接围绕 issue 中高频实体：

```text
assistant:
<function=search_code_snippets>
<parameter>search_terms</parameter>
<parameter>["SslHandler", "ByteBuf", "shared", "concurrent", "copy"]</parameter>
```

工具自动填充时被外部 Pulsar URL 和环境信息污染：

```text
OBSERVATION: search_code_snippets was called without search_terms or line_nums.
Auto-filled search_terms from the issue context:
['.copy()', 'java -version', 'uname -a',
 '//github.com/apache/pulsar/issues/2401',
 'github.com', 'apache', 'pulsar', 'issues']
Using multi-language default file pattern '**/*'.
```

随后 Agent 限定到 SSL 目录，但仍停留在 `SslHandler.java`：

```text
assistant:
<function=search_code_snippets>
<parameter>search_terms</parameter>
<parameter>["SslHandler", "ByteBuf", "shared", "concurrent", "copy"]</parameter>
<parameter>file_path_or_pattern</parameter>
<parameter>**/src/main/java/io/netty/handler/ssl/**</parameter>

assistant:
<function=get_entity_contents>
<parameter>entity_names</parameter>
<parameter>['io/netty/handler/ssl/SslHandler.java']</parameter>
```

### 5.4 失败原因

这里的失败不是没有找到相关类，而是没有越过“显式类名诱饵”：

```text
Issue 明说 SslHandler
真实 patch 在 SslHandlerCoalescingBufferQueue 和 AbstractCoalescingBufferQueue
```

要定位正确，需要知道 Netty 的数据路径：

```text
SslHandler
  -> wrap / decode pipeline
  -> coalescing buffer queue
  -> compose(ByteBuf cumulation, ByteBuf next)
  -> shared ByteBuf retain/copy 语义
```

当前 baseline 缺少 Java inheritance / composition / protected override 的关系扩展，导致只盯住公开类 `SslHandler`，没有进入内部 buffer queue 实现。

### 5.5 对框架设计的启发

Java agent 需要在初始类命中后强制做一次“实现闭包扩展”：

```text
mentioned class -> field/member type -> helper class -> superclass -> overridden method -> data ownership operation
```

对 Netty 这种框架型仓库，还需要针对 `ByteBuf` 这类资源对象识别所有权操作：

```text
copy / duplicate / retain / release / compose / addComponent
```

## 6. 案例五：Java / AssertJ 的 API 层与内部实现层错位

### 6.1 样本与真实答案

样本：`assertj__assertj-1332`

仓库：`assertj/assertj`

Issue 摘要：非严格字符串断言应该抛 `AssertionFailedError`，以便 IDE 显示 diff。Issue 中还包含一张 IDE diff 截图。

真实 gold 文件：

```text
src/main/java/org/assertj/core/internal/Strings.java
```

真实 function gold 包括：

```text
assertEqualsIgnoringCase
assertEqualsIgnoringWhitespace
assertEqualsNormalizingWhitespace
assertIsEqualToIgnoringNewLines
assertIsEqualToNormalizingNewlines
normalizeNewlines
```

### 6.2 各 baseline 的结果

| Baseline | file_rec@all | module_rec@all | function_rec@all | 预测倾向 |
|---|---:|---:|---:|---|
| LocAgent / Qwen8B | 0.00 | 0.00 | 0.00 | 只定位到 public API `AbstractCharSequenceAssert.java` |
| CoSIL / Qwen8B | 1.00 | 0.00 | 0.00 | 文件命中，但 module/function 偏 API 层 |
| BM25-MMIR | 1.00 | 0.00 | 0.11 | 文件命中，函数只命中一小部分 |
| GraphLocator full / Qwen8B | 0.00 | 0.00 | 0.00 | 偏 `AbstractCharSequenceAssert.java` |

LocAgent 输出：

```text
src/main/java/org/assertj/core/api/AbstractCharSequenceAssert.java
function: isEqualToIgnoringNewLines
function: isEqualToIgnoringWhitespace
```

CoSIL 输出：

```text
src/main/java/org/assertj/core/api/AbstractCharSequenceAssert.java
src/main/java/org/assertj/core/internal/Strings.java
src/main/java/org/assertj/core/util/CheckReturnValue.java
src/main/java/org/assertj/core/internal/ComparatorBasedComparisonStrategy.java
src/main/java/org/assertj/core/util/IterableUtil.java
```

BM25-MMIR top 文件：

```text
src/main/java/org/assertj/core/util/diff/DiffUtils.java
src/main/java/org/assertj/core/error/ShouldBeEqual.java
src/main/java/org/assertj/core/api/AbstractCharSequenceAssert.java
src/main/java/org/assertj/core/internal/Strings.java
src/main/java/org/assertj/core/api/JUnitJupiterSoftAssertions.java
src/test/java/org/assertj/core/internal/strings/Strings_assertIsEqualToNormalizingNewlines_Test.java
```

### 6.3 LocAgent 真实轨迹片段

LocAgent 正确理解了问题现象：

```text
The problem describes an issue in AssertJ where certain non-strict string assertion methods
(like `isEqualToIgnoringNewLines`, `isEqualToIgnoringWhitespace`) should throw `AssertionFailedError`
instead of `AssertionError` to enable better IDE diff views.
```

但搜索自动填充被 public API method 和截图上下文牵引：

```text
OBSERVATION: search_code_snippets was called without search_terms or line_nums.
Auto-filled search_terms from the issue context:
['ChangeSetGeneratorIntegrationTest',
 'org.opentest4j.AssertionFailedError',
 'assertThat(...).isEqualTo(...)',
 'isEqualTo(...)',
 'AssertionFailedError',
 'isEqualToIgnoringNewLines',
 'isEqualToIgnoringWhitespace',
 'ChangeSetGeneratorIntegrationTest.java']
```

后续推理明确停在 API 层：

```text
From the search results, I can see that the `AbstractCharSequenceAssert` class is located in
`src/main/java/org/assertj/core/api/AbstractCharSequenceAssert.java`.
However, the specific methods `isEqualToIgnoringNewLines` and `isEqualToIgnoringWhitespace`
are not directly visible in the snippet provided.
```

最终它把 API wrapper 当成 patch target：

```text
src/main/java/org/assertj/core/api/AbstractCharSequenceAssert.java
function: isEqualToIgnoringNewLines
function: isEqualToIgnoringWhitespace
```

### 6.4 失败原因

AssertJ 的 public API 和 internal implementation 分层清晰：

```text
AbstractCharSequenceAssert.isEqualToIgnoringWhitespace(...)
  -> strings.assertEqualsIgnoringWhitespace(...)
  -> Strings.java 内部 failure 构造
```

Issue 文本提到了 public API method，因此 baseline 能找到 API 层；但真实修改在 internal `Strings.java`，因为要改变 failure object 的构造参数。缺少“API wrapper -> delegate internal implementation”的调用边，是导致 LocAgent/GraphLocator 文件级失败的主要原因。

CoSIL 和 BM25 能命中文件，但 function 层仍不足，说明文件级命中不等于实体级定位正确。

## 7. 跨样本共性失败机制

这些非 JS 样本的共性不是“模型不懂 Java/Python”，而是 agent 搜索范式没有把语言语义纳入检索路径。

### 7.1 URL 和截图被当成 query，而不是 evidence

在 mypy、gson、netty 中，URL 都是复现或外部背景：

- mypy playground URL：说明复现代码和 flags。
- Gson StackOverflow/GitHub URL：说明用户困惑和历史 issue。
- Netty Pulsar URL：说明下游项目现象和 workaround。

这些 URL 不应直接变成 patch target query。当前工具自动填充会把 URL token、`github.com`、`issues`、`mypy-play`、环境命令等放入检索，稀释真正的代码语义。

### 7.2 显式 API 类名容易成为定位陷阱

典型错位：

| 样本 | Issue 显式实体 | 真实 patch 层 |
|---|---|---|
| `assertj__assertj-1332` | `AbstractCharSequenceAssert` public API | `internal/Strings.java` failure construction |
| `google__gson-2498` | `Gson.toJsonTree` / `TypeAdapter` | `Excluder` / reflective adapter / anonymous class predicate |
| `netty__netty-14086` | `SslHandler` | `SslHandlerCoalescingBufferQueue` / `AbstractCoalescingBufferQueue` |
| `pyca__cryptography-7520` | `BestAvailableEncryption` | public API + backend + OpenSSH serializer |

### 7.3 多语言结构边缺失

Python 需要：

- name binding / symbol table / binder frame；
- type narrowing 与删除变量状态；
- public API 到 backend serializer 的参数传递。

Java 需要：

- public API 到 internal delegate；
- class exclusion 策略点；
- inheritance / overridden method；
- resource ownership 操作，例如 `retain`、`copy`、`release`、`compose`。

当前 baseline 多数停留在 BM25/LLM 搜索加局部代码阅读，没有稳定构造这些语言特定边。

## 8. 对新框架的直接要求

基于这些失败样本，新框架至少需要增加四类能力。

### 8.1 证据角色识别

先判断 issue 里的 URL、图片、代码片段属于哪种角色：

```text
reproduction-url       复现环境，例如 mypy-play
external-context-url   外部项目或 StackOverflow 讨论，例如 Pulsar/Gson
ui-symptom-image       UI/IDE 截图，例如 AssertJ diff screenshot
api-mention           用户可见 API，例如 toJsonTree / SslHandler
patch-target-candidate 真实可能修改点
```

### 8.2 语言语义路由

按仓库语言选择不同的搜索扩展规则：

```text
Python:
  symbol table -> binder -> type checker -> error reporting

Java:
  public API -> delegate/internal -> factory/strategy -> overridden method

JS/TS:
  route/component -> state selector -> action/reducer -> rendering branch
```

### 8.3 多跳候选闭包

候选不是一个文件，而是一组必须共同满足的闭包：

```text
API 层命中
  -> delegate/internal 实现层
  -> 状态/策略判断点
  -> 测试或异常输出点
```

cryptography 的 `kdf_rounds` 样本尤其说明：只命中 `ssh.py` 不够，必须同时命中 public interface 和 backend dispatch。

### 8.4 Failure-aware verifier

在输出前做反事实检查：

```text
如果只修改当前候选文件，是否能解释 issue 中的核心现象？
是否覆盖了新增参数/状态/错误对象从入口到出口的完整路径？
候选是否只是 evidence seed，而非 patch target？
候选是否只是 public wrapper，真实实现是否在 delegate/internal 层？
```

## 9. 小结

非 JS 的失败案例说明，跨语言定位不能只做“多语言文件后缀支持”。真正需要的是语言语义边和证据角色建模：

- Python 的难点是符号生命周期、类型状态和接口传参闭包。
- Java 的难点是 public API 与 internal implementation 分层、factory/strategy 机制、继承/override 和资源所有权语义。
- URL 和图片不能直接作为检索词使用，必须先转成结构化 evidence，再通过语言语义图传播到 patch target。

这也是后续框架设计的核心动机：从“LLM 读 issue 后搜索代码”升级为“多模态证据解析 + 语言语义图扩展 + agent 验证闭包”的定位范式。
