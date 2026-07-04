# GraphLocator Newtest Multimodal Localization

这个目录用于测试 GraphLocator 在 SWE-bench Multimodal / OmniGIRL 多模态 issue 上的迁移效果。

GraphLocator 原生 `--dataset_language` 只支持 `python/java`，因此这里第一阶段不改图结构，只通过 `muladapter` 增强 issue 文本，并复用原有图构建逻辑。对 JS/TS 前端仓库，这个运行更多是“兼容性/失败模式”测试。

```bash
SAMPLE_SIZE=2 MAX_SEARCH_TURN=1 MAX_CAUSAL_TURN=2 MULADAPTER_MODE=codev_compact MULADAPTER_MODEL=qwen3-vl-8b MULADAPTER_BASE_URL=http://10.102.65.40:8002/v1 bash newtest/scripts/run_graphlocator_swebench_multimodal_60.sh
```
