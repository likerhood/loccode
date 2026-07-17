# pyca__cryptography-7520 跨接口参数传递闭包失败分析

本文分析 OmniGIRL full-candidates 中的 Python 样本 `pyca__cryptography-7520`。这个样本的价值在于：它不是单个函数内部的 bug，而是一个新参数需要从 public API 一路传递到 backend 和 OpenSSH serializer 的跨接口闭包问题。现有 baseline 中，词法检索可以接近局部实现，但 Agent 和图方法普遍缺少“参数传播链必须闭合”的验证。

本文只使用本地真实结果和轨迹，不编造不存在的 Mimo 或子集轨迹。该样本出现在 OmniGIRL full-candidates，不在当前本地 `omnigirl-unified60` 子集中。

## 1. 数据来源

样本与结果来源：

```text
GraphLocator/datasets/omnigirl_full_candidates.jsonl
LocAgent/newtest/omnigirl-full-candidates/results/openai_qwen3-vl-8b/location/loc_outputs.jsonl
LocAgent/newtest/omnigirl-full-candidates/results/openai_qwen3-vl-8b/location/loc_trajs.jsonl
CoSIL/newtest/omnigirl-full-candidates/results/openai_qwen3-vl-8b/file_level/loc_outputs.jsonl
CoSIL/newtest/omnigirl-full-candidates/results/openai_qwen3-vl-8b/file_level/localization_logs/pyca__cryptography-7520.log
MM-IR/results/omnigirl-full-candidates/bm25-mmir/loc_results.json
MM-IR/results/omnigirl-full-candidates/bm25-mmir/eval/per_instance_metrics_3level.csv
```

样本基本信息：

| 字段 | 内容 |
|---|---|
| instance_id | `pyca__cryptography-7520` |
| 仓库 | `pyca/cryptography` |
| 语言 | Python |
| base commit | `ceaf549de1c447d99277ceb8b8d086b79b41e794` |
| 图片 | 无，`image_urls=[]` |
| URL | `https://github.com/ansible-collections/community.crypto/issues/449` |

## 2. Issue 到底要求修什么

Issue 标题和摘要是：

```text
[WIP] feat: add kdf_rounds param to encryption algorithm

Currently the number of kdf_rounds used when encrypting OpenSSH private keys
is fixed at the ssh-keygen default of 16. ssh-keygen however parameterizes
this value with the -a flag. This PR permits the same parameterization through
the BestAvailableEncryption class.
```

外部 URL 是 Ansible community.crypto 的需求讨论，核心诉求是：

```text
community.crypto.openssh_keypair 希望像 ssh-keygen -a 100 一样，
控制生成 ed25519/OpenSSH private key 时的 KDF rounds。
```

所以这个 URL 不是代码文件链接，而是需求来源。它提供了语义：

```text
OpenSSH private key encryption
ssh-keygen -a
KDF rounds
BestAvailableEncryption
```

真正修复目标不在 Ansible 仓库，而在 `cryptography` 的 key serialization API 和 OpenSSH 序列化实现。

## 3. 真实 gold patch

真实修改文件有 4 个：

```text
src/cryptography/hazmat/backends/openssl/backend.py
src/cryptography/hazmat/primitives/_serialization.py
src/cryptography/hazmat/primitives/serialization/__init__.py
src/cryptography/hazmat/primitives/serialization/ssh.py
```

真实修改链路可以概括为：

```text
PrivateFormat.OpenSSH.encryption_builder()
  -> KeySerializationEncryptionBuilder.kdf_rounds()
  -> _KeySerializationEncryption(password, kdf_rounds)
  -> backend._private_key_bytes(...)
  -> ssh._serialize_ssh_private_key(...)
  -> OpenSSH bcrypt KDF rounds
```

### 3.1 Public API 层：新增 builder

`src/cryptography/hazmat/primitives/_serialization.py` 新增 `PrivateFormat.encryption_builder()` 和 builder 类：

```diff
+    def encryption_builder(self) -> "KeySerializationEncryptionBuilder":
+        if self is not PrivateFormat.OpenSSH:
+            raise ValueError(
+                "encryption_builder only supported with PrivateFormat.OpenSSH"
+            )
+        return KeySerializationEncryptionBuilder(self)
```

新增 `KeySerializationEncryptionBuilder.kdf_rounds()`：

