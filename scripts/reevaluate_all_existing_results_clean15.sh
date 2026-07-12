#!/usr/bin/env bash
set -euo pipefail

# Re-evaluate already generated baseline predictions on a clean15 subset.
#
# This script never reruns localization. It:
#   1. builds clean_subsets/<benchmark>.clean15.samples.jsonl;
#   2. finds existing prediction files for requested baselines;
#   3. writes eval_clean15/ and eval_strict_clean15/ next to the original eval/.
#
# Examples:
#   BENCHMARK=swebench_multimodal-full-dev MODEL_TAG=openai_qwen3-vl-8b GALA_MODEL_TAG=qwen3-vl-8b \
#     bash scripts/reevaluate_all_existing_results_clean15.sh
#
#   BENCHMARK=omnigirl-unified60 BASELINES="locagent cosil graphlocator gala" \
#     bash scripts/reevaluate_all_existing_results_clean15.sh

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

BENCHMARK="${BENCHMARK:-swebench_multimodal-full-dev}"
BASELINES="${BASELINES:-locagent cosil graphlocator gala mmir}"
MODEL_TAG="${MODEL_TAG:-openai_qwen3-vl-8b}"
GALA_MODEL_TAG="${GALA_MODEL_TAG:-qwen3-vl-8b}"
MMIR_METHODS="${MMIR_METHODS:-bm25-mmir e5-mmir jina-code-v2-mmir codesage-large-v2-mmir coderankembed-mmir}"
MAX_GOLD="${MAX_GOLD:-15}"
CLEAN_MODE="${CLEAN_MODE:-three-level}"
SUFFIX="${SUFFIX:-clean15}"
CONDA_ENV_ROOT="${CONDA_ENV_ROOT:-}"
if [[ -z "${PYTHON_BIN:-}" ]]; then
  if [[ -n "${CONDA_ENV_ROOT}" && -x "${CONDA_ENV_ROOT%/}/locagent/bin/python" ]]; then
    PYTHON_BIN="${CONDA_ENV_ROOT%/}/locagent/bin/python"
  elif [[ -x "/data2/like/envs/locagent/bin/python" ]]; then
    PYTHON_BIN="/data2/like/envs/locagent/bin/python"
  elif [[ -x "/data/like/envs/locagent/bin/python" ]]; then
    PYTHON_BIN="/data/like/envs/locagent/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  else
    PYTHON_BIN="python3"
  fi
fi
FORCE="${FORCE:-0}"
DRY_RUN="${DRY_RUN:-0}"

case "${BENCHMARK}" in
  swebench_multimodal-full-dev)
    SAMPLES="${SAMPLES:-${ROOT_DIR}/LocAgent/newtest/swebench_multimodal-full-dev/data/samples.jsonl}"
    STRUCTURE_DIR="${STRUCTURE_DIR:-${ROOT_DIR}/LocAgent/newtest/swebench_multimodal-full-dev/repo_structures}"
    ;;
  swebench_multimodal-60)
    SAMPLES="${SAMPLES:-${ROOT_DIR}/LocAgent/newtest/swebench_multimodal-60/data/samples.jsonl}"
    STRUCTURE_DIR="${STRUCTURE_DIR:-${ROOT_DIR}/LocAgent/newtest/swebench_multimodal-60/repo_structures}"
    ;;
  omnigirl-full-candidates)
    SAMPLES="${SAMPLES:-${ROOT_DIR}/MM-IR/data/omnigirl-full-candidates/samples.jsonl}"
    STRUCTURE_DIR="${STRUCTURE_DIR:-${ROOT_DIR}/MM-IR/data/omnigirl-full-candidates/repo_structures}"
    ;;
  omnigirl-unified60)
    SAMPLES="${SAMPLES:-${ROOT_DIR}/LocAgent/newtest/omnigirl-unified60/data/samples.jsonl}"
    STRUCTURE_DIR="${STRUCTURE_DIR:-${ROOT_DIR}/LocAgent/newtest/omnigirl-unified60/repo_structures}"
    ;;
  *)
    SAMPLES="${SAMPLES:-${ROOT_DIR}/LocAgent/newtest/${BENCHMARK}/data/samples.jsonl}"
    STRUCTURE_DIR="${STRUCTURE_DIR:-${ROOT_DIR}/LocAgent/newtest/${BENCHMARK}/repo_structures}"
    ;;
esac

CLEAN_PREFIX="${CLEAN_PREFIX:-${ROOT_DIR}/clean_subsets/${BENCHMARK}.${SUFFIX}}"
CLEAN_SAMPLES="${CLEAN_PREFIX}.samples.jsonl"

truthy() {
  [[ "${1:-}" == "1" || "${1:-}" == "true" || "${1:-}" == "yes" ]]
}

