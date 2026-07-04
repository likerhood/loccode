# LocAgent Newtest Multimodal Localization

这个目录用于单独测试 LocAgent 在 SWE-bench Multimodal / OmniGIRL 这类多模态 issue 上的 file-level 定位效果。

特点：

- 所有新增测试逻辑都放在 `newtest/`，不改 LocAgent 核心流程。
- 数据准备阶段会调用本仓库 `muladapter` 增强 `problem_statement`。
- `MULADAPTER_MODE=url_only` 只拼接图片/网页链接。
- `MULADAPTER_MODE=codev_compact` 会把图片/网页转成更短的 CodeV 风格上下文。
- GT 文件来自 gold patch，因此默认使用 SWE-bench Multimodal `dev` split。

快速 smoke test：

```bash
python newtest/tests/test_prepare_and_eval.py
```

运行 SWE-bench Multimodal 60：

```bash
SAMPLE_SIZE=60 MODEL=openai/qwen3-vl-8b MULADAPTER_MODE=codev_compact MULADAPTER_MODEL=qwen3-vl-8b MULADAPTER_BASE_URL=http://10.102.65.40:8002/v1 bash newtest/scripts/run_locagent_swebench_multimodal_60.sh
```