```diff
+class KeySerializationEncryptionBuilder(object):
+    def __init__(
+        self,
+        format: PrivateFormat,
+        *,
+        _kdf_rounds: typing.Optional[int] = None,
+    ) -> None:
+        self._format = format
+        self._kdf_rounds = _kdf_rounds
+
+    def kdf_rounds(self, rounds: int) -> "KeySerializationEncryptionBuilder":
+        if self._kdf_rounds is not None:
+            raise ValueError("kdf_rounds already set")
+        return KeySerializationEncryptionBuilder(
+            self._format, _kdf_rounds=rounds
+        )
```

并用内部 `_KeySerializationEncryption` 携带 format、password 和 kdf_rounds：

```diff
+class _KeySerializationEncryption(KeySerializationEncryption):
+    def __init__(
+        self,
+        format: PrivateFormat,
+        password: bytes,
+        *,
+        kdf_rounds: typing.Optional[int],
+    ):
+        self._format = format
+        self.password = password
+        self._kdf_rounds = kdf_rounds
```

### 3.2 Export 层：让内部 encryption object 可被 backend/ssh 使用

`src/cryptography/hazmat/primitives/serialization/__init__.py` 导出 `_KeySerializationEncryption`：

```diff
 from cryptography.hazmat.primitives._serialization import (
     Encoding,
     KeySerializationEncryption,
     NoEncryption,
     ParameterFormat,
     PrivateFormat,
     PublicFormat,
+    _KeySerializationEncryption,
 )
```

### 3.3 Backend 层：接受新的 encryption object 并转发

`src/cryptography/hazmat/backends/openssl/backend.py` 在 `_private_key_bytes` 中识别 OpenSSH 专用 encryption object：

```diff
+        elif (
+            isinstance(
+                encryption_algorithm, serialization._KeySerializationEncryption
+            )
+            and encryption_algorithm._format
+            is format
+            is serialization.PrivateFormat.OpenSSH
+        ):
+            password = encryption_algorithm.password
```

然后把整个 `encryption_algorithm` 传给 SSH serializer：

```diff
         if format is serialization.PrivateFormat.OpenSSH:
             if encoding is serialization.Encoding.PEM:
-                return ssh.serialize_ssh_private_key(key, password)
+                return ssh._serialize_ssh_private_key(
+                    key, password, encryption_algorithm
+                )
```

### 3.4 OpenSSH serializer 层：真正使用 kdf_rounds

`src/cryptography/hazmat/primitives/serialization/ssh.py` 把 serializer 改成接收 encryption algorithm：

```diff
-def serialize_ssh_private_key(
+def _serialize_ssh_private_key(
     private_key: _SSH_PRIVATE_KEY_TYPES,
-    password: typing.Optional[bytes] = None,
+    password: bytes,
+    encryption_algorithm: KeySerializationEncryption,
 ) -> bytes:
```

在 bcrypt KDF options 中覆盖默认 rounds：

```diff
         rounds = _DEFAULT_ROUNDS
+        if (
+            isinstance(encryption_algorithm, _KeySerializationEncryption)
+            and encryption_algorithm._kdf_rounds is not None
+        ):
+            rounds = encryption_algorithm._kdf_rounds
         salt = os.urandom(16)
         f_kdfoptions.put_sshstr(salt)
         f_kdfoptions.put_u32(rounds)
```

### 3.5 为什么这是“跨接口闭包”

这个 patch 不是“找到 `ssh.py` 改一个常量”这么简单。它必须同时满足：

1. public API 能表达 `kdf_rounds`；
2. API object 能携带 `format/password/kdf_rounds`；
3. backend 能识别这个新 encryption object；
4. backend 能把 object 传到 OpenSSH serializer；
5. serializer 能把 rounds 写入 OpenSSH KDF options；
6. 非 OpenSSH format 要拒绝 builder，避免污染其它 serialization 逻辑。

这就是“参数传播闭包”：新参数从入口到落地实现之间的所有中间层都必须闭合。

## 4. Gold module/function 的评估口径

当前三层评估把该样本映射成：

Gold files：

```text
src/cryptography/hazmat/backends/openssl/backend.py
src/cryptography/hazmat/primitives/_serialization.py
src/cryptography/hazmat/primitives/serialization/__init__.py
src/cryptography/hazmat/primitives/serialization/ssh.py
```

Gold modules：

