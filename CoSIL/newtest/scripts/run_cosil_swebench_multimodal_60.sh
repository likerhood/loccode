#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

export PYTHONPATH="${PYTHONPATH:-}:${REPO_ROOT}"
PYTHON_BIN="${PYTHON_BIN:-python}"

run_cosil_module() {
  local module="$1"
  shift
  COSIL_FL_DIR="${REPO_ROOT}/CoSIL/fl" \
  COSIL_KEEP_NON_PYTHON="${COSIL_KEEP_NON_PYTHON:-1}" \
  "${PYTHON_BIN}" -c '
import os
import sys
import importlib
import CoSIL  # noqa: F401

fl_dir = os.environ["COSIL_FL_DIR"]
if fl_dir not in sys.path:
    sys.path.append(fl_dir)
module = sys.argv[1]
args = sys.argv[2:]
mod = importlib.import_module(module)
if os.environ.get("COSIL_KEEP_NON_PYTHON") == "1" and hasattr(mod, "filter_none_python"):
    mod.filter_none_python = lambda structure: None
sys.argv = [sys.argv[0]] + args
mod.main()
' "${module}" "$@"
}

export OPENAI_API_KEY="${OPENAI_API_KEY:-dummy}"
export OPENAI_API_BASE="${OPENAI_API_BASE:-http://10.102.65.40:8002/v1}"
export HF_ENDPOINT="${HF_ENDPOINT:-https://huggingface.co}"
export GITHUB_URL_PREFIX="${GITHUB_URL_PREFIX:-https://gh.xmly.dev/https://github.com}"
export MULADAPTER_MODE="${MULADAPTER_MODE:-codev_compact}"
export MULADAPTER_DEFAULT_MODE="${MULADAPTER_DEFAULT_MODE:-${MULADAPTER_MODE}}"
export MULADAPTER_MODEL="${MULADAPTER_MODEL:-qwen3-vl-8b}"
export MULADAPTER_BASE_URL="${MULADAPTER_BASE_URL:-${OPENAI_API_BASE}}"
export MULADAPTER_API_KEY="${MULADAPTER_API_KEY:-${OPENAI_API_KEY}}"

BENCHMARK="${BENCHMARK:-swebench_multimodal}"
TEST_NAME="${TEST_NAME:-${BENCHMARK}-60}"
SAMPLE_SIZE="${SAMPLE_SIZE:-60}"
SEED="${SEED:-20260614}"
MODEL="${MODEL:-openai/qwen3-vl-8b}"
MODEL_TAG="${MODEL//\//_}"
SOURCE_JSONL="${SOURCE_JSONL:-}"
NUM_THREADS="${NUM_THREADS:-1}"
RUN_FUNCTION_LEVEL="${RUN_FUNCTION_LEVEL:-0}"
BUILD_STRUCTURES="${BUILD_STRUCTURES:-1}"
COSIL_KEEP_NON_PYTHON="${COSIL_KEEP_NON_PYTHON:-1}"
REBUILD_STRUCTURES="${REBUILD_STRUCTURES:-0}"
ALLOW_TEXT_ONLY="${ALLOW_TEXT_ONLY:-}"
if [[ -z "${ALLOW_TEXT_ONLY}" && "${BENCHMARK}" == "omnigirl" ]]; then
  ALLOW_TEXT_ONLY="1"
fi

TEST_ROOT="${REPO_ROOT}/newtest/${TEST_NAME}"
DATA_DIR="${TEST_ROOT}/data"
STRUCTURE_DIR="${STRUCTURE_DIR_OVERRIDE:-${TEST_ROOT}/repo_structures}"
REPO_WORK_DIR="${TEST_ROOT}/repo_work"
RESULT_DIR="${TEST_ROOT}/results/${MODEL_TAG}"
FILE_OUT="${RESULT_DIR}/file_level"
FUNC_OUT="${RESULT_DIR}/func_level"
EVAL_DIR="${RESULT_DIR}/eval"

mkdir -p "${DATA_DIR}" "${STRUCTURE_DIR}" "${REPO_WORK_DIR}" "${RESULT_DIR}" "${EVAL_DIR}"

