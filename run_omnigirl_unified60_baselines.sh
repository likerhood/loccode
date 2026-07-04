#!/usr/bin/env bash
set -euo pipefail

# Run all localization baselines on the exact same OmniGIRL 60-sample subset.
#
# Results are isolated under the shared experiment name:
#   LocAgent:     LocAgent/newtest/${EXP_NAME}/results/...
#   CoSIL:        CoSIL/newtest/${EXP_NAME}/results/...
#   GraphLocator: GraphLocator/newtest/${EXP_NAME}/results/...
#   GALA:         GALA/mytest/${EXP_NAME}/results/...
#   MM-IR:        MM-IR/results/${EXP_NAME}/bm25-mmir/...
#
# Useful switches:
#   RUN_GRAPHLOCATOR=0 bash run_omnigirl_unified60_baselines.sh
#   CLEAN_UNIFIED=1 bash run_omnigirl_unified60_baselines.sh

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXP_NAME="${EXP_NAME:-omnigirl-unified60}"
BENCHMARK="${BENCHMARK:-omnigirl}"
SAMPLE_SIZE="${SAMPLE_SIZE:-60}"
SEED="${SEED:-20260614}"
USED_LIST="${USED_LIST:-newtest_instances}"

MODEL="${MODEL:-openai/qwen3-vl-8b}"
VLM_MODEL="${VLM_MODEL:-qwen3-vl-8b}"
OPENAI_API_BASE="${OPENAI_API_BASE:-http://10.102.65.40:8002/v1}"
OPENAI_API_KEY="${OPENAI_API_KEY:-dummy}"

LOCAGENT_PY="${LOCAGENT_PY:-/home/like/miniconda3/envs/locagent/bin/python}"
COSIL_PY="${COSIL_PY:-${LOCAGENT_PY}}"
GRAPHLOCATOR_PY="${GRAPHLOCATOR_PY:-/home/like/miniconda3/envs/graphlocator/bin/python}"
GALA_PY="${GALA_PY:-${LOCAGENT_PY}}"
MMIR_PY="${MMIR_PY:-/home/like/miniconda3/envs/mmir/bin/python}"

RUN_LOCAGENT="${RUN_LOCAGENT:-1}"
RUN_COSIL="${RUN_COSIL:-1}"
RUN_GRAPHLOCATOR="${RUN_GRAPHLOCATOR:-1}"
RUN_GALA="${RUN_GALA:-1}"
RUN_MMIR="${RUN_MMIR:-1}"
CLEAN_UNIFIED="${CLEAN_UNIFIED:-0}"

SOURCE_JSONL="${SOURCE_JSONL:-}"
CANONICAL_ROOT="${ROOT_DIR}/LocAgent/newtest/${EXP_NAME}"
CANONICAL_DATA_DIR="${CANONICAL_ROOT}/data"
CANONICAL_SAMPLES="${CANONICAL_DATA_DIR}/samples.jsonl"
CANONICAL_STRUCTURE_DIR="${CANONICAL_ROOT}/repo_structures"

ensure_python() {
  local py="$1"
  local label="$2"
  if [[ ! -x "${py}" ]]; then
    echo "ERROR: ${label} python not found or not executable: ${py}" >&2
    exit 2
  fi
}

run_step() {
  local label="$1"
  shift
  echo
  echo "========== ${label} =========="
  "$@"
}

ensure_python "${LOCAGENT_PY}" "LocAgent"
ensure_python "${COSIL_PY}" "CoSIL"
ensure_python "${GRAPHLOCATOR_PY}" "GraphLocator"
ensure_python "${GALA_PY}" "GALA"
ensure_python "${MMIR_PY}" "MM-IR"

if [[ "${CLEAN_UNIFIED}" == "1" || "${CLEAN_UNIFIED}" == "true" ]]; then
  echo "[clean] removing previous unified outputs"
  rm -rf \
    "${ROOT_DIR}/LocAgent/newtest/${EXP_NAME}" \
    "${ROOT_DIR}/CoSIL/newtest/${EXP_NAME}" \
    "${ROOT_DIR}/GraphLocator/newtest/${EXP_NAME}" \
    "${ROOT_DIR}/GALA/mytest/${EXP_NAME}" \
    "${ROOT_DIR}/MM-IR/results/${EXP_NAME}"