```text
src/cryptography/hazmat/backends/openssl/backend.py::Backend
src/cryptography/hazmat/primitives/_serialization.py::Encoding
src/cryptography/hazmat/primitives/_serialization.py::PrivateFormat
src/cryptography/hazmat/primitives/_serialization.py::PublicFormat
src/cryptography/hazmat/primitives/serialization/ssh.py
```

Gold function：

```text
src/cryptography/hazmat/primitives/serialization/ssh.py::serialize_ssh_private_key
```

这里要注意一个评估限制：patch 新增了 `KeySerializationEncryptionBuilder`、`_KeySerializationEncryption` 等新实体，但旧版本 repo structure 中不存在这些新增函数/类，因此 function/module gold 无法完整表达“新增 API builder”这部分真实修改。这个案例也说明 function-level 指标要结合 eligible/coverage 解释，file-level 对这种跨接口改动更稳。

## 5. 各 baseline 结果

### 5.1 汇总表

| Baseline | 数据集 | file_rec@all | module_rec@all | function_rec@all | 主要表现 |
|---|---|---:|---:|---:|---|
| LocAgent / Qwen3-VL-8B | Omni full-candidates | 0.00 | 0.00 | 0.00 | 被 KDF、x509、keywrap 等无关符号带偏 |
| CoSIL / Qwen3-VL-8B | Omni full-candidates | 0.25 | 0.25 | 0.00 | 命中 `serialization/ssh.py`，但漏掉 API/export/backend |
| BM25-MMIR | Omni full-candidates | 0.75 | 0.20 | 0.00 | 命中 3/4 文件，但函数层和闭包关系不准 |

该样本不在当前本地 `omnigirl-unified60` Qwen 结果中，因此没有 GraphLocator/GALA unified60 的真实预测可展示。

## 6. LocAgent / Qwen3-VL-8B 轨迹分析

LocAgent 最终输出文件：

```text
src/cryptography/hazmat/primitives/keywrap.py
src/cryptography/utils.py
src/cryptography/hazmat/primitives/twofactor/hotp.py
src/cryptography/x509/ocsp.py
src/cryptography/x509/name.py
src/cryptography/x509/general_name.py
src/cryptography/x509/extensions.py
src/cryptography/x509/certificate_transparency.py
src/cryptography/x509/base.py
```

最终函数/实体里出现：

```text
src/cryptography/hazmat/primitives/keywrap.py::aes_key_wrap_with_padding
src/cryptography/hazmat/primitives/twofactor/hotp.py::_generate_uri
src/cryptography/x509/ocsp.py::issuer_key_hash
src/cryptography/x509/name.py::get_attributes_for_oid
src/cryptography/x509/extensions.py::AuthorityKeyIdentifier.from_issuer_public_key
src/cryptography/hazmat/primitives/kdf/kbkdf.py::KBKDFHMAC._prf
```

这些都不是 gold。

### 6.1 它一开始确实抓住了关键 token

真实轨迹中，LocAgent 先尝试搜索：

```text
assistant:
<function=search_code_snippets>
<parameter>search_terms</parameter>
<parameter>["BestAvailableEncryption", "kdf_rounds"]</parameter>
```

这一步方向是对的：`BestAvailableEncryption` 是 public API 入口，`kdf_rounds` 是新增参数。

### 6.2 但工具调用实际变成了“上下文自动填充”

轨迹里的工具返回：

```text
OBSERVATION:
search_code_snippets was called without search_terms or line_nums.
Auto-filled search_terms from the issue context:
['kdf_rounds', 'ssh-keygen',
 'flag. This PR permits the same parameterization through the',
 'class.\r\n\r\n### Open Questions\r\n- [] Should this parameter be passed through',
 'where it is generally not applicable or should another data structure e.g.',
 'be created and passed through',
 'at the level of',
 'because it is only applied in the']
Using multi-language default file pattern '**/*.py'.
```

这个片段很关键：模型写出了 `["BestAvailableEncryption", "kdf_rounds"]`，但工具层记录认为 search_terms 为空并触发了自动填充。自动填充出来的 query 混入了大量长句碎片，导致检索不是围绕 symbol 搜索，而是围绕 issue 长文本做弱匹配。

工具随后返回的 repository structure 结果集中，前排变成：