echo "[1/4] Prepare ${BENCHMARK} ${SAMPLE_SIZE}-sample data -> ${TEST_NAME}"
PREPARE_ARGS=(
  newtest/scripts/prepare_multimodal_localization.py
  --benchmark "${BENCHMARK}" \
  --sample-size "${SAMPLE_SIZE}" \
  --seed "${SEED}" \
  --output-dir "${DATA_DIR}"
)
if [[ -n "${SOURCE_JSONL}" ]]; then
  PREPARE_ARGS+=(--source-jsonl "${SOURCE_JSONL}")
fi
if [[ "${ALLOW_TEXT_ONLY}" == "1" || "${ALLOW_TEXT_ONLY}" == "true" ]]; then
  PREPARE_ARGS+=(--allow-text-only)
fi
"${PYTHON_BIN}" "${PREPARE_ARGS[@]}"

if [[ "${BUILD_STRUCTURES}" == "1" ]]; then
  echo "[2/4] Build repo structures"
  STRUCTURE_ARGS=(
    test/swebench-multimodal-60/build_repo_structures.py
    --samples "${DATA_DIR}/samples.jsonl" \
    --structure-dir "${STRUCTURE_DIR}" \
    --repo-work-dir "${REPO_WORK_DIR}"
  )
  if [[ "${REBUILD_STRUCTURES}" == "1" || "${REBUILD_STRUCTURES}" == "true" ]]; then
    STRUCTURE_ARGS+=(--force)
  fi
  "${PYTHON_BIN}" "${STRUCTURE_ARGS[@]}"
else
  echo "[2/4] Skip repo structure build"
fi

ROOT_STRUCTURE_LINK="${REPO_ROOT}/repo_structures"
if [[ -L "${ROOT_STRUCTURE_LINK}" ]]; then
  ln -sfn "${STRUCTURE_DIR}" "${ROOT_STRUCTURE_LINK}"
elif [[ ! -e "${ROOT_STRUCTURE_LINK}" ]]; then
  ln -s "${STRUCTURE_DIR}" "${ROOT_STRUCTURE_LINK}"
fi
export PROJECT_FILE_LOC="${STRUCTURE_DIR}"

echo "[3/4] Run CoSIL file-level localization"
run_cosil_module "CoSIL.fl.CoSIL_localize_file" \
  --file_level \
  --output_folder "${FILE_OUT}" \
  --num_threads "${NUM_THREADS}" \
  --model "${MODEL}" \
  --dataset "${DATA_DIR}/samples.jsonl" \
  --skip_existing

echo "[3.5/4] Normalize multi-language file-level outputs"
"${PYTHON_BIN}" newtest/scripts/normalize_file_level_outputs.py \
  --input "${FILE_OUT}/loc_outputs.jsonl" \
  --structure-dir "${STRUCTURE_DIR}"

if [[ "${RUN_FUNCTION_LEVEL}" == "1" ]]; then
  run_cosil_module "CoSIL.fl.CoSIL_localize_func" \
    --output_folder "${FUNC_OUT}" \
    --loc_file "${FILE_OUT}/loc_outputs.jsonl" \
    --output_file "loc_${MODEL_TAG}_func.jsonl" \
    --temperature 0.0 \
    --model "${MODEL}" \
    --dataset "${DATA_DIR}/samples.jsonl" \
    --skip_existing \
    --num_threads "${NUM_THREADS}"
fi

echo "[4/4] Evaluate file-level localization"
"${PYTHON_BIN}" newtest/scripts/eval_file_level.py \
  --samples "${DATA_DIR}/samples.jsonl" \
  --pred-file "${FILE_OUT}/loc_outputs.jsonl" \
  --output-dir "${EVAL_DIR}"

"${PYTHON_BIN}" newtest/scripts/eval_3level_localization.py \
  --samples "${DATA_DIR}/samples.jsonl" \
  --pred-file "${FILE_OUT}/loc_outputs.jsonl" \
  --structure-dir "${STRUCTURE_DIR}" \
  --output-dir "${EVAL_DIR}"

echo "Done: ${EVAL_DIR}/metrics.md"
