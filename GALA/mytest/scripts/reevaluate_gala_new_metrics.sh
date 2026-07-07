#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MYTEST_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${MYTEST_ROOT}/.." && pwd)"
cd "${REPO_ROOT}"

export PYTHONPATH="${PYTHONPATH:-}:${REPO_ROOT}:${SCRIPT_DIR}"

if [[ -z "${PYTHON_BIN:-}" ]]; then
  if [[ -n "${CONDA_PREFIX:-}" && -x "${CONDA_PREFIX}/bin/python" ]]; then
    PYTHON_BIN="${CONDA_PREFIX}/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  else
    PYTHON_BIN="python"
  fi
fi

VLM_MODEL="${VLM_MODEL:-qwen3-vl-8b}"
MODEL_TAG="${VLM_MODEL//\//_}"
TEST_NAME="${TEST_NAME:?Set TEST_NAME, for example test1/swebench-multimodal-60}"

TEST_ROOT="${MYTEST_ROOT}/${TEST_NAME}"
DATA_DIR="${TEST_ROOT}/data"
RESULT_DIR="${TEST_ROOT}/results/${MODEL_TAG}"
EVAL_DIR="${RESULT_DIR}/eval"
STRUCTURE_DIR="${STRUCTURE_DIR:-}"
if [[ -z "${STRUCTURE_DIR}" ]]; then
  LOC_CODE_ROOT="$(cd "${REPO_ROOT}/.." && pwd)"
  if [[ "${TEST_NAME}" == *"swebench"* ]]; then
    candidates=(
      "${LOC_CODE_ROOT}/MM-IR/data/swebench_multimodal-full-candidates/repo_structures"
      "${LOC_CODE_ROOT}/LocAgent/newtest/swebench_multimodal-60/repo_structures"
      "${LOC_CODE_ROOT}/CoSIL/newtest/swebench_multimodal-60/repo_structures"
    )
  else
    candidates=(
      "${LOC_CODE_ROOT}/MM-IR/data/omnigirl-full-candidates/repo_structures"
      "${LOC_CODE_ROOT}/LocAgent/newtest/omnigirl-60/repo_structures"
      "${LOC_CODE_ROOT}/CoSIL/newtest/omnigirl-60/repo_structures"
    )
  fi
  for candidate in "${candidates[@]}"; do
    if [[ -d "${candidate}" ]]; then
      STRUCTURE_DIR="${candidate}"
      break
    fi
  done
fi

if [[ ! -f "${DATA_DIR}/gt_files.json" ]]; then
  echo "Missing GT file: ${DATA_DIR}/gt_files.json" >&2
  exit 1
fi
if [[ ! -d "${RESULT_DIR}" ]]; then
  echo "Missing result dir: ${RESULT_DIR}" >&2
  exit 1
fi

EVAL_ARGS=(
  --result-dir "${RESULT_DIR}" \
  --gt-file "${DATA_DIR}/gt_files.json" \
  --samples "${DATA_DIR}/samples.json" \
  --output-dir "${EVAL_DIR}" \
  --loc-output "${RESULT_DIR}/loc_results.json"
)
if [[ -n "${STRUCTURE_DIR}" ]]; then
  EVAL_ARGS+=(--structure-dir "${STRUCTURE_DIR}")
fi
"${PYTHON_BIN}" "${SCRIPT_DIR}/eval_gala_localization.py" "${EVAL_ARGS[@]}"

echo "Metrics: ${EVAL_DIR}/metrics.md"