```text
src/cryptography/x509/ocsp.py
src/cryptography/x509/name.py
src/cryptography/x509/general_name.py
src/cryptography/x509/extensions.py
...
```

这解释了为什么最终输出大量 x509 文件。

### 6.3 出现错误实体拼接

后续轨迹中，LocAgent 调用：

```text
assistant:
<function=get_entity_contents>
<parameter>entity_names</parameter>
<parameter>['src/cryptography/hazmat/primitives/keywrap.py:BestAvailableEncryption']</parameter>
```

这是错误的实体组合。`BestAvailableEncryption` 不是 `keywrap.py` 中的实体，而属于 serialization 相关 API。这个错误说明当前 Agent 至少有两个缺口：

1. 没有验证 symbol 真实所属文件；
2. 搜索结果中的文件名和 issue 里的 symbol 被 LLM 拼成了一个不存在的 entity。

### 6.4 LocAgent 为什么完全失败

LocAgent 失败不是因为完全没看懂 issue，而是因为：

```text
正确 token -> 工具层 query 退化 -> 召回 x509/keywrap/kdf 泛相关文件
           -> symbol 所属文件未校验
           -> 最终从错误实体邻域输出
```

它缺少的是“参数传播图”而不是普通关键词理解。

对这个样本，合理搜索应该是：

```text
BestAvailableEncryption -> 定位 _serialization.py
PrivateFormat.OpenSSH -> 定位 serialization format API
private_bytes / _private_key_bytes -> 定位 backend.py
serialize_ssh_private_key -> 定位 ssh.py
kdf_rounds / _DEFAULT_ROUNDS -> 定位 OpenSSH serializer 中 KDF rounds 落点
```

而不是从 `kdf` 泛词扩散到 `pbkdf2/hkdf/scrypt/kbkdf` 或从 `key` 扩散到 `keywrap/x509`。

## 7. CoSIL / Qwen3-VL-8B 轨迹分析

CoSIL 输出：

```text
src/cryptography/hazmat/primitives/serialization/ssh.py
src/cryptography/hazmat/primitives/kdf/pbkdf2.py
src/cryptography/hazmat/primitives/kdf/hkdf.py
src/cryptography/hazmat/primitives/kdf/scrypt.py
src/cryptography/hazmat/primitives/kdf/__init__.py
```

对应指标：

| 指标 | relaxed | strict |
|---|---:|---:|
| file_rec@all | 0.25 | 0.25 |
| module_rec@all | 0.25 | 0.25 |
| function_rec@all | 0.00 | 0.00 |
| file_acc@15 | 1.00 | 0.00 |

这里 relaxed `file_acc@15=1.00` 是因为 top-15 中至少命中一个 gold 文件；strict `file_acc@15=0.00` 是因为没有覆盖全部 4 个 gold 文件。

CoSIL 日志中 prompt 包含了 issue 和仓库结构，其中能看到正确目录：

```text
src/
  cryptography/
    hazmat/
      backends/
        openssl/
          backend.py
      primitives/
        _serialization.py
        kdf/
          pbkdf2.py
          hkdf.py
          scrypt.py
        serialization/
          __init__.py
          ssh.py
```

最终 LLM 输出：

```text
src/cryptography/hazmat/primitives/serialization/ssh.py
src/cryptography/hazmat/primitives/kdf/__init__.py
src/cryptography/hazmat/primitives/kdf/pbkdf2.py
src/cryptography/hazmat/primitives/kdf/scrypt.py
src/cryptography/hazmat/primitives/kdf/hkdf.py
```

### 7.1 CoSIL 为什么部分成功

CoSIL 抓住了“OpenSSH private key encryption + KDF rounds”这个局部实现点，因此命中 `serialization/ssh.py`。

但它把 `kdf_rounds` 理解成“去 KDF 算法模块找实现”：

```text
pbkdf2.py
hkdf.py
scrypt.py
kdf/__init__.py
```

这在语义上不正确。OpenSSH private key encryption 这里不是要改通用 KDF 算法，而是要把 rounds 参数写入 OpenSSH serialization 的 bcrypt KDF options。

### 7.2 CoSIL 漏掉了什么

CoSIL 没有闭合这条链：

```text
BestAvailableEncryption / PrivateFormat.OpenSSH
  -> _KeySerializationEncryptionBuilder
  -> backend._private_key_bytes
  -> ssh._serialize_ssh_private_key
```

