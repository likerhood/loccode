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

export OPENAI_API_KEY="${OPENAI_API_KEY:-dummy}"
export VLM_API_KEY="${VLM_API_KEY:-${OPENAI_API_KEY}}"
export TEXT_API_KEY="${TEXT_API_KEY:-${OPENAI_API_KEY}}"

VLM_MODEL="${VLM_MODEL:-qwen3-vl-8b}"
VLM_BASE_URL="${VLM_BASE_URL:-http://10.102.65.40:8002/v1}"
TEXT_MODEL_NAME="${TEXT_MODEL_NAME:-${VLM_MODEL}}"
TEXT_BASE_URL="${TEXT_BASE_URL:-${VLM_BASE_URL}}"
VLM_API_MODEL_NAME="${VLM_API_MODEL_NAME:-${VLM_MODEL}}"
TEXT_API_MODEL_NAME="${TEXT_API_MODEL_NAME:-${TEXT_MODEL_NAME}}"

DATASET="${DATASET:-SWE-bench/SWE-bench_Multimodal}"
SPLIT="${SPLIT:-dev}"
INPUT_FILE="${INPUT_FILE:-}"
SAMPLE_SIZE="${SAMPLE_SIZE:-60}"
SEED="${SEED:-20260625}"
MAX_WORKERS="${MAX_WORKERS:-1}"
CLONE_REPOS="${CLONE_REPOS:-1}"
DOWNLOAD_IMAGES="${DOWNLOAD_IMAGES:-1}"
RUN_IMAGE_IR="${RUN_IMAGE_IR:-1}"
REUSE_IMAGE_IR="${REUSE_IMAGE_IR:-1}"
RESUME_IMAGE_IR="${RESUME_IMAGE_IR:-1}"
FORCE_IMAGE_IR="${FORCE_IMAGE_IR:-0}"
CHECK_IMAGE_IR_COMPLETE="${CHECK_IMAGE_IR_COMPLETE:-1}"
RUN_BUILD_CODE_GRAPH="${RUN_BUILD_CODE_GRAPH:-1}"
RUN_ALIGN_CODE_GRAPH="${RUN_ALIGN_CODE_GRAPH:-1}"
FORCE_REBUILD="${FORCE_REBUILD:-0}"
GITHUB_MIRROR_PREFIX="${GITHUB_MIRROR_PREFIX:-${REPO_GITHUB_MIRROR_PREFIX:-https://gh.xmly.dev}}"
ALLOW_MISSING_PATCH="${ALLOW_MISSING_PATCH:-0}"
STRUCTURE_DIR="${STRUCTURE_DIR:-}"
if [[ -z "${STRUCTURE_DIR}" ]]; then
  LOC_CODE_ROOT="$(cd "${REPO_ROOT}/.." && pwd)"
  for candidate in \
    "${LOC_CODE_ROOT}/MM-IR/data/swebench_multimodal-full-candidates/repo_structures" \
    "${LOC_CODE_ROOT}/LocAgent/newtest/swebench_multimodal-60/repo_structures" \
    "${LOC_CODE_ROOT}/CoSIL/newtest/swebench_multimodal-60/repo_structures" \
    ; do
    if [[ -d "${candidate}" ]]; then
      STRUCTURE_DIR="${candidate}"
      break
    fi
  done
fi

MODEL_TAG="${VLM_MODEL//\//_}"
TEST_NAME="${TEST_NAME:-swebench-multimodal-60}"
TEST_ROOT="${MYTEST_ROOT}/${TEST_NAME}"
DATA_DIR="${TEST_ROOT}/data"
IMAGE_DIR="${IMAGE_DIR:-${TEST_ROOT}/images}"
REPO_DIR="${TEST_ROOT}/repos"
RESULT_DIR="${TEST_ROOT}/results/${MODEL_TAG}"
EVAL_DIR="${RESULT_DIR}/eval"
EVAL_STRICT_DIR="${RESULT_DIR}/eval_strict"

mkdir -p "${DATA_DIR}" "${IMAGE_DIR}" "${REPO_DIR}" "${RESULT_DIR}" "${EVAL_DIR}" "${EVAL_STRICT_DIR}"

echo "[1/6] Prepare SWE-bench Multimodal ${SAMPLE_SIZE}-sample localization subset"
PREPARE_ARGS=(
  --dataset "${DATASET}"
  --split "${SPLIT}"
  --sample-size "${SAMPLE_SIZE}"
  --seed "${SEED}"
  --output-dir "${DATA_DIR}"
)
if [[ -n "${INPUT_FILE}" ]]; then
  PREPARE_ARGS+=(--input-file "${INPUT_FILE}")
fi
if [[ "${ALLOW_MISSING_PATCH}" == "1" ]]; then
  PREPARE_ARGS+=(--allow-missing-patch)
fi
"${PYTHON_BIN}" "${SCRIPT_DIR}/prepare_swebench_multimodal_60.py" "${PREPARE_ARGS[@]}"

if [[ "${CLONE_REPOS}" == "1" ]]; then
  echo "[2/6] Clone repositories"
  "${PYTHON_BIN}" "${SCRIPT_DIR}/download_repos.py" \
    --samples "${DATA_DIR}/samples.json" \
    --repo-dir "${REPO_DIR}" \
    --github-mirror-prefix "${GITHUB_MIRROR_PREFIX}"
else
  echo "[2/6] Skip repository clone"
fi

