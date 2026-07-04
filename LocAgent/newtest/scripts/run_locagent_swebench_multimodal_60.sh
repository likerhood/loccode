#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

export PYTHONPATH="${PYTHONPATH:-}:${REPO_ROOT}"
PYTHON_BIN="${PYTHON_BIN:-python}"

export OPENAI_API_KEY="${OPENAI_API_KEY:-dummy}"
export OPENAI_API_BASE="${OPENAI_API_BASE:-http://10.102.65.40:8002/v1}"
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
USED_LIST="${USED_LIST:-newtest_instances}"
SOURCE_JSONL="${SOURCE_JSONL:-}"
ALLOW_TEXT_ONLY="${ALLOW_TEXT_ONLY:-}"
NUM_PROCESSES="${NUM_PROCESSES:-1}"
NUM_SAMPLES="${NUM_SAMPLES:-1}"
EVAL_N_LIMIT="${EVAL_N_LIMIT:-0}"
RERUN_EMPTY_LOCATION="${RERUN_EMPTY_LOCATION:-0}"
MAX_ATTEMPT_NUM="${MAX_ATTEMPT_NUM:-1}"
BUILD_STRUCTURES="${BUILD_STRUCTURES:-1}"
REBUILD_STRUCTURES="${REBUILD_STRUCTURES:-0}"

TEST_ROOT="${REPO_ROOT}/newtest/${TEST_NAME}"
DATA_DIR="${TEST_ROOT}/data"
OUTPUT_DIR="${TEST_ROOT}/results/${MODEL_TAG}/location"
EVAL_DIR="${TEST_ROOT}/results/${MODEL_TAG}/eval"
# Keep LocAgent's structures isolated from CoSIL/other projects by default.
# Use LOCAGENT_STRUCTURE_DIR_OVERRIDE only when an explicit cross-project
# structure directory is intended.
STRUCTURE_DIR="${LOCAGENT_STRUCTURE_DIR_OVERRIDE:-${TEST_ROOT}/repo_structures}"

mkdir -p "${DATA_DIR}" "${OUTPUT_DIR}" "${EVAL_DIR}"

echo "[1/3] Prepare ${BENCHMARK} ${SAMPLE_SIZE}-sample data -> ${TEST_NAME}"
PREPARE_ARGS=(
  newtest/scripts/prepare_multimodal_localization.py
  --benchmark "${BENCHMARK}"
  --sample-size "${SAMPLE_SIZE}"
  --seed "${SEED}"
  --output-dir "${DATA_DIR}"
  --used-list-name "${USED_LIST}"
)
if [[ -n "${SOURCE_JSONL}" ]]; then
  PREPARE_ARGS+=(--source-jsonl "${SOURCE_JSONL}")
fi
if [[ "${ALLOW_TEXT_ONLY}" == "1" || "${ALLOW_TEXT_ONLY}" == "true" ]]; then
  PREPARE_ARGS+=(--allow-text-only)
fi
"${PYTHON_BIN}" "${PREPARE_ARGS[@]}"

CONFIG_FILE="config.toml"
CONFIG_BACKUP=""
if [[ -f "${CONFIG_FILE}" ]]; then
  CONFIG_BACKUP="$(mktemp)"
  cp "${CONFIG_FILE}" "${CONFIG_BACKUP}"
fi
restore_config() {
  if [[ -n "${CONFIG_BACKUP}" && -f "${CONFIG_BACKUP}" ]]; then
    cp "${CONFIG_BACKUP}" "${CONFIG_FILE}"
    rm -f "${CONFIG_BACKUP}"
  else
    rm -f "${CONFIG_FILE}"
  fi
}
trap restore_config EXIT INT TERM
cp "${DATA_DIR}/config.newtest.toml" "${CONFIG_FILE}"

echo "[2/3] Run LocAgent localization"
export LOCAGENT_REPO_CACHE_DIR="${LOCAGENT_REPO_CACHE_DIR:-repo_newtest_${TEST_NAME}}"
export LOCAGENT_REPO_CACHE_MODE="${LOCAGENT_REPO_CACHE_MODE:-shared}"
export GRAPH_INDEX_DIR="${GRAPH_INDEX_DIR:-index_data/newtest_${TEST_NAME}/graph_index_v2.3}"
export BM25_INDEX_DIR="${BM25_INDEX_DIR:-index_data/newtest_${TEST_NAME}/BM25_index_multilang}"
export LOCAGENT_STRUCTURE_DIR="${STRUCTURE_DIR}"
export LOCAGENT_MAX_OBSERVATION_CHARS="${LOCAGENT_MAX_OBSERVATION_CHARS:-24000}"
export LOCAGENT_MAX_SEARCH_RESULTS="${LOCAGENT_MAX_SEARCH_RESULTS:-8}"
export LOCAGENT_BM25_TOP_K="${LOCAGENT_BM25_TOP_K:-8}"

if [[ "${BUILD_STRUCTURES}" == "1" || "${BUILD_STRUCTURES}" == "true" ]]; then
  STRUCTURE_ARGS=(
    newtest/scripts/build_repo_structures.py
    --samples "${DATA_DIR}/samples.jsonl"
    --output-dir "${STRUCTURE_DIR}"
    --repo-base-dir "${LOCAGENT_REPO_CACHE_DIR}"
    --dataset "newtest_${TEST_NAME}"
    --split train
  )
  if [[ "${REBUILD_STRUCTURES}" != "1" && "${REBUILD_STRUCTURES}" != "true" ]]; then
    STRUCTURE_ARGS+=(--skip-existing)
  fi
  "${PYTHON_BIN}" "${STRUCTURE_ARGS[@]}"
fi

LOCALIZE_ARGS=(
  auto_search_main.py
  --dataset "${DATA_DIR}/samples.jsonl" \
  --split train \
  --used_list "${USED_LIST}" \
  --model "${MODEL}" \
  --localize \
  --merge \
  --output_folder "${OUTPUT_DIR}" \
  --eval_n_limit "${EVAL_N_LIMIT}" \
  --max_attempt_num "${MAX_ATTEMPT_NUM}" \
  --num_processes "${NUM_PROCESSES}" \
  --num_samples "${NUM_SAMPLES}" \
  --repo_cache_mode shared \
  --use_function_calling \
  --simple_desc
)
if [[ "${RERUN_EMPTY_LOCATION}" == "1" || "${RERUN_EMPTY_LOCATION}" == "true" ]]; then
  LOCALIZE_ARGS+=(--rerun_empty_location)
fi

"${PYTHON_BIN}" "${LOCALIZE_ARGS[@]}"

echo "[3/3] Evaluate file-level localization"
"${PYTHON_BIN}" newtest/scripts/eval_file_level.py \
  --samples "${DATA_DIR}/samples.jsonl" \
  --pred-file "${OUTPUT_DIR}/merged_loc_outputs_mrr.jsonl" \
  --output-dir "${EVAL_DIR}"

if [[ -n "${STRUCTURE_DIR}" && -d "${STRUCTURE_DIR}" ]]; then
  "${PYTHON_BIN}" newtest/scripts/eval_3level_localization.py \
    --samples "${DATA_DIR}/samples.jsonl" \
    --pred-file "${OUTPUT_DIR}/merged_loc_outputs_mrr.jsonl" \
    --structure-dir "${STRUCTURE_DIR}" \
    --output-dir "${EVAL_DIR}"
fi

echo "Done: ${EVAL_DIR}/metrics.md"
