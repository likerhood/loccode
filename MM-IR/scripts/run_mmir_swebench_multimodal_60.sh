#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SAMPLE_FILE="${SAMPLE_FILE:-/home/like/locCode/LocAgent/newtest/swebench_multimodal-60/data/samples.jsonl}"
STRUCTURE_DIR="${STRUCTURE_DIR:-/home/like/locCode/LocAgent/newtest/swebench_multimodal-60/repo_structures}"
METHOD="${METHOD:-bm25-mmir}"
OUTPUT_DIR="${OUTPUT_DIR:-${ROOT_DIR}/results/swebench_multimodal-60/${METHOD}}"
LIMIT="${LIMIT:-0}"
DENSE_MODEL="${DENSE_MODEL:-}"
DENSE_BATCH_SIZE="${DENSE_BATCH_SIZE:-16}"
DENSE_DEVICE="${DENSE_DEVICE:-}"
if [[ -z "${PYTHON_BIN:-}" ]]; then
  if command -v python >/dev/null 2>&1; then
    PYTHON_BIN=python
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN=python3
  else
    PYTHON_BIN=/home/like/miniconda3/envs/locagent/bin/python
  fi
fi

export PYTHONPATH="${ROOT_DIR}:${PYTHONPATH:-}"

"${PYTHON_BIN}" -m mmir.cli locate \
  --samples "${SAMPLE_FILE}" \
  --structure-dir "${STRUCTURE_DIR}" \
  --output-dir "${OUTPUT_DIR}" \
  --method "${METHOD}" \
  --limit "${LIMIT}" \
  --dense-model "${DENSE_MODEL}" \
  --dense-batch-size "${DENSE_BATCH_SIZE}" \
  --dense-device "${DENSE_DEVICE}"

"${PYTHON_BIN}" -m mmir.evaluation.eval_3level \
  --samples "${SAMPLE_FILE}" \
  --predictions "${OUTPUT_DIR}/loc_results.json" \
  --structure-dir "${STRUCTURE_DIR}" \
  --output-dir "${OUTPUT_DIR}/eval" \
  --limit "${LIMIT}"

echo "MM-IR SWE-bench Multimodal results: ${OUTPUT_DIR}"
