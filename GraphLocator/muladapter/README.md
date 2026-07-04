# GraphLocator muladapter

Local adapter for multilingual and multimodal benchmark inputs. This folder is
isolated from GraphLocator's core RDFS/CIG implementation.

Current smoke-test capabilities:

- append image/web URLs to issue text;
- optionally append CodeV-style image captions and web summaries with
  `MULADAPTER_MODE=codev_caption`;
- support short CodeV-style context with `MULADAPTER_MODE=codev_compact`, which
  is recommended for GraphLocator's prompt-sensitive search/CIG flow;
- cache image/web context under `muladapter/cache/` without preprocessing or
  modifying the source dataset;
- scan multilingual source files;
- export an adapter-side membership skeleton with file and symbol nodes;
- run isolated unit tests.

Useful modes:

- `MULADAPTER_MODE=off`: original issue text only.
- `MULADAPTER_MODE=url_only`: append image/web URLs only. This is the default.
- `MULADAPTER_MODE=codev_caption`: append CodeV-style image captions and web
  summaries.
- `MULADAPTER_MODE=codev_compact`: shorter Visual Summary / Expected-vs-Actual /
  Localization Clues context for GraphLocator.

For image captioning, set `MULADAPTER_MODEL`, `MULADAPTER_BASE_URL`, and
optionally `MULADAPTER_API_KEY`. Web links that look like patches, commits,
pull requests, or compare pages are not fetched in detail to avoid answer
leakage.

Run:

```bash
cd /home/like/locCode/GraphLocator
bash muladapter/runners/run_smoke_test.sh
```