run_cmd() {
  echo "+ $*"
  if ! truthy "${DRY_RUN}"; then
    "$@"
  fi
}

has_baseline() {
  local target="$1"
  for item in ${BASELINES}; do
    [[ "${item}" == "${target}" ]] && return 0
  done
  return 1
}

reeval_one() {
  local label="$1"
  local result_dir="$2"
  local pred_file="$3"
  if [[ ! -s "${pred_file}" ]]; then
    echo "[skip] ${label}: prediction file not found: ${pred_file}"
    return 0
  fi
  local args=(
    "${PYTHON_BIN}" "${ROOT_DIR}/scripts/reevaluate_existing_results_clean15.py"
    --samples "${CLEAN_SAMPLES}"
    --pred-file "${pred_file}"
    --structure-dir "${STRUCTURE_DIR}"
    --result-dir "${result_dir}"
    --suffix "${SUFFIX}"
    --python "${PYTHON_BIN}"
  )
  truthy "${FORCE}" && args+=(--force)
  truthy "${DRY_RUN}" && args+=(--dry-run)
  echo
  echo "========== Re-evaluate ${label} (${BENCHMARK}) =========="
  run_cmd "${args[@]}"
}

if [[ ! -s "${SAMPLES}" ]]; then
  echo "ERROR: samples not found: ${SAMPLES}" >&2
  exit 2
fi
if [[ ! -d "${STRUCTURE_DIR}" ]]; then
  echo "ERROR: structure dir not found: ${STRUCTURE_DIR}" >&2
  exit 2
fi

echo "Clean15 re-evaluation"
echo "Root:          ${ROOT_DIR}"
echo "Benchmark:     ${BENCHMARK}"
echo "Samples:       ${SAMPLES}"
echo "Structure dir: ${STRUCTURE_DIR}"
echo "Baselines:     ${BASELINES}"
echo "Model tag:     ${MODEL_TAG}"
echo "GALA tag:      ${GALA_MODEL_TAG}"
echo "MM-IR methods: ${MMIR_METHODS}"
echo "Clean mode:    ${CLEAN_MODE}"
echo "Max gold:      ${MAX_GOLD}"
echo "Suffix:        ${SUFFIX}"

run_cmd "${PYTHON_BIN}" "${ROOT_DIR}/scripts/build_three_level_clean_subset.py" \
  --samples "${SAMPLES}" \
  --structure-dir "${STRUCTURE_DIR}" \
  --output-prefix "${CLEAN_PREFIX}" \
  --mode "${CLEAN_MODE}" \
  --max-gold "${MAX_GOLD}" \
  --write-diagnostic

if has_baseline locagent; then
  reeval_one \
    "LocAgent" \
    "${ROOT_DIR}/LocAgent/newtest/${BENCHMARK}/results/${MODEL_TAG}" \
    "${ROOT_DIR}/LocAgent/newtest/${BENCHMARK}/results/${MODEL_TAG}/location/merged_loc_outputs_mrr.jsonl"
fi

if has_baseline cosil; then
  reeval_one \
    "CoSIL" \
    "${ROOT_DIR}/CoSIL/newtest/${BENCHMARK}/results/${MODEL_TAG}" \
    "${ROOT_DIR}/CoSIL/newtest/${BENCHMARK}/results/${MODEL_TAG}/file_level/loc_outputs.jsonl"
fi

if has_baseline graphlocator; then
  reeval_one \
    "GraphLocator" \
    "${ROOT_DIR}/GraphLocator/newtest/${BENCHMARK}/results/${MODEL_TAG}" \
    "${ROOT_DIR}/GraphLocator/newtest/${BENCHMARK}/results/${MODEL_TAG}/loc_results.json"
fi

if has_baseline gala; then
  reeval_one \
    "GALA" \
    "${ROOT_DIR}/GALA/mytest/${BENCHMARK}/results/${GALA_MODEL_TAG}" \
    "${ROOT_DIR}/GALA/mytest/${BENCHMARK}/results/${GALA_MODEL_TAG}/loc_results.json"
fi

if has_baseline mmir; then
  for method in ${MMIR_METHODS}; do
    reeval_one \
      "MM-IR ${method}" \
      "${ROOT_DIR}/MM-IR/results/${BENCHMARK}/${method}" \
      "${ROOT_DIR}/MM-IR/results/${BENCHMARK}/${method}/loc_results.json"
  done
fi

echo
echo "Done. Clean subset:"
echo "  ${CLEAN_SAMPLES}"
echo "Clean metrics are written as:"
echo "  <baseline-result-dir>/eval_${SUFFIX}/metrics_3level.md"
echo "  <baseline-result-dir>/eval_strict_${SUFFIX}/metrics_3level.md"
