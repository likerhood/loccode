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
#   FORCE_RERUN=1 bash run_omnigirl_unified60_baselines.sh
#   FORCE_PREPARE=1 FORCE_STRUCTURES=1 bash run_omnigirl_unified60_baselines.sh

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXP_NAME="${EXP_NAME:-omnigirl-unified60}"
BENCHMARK="${BENCHMARK:-omnigirl}"
SAMPLE_SIZE="${SAMPLE_SIZE:-60}"
SEED="${SEED:-20260614}"
USED_LIST="${USED_LIST:-newtest_instances}"

MODEL="${MODEL:-openai/qwen3-vl-8b}"
LITELLM_MODEL="${LITELLM_MODEL:-${MODEL}}"
if [[ "${LITELLM_MODEL}" != */* ]]; then
  LITELLM_MODEL="openai/${LITELLM_MODEL}"
fi
VLM_MODEL="${VLM_MODEL:-qwen3-vl-8b}"
OPENAI_API_BASE="${OPENAI_API_BASE:-http://10.102.65.40:8002/v1}"
OPENAI_API_KEY="${OPENAI_API_KEY:-dummy}"

CONDA_ENV_ROOT="${CONDA_ENV_ROOT:-}"

env_python_default() {
  local env_name="$1"
  if [[ -n "${CONDA_ENV_ROOT}" ]]; then
    echo "${CONDA_ENV_ROOT%/}/${env_name}/bin/python"
    return 0
  fi
  if command -v conda >/dev/null 2>&1; then
    local base
    base="$(conda info --base 2>/dev/null || true)"
    if [[ -n "${base}" && -x "${base}/envs/${env_name}/bin/python" ]]; then
      echo "${base}/envs/${env_name}/bin/python"
      return 0
    fi
  fi
  echo ""
}

LOCAGENT_PY="${LOCAGENT_PY:-$(env_python_default locagent)}"
COSIL_PY="${COSIL_PY:-$(env_python_default cosil)}"
GRAPHLOCATOR_PY="${GRAPHLOCATOR_PY:-$(env_python_default graphlocator)}"
GALA_PY="${GALA_PY:-$(env_python_default gala)}"
MMIR_PY="${MMIR_PY:-$(env_python_default mmir)}"

RUN_LOCAGENT="${RUN_LOCAGENT:-1}"
RUN_COSIL="${RUN_COSIL:-1}"
RUN_GRAPHLOCATOR="${RUN_GRAPHLOCATOR:-1}"
RUN_GALA="${RUN_GALA:-1}"
RUN_MMIR="${RUN_MMIR:-1}"
CLEAN_UNIFIED="${CLEAN_UNIFIED:-0}"
FORCE_RERUN="${FORCE_RERUN:-0}"
FORCE_PREPARE="${FORCE_PREPARE:-0}"
FORCE_STRUCTURES="${FORCE_STRUCTURES:-0}"

USER_SOURCE_JSONL="${SOURCE_JSONL:-}"
CANONICAL_ROOT="${ROOT_DIR}/LocAgent/newtest/${EXP_NAME}"
CANONICAL_DATA_DIR="${CANONICAL_ROOT}/data"
CANONICAL_SAMPLES="${CANONICAL_DATA_DIR}/samples.jsonl"
CANONICAL_STRUCTURE_DIR="${CANONICAL_ROOT}/repo_structures"
COSIL_STRUCTURE_DIR="${COSIL_STRUCTURE_DIR:-${ROOT_DIR}/CoSIL/newtest/${EXP_NAME}/repo_structures}"

resolve_prepare_source_jsonl() {
  if [[ -n "${USER_SOURCE_JSONL}" ]]; then
    if [[ ! -s "${USER_SOURCE_JSONL}" ]]; then
      echo "ERROR: SOURCE_JSONL was set but does not exist or is empty: ${USER_SOURCE_JSONL}" >&2
      echo "Unset SOURCE_JSONL to allow automatic local/HuggingFace preparation." >&2
      exit 2
    fi
    echo "${USER_SOURCE_JSONL}"
    return 0
  fi

  local candidate
  local candidates=(
    "${OMNIGIRL_SOURCE_JSONL:-}"
    "${ROOT_DIR}/LocAgent/test/OmniGIRL_small60/test60/samples.jsonl"
    "${ROOT_DIR}/OmniGIRL/omnigirl/harness/benchmark/OmniGIRL.json"
    "${ROOT_DIR}/MM-IR/data/omnigirl-full-candidates/source_omnigirl_full.jsonl"
    "${ROOT_DIR}/MM-IR/data/omnigirl-full-candidates/samples.jsonl"
  )
  for candidate in "${candidates[@]}"; do
    if [[ -n "${candidate}" && -s "${candidate}" ]]; then
      echo "${candidate}"
      return 0
    fi
  done

  echo ""
}

ensure_python() {
  local py="$1"
  local label="$2"
  if [[ ! -x "${py}" ]]; then
    echo "ERROR: ${label} python not found or not executable: ${py}" >&2
    exit 2
  fi
}

is_truthy() {
  [[ "${1:-}" == "1" || "${1:-}" == "true" || "${1:-}" == "yes" ]]
}

ensure_import() {
  local py="$1"
  local module="$2"
  local label="$3"
  if ! "${py}" -c "import ${module}" >/dev/null 2>&1; then
    echo "ERROR: ${label} python is missing required module '${module}': ${py}" >&2
    echo "       Set the correct *_PY variable or install the package in that environment." >&2
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

run_if_needed() {
  local label="$1"
  local markers="$2"
  shift 2
  if ! is_truthy "${FORCE_RERUN}"; then
    local all_done=1
    local marker
    IFS='|' read -r -a marker_list <<< "${markers}"
    for marker in "${marker_list[@]}"; do
      if [[ ! -s "${marker}" ]]; then
        all_done=0
        break
      fi
    done
    if [[ "${all_done}" == "1" ]]; then
      echo
      echo "========== Skip ${label} =========="
      echo "[skip] Found completed metrics:"
      for marker in "${marker_list[@]}"; do
        echo "[skip]   ${marker}"
      done
      echo "[skip] Use FORCE_RERUN=1 to rerun this baseline."
      return 0
    fi
  fi
  run_step "${label}" "$@"
}

sample_rows() {
  if [[ -f "${CANONICAL_SAMPLES}" ]]; then
    wc -l < "${CANONICAL_SAMPLES}" | tr -d ' '
  else
    echo 0
  fi
}

structure_rows() {
  if [[ -d "${CANONICAL_STRUCTURE_DIR}" ]]; then
    find "${CANONICAL_STRUCTURE_DIR}" -maxdepth 1 -type f -name '*.json' | wc -l | tr -d ' '
  else
    echo 0
  fi
}

ensure_python "${LOCAGENT_PY}" "LocAgent"
if is_truthy "${RUN_COSIL}"; then
  ensure_python "${COSIL_PY}" "CoSIL"
  ensure_import "${COSIL_PY}" "anthropic" "CoSIL"
fi
if is_truthy "${RUN_GRAPHLOCATOR}"; then
  ensure_python "${GRAPHLOCATOR_PY}" "GraphLocator"
fi
if is_truthy "${RUN_GALA}"; then
  ensure_python "${GALA_PY}" "GALA"
fi
if is_truthy "${RUN_MMIR}"; then
  ensure_python "${MMIR_PY}" "MM-IR"
fi

MODEL_TAG="${MODEL//\//_}"
GALA_MODEL_TAG="${VLM_MODEL//\//_}"
MMIR_METHOD_NAME="${MMIR_METHOD:-bm25-mmir}"

LOCAGENT_METRICS="${ROOT_DIR}/LocAgent/newtest/${EXP_NAME}/results/${MODEL_TAG}/eval/metrics_3level.md"
LOCAGENT_STRICT_METRICS="${ROOT_DIR}/LocAgent/newtest/${EXP_NAME}/results/${MODEL_TAG}/eval_strict/metrics_3level.md"
COSIL_METRICS="${ROOT_DIR}/CoSIL/newtest/${EXP_NAME}/results/${MODEL_TAG}/eval/metrics_3level.md"
COSIL_STRICT_METRICS="${ROOT_DIR}/CoSIL/newtest/${EXP_NAME}/results/${MODEL_TAG}/eval_strict/metrics_3level.md"
GRAPHLOCATOR_METRICS="${ROOT_DIR}/GraphLocator/newtest/${EXP_NAME}/results/${MODEL_TAG}/eval/metrics_3level.md"
GRAPHLOCATOR_STRICT_METRICS="${ROOT_DIR}/GraphLocator/newtest/${EXP_NAME}/results/${MODEL_TAG}/eval_strict/metrics_3level.md"
GALA_METRICS="${ROOT_DIR}/GALA/mytest/${EXP_NAME}/results/${GALA_MODEL_TAG}/eval/metrics_3level.md"
GALA_STRICT_METRICS="${ROOT_DIR}/GALA/mytest/${EXP_NAME}/results/${GALA_MODEL_TAG}/eval_strict/metrics_3level.md"
MMIR_METRICS="${ROOT_DIR}/MM-IR/results/${EXP_NAME}/${MMIR_METHOD_NAME}/eval/metrics_3level.md"
MMIR_STRICT_METRICS="${ROOT_DIR}/MM-IR/results/${EXP_NAME}/${MMIR_METHOD_NAME}/eval_strict/metrics_3level.md"

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

PREPARE_SOURCE_JSONL="$(resolve_prepare_source_jsonl)"
if [[ -n "${PREPARE_SOURCE_JSONL}" ]]; then
  echo "Prepare source: local JSONL ${PREPARE_SOURCE_JSONL}"
else
  echo "Prepare source: HuggingFace dataset fallback (Deep-Software-Analytics/OmniGIRL)"
  if [[ -n "${HF_ENDPOINT:-}" ]]; then
    echo "HF endpoint: ${HF_ENDPOINT}"
  fi
fi

PREPARE_ARGS=(
  newtest/scripts/prepare_multimodal_localization.py
  --benchmark "${BENCHMARK}"
  --sample-size "${SAMPLE_SIZE}"
  --seed "${SEED}"
  --output-dir "${CANONICAL_DATA_DIR}"
  --used-list-name "${USED_LIST}"
  --allow-text-only
)
if [[ -n "${PREPARE_SOURCE_JSONL}" ]]; then
  PREPARE_ARGS+=(--source-jsonl "${PREPARE_SOURCE_JSONL}")
fi

if ! is_truthy "${FORCE_PREPARE}" && [[ -s "${CANONICAL_SAMPLES}" ]] && [[ "$(sample_rows)" == "${SAMPLE_SIZE}" ]]; then
  echo
  echo "========== Skip Prepare canonical OmniGIRL ${SAMPLE_SIZE} =========="
  echo "[skip] Found ${CANONICAL_SAMPLES} with ${SAMPLE_SIZE} rows."
  echo "[skip] Use FORCE_PREPARE=1 to regenerate canonical samples."
else
  echo
  echo "========== Prepare canonical OmniGIRL ${SAMPLE_SIZE} =========="
  (
    cd "${ROOT_DIR}/LocAgent"
    OPENAI_API_BASE="${OPENAI_API_BASE}" OPENAI_API_KEY="${OPENAI_API_KEY}" \
      "${LOCAGENT_PY}" "${PREPARE_ARGS[@]}"
  )
fi

if ! is_truthy "${FORCE_STRUCTURES}" && [[ "$(structure_rows)" -ge "$(sample_rows)" ]] && [[ "$(sample_rows)" -gt 0 ]]; then
  echo
  echo "========== Skip Build canonical repo_structures =========="
  echo "[skip] Found $(structure_rows) structure files for $(sample_rows) samples."
  echo "[skip] Use FORCE_STRUCTURES=1 to rebuild canonical structures."
else
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
      --skip-existing \
      --continue-on-error
  )
fi

if is_truthy "${RUN_LOCAGENT}" || is_truthy "${RUN_COSIL}" || is_truthy "${RUN_GRAPHLOCATOR}" || is_truthy "${RUN_GALA}" || is_truthy "${RUN_MMIR}"; then
  echo
  echo "========== Delegate unified60 baseline execution =========="
  echo "[delegate] Reusing run_omnigirl_full_baselines.sh so resume/eval-only/CoSIL repair logic stays consistent."
  if [[ -z "${RUN_MMIR_METHODS:-}" ]]; then
    export RUN_MMIR_METHODS="${MMIR_METHOD_NAME}"
  fi
  exec env \
    EXP_NAME="${EXP_NAME}" \
    BENCHMARK="${BENCHMARK}" \
    SAMPLE_SIZE="${SAMPLE_SIZE}" \
    SEED="${SEED}" \
    MODEL="${MODEL}" \
    VLM_MODEL="${VLM_MODEL}" \
    TEXT_MODEL_NAME="${TEXT_MODEL_NAME:-${VLM_MODEL}}" \
    OPENAI_API_BASE="${OPENAI_API_BASE}" \
    OPENAI_API_KEY="${OPENAI_API_KEY}" \
    SOURCE_JSONL="${CANONICAL_SAMPLES}" \
    STRUCTURE_DIR="${CANONICAL_STRUCTURE_DIR}" \
    COSIL_STRUCTURE_DIR="${COSIL_STRUCTURE_DIR}" \
    LOCAGENT_PY="${LOCAGENT_PY}" \
    COSIL_PY="${COSIL_PY}" \
    GRAPHLOCATOR_PY="${GRAPHLOCATOR_PY}" \
    GALA_PY="${GALA_PY}" \
    MMIR_PY="${MMIR_PY}" \
    RUN_LOCAGENT="${RUN_LOCAGENT}" \
    RUN_COSIL="${RUN_COSIL}" \
    RUN_GRAPHLOCATOR="${RUN_GRAPHLOCATOR}" \
    RUN_GALA="${RUN_GALA}" \
    RUN_MMIR="${RUN_MMIR}" \
    RUN_MMIR_METHODS="${RUN_MMIR_METHODS}" \
    FORCE_RERUN="${FORCE_RERUN}" \
    DRY_RUN="${DRY_RUN:-0}" \
    "${ROOT_DIR}/run_omnigirl_full_baselines.sh"
fi

echo
echo "All baseline execution flags are disabled. Prepared canonical samples/structures only."
exit 0

if is_truthy "${RUN_LOCAGENT}"; then
  run_if_needed "Run LocAgent on ${EXP_NAME}" "${LOCAGENT_METRICS}|${LOCAGENT_STRICT_METRICS}" \
    bash -c "cd '${ROOT_DIR}/LocAgent' && \
      PYTHON_BIN='${LOCAGENT_PY}' \
      OPENAI_API_KEY='${OPENAI_API_KEY}' \
      OPENAI_API_BASE='${OPENAI_API_BASE}' \
      MODEL='${MODEL}' \
      LOCAGENT_MODEL='${LOCAGENT_MODEL:-}' \
      LOCAGENT_BACKEND_MODEL='${LOCAGENT_BACKEND_MODEL:-${LITELLM_MODEL}}' \
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

if is_truthy "${RUN_COSIL}"; then
  run_if_needed "Run CoSIL on ${EXP_NAME}" "${COSIL_METRICS}|${COSIL_STRICT_METRICS}" \
    bash -c "cd '${ROOT_DIR}/CoSIL' && \
      PYTHON_BIN='${COSIL_PY}' \
      OPENAI_API_KEY='${OPENAI_API_KEY}' \
      OPENAI_API_BASE='${OPENAI_API_BASE}' \
      MODEL='${MODEL}' \
      COSIL_BACKEND_MODEL='${COSIL_BACKEND_MODEL:-${LITELLM_MODEL}}' \
      BENCHMARK='${BENCHMARK}' \
      TEST_NAME='${EXP_NAME}' \
      SAMPLE_SIZE='${SAMPLE_SIZE}' \
      SEED='${SEED}' \
      SOURCE_JSONL='${CANONICAL_SAMPLES}' \
      ALLOW_TEXT_ONLY=1 \
      STRUCTURE_DIR_OVERRIDE='${COSIL_STRUCTURE_DIR}' \
      BUILD_STRUCTURES='${COSIL_BUILD_STRUCTURES:-1}' \
      REBUILD_STRUCTURES='${COSIL_REBUILD_STRUCTURES:-0}' \
      bash newtest/scripts/run_cosil_swebench_multimodal_60.sh"
fi

if is_truthy "${RUN_GRAPHLOCATOR}"; then
  run_if_needed "Run GraphLocator on ${EXP_NAME}" "${GRAPHLOCATOR_METRICS}|${GRAPHLOCATOR_STRICT_METRICS}" \
    bash -c "cd '${ROOT_DIR}/GraphLocator' && \
      PYTHON_BIN='${GRAPHLOCATOR_PY}' \
      OPENAI_API_KEY='${OPENAI_API_KEY}' \
      OPENAI_API_BASE='${OPENAI_API_BASE}' \
      MODEL='${MODEL}' \
      GRAPHLOCATOR_BACKEND_MODEL='${GRAPHLOCATOR_BACKEND_MODEL:-${LITELLM_MODEL}}' \
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

if is_truthy "${RUN_GALA}"; then
  GALA_OMNI_RUNNER="${GALA_OMNI_RUNNER:-mytest/scripts/run_gala_omnigirl_js_ts_60_localization.sh}"
  if [[ ! -f "${ROOT_DIR}/GALA/${GALA_OMNI_RUNNER}" ]]; then
    cat >&2 <<EOF
ERROR: GALA OmniGIRL runner not found:
  ${ROOT_DIR}/GALA/${GALA_OMNI_RUNNER}

This usually means the repository on this machine is stale or GALA/mytest/scripts
was not tracked by git. Pull the latest repository, or set GALA_OMNI_RUNNER to
an existing runner under GALA/.
EOF
    exit 2
  fi
  run_if_needed "Run GALA on ${EXP_NAME}" "${GALA_METRICS}|${GALA_STRICT_METRICS}" \
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
      bash '${GALA_OMNI_RUNNER}'"
fi

if is_truthy "${RUN_MMIR}"; then
  run_if_needed "Run MM-IR ${MMIR_METHOD_NAME} on ${EXP_NAME}" "${MMIR_METRICS}|${MMIR_STRICT_METRICS}" \
    bash -c "cd '${ROOT_DIR}/MM-IR' && \
      PYTHON_BIN='${MMIR_PY}' \
      METHOD='${MMIR_METHOD_NAME}' \
      DENSE_MODEL='${MMIR_DENSE_MODEL:-}' \
      DENSE_BATCH_SIZE='${MMIR_DENSE_BATCH_SIZE:-16}' \
      DENSE_DEVICE='${MMIR_DENSE_DEVICE:-${DENSE_DEVICE:-}}' \
      DENSE_DEVICE_AUTO_FALLBACK='${DENSE_DEVICE_AUTO_FALLBACK:-1}' \
      SAMPLE_FILE='${CANONICAL_SAMPLES}' \
      STRUCTURE_DIR='${CANONICAL_STRUCTURE_DIR}' \
      OUTPUT_DIR='${ROOT_DIR}/MM-IR/results/${EXP_NAME}/${MMIR_METHOD_NAME}' \
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

Completion markers:
  LocAgent:      ${LOCAGENT_METRICS}
                 ${LOCAGENT_STRICT_METRICS}
  CoSIL:         ${COSIL_METRICS}
                 ${COSIL_STRICT_METRICS}
  GraphLocator:  ${GRAPHLOCATOR_METRICS}
                 ${GRAPHLOCATOR_STRICT_METRICS}
  GALA:          ${GALA_METRICS}
                 ${GALA_STRICT_METRICS}
  MM-IR:         ${MMIR_METRICS}
                 ${MMIR_STRICT_METRICS}

Structure directories:
  Shared:        ${CANONICAL_STRUCTURE_DIR}
  CoSIL:         ${COSIL_STRUCTURE_DIR}

EOF
