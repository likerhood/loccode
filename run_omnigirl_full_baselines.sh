#!/usr/bin/env bash
set -euo pipefail

# Run all localization baselines on the current runnable OmniGIRL full-candidates set.
#
# Default OmniGIRL full input is the local runnable candidate set:
#   MM-IR/data/omnigirl-full-candidates/samples.jsonl      (631 rows locally)
#   MM-IR/data/omnigirl-full-candidates/repo_structures/
#
# This is intentionally the "runnable full-candidates"口径, not raw OmniGIRL 959.
# Override SOURCE_JSONL / STRUCTURE_DIR if you prepare a different full set.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

EXP_NAME="${EXP_NAME:-omnigirl-full-candidates}"
BENCHMARK="${BENCHMARK:-omnigirl}"
SEED="${SEED:-20260614}"
USED_LIST="${USED_LIST:-omnigirl_full_candidate_instances}"

MODEL="${MODEL:-openai/qwen3-vl-8b}"
VLM_MODEL="${VLM_MODEL:-qwen3-vl-8b}"
TEXT_MODEL_NAME="${TEXT_MODEL_NAME:-${VLM_MODEL}}"
OPENAI_API_BASE="${OPENAI_API_BASE:-http://10.102.65.40:8002/v1}"
OPENAI_API_KEY="${OPENAI_API_KEY:-dummy}"
MULADAPTER_MODEL="${MULADAPTER_MODEL:-${VLM_MODEL}}"
MULADAPTER_BASE_URL="${MULADAPTER_BASE_URL:-${OPENAI_API_BASE}}"
MULADAPTER_API_KEY="${MULADAPTER_API_KEY:-${OPENAI_API_KEY}}"
VLM_BASE_URL="${VLM_BASE_URL:-${OPENAI_API_BASE}}"
VLM_API_KEY="${VLM_API_KEY:-${OPENAI_API_KEY}}"
TEXT_BASE_URL="${TEXT_BASE_URL:-${OPENAI_API_BASE}}"
TEXT_API_KEY="${TEXT_API_KEY:-${OPENAI_API_KEY}}"

RUN_LOCAGENT="${RUN_LOCAGENT:-1}"
RUN_COSIL="${RUN_COSIL:-1}"
RUN_GRAPHLOCATOR="${RUN_GRAPHLOCATOR:-1}"
RUN_GALA="${RUN_GALA:-1}"
RUN_MMIR="${RUN_MMIR:-1}"
RUN_MMIR_METHODS="${RUN_MMIR_METHODS:-bm25-mmir e5-mmir jina-code-v2-mmir codesage-large-v2-mmir coderankembed-mmir}"

CLEAN_FULL="${CLEAN_FULL:-0}"
FORCE_RERUN="${FORCE_RERUN:-0}"
DRY_RUN="${DRY_RUN:-0}"

SOURCE_JSONL="${SOURCE_JSONL:-${ROOT_DIR}/MM-IR/data/omnigirl-full-candidates/samples.jsonl}"
STRUCTURE_DIR="${STRUCTURE_DIR:-${ROOT_DIR}/MM-IR/data/omnigirl-full-candidates/repo_structures}"
COSIL_STRUCTURE_DIR="${COSIL_STRUCTURE_DIR:-${STRUCTURE_DIR}}"
CONDA_ENV_ROOT="${CONDA_ENV_ROOT:-}"

MODEL_TAG="${MODEL//\//_}"
GALA_MODEL_TAG="${VLM_MODEL//\//_}"

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

is_truthy() {
  [[ "${1:-}" == "1" || "${1:-}" == "true" || "${1:-}" == "yes" ]]
}

run_cmd() {
  echo "+ $*"
  if ! is_truthy "${DRY_RUN}"; then
    "$@"
  fi
}

run_shell() {
  local script="$1"
  echo "+ bash -lc ${script}"
  if ! is_truthy "${DRY_RUN}"; then
    bash -lc "${script}"
  fi
}

