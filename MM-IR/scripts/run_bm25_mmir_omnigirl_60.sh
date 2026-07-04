#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RESULT_DIR="${ROOT_DIR}/results/omnigirl-60/bm25-mmir"
LOG_DIR="${RESULT_DIR}/logs"
mkdir -p "${LOG_DIR}"

export METHOD=bm25-mmir
export LIMIT="${LIMIT:-0}"
export OUTPUT_DIR="${OUTPUT_DIR:-${RESULT_DIR}}"
export SAMPLE_FILE="${SAMPLE_FILE:-/home/like/locCode/LocAgent/newtest/omnigirl-60/data/samples.jsonl}"
export STRUCTURE_DIR="${STRUCTURE_DIR:-/home/like/locCode/LocAgent/newtest/omnigirl-60/repo_structures}"
if [[ -z "${PYTHON_BIN:-}" && -x /home/like/miniconda3/envs/mmir/bin/python ]]; then
  export PYTHON_BIN=/home/like/miniconda3/envs/mmir/bin/python
fi

echo "[BM25-MMIR] OmniGIRL 60"
echo "[BM25-MMIR] samples: ${SAMPLE_FILE}"
echo "[BM25-MMIR] structures: ${STRUCTURE_DIR}"
echo "[BM25-MMIR] output: ${OUTPUT_DIR}"

bash "${ROOT_DIR}/scripts/run_mmir_omnigirl_60.sh" 2>&1 | tee "${LOG_DIR}/run.log"

echo "[BM25-MMIR] OmniGIRL metrics:"
echo "${OUTPUT_DIR}/eval/metrics_3level.md"
