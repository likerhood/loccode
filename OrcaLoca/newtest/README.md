# OrcaLoca Newtest Multimodal Localization

这个目录用于测试 OrcaLoca 在 SWE-bench Multimodal / OmniGIRL 多模态 issue 上的定位效果。

OrcaLoca 原生依赖 Docker/SWE-agent 环境，运行成本较高；这里的脚本只负责：

- 准备带 `muladapter` 增强文本的数据；
- 写入 OrcaLoca 数据集缓存，让 `evaluation/run.py` 可以按本地数据跑；
- 从 `evaluation/output.json` 或搜索输出中抽取 file-level 定位指标。

```bash
SAMPLE_SIZE=2 FINAL_STAGE=search MULADAPTER_MODE=codev_compact MULADAPTER_MODEL=qwen3-vl-8b MULADAPTER_BASE_URL=http://10.102.65.40:8002/v1 bash newtest/scripts/run_orcaloca_swebench_multimodal_60.sh
```