ensure_python() {
  local py="$1"
  local label="$2"
  if [[ -x "${py}" ]]; then
    return 0
  fi
  if is_truthy "${DRY_RUN}"; then
    echo "[dry-run warn] ${label} python not found yet: ${py:-<empty>}"
    return 0
  fi
  echo "ERROR: ${label} python not found or not executable: ${py:-<empty>}" >&2
  echo "Set ${label^^}_PY or run setup_baseline_conda_envs.sh first." >&2
  exit 2
}

ensure_import() {
  local py="$1"
  local module="$2"
  local label="$3"
  if is_truthy "${DRY_RUN}"; then
    return 0
  fi
  if ! "${py}" -c "import ${module}" >/dev/null 2>&1; then
    echo "ERROR: ${label} python is missing required module '${module}': ${py}" >&2
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

metric_pair() {
  local dir="$1"
  echo "${dir}/eval/metrics_3level.md|${dir}/eval_strict/metrics_3level.md"
}

metrics_complete() {
  local dir="$1"
  [[ -s "${dir}/eval/metrics_3level.md" && -s "${dir}/eval_strict/metrics_3level.md" ]]
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
      echo "[skip] Use FORCE_RERUN=1 to rerun."
      return 0
    fi
  fi
  run_step "${label}" "$@"
}

run_eval_if_possible() {
  local label="$1"
  local result_dir="$2"
  local pred_file="$3"
  local command="$4"
  if metrics_complete "${result_dir}" && ! is_truthy "${FORCE_RERUN}"; then
    echo
    echo "========== Skip ${label} eval =========="
    echo "[skip] Found ${result_dir}/eval/metrics_3level.md"
    echo "[skip] Found ${result_dir}/eval_strict/metrics_3level.md"
    return 0
  fi
  if [[ -s "${pred_file}" ]] && ! is_truthy "${FORCE_RERUN}"; then
    run_step "Evaluate existing ${label} predictions" run_shell "${command}"
    return 0
  fi
  return 1
}

sample_rows() {
  if [[ -f "${SOURCE_JSONL}" ]]; then
    wc -l < "${SOURCE_JSONL}" | tr -d ' '
  else
    echo 0
  fi
}

structure_rows() {
  if [[ -d "${STRUCTURE_DIR}" ]]; then
    find "${STRUCTURE_DIR}" -maxdepth 1 -type f -name '*.json' | wc -l | tr -d ' '
  else
    echo 0
  fi
}

ensure_inputs() {
  if [[ -s "${SOURCE_JSONL}" && -d "${STRUCTURE_DIR}" ]]; then
    return 0
  fi
  if is_truthy "${DRY_RUN}"; then
    [[ -s "${SOURCE_JSONL}" ]] || echo "[dry-run warn] Omni source JSONL not found: ${SOURCE_JSONL}"
    [[ -d "${STRUCTURE_DIR}" ]] || echo "[dry-run warn] Omni structure dir not found: ${STRUCTURE_DIR}"
    return 0
  fi
  [[ -s "${SOURCE_JSONL}" ]] || {
    echo "ERROR: Omni source JSONL not found: ${SOURCE_JSONL}" >&2
    echo "Prepare MM-IR/data/omnigirl-full-candidates first, or set SOURCE_JSONL=/path/to/samples.jsonl." >&2
    exit 2
  }
  [[ -d "${STRUCTURE_DIR}" ]] || {
    echo "ERROR: Omni structure dir not found: ${STRUCTURE_DIR}" >&2
    echo "Prepare repo_structures first, or set STRUCTURE_DIR=/path/to/repo_structures." >&2
    exit 2
  }
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
ensure_inputs

SAMPLE_COUNT="$(sample_rows)"
if [[ "${SAMPLE_COUNT}" == "0" ]] && is_truthy "${DRY_RUN}"; then
  SAMPLE_COUNT="${SAMPLE_SIZE:-631}"
fi
SAMPLE_SIZE="${SAMPLE_SIZE:-${SAMPLE_COUNT}}"

LOCAGENT_RESULT_DIR="${ROOT_DIR}/LocAgent/newtest/${EXP_NAME}/results/${MODEL_TAG}"
COSIL_RESULT_DIR="${ROOT_DIR}/CoSIL/newtest/${EXP_NAME}/results/${MODEL_TAG}"
GRAPHLOCATOR_RESULT_DIR="${ROOT_DIR}/GraphLocator/newtest/${EXP_NAME}/results/${MODEL_TAG}"
GALA_RESULT_DIR="${ROOT_DIR}/GALA/mytest/${EXP_NAME}/results/${GALA_MODEL_TAG}"

if is_truthy "${CLEAN_FULL}"; then
  echo "[clean] removing previous Omni full outputs"
  run_cmd rm -rf \
    "${ROOT_DIR}/LocAgent/newtest/${EXP_NAME}" \
    "${ROOT_DIR}/CoSIL/newtest/${EXP_NAME}" \
    "${ROOT_DIR}/GraphLocator/newtest/${EXP_NAME}" \
    "${ROOT_DIR}/GALA/mytest/${EXP_NAME}" \
    "${ROOT_DIR}/MM-IR/results/${EXP_NAME}"
fi

cat <<EOF
OmniGIRL full-candidates experiment: ${EXP_NAME}
Benchmark: ${BENCHMARK}
Source samples: ${SOURCE_JSONL}
Source sample rows: ${SAMPLE_COUNT}
Structure dir: ${STRUCTURE_DIR}
Structure files: $(structure_rows)
OpenAI-compatible endpoint: ${OPENAI_API_BASE}
Model: ${MODEL}
VLM model: ${VLM_MODEL}
Text model: ${TEXT_MODEL_NAME}
Dry run: ${DRY_RUN}
EOF

if is_truthy "${RUN_LOCAGENT}"; then
  LOCAGENT_PRED="${LOCAGENT_RESULT_DIR}/location/merged_loc_outputs_mrr.jsonl"
  LOCAGENT_EVAL_CMD="cd '${ROOT_DIR}/LocAgent' && \
      '${LOCAGENT_PY}' newtest/scripts/eval_file_level.py \
        --samples '${SOURCE_JSONL}' \
        --pred-file '${LOCAGENT_PRED}' \
        --output-dir '${LOCAGENT_RESULT_DIR}/eval' && \
      '${LOCAGENT_PY}' newtest/scripts/eval_3level_localization.py \
        --samples '${SOURCE_JSONL}' \
        --pred-file '${LOCAGENT_PRED}' \
        --structure-dir '${STRUCTURE_DIR}' \
        --output-dir '${LOCAGENT_RESULT_DIR}/eval' && \
      '${LOCAGENT_PY}' newtest/scripts/eval_3level_localization_strict.py \
        --samples '${SOURCE_JSONL}' \
        --pred-file '${LOCAGENT_PRED}' \
        --structure-dir '${STRUCTURE_DIR}' \
        --output-dir '${LOCAGENT_RESULT_DIR}/eval_strict'"
  if ! run_eval_if_possible "LocAgent" "${LOCAGENT_RESULT_DIR}" "${LOCAGENT_PRED}" "${LOCAGENT_EVAL_CMD}"; then
    run_if_needed "Run LocAgent on ${EXP_NAME}" "$(metric_pair "${LOCAGENT_RESULT_DIR}")" \
      run_shell "cd '${ROOT_DIR}/LocAgent' && \
        PYTHON_BIN='${LOCAGENT_PY}' \
        OPENAI_API_KEY='${OPENAI_API_KEY}' \
        OPENAI_API_BASE='${OPENAI_API_BASE}' \
        MULADAPTER_MODEL='${MULADAPTER_MODEL}' \
        MULADAPTER_BASE_URL='${MULADAPTER_BASE_URL}' \
        MULADAPTER_API_KEY='${MULADAPTER_API_KEY}' \
        MODEL='${MODEL}' \
        BENCHMARK='${BENCHMARK}' \
        TEST_NAME='${EXP_NAME}' \
        SAMPLE_SIZE='${SAMPLE_SIZE}' \
        SEED='${SEED}' \
        SOURCE_JSONL='${SOURCE_JSONL}' \
        ALLOW_TEXT_ONLY=1 \
        LOCAGENT_STRUCTURE_DIR_OVERRIDE='${STRUCTURE_DIR}' \
        NUM_PROCESSES='${LOCAGENT_NUM_PROCESSES:-1}' \
        NUM_SAMPLES='${LOCAGENT_NUM_SAMPLES:-1}' \
        MAX_ATTEMPT_NUM='${LOCAGENT_MAX_ATTEMPT_NUM:-12}' \
        RERUN_EMPTY_LOCATION='${LOCAGENT_RERUN_EMPTY_LOCATION:-1}' \
        BUILD_STRUCTURES=0 \
        bash newtest/scripts/run_locagent_swebench_multimodal_60.sh"
  fi
fi

if is_truthy "${RUN_COSIL}"; then
  COSIL_PRED="${COSIL_RESULT_DIR}/file_level/loc_outputs.jsonl"
  COSIL_EVAL_CMD="cd '${ROOT_DIR}/CoSIL' && \
      '${COSIL_PY}' newtest/scripts/eval_file_level.py \
        --samples '${SOURCE_JSONL}' \
        --pred-file '${COSIL_PRED}' \
        --output-dir '${COSIL_RESULT_DIR}/eval' && \
      '${COSIL_PY}' newtest/scripts/eval_3level_localization.py \
        --samples '${SOURCE_JSONL}' \
        --pred-file '${COSIL_PRED}' \
        --structure-dir '${COSIL_STRUCTURE_DIR}' \
        --output-dir '${COSIL_RESULT_DIR}/eval' && \
      '${COSIL_PY}' newtest/scripts/eval_3level_localization_strict.py \
        --samples '${SOURCE_JSONL}' \
        --pred-file '${COSIL_PRED}' \
        --structure-dir '${COSIL_STRUCTURE_DIR}' \
        --output-dir '${COSIL_RESULT_DIR}/eval_strict'"
  if ! run_eval_if_possible "CoSIL" "${COSIL_RESULT_DIR}" "${COSIL_PRED}" "${COSIL_EVAL_CMD}"; then
    run_if_needed "Run CoSIL on ${EXP_NAME}" "$(metric_pair "${COSIL_RESULT_DIR}")" \
      run_shell "cd '${ROOT_DIR}/CoSIL' && \
        PYTHON_BIN='${COSIL_PY}' \
        OPENAI_API_KEY='${OPENAI_API_KEY}' \
        OPENAI_API_BASE='${OPENAI_API_BASE}' \
        MULADAPTER_MODEL='${MULADAPTER_MODEL}' \
        MULADAPTER_BASE_URL='${MULADAPTER_BASE_URL}' \
        MULADAPTER_API_KEY='${MULADAPTER_API_KEY}' \
        MODEL='${MODEL}' \
        BENCHMARK='${BENCHMARK}' \
        TEST_NAME='${EXP_NAME}' \
        SAMPLE_SIZE='${SAMPLE_SIZE}' \
        SEED='${SEED}' \
        SOURCE_JSONL='${SOURCE_JSONL}' \
        ALLOW_TEXT_ONLY=1 \
        STRUCTURE_DIR_OVERRIDE='${COSIL_STRUCTURE_DIR}' \
        BUILD_STRUCTURES='${COSIL_BUILD_STRUCTURES:-0}' \
        REBUILD_STRUCTURES='${COSIL_REBUILD_STRUCTURES:-0}' \
        bash newtest/scripts/run_cosil_swebench_multimodal_60.sh"
  fi
fi

if is_truthy "${RUN_GRAPHLOCATOR}"; then
  GRAPHLOCATOR_PRED="${GRAPHLOCATOR_RESULT_DIR}/loc_results.json"
  GRAPHLOCATOR_EVAL_CMD="cd '${ROOT_DIR}/GraphLocator' && \
      '${GRAPHLOCATOR_PY}' newtest/scripts/eval_file_level.py \
        --samples '${SOURCE_JSONL}' \
        --pred-file '${GRAPHLOCATOR_PRED}' \
        --output-dir '${GRAPHLOCATOR_RESULT_DIR}/eval' && \
      '${GRAPHLOCATOR_PY}' newtest/scripts/eval_3level_localization.py \
        --samples '${SOURCE_JSONL}' \
        --pred-file '${GRAPHLOCATOR_PRED}' \
        --structure-dir '${STRUCTURE_DIR}' \
        --output-dir '${GRAPHLOCATOR_RESULT_DIR}/eval' && \
      '${GRAPHLOCATOR_PY}' newtest/scripts/eval_3level_localization_strict.py \
        --samples '${SOURCE_JSONL}' \
        --pred-file '${GRAPHLOCATOR_PRED}' \
        --structure-dir '${STRUCTURE_DIR}' \
        --output-dir '${GRAPHLOCATOR_RESULT_DIR}/eval_strict'"
  if ! run_eval_if_possible "GraphLocator" "${GRAPHLOCATOR_RESULT_DIR}" "${GRAPHLOCATOR_PRED}" "${GRAPHLOCATOR_EVAL_CMD}"; then
    run_if_needed "Run GraphLocator on ${EXP_NAME}" "$(metric_pair "${GRAPHLOCATOR_RESULT_DIR}")" \
      run_shell "cd '${ROOT_DIR}/GraphLocator' && \
        PYTHON_BIN='${GRAPHLOCATOR_PY}' \
        OPENAI_API_KEY='${OPENAI_API_KEY}' \
        OPENAI_API_BASE='${OPENAI_API_BASE}' \
        MULADAPTER_MODEL='${MULADAPTER_MODEL}' \
        MULADAPTER_BASE_URL='${MULADAPTER_BASE_URL}' \
        MULADAPTER_API_KEY='${MULADAPTER_API_KEY}' \
        MODEL='${MODEL}' \
        BENCHMARK='${BENCHMARK}' \
        TEST_NAME='${EXP_NAME}' \
        SAMPLE_SIZE='${SAMPLE_SIZE}' \
        SEED='${SEED}' \
        SOURCE_JSONL='${SOURCE_JSONL}' \
        ALLOW_TEXT_ONLY=1 \
        STRUCTURE_DIR='${STRUCTURE_DIR}' \
        SKIP_EXIST='${GRAPHLOCATOR_SKIP_EXIST:-1}' \
        REBUILD_SKELETON='${GRAPHLOCATOR_REBUILD_SKELETON:-0}' \
        bash newtest/scripts/run_graphlocator_swebench_multimodal_60.sh"
  fi
fi

if is_truthy "${RUN_GALA}"; then
  GALA_PRED="${GALA_RESULT_DIR}/loc_results.json"
  GALA_EVAL_CMD="cd '${ROOT_DIR}/GALA' && \
      '${GALA_PY}' mytest/scripts/eval_gala_localization.py \
        --result-dir '${GALA_RESULT_DIR}' \
        --gt-file '${ROOT_DIR}/GALA/mytest/${EXP_NAME}/data/gt_files.json' \
        --samples '${ROOT_DIR}/GALA/mytest/${EXP_NAME}/data/samples.json' \
        --output-dir '${GALA_RESULT_DIR}/eval' \
        --loc-output '${GALA_PRED}' \
        --structure-dir '${STRUCTURE_DIR}' && \
      '${GALA_PY}' mytest/scripts/eval_gala_localization_strict.py \
        --result-dir '${GALA_RESULT_DIR}' \
        --gt-file '${ROOT_DIR}/GALA/mytest/${EXP_NAME}/data/gt_files.json' \
        --samples '${ROOT_DIR}/GALA/mytest/${EXP_NAME}/data/samples.json' \
        --output-dir '${GALA_RESULT_DIR}/eval_strict' \
        --loc-output '${GALA_PRED}' \
        --structure-dir '${STRUCTURE_DIR}'"
  if ! run_eval_if_possible "GALA" "${GALA_RESULT_DIR}" "${GALA_PRED}" "${GALA_EVAL_CMD}"; then
    run_if_needed "Run GALA on ${EXP_NAME}" "$(metric_pair "${GALA_RESULT_DIR}")" \
      run_shell "cd '${ROOT_DIR}/GALA' && \
        PYTHON_BIN='${GALA_PY}' \
        OPENAI_API_KEY='${OPENAI_API_KEY}' \
        VLM_API_KEY='${VLM_API_KEY}' \
        TEXT_API_KEY='${TEXT_API_KEY}' \
        VLM_MODEL='${VLM_MODEL}' \
        VLM_BASE_URL='${VLM_BASE_URL}' \
        TEXT_MODEL_NAME='${TEXT_MODEL_NAME}' \
        TEXT_BASE_URL='${TEXT_BASE_URL}' \
        TEST_NAME='${EXP_NAME}' \
        INPUT_FILE='${SOURCE_JSONL}' \
        SAMPLE_SIZE='${SAMPLE_SIZE}' \
        SEED='${SEED}' \
        ALLOW_NO_IMAGES=1 \
        ALLOW_NON_GALA_FILES=1 \
        ALLOW_MISSING_PATCH=1 \
        STRUCTURE_DIR='${STRUCTURE_DIR}' \
        MAX_WORKERS='${MAX_WORKERS:-1}' \
        bash mytest/scripts/run_gala_omnigirl_js_ts_60_localization.sh"
  fi
fi

if is_truthy "${RUN_MMIR}"; then
  for MMIR_METHOD_NAME in ${RUN_MMIR_METHODS}; do
    MMIR_RESULT_DIR="${ROOT_DIR}/MM-IR/results/${EXP_NAME}/${MMIR_METHOD_NAME}"
    MMIR_PRED="${MMIR_RESULT_DIR}/loc_results.json"
    MMIR_EVAL_CMD="cd '${ROOT_DIR}/MM-IR' && \
        '${MMIR_PY}' -m mmir.evaluation.eval_3level \
          --samples '${SOURCE_JSONL}' \
          --predictions '${MMIR_PRED}' \
          --structure-dir '${STRUCTURE_DIR}' \
          --output-dir '${MMIR_RESULT_DIR}/eval' \
          --limit '${MMIR_LIMIT:-0}' && \
        '${MMIR_PY}' -m mmir.evaluation.eval_3level_strict \
          --samples '${SOURCE_JSONL}' \
          --predictions '${MMIR_PRED}' \
          --structure-dir '${STRUCTURE_DIR}' \
          --output-dir '${MMIR_RESULT_DIR}/eval_strict' \
          --limit '${MMIR_LIMIT:-0}'"
    if ! run_eval_if_possible "MM-IR ${MMIR_METHOD_NAME}" "${MMIR_RESULT_DIR}" "${MMIR_PRED}" "${MMIR_EVAL_CMD}"; then
      run_if_needed "Run MM-IR ${MMIR_METHOD_NAME} on ${EXP_NAME}" "$(metric_pair "${MMIR_RESULT_DIR}")" \
        run_shell "cd '${ROOT_DIR}/MM-IR' && \
          PYTHON_BIN='${MMIR_PY}' \
          METHOD='${MMIR_METHOD_NAME}' \
          DENSE_MODEL='${MMIR_DENSE_MODEL:-}' \
          DENSE_BATCH_SIZE='${MMIR_DENSE_BATCH_SIZE:-${DENSE_BATCH_SIZE:-16}}' \
          DENSE_DEVICE='${MMIR_DENSE_DEVICE:-${DENSE_DEVICE:-}}' \
          LIMIT='${MMIR_LIMIT:-0}' \
          SAMPLE_FILE='${SOURCE_JSONL}' \
          STRUCTURE_DIR='${STRUCTURE_DIR}' \
          OUTPUT_DIR='${MMIR_RESULT_DIR}' \
          bash scripts/run_mmir_omnigirl_60.sh"
    fi
  done
fi

cat <<EOF

All requested baselines finished or were skipped for ${EXP_NAME}.

Result directories:
  LocAgent:      ${ROOT_DIR}/LocAgent/newtest/${EXP_NAME}/results
  CoSIL:         ${ROOT_DIR}/CoSIL/newtest/${EXP_NAME}/results
  GraphLocator:  ${ROOT_DIR}/GraphLocator/newtest/${EXP_NAME}/results
  GALA:          ${ROOT_DIR}/GALA/mytest/${EXP_NAME}/results
  MM-IR:         ${ROOT_DIR}/MM-IR/results/${EXP_NAME}

Each completed baseline should have:
  eval/metrics_3level.md
  eval_strict/metrics_3level.md

MM-IR methods requested:
  ${RUN_MMIR_METHODS}

EOF