fi

mkdir -p "${CANONICAL_DATA_DIR}" "${CANONICAL_STRUCTURE_DIR}"

echo "Unified OmniGIRL experiment: ${EXP_NAME}"
echo "Canonical samples: ${CANONICAL_SAMPLES}"
echo "Canonical structures: ${CANONICAL_STRUCTURE_DIR}"

PREPARE_ARGS=(
  newtest/scripts/prepare_multimodal_localization.py
  --benchmark "${BENCHMARK}"
  --sample-size "${SAMPLE_SIZE}"
  --seed "${SEED}"
  --output-dir "${CANONICAL_DATA_DIR}"
  --used-list-name "${USED_LIST}"
  --allow-text-only
)
if [[ -n "${SOURCE_JSONL}" ]]; then
  PREPARE_ARGS+=(--source-jsonl "${SOURCE_JSONL}")
fi

echo
echo "========== Prepare canonical OmniGIRL ${SAMPLE_SIZE} =========="
(
  cd "${ROOT_DIR}/LocAgent"
  OPENAI_API_BASE="${OPENAI_API_BASE}" OPENAI_API_KEY="${OPENAI_API_KEY}" \
    "${LOCAGENT_PY}" "${PREPARE_ARGS[@]}"
)

echo
echo "========== Build canonical repo_structures =========="
(
  cd "${ROOT_DIR}/LocAgent"
  "${LOCAGENT_PY}" newtest/scripts/build_repo_structures.py \
    --samples "${CANONICAL_SAMPLES}" \
    --output-dir "${CANONICAL_STRUCTURE_DIR}" \
    --repo-base-dir "repo_newtest_${EXP_NAME}" \
    --dataset "newtest_${EXP_NAME}" \
    --split train \
    --skip-existing
)

if [[ "${RUN_LOCAGENT}" == "1" || "${RUN_LOCAGENT}" == "true" ]]; then
  run_step "Run LocAgent on ${EXP_NAME}" \
    bash -c "cd '${ROOT_DIR}/LocAgent' && \
      PYTHON_BIN='${LOCAGENT_PY}' \
      OPENAI_API_KEY='${OPENAI_API_KEY}' \
      OPENAI_API_BASE='${OPENAI_API_BASE}' \
      MODEL='${MODEL}' \
      BENCHMARK='${BENCHMARK}' \
      TEST_NAME='${EXP_NAME}' \
      SAMPLE_SIZE='${SAMPLE_SIZE}' \
      SEED='${SEED}' \
      SOURCE_JSONL='${CANONICAL_SAMPLES}' \
      ALLOW_TEXT_ONLY=1 \
      LOCAGENT_STRUCTURE_DIR_OVERRIDE='${CANONICAL_STRUCTURE_DIR}' \
      NUM_PROCESSES='${LOCAGENT_NUM_PROCESSES:-1}' \
      NUM_SAMPLES='${LOCAGENT_NUM_SAMPLES:-5}' \
      MAX_ATTEMPT_NUM='${LOCAGENT_MAX_ATTEMPT_NUM:-12}' \
      RERUN_EMPTY_LOCATION='${LOCAGENT_RERUN_EMPTY_LOCATION:-1}' \
      BUILD_STRUCTURES=0 \
      bash newtest/scripts/run_locagent_swebench_multimodal_60.sh"
fi

if [[ "${RUN_COSIL}" == "1" || "${RUN_COSIL}" == "true" ]]; then
  run_step "Run CoSIL on ${EXP_NAME}" \
    bash -c "cd '${ROOT_DIR}/CoSIL' && \
      PYTHON_BIN='${COSIL_PY}' \
      OPENAI_API_KEY='${OPENAI_API_KEY}' \
      OPENAI_API_BASE='${OPENAI_API_BASE}' \
      MODEL='${MODEL}' \
      BENCHMARK='${BENCHMARK}' \
      TEST_NAME='${EXP_NAME}' \
      SAMPLE_SIZE='${SAMPLE_SIZE}' \
      SEED='${SEED}' \
      SOURCE_JSONL='${CANONICAL_SAMPLES}' \
      ALLOW_TEXT_ONLY=1 \
      STRUCTURE_DIR_OVERRIDE='${CANONICAL_STRUCTURE_DIR}' \
      BUILD_STRUCTURES=0 \
      bash newtest/scripts/run_cosil_swebench_multimodal_60.sh"