它只停在 `ssh.py` 和泛 KDF 文件，没有继续向上追踪 public API，也没有向中间层追踪 backend dispatch。

因此它适合“局部实现定位”，不擅长“新增参数跨接口传播”。

## 8. BM25-MMIR 结果分析

BM25-MMIR top 文件：

```text
src/_cffi_src/build_openssl.py
src/cryptography/hazmat/primitives/serialization/ssh.py
src/cryptography/hazmat/primitives/kdf/kbkdf.py
src/cryptography/hazmat/bindings/openssl/binding.py
src/cryptography/hazmat/primitives/_serialization.py
src/cryptography/hazmat/backends/openssl/backend.py
src/cryptography/hazmat/primitives/asymmetric/rsa.py
setup.py
src/cryptography/x509/name.py
src/rust/src/x509/ocsp_req.rs
tests/hazmat/primitives/test_serialization.py
release.py
tests/utils.py
src/rust/src/lib.rs
tests/hazmat/primitives/test_pkcs7.py
```

BM25 命中了 3 个 gold 文件：

```text
src/cryptography/hazmat/primitives/serialization/ssh.py
src/cryptography/hazmat/primitives/_serialization.py
src/cryptography/hazmat/backends/openssl/backend.py
```

但漏掉：

```text
src/cryptography/hazmat/primitives/serialization/__init__.py
```

指标：

| 指标 | 值 |
|---|---:|
| file_rec@all | 0.75 |
| module_rec@all | 0.20 |
| function_rec@all | 0.00 |

### 8.1 BM25 为什么 file-level 较好

这个 issue 文本里出现了强词：

```text
OpenSSH
private keys
encryption
kdf_rounds
BestAvailableEncryption
ssh-keygen
```

这些词足以把 BM25 拉到 `ssh.py`、`_serialization.py`、`backend.py` 附近。

### 8.2 BM25 为什么 function/module 不行

BM25 的 function 预测包括：

```text
src/cryptography/hazmat/backends/openssl/backend.py::_zero_data
src/cryptography/hazmat/backends/openssl/backend.py::_zeroed_bytearray
src/cryptography/hazmat/backends/openssl/backend.py::_zeroed_null_terminated_buf
src/cryptography/hazmat/primitives/kdf/kbkdf.py::derive
```

真实 function gold 是：

```text
src/cryptography/hazmat/primitives/serialization/ssh.py::serialize_ssh_private_key
```

BM25 能找到文件邻域，但无法判断“哪个函数承载了参数落地”。它会被 `bytes`、`openssl`、`kdf`、`key` 等词吸引到相近但错误的函数。

这说明 lexical retrieval 适合召回候选文件，不适合独立解决跨接口闭包和函数级定位。

## 9. 这个案例暴露出的共性问题

### 9.1 URL 是需求来源，不是 patch target

外部 URL 指向 Ansible issue。它告诉我们用户想在 Ansible 的 `openssh_keypair` 中设置 KDF rounds，但真正修改在 `cryptography` 的 serialization API。

Baseline 如果只把 URL 摘要当作普通文本，会得到：

```text
openssh_keypair
ed25519
ssh-keygen
kdf
private key
```

这些词可以召回 `ssh.py`，但不足以推导出 `_serialization.py` 和 `backend.py` 必须修改。

### 9.2 新参数需要“接口传播闭包”

正确推理应该显式检查：

```text
参数在哪里被用户设置？
参数封装进哪个 object？
哪个 backend 接受这个 object？
哪个 format-specific serializer 使用这个 object？
最终是否写入 OpenSSH KDF options？
```

当前 baseline 多数只做“相关文件排序”，没有验证参数是否从入口传到落点。

### 9.3 Symbol 所属文件必须强校验

LocAgent 的：

```text
src/cryptography/hazmat/primitives/keywrap.py:BestAvailableEncryption
```

是一个典型错误：LLM 把一个文件和一个不属于该文件的 symbol 拼到一起。对 Agent 框架来说，所有 entity 查询都应该经过 symbol table 校验：

```text
if symbol not in file.symbols:
    reject entity query
    search symbol globally
```

否则工具会围绕错误实体继续扩散。

### 9.4 不能把 KDF 词直接映射到 KDF 模块

CoSIL 输出 `pbkdf2.py/hkdf.py/scrypt.py`，说明模型把 `kdf_rounds` 误解为通用 KDF 算法修改。

