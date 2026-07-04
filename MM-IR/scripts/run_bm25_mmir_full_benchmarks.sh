#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[BM25-MMIR full] Running SWE-bench Multimodal full eligible candidates"
BENCHMARK=swebench_multimodal \
SAMPLE_SIZE="${SAMPLE_SIZE:-0}" \
bash "${ROOT_DIR}/scripts/prepare_and_run_bm25_mmir_full_candidates.sh"

echo
echo "[BM25-MMIR full] Running OmniGIRL full eligible candidates"
BENCHMARK=omnigirl \
SAMPLE_SIZE="${SAMPLE_SIZE:-0}" \
bash "${ROOT_DIR}/scripts/prepare_and_run_bm25_mmir_full_candidates.sh"

echo
echo "[BM25-MMIR full] Done."
echo "SWE-bench Multimodal metrics:"
echo "${ROOT_DIR}/results/swebench_multimodal-full-candidates/bm25-mmir/eval/metrics_3level.md"
echo "OmniGIRL metrics:"
echo "${ROOT_DIR}/results/omnigirl-full-candidates/bm25-mmir/eval/metrics_3level.md"
