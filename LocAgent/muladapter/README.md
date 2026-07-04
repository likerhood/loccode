# LocAgent muladapter

This folder contains a local, non-invasive adapter for multilingual and
multimodal benchmark inputs. It does not change LocAgent's core agent logic.

Current smoke-test capabilities:

- append image and web URLs to `problem_statement`;
- optionally build CodeV-style visual/web textual context with
  `MULADAPTER_MODE=codev_caption` or compact context with
  `MULADAPTER_MODE=codev_compact`;
- cache image/web context under `muladapter/cache/` without preprocessing or
  modifying the source dataset;
- scan common multilingual source files;
- extract lightweight file/symbol records;
- export LocAgent-style `repo_index/files.jsonl` and `repo_index/symbols.jsonl`;
- run isolated unit tests under `muladapter/tests`.

Useful modes:

- `MULADAPTER_MODE=off`: original issue text only.
- `MULADAPTER_MODE=url_only`: append image/web URLs only. This is the default.
- `MULADAPTER_MODE=codev_caption`: append CodeV-style image captions and web
  summaries.
- `MULADAPTER_MODE=codev_compact`: shorter CodeV-style context for fragile or
  prompt-length-sensitive baselines.

For image captioning, set `MULADAPTER_MODEL`, `MULADAPTER_BASE_URL`, and
optionally `MULADAPTER_API_KEY`. Web links that look like patches, commits,
pull requests, or compare pages are not fetched in detail to avoid answer
leakage.

Run:

```bash
cd /home/like/locCode/LocAgent
bash muladapter/runners/run_smoke_test.sh
```