但这里的 KDF rounds 是 OpenSSH private key file format 中的 bcrypt KDF option，不是 cryptography 通用 KDF primitive 的行为。

因此需要区分：

```text
domain term: KDF rounds
implementation locus: OpenSSH serialization format
not necessarily: hazmat/primitives/kdf/*
```

## 10. 对框架设计的启发

这个样本建议引入一个专门的“参数传播闭包检查器”。

### 10.1 参数传播图

构图时应识别以下节点和边：

```text
Parameter(kdf_rounds)
  -> API method: PrivateFormat.OpenSSH.encryption_builder()
  -> Builder method: KeySerializationEncryptionBuilder.kdf_rounds()
  -> Internal object: _KeySerializationEncryption
  -> Backend method: Backend._private_key_bytes
  -> Serializer: ssh._serialize_ssh_private_key
  -> Sink: f_kdfoptions.put_u32(rounds)
```

边类型：

```text
defines_parameter
stores_parameter
passes_object
checks_format
dispatches_to_format_serializer
writes_protocol_field
```

### 10.2 Agent 搜索策略

Agent 不应该只搜索：

```text
kdf_rounds
ssh-keygen
encryption
```

而应该拆成四组 query：

Public API：

```text
BestAvailableEncryption
PrivateFormat OpenSSH
KeySerializationEncryption
encryption_builder
```

Backend dispatch：

```text
private_bytes
_private_key_bytes
serialization PrivateFormat.OpenSSH
```

Serializer sink：

```text
serialize_ssh_private_key
_DEFAULT_ROUNDS
put_u32 rounds
bcrypt kdfoptions
```

Parameter closure：

```text
kdf_rounds password format encryption_algorithm
```

### 10.3 候选文件选择规则

这类样本的候选集合不应该只按单文件相关性排序，而应该按链路覆盖：

```text
是否包含 API 入口？
是否包含参数 carrier object？
是否包含 backend dispatch？
是否包含 format-specific sink？
```

一个更合理的 top 文件集合是：

```text
src/cryptography/hazmat/primitives/_serialization.py
src/cryptography/hazmat/primitives/serialization/__init__.py
src/cryptography/hazmat/backends/openssl/backend.py
src/cryptography/hazmat/primitives/serialization/ssh.py
```

即使 `__init__.py` 词法相关性低，也应该因为 export closure 被加入。

### 10.4 Verifier 设计

最终 verifier 应该问：

```text
如果只改 ssh.py，用户能通过 BestAvailableEncryption 设置 kdf_rounds 吗？
如果只改 _serialization.py，backend 会把参数传给 ssh serializer 吗？
如果不改 __init__.py，backend 能 import/use internal encryption object 吗？
如果不改 backend.py，serializer 能拿到 encryption_algorithm 吗？
```

只要有一个答案是否定的，就说明 patch target 集合没有闭合。

## 11. 论文动机表述

这个样本可以支撑一个明确的论文动机：

```text
现有定位方法往往把 issue localization 视为相关文件排序问题。
但在真实软件仓库中，许多改动是跨接口的参数传播或状态传播问题。
这类问题要求定位系统不仅找到与关键词相关的文件，还要验证新行为是否从 public API 入口传递到最终实现 sink。
```

可以把它归入：

```text
跨接口参数传播闭包失败
```

对应改进方向：

```text
从 keyword retrieval / graph expansion
升级为 evidence-guided parameter-flow closure localization。
```

## 12. 总结

`pyca__cryptography-7520` 的核心不是“哪个 KDF 文件要改”，而是：

```text
kdf_rounds 这个新参数如何从 BestAvailableEncryption 入口，
穿过 serialization API、backend dispatch，
最终落到 OpenSSH serializer 的 bcrypt KDF options。
```

Baseline 失败模式很清楚：

| 方法 | 失败点 |
|---|---|
| LocAgent | 初始 token 正确，但工具 query 退化和 symbol-file 错配导致漂移到 keywrap/x509 |
| CoSIL | 命中 `ssh.py`，但把 KDF 误解成通用 KDF primitive，漏掉 API 和 backend |
| BM25-MMIR | file-level 召回较好，但无法判断参数传播闭包和函数落点 |

因此，这个案例适合作为“多语言 Agent 框架需要参数流/接口闭包图”的代表样本。
