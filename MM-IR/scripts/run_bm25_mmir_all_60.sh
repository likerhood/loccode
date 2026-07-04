#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[BM25-MMIR] Running both 60-sample benchmarks sequentially"
echo "[BM25-MMIR] 1/2 SWE-bench Multimodal"
bash "${ROOT_DIR}/scripts/run_bm25_mmir_swebench_multimodal_60.sh"

echo
echo "[BM25-MMIR] 2/2 OmniGIRL"
bash "${ROOT_DIR}/scripts/run_bm25_mmir_omnigirl_60.sh"

echo
echo "[BM25-MMIR] Done."
echo "SWE-bench Multimodal metrics:"
echo "${ROOT_DIR}/results/swebench_multimodal-60/bm25-mmir/eval/metrics_3level.md"
echo "OmniGIRL metrics:"
echo "${ROOT_DIR}/results/omnigirl-60/bm25-mmir/eval/metrics_3level.md"