fi

if [[ "${RUN_GRAPHLOCATOR}" == "1" || "${RUN_GRAPHLOCATOR}" == "true" ]]; then
  run_step "Run GraphLocator on ${EXP_NAME}" \
    bash -c "cd '${ROOT_DIR}/GraphLocator' && \
      PYTHON_BIN='${GRAPHLOCATOR_PY}' \
      OPENAI_API_KEY='${OPENAI_API_KEY}' \
      OPENAI_API_BASE='${OPENAI_API_BASE}' \
      MODEL='${MODEL}' \
      BENCHMARK='${BENCHMARK}' \
      TEST_NAME='${EXP_NAME}' \
      SAMPLE_SIZE='${SAMPLE_SIZE}' \
      SEED='${SEED}' \
      SOURCE_JSONL='${CANONICAL_SAMPLES}' \
      ALLOW_TEXT_ONLY=1 \
      STRUCTURE_DIR='${CANONICAL_STRUCTURE_DIR}' \
      SKIP_EXIST='${GRAPHLOCATOR_SKIP_EXIST:-1}' \
      REBUILD_SKELETON='${GRAPHLOCATOR_REBUILD_SKELETON:-0}' \
      bash newtest/scripts/run_graphlocator_swebench_multimodal_60.sh"
fi

if [[ "${RUN_GALA}" == "1" || "${RUN_GALA}" == "true" ]]; then
  run_step "Run GALA on ${EXP_NAME}" \
    bash -c "cd '${ROOT_DIR}/GALA' && \
      PYTHON_BIN='${GALA_PY}' \
      OPENAI_API_KEY='${OPENAI_API_KEY}' \
      VLM_MODEL='${VLM_MODEL}' \
      VLM_BASE_URL='${OPENAI_API_BASE}' \
      TEXT_MODEL_NAME='${VLM_MODEL}' \
      TEXT_BASE_URL='${OPENAI_API_BASE}' \
      TEST_NAME='${EXP_NAME}' \
      INPUT_FILE='${CANONICAL_SAMPLES}' \
      SAMPLE_SIZE='${SAMPLE_SIZE}' \
      SEED='${SEED}' \
      ALLOW_NO_IMAGES=1 \
      ALLOW_NON_GALA_FILES=1 \
      ALLOW_MISSING_PATCH=1 \
      STRUCTURE_DIR='${CANONICAL_STRUCTURE_DIR}' \
      bash mytest/scripts/run_gala_omnigirl_js_ts_60_localization.sh"
fi

if [[ "${RUN_MMIR}" == "1" || "${RUN_MMIR}" == "true" ]]; then
  run_step "Run BM25-MMIR on ${EXP_NAME}" \
    bash -c "cd '${ROOT_DIR}/MM-IR' && \
      PYTHON_BIN='${MMIR_PY}' \
      METHOD='${MMIR_METHOD:-bm25-mmir}' \
      SAMPLE_FILE='${CANONICAL_SAMPLES}' \
      STRUCTURE_DIR='${CANONICAL_STRUCTURE_DIR}' \
      OUTPUT_DIR='${ROOT_DIR}/MM-IR/results/${EXP_NAME}/${MMIR_METHOD:-bm25-mmir}' \
      bash scripts/run_mmir_omnigirl_60.sh"
fi

cat <<EOF

All requested baselines finished for ${EXP_NAME}.

Result directories:
  LocAgent:      ${ROOT_DIR}/LocAgent/newtest/${EXP_NAME}/results
  CoSIL:         ${ROOT_DIR}/CoSIL/newtest/${EXP_NAME}/results
  GraphLocator:  ${ROOT_DIR}/GraphLocator/newtest/${EXP_NAME}/results
  GALA:          ${ROOT_DIR}/GALA/mytest/${EXP_NAME}/results
  MM-IR:         ${ROOT_DIR}/MM-IR/results/${EXP_NAME}

EOF
