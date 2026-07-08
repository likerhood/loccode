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
export GRAPHLOCATOR_TEXT_TOOLS="${GRAPHLOCATOR_TEXT_TOOLS:-1}"

BENCHMARK="${BENCHMARK:-swebench_multimodal}"
TEST_NAME="${TEST_NAME:-${BENCHMARK}-60}"
SAMPLE_SIZE="${SAMPLE_SIZE:-60}"
SEED="${SEED:-20260614}"
MODEL="${MODEL:-openai/qwen3-vl-8b}"
MODEL_TAG="${MODEL//\//_}"
export GRAPHLOCATOR_BACKEND_MODEL="${GRAPHLOCATOR_BACKEND_MODEL:-${MODEL}}"
if [[ "${GRAPHLOCATOR_BACKEND_MODEL}" != */* ]]; then
  export GRAPHLOCATOR_BACKEND_MODEL="openai/${GRAPHLOCATOR_BACKEND_MODEL}"
fi
SOURCE_JSONL="${SOURCE_JSONL:-}"
ALLOW_TEXT_ONLY="${ALLOW_TEXT_ONLY:-}"
DATASET_LANGUAGE="${DATASET_LANGUAGE:-auto}"
SEARCH_TOPK="${SEARCH_TOPK:-5}"
MAX_SEARCH_TURN="${MAX_SEARCH_TURN:-5}"
MAX_CAUSAL_TURN="${MAX_CAUSAL_TURN:-20}"
SKIP_EXIST="${SKIP_EXIST:-1}"
REBUILD_SKELETON="${REBUILD_SKELETON:-0}"
STRUCTURE_DIR="${STRUCTURE_DIR:-}"
if [[ -z "${STRUCTURE_DIR}" ]]; then
  LOC_CODE_ROOT="$(cd "${REPO_ROOT}/.." && pwd)"
  if [[ "${BENCHMARK}" == "swebench_multimodal" ]]; then
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

TEST_ROOT="${REPO_ROOT}/newtest/${TEST_NAME}"
DATA_DIR="${TEST_ROOT}/data"
DATASET_STEM="${TEST_NAME//[^A-Za-z0-9_]/_}"
REPO_PLAYGROUND="${TEST_ROOT}/repo_playground"
REPO_SKELETON="${TEST_ROOT}/repo_skeleton"
RESULT_DIR="${TEST_ROOT}/results/${MODEL_TAG}"
EVAL_DIR="${RESULT_DIR}/eval"
EVAL_STRICT_DIR="${RESULT_DIR}/eval_strict"

mkdir -p "${DATA_DIR}" "${REPO_PLAYGROUND}" "${REPO_SKELETON}" "${RESULT_DIR}" "${EVAL_DIR}" "${EVAL_STRICT_DIR}" "${REPO_ROOT}/datasets"

echo "[1/3] Prepare ${BENCHMARK} ${SAMPLE_SIZE}-sample data -> ${TEST_NAME}"
PREPARE_ARGS=(
  newtest/scripts/prepare_multimodal_localization.py
  --benchmark "${BENCHMARK}"
  --sample-size "${SAMPLE_SIZE}"
  --seed "${SEED}"
  --output-dir "${DATA_DIR}"
)
if [[ -n "${SOURCE_JSONL}" ]]; then
  PREPARE_ARGS+=(--source-jsonl "${SOURCE_JSONL}")
fi
if [[ "${ALLOW_TEXT_ONLY}" == "1" || "${ALLOW_TEXT_ONLY}" == "true" ]]; then
  PREPARE_ARGS+=(--allow-text-only)
fi
"${PYTHON_BIN}" "${PREPARE_ARGS[@]}"
cp "${DATA_DIR}/samples.jsonl" "${REPO_ROOT}/datasets/${DATASET_STEM}.jsonl"

if [[ "${GRAPHLOCATOR_ENSURE_TS_LIB:-1}" == "1" ]]; then
  echo "[tree-sitter] Ensure GraphLocator language library"
  "${PYTHON_BIN}" newtest/scripts/ensure_tree_sitter_lib.py
fi

export GIT_CONFIG_GLOBAL="${TEST_ROOT}/gitconfig"
touch "${GIT_CONFIG_GLOBAL}"
GITHUB_URL_PREFIX="${GITHUB_URL_PREFIX:-https://gh.xmly.dev/https://github.com}"
if [[ -n "${GITHUB_URL_PREFIX}" ]]; then
  git config --global "url.${GITHUB_URL_PREFIX%/}/.insteadOf" "https://github.com/"
fi

if [[ "${REBUILD_SKELETON}" == "1" || "${REBUILD_SKELETON}" == "true" ]]; then
  echo "Rebuild repo skeletons because REBUILD_SKELETON=${REBUILD_SKELETON}"
  rm -rf "${REPO_SKELETON}"
  mkdir -p "${REPO_SKELETON}"
fi

echo "[2/3] Run GraphLocator"
echo "GraphLocator display model: ${MODEL}"
echo "GraphLocator backend model: ${GRAPHLOCATOR_BACKEND_MODEL}"
ARGS=(
  --dataset_name "${DATASET_STEM}"
  --dataset_language "${DATASET_LANGUAGE}"
  --model_name "${GRAPHLOCATOR_BACKEND_MODEL}"
  --results_dir "${RESULT_DIR}"
  --repo_playground "${REPO_PLAYGROUND}"
  --repo_skeleton_path "${REPO_SKELETON}"
  --search_topk "${SEARCH_TOPK}"
  --max_search_turn "${MAX_SEARCH_TURN}"
  --max_causal_turn "${MAX_CAUSAL_TURN}"
)
if [[ -n "${STRUCTURE_DIR}" ]]; then
  ARGS+=(--structure_dir "${STRUCTURE_DIR}")
fi
if [[ "${SKIP_EXIST}" == "1" ]]; then
  ARGS+=(--skip_exist)
fi
"${PYTHON_BIN}" graphlocator.py "${ARGS[@]}"

echo "[3/3] Evaluate file-level localization"
"${PYTHON_BIN}" newtest/scripts/eval_file_level.py \
  --samples "${DATA_DIR}/samples.jsonl" \
  --pred-file "${RESULT_DIR}/loc_results.json" \
  --output-dir "${EVAL_DIR}"

if [[ -n "${STRUCTURE_DIR}" && -d "${STRUCTURE_DIR}" ]]; then
  "${PYTHON_BIN}" newtest/scripts/eval_3level_localization.py \
    --samples "${DATA_DIR}/samples.jsonl" \
    --pred-file "${RESULT_DIR}/loc_results.json" \
    --structure-dir "${STRUCTURE_DIR}" \
    --output-dir "${EVAL_DIR}"

  "${PYTHON_BIN}" newtest/scripts/eval_3level_localization_strict.py \
    --samples "${DATA_DIR}/samples.jsonl" \
    --pred-file "${RESULT_DIR}/loc_results.json" \
    --structure-dir "${STRUCTURE_DIR}" \
    --output-dir "${EVAL_STRICT_DIR}"
fi

echo "Done: ${EVAL_DIR}/metrics.md"
echo "Strict three-level metrics: ${EVAL_STRICT_DIR}/metrics_3level.md"
