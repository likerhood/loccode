# CoSIL muladapter

Local adapter for multilingual and multimodal benchmark inputs. New files stay
inside `muladapter/` and do not change CoSIL's two-stage localization logic.

Current smoke-test capabilities:

- append image/web URLs to issue text;
- optionally append CodeV-style image captions and web summaries with
  `MULADAPTER_MODE=codev_caption`;
- support compact multimodal context with `MULADAPTER_MODE=codev_compact`;
- cache image/web context under `muladapter/cache/` without preprocessing or
  modifying the source dataset;
- scan multilingual source files;
- export a CoSIL-compatible `repo_structures/<instance_id>.json` with `text`,
  `classes`, and `functions` fields;
- run isolated unit tests.

Useful modes:

- `MULADAPTER_MODE=off`: original issue text only.
- `MULADAPTER_MODE=url_only`: append image/web URLs only. This is the default.
- `MULADAPTER_MODE=codev_caption`: append CodeV-style image captions and web
  summaries.
- `MULADAPTER_MODE=codev_compact`: shorter CodeV-style context.

For image captioning, set `MULADAPTER_MODEL`, `MULADAPTER_BASE_URL`, and
optionally `MULADAPTER_API_KEY`. Web links that look like patches, commits,
pull requests, or compare pages are not fetched in detail to avoid answer
leakage. For CoSIL on JS/TS-heavy benchmarks, start with file-level localization
before relying on function-level outputs.

Run:

```bash
cd /home/like/locCode/CoSIL
bash muladapter/runners/run_smoke_test.sh
```
