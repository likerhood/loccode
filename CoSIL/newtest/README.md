# CoSIL Newtest Multimodal Localization

这个目录用于单独测试 CoSIL 在 SWE-bench Multimodal / OmniGIRL 这类多模态 issue 上的 file-level 定位效果。

新增逻辑只放在 `newtest/`：

- `scripts/prepare_multimodal_localization.py`：准备数据、增强 issue 文本、抽取 file-level GT。
- `scripts/eval_file_level.py`：统一计算 Acc@k / MRR / MAP / Empty。
- `scripts/run_cosil_swebench_multimodal_60.sh`：运行 CoSIL file-level localization。

默认使用 SWE-bench Multimodal `dev` split，因为它有公开 gold patch，可用于本地定位评估。

```bash
SAMPLE_SIZE=60 RUN_FUNCTION_LEVEL=0 MULADAPTER_MODE=codev_compact MULADAPTER_MODEL=qwen3-vl-8b MULADAPTER_BASE_URL=http://10.102.65.40:8002/v1 bash newtest/scripts/run_cosil_swebench_multimodal_60.sh
```
