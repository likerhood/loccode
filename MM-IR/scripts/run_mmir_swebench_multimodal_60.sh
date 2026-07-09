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
DENSE_DEVICE_AUTO_FALLBACK="${DENSE_DEVICE_AUTO_FALLBACK:-1}"
MMIR_DENSE_FAIL_FAST="${MMIR_DENSE_FAIL_FAST:-1}"
if [[ -z "${PYTHON_BIN:-}" ]]; then
  if [[ -x /home/like/miniconda3/envs/mmir/bin/python ]]; then
    PYTHON_BIN=/home/like/miniconda3/envs/mmir/bin/python
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN=python
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN=python3
  else
    echo "ERROR: no python found. Set PYTHON_BIN=/path/to/python." >&2
    exit 2
  fi
fi

export PYTHONPATH="${ROOT_DIR}:${PYTHONPATH:-}"
export MMIR_DENSE_FAIL_FAST

if [[ "${METHOD}" != "bm25-mmir" ]]; then
  echo "[MM-IR] dense method: ${METHOD}"
  echo "[MM-IR] dense model override: ${DENSE_MODEL:-<default>}"
  echo "[MM-IR] dense device requested: ${DENSE_DEVICE:-auto}"
  echo "[MM-IR] dense batch size: ${DENSE_BATCH_SIZE}"
  echo "[MM-IR] HF_ENDPOINT: ${HF_ENDPOINT:-<default>}"
  echo "[MM-IR] TRANSFORMERS_CACHE: ${TRANSFORMERS_CACHE:-<default>}"
  "${PYTHON_BIN}" - <<'PY'
import torch
print("[MM-IR] torch:", torch.__version__)
print("[MM-IR] torch cuda available:", torch.cuda.is_available())
print("[MM-IR] torch cuda version:", getattr(torch.version, "cuda", None))
print("[MM-IR] torch device count:", torch.cuda.device_count())
PY
fi

fallback_enabled() {
  [[ "${DENSE_DEVICE_AUTO_FALLBACK}" != "0" && "${DENSE_DEVICE_AUTO_FALLBACK}" != "false" && "${DENSE_DEVICE_AUTO_FALLBACK}" != "no" ]]
}

if [[ "${METHOD}" != "bm25-mmir" && "${DENSE_DEVICE}" == cuda* ]] && fallback_enabled; then
  if ! "${PYTHON_BIN}" - <<'PY' >/dev/null 2>&1
import torch
raise SystemExit(0 if torch.cuda.is_available() else 1)
PY
  then
    echo "[MM-IR][warn] DENSE_DEVICE=${DENSE_DEVICE} requested, but torch cannot access CUDA in ${PYTHON_BIN}." >&2
    echo "[MM-IR][warn] Falling back to DENSE_DEVICE=cpu. Set DENSE_DEVICE_AUTO_FALLBACK=0 to fail instead." >&2
    DENSE_DEVICE="cpu"
  fi
fi

run_locate() {
  local device="$1"
  "${PYTHON_BIN}" -m mmir.cli locate \
    --samples "${SAMPLE_FILE}" \
    --structure-dir "${STRUCTURE_DIR}" \
    --output-dir "${OUTPUT_DIR}" \
    --method "${METHOD}" \
    --limit "${LIMIT}" \
    --dense-model "${DENSE_MODEL}" \
    --dense-batch-size "${DENSE_BATCH_SIZE}" \
    --dense-device "${device}"
}

if ! run_locate "${DENSE_DEVICE}"; then
  if [[ "${METHOD}" != "bm25-mmir" && "${DENSE_DEVICE}" == cuda* ]] && fallback_enabled; then
    echo "[MM-IR][warn] Dense run failed on ${DENSE_DEVICE}; retrying ${METHOD} on CPU." >&2
    echo "[MM-IR][warn] To fail instead, set DENSE_DEVICE_AUTO_FALLBACK=0." >&2
    DENSE_DEVICE="cpu"
    run_locate "${DENSE_DEVICE}"
  else
    exit 1
  fi
fi

"${PYTHON_BIN}" -m mmir.evaluation.eval_3level \
  --samples "${SAMPLE_FILE}" \
  --predictions "${OUTPUT_DIR}/loc_results.json" \
  --structure-dir "${STRUCTURE_DIR}" \
  --output-dir "${OUTPUT_DIR}/eval" \
  --limit "${LIMIT}"

"${PYTHON_BIN}" -m mmir.evaluation.eval_3level_strict \
  --samples "${SAMPLE_FILE}" \
  --predictions "${OUTPUT_DIR}/loc_results.json" \
  --structure-dir "${STRUCTURE_DIR}" \
  --output-dir "${OUTPUT_DIR}/eval_strict" \
  --limit "${LIMIT}"

echo "MM-IR SWE-bench Multimodal results: ${OUTPUT_DIR}"
echo "  relaxed metrics: ${OUTPUT_DIR}/eval/metrics_3level.md"
echo "  strict metrics:  ${OUTPUT_DIR}/eval_strict/metrics_3level.md"