if [[ "${DOWNLOAD_IMAGES}" == "1" ]]; then
  echo "[3/6] Download image assets"
  "${PYTHON_BIN}" "${SCRIPT_DIR}/download_images.py" \
    --input-data "${DATA_DIR}/samples.json" \
    --image-dir "${IMAGE_DIR}" \
    --failures-file "${DATA_DIR}/image_download_failures.json" \
    --retries "${IMAGE_DOWNLOAD_RETRIES:-3}" \
    --retry-sleep "${IMAGE_DOWNLOAD_RETRY_SLEEP:-10}" \
    --backoff "${IMAGE_DOWNLOAD_BACKOFF:-2}"
else
  echo "[3/6] Skip image download"
fi

if [[ "${RUN_IMAGE_IR}" == "1" ]]; then
  echo "[4/6] Check image IR completeness"
  IMAGE_IR_PATH="${RESULT_DIR}/image_ir_data.json"
  IMAGE_IR_REPORT="${RESULT_DIR}/image_ir_completeness.json"
  if [[ "${FORCE_IMAGE_IR}" != "1" && "${REUSE_IMAGE_IR}" == "1" && "${CHECK_IMAGE_IR_COMPLETE}" == "1" ]] && \
    "${PYTHON_BIN}" "${SCRIPT_DIR}/check_image_ir_complete.py" \
      --samples "${DATA_DIR}/samples.json" \
      --image-dir "${IMAGE_DIR}" \
      --image-ir "${IMAGE_IR_PATH}" \
      --report "${IMAGE_IR_REPORT}"; then
    echo "[4/6] Reuse complete image IR: ${IMAGE_IR_PATH}"
  else
    echo "[4/6] Generate/resume image IR"
    IR_ARGS=(
      --input_data "${DATA_DIR}/samples.json"
      --output_dir "${RESULT_DIR}"
      --image_dir "${IMAGE_DIR}"
      --result_path "${RESULT_DIR}"
      --model_name "${VLM_API_MODEL_NAME}"
      --base_url "${VLM_BASE_URL}"
      --max_workers "${MAX_WORKERS}"
    )
    if [[ "${RESUME_IMAGE_IR}" == "1" && "${FORCE_IMAGE_IR}" != "1" ]]; then
      IR_ARGS+=(--resume_existing)
    fi
    "${PYTHON_BIN}" main.py generate-image-ir "${IR_ARGS[@]}"
    if [[ "${CHECK_IMAGE_IR_COMPLETE}" == "1" ]]; then
      "${PYTHON_BIN}" "${SCRIPT_DIR}/check_image_ir_complete.py" \
        --samples "${DATA_DIR}/samples.json" \
        --image-dir "${IMAGE_DIR}" \
        --image-ir "${IMAGE_IR_PATH}" \
        --report "${IMAGE_IR_REPORT}"
    fi
  fi
else
  echo "[4/6] Skip image IR generation"
fi

REBUILD_ARGS=()
if [[ "${FORCE_REBUILD}" == "1" ]]; then
  REBUILD_ARGS+=(--force_rebuild)
fi

if [[ "${RUN_BUILD_CODE_GRAPH}" == "1" ]]; then
  echo "[5/6] Build GALA seed-file localization artifacts"
  "${PYTHON_BIN}" main.py build-code-graph \
    --input_data "${RESULT_DIR}/image_ir_data.json" \
    --output_dir "${RESULT_DIR}" \
    --image_dir "${IMAGE_DIR}" \
    --repo_path "${REPO_DIR}" \
    --model_name "${VLM_API_MODEL_NAME}" \
    --base_url "${VLM_BASE_URL}" \
    --result_path "${RESULT_DIR}" \
    --text_model_name "${TEXT_API_MODEL_NAME}" \
    --text_base_url "${TEXT_BASE_URL}" \
    --text_api_key "${TEXT_API_KEY}" \
    "${REBUILD_ARGS[@]}"
else
  echo "[5/6] Skip build-code-graph"
fi

if [[ "${RUN_ALIGN_CODE_GRAPH}" == "1" ]]; then
  echo "[6/6] Align image/code graph and evaluate localization"
  "${PYTHON_BIN}" main.py align-code-graph \
    --input_data "${RESULT_DIR}/image_ir_data.json" \
    --output_dir "${RESULT_DIR}" \
    --image_dir "${IMAGE_DIR}" \
    --repo_path "${REPO_DIR}" \
    --model_name "${VLM_API_MODEL_NAME}" \
    --base_url "${VLM_BASE_URL}" \
    --result_path "${RESULT_DIR}" \
    --text_model_name "${TEXT_API_MODEL_NAME}" \
    --text_base_url "${TEXT_BASE_URL}" \
    --text_api_key "${TEXT_API_KEY}" \
    "${REBUILD_ARGS[@]}"
else
  echo "[6/6] Skip align-code-graph"
fi

echo "[eval] Evaluate localization results"
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

STRICT_EVAL_ARGS=(
  --result-dir "${RESULT_DIR}" \
  --gt-file "${DATA_DIR}/gt_files.json" \
  --samples "${DATA_DIR}/samples.json" \
  --output-dir "${EVAL_STRICT_DIR}" \
  --loc-output "${RESULT_DIR}/loc_results.json"
)
if [[ -n "${STRUCTURE_DIR}" ]]; then
  STRICT_EVAL_ARGS+=(--structure-dir "${STRUCTURE_DIR}")
fi
"${PYTHON_BIN}" "${SCRIPT_DIR}/eval_gala_localization_strict.py" "${STRICT_EVAL_ARGS[@]}"

echo
echo "Done."
echo "Data: ${DATA_DIR}/samples.json"
echo "Images: ${IMAGE_DIR}"
echo "Repos: ${REPO_DIR}"
echo "Results: ${RESULT_DIR}"
echo "Metrics: ${EVAL_DIR}/metrics.md"
echo "Strict metrics: ${EVAL_STRICT_DIR}/metrics_3level.md"
