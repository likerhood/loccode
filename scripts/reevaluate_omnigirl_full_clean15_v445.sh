#!/usr/bin/env bash
set -euo pipefail

# Re-evaluate existing OmniGIRL full-candidates predictions on a fixed Clean15 v445 subset.
#
# This script does not rerun localization. It fixes the comparison口径 by using:
#   clean_subsets/omnigirl-full-candidates.clean15.v445.samples.jsonl
#
# All metrics are written with suffix clean15_v445:
#   <result-dir>/eval_clean15_v445/
#   <result-dir>/eval_strict_clean15_v445/
#   <result-dir>/filtered_predictions_clean15_v445/
#
# Typical usage:
#   MODEL_TAG=mimo-v2.5 GALA_MODEL_TAG=mimo-v2.5 \
#     bash scripts/reevaluate_omnigirl_full_clean15_v445.sh
#
#   MODEL_TAG=openai_qwen3-vl-8b GALA_MODEL_TAG=qwen3-vl-8b \
#     bash scripts/reevaluate_omnigirl_full_clean15_v445.sh

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

BENCHMARK="${BENCHMARK:-omnigirl-full-candidates}"
FULL_SAMPLES="${FULL_SAMPLES:-${ROOT_DIR}/MM-IR/data/omnigirl-full-candidates/samples.jsonl}"
STRUCTURE_DIR="${STRUCTURE_DIR:-${ROOT_DIR}/MM-IR/data/omnigirl-full-candidates/repo_structures}"

MAX_GOLD="${MAX_GOLD:-15}"
CLEAN_MODE="${CLEAN_MODE:-three-level}"
CLEAN_VERSION="${CLEAN_VERSION:-v445}"
CLEAN_EXPECTED_ROWS="${CLEAN_EXPECTED_ROWS:-445}"
CLEAN_SUFFIX="${CLEAN_SUFFIX:-clean15.${CLEAN_VERSION}}"
EVAL_SUFFIX="${EVAL_SUFFIX:-clean15_${CLEAN_VERSION}}"
CLEAN_PREFIX="${CLEAN_PREFIX:-${ROOT_DIR}/clean_subsets/${BENCHMARK}.${CLEAN_SUFFIX}}"
CLEAN_SAMPLES="${CLEAN_PREFIX}.samples.jsonl"
CLEAN_IDS="${CLEAN_PREFIX}.ids.txt"
CLEAN_MANIFEST="${CLEAN_PREFIX}.manifest.json"
CLEAN_EXCLUDED="${CLEAN_PREFIX}.excluded.jsonl"
CLEAN_PER_SAMPLE="${CLEAN_PREFIX}.per_sample.jsonl"
CLEAN_PROGRESS_INTERVAL="${CLEAN_PROGRESS_INTERVAL:-25}"
FORCE_CLEAN_SUBSET="${FORCE_CLEAN_SUBSET:-0}"
DRY_RUN="${DRY_RUN:-0}"

BASELINES="${BASELINES:-locagent cosil graphlocator gala mmir}"
MODEL_TAG="${MODEL_TAG:-mimo-v2.5}"
GALA_MODEL_TAG="${GALA_MODEL_TAG:-${MODEL_TAG}}"
MMIR_METHODS="${MMIR_METHODS:-bm25-mmir e5-mmir jina-code-v2-mmir codesage-large-v2-mmir coderankembed-mmir}"
CONDA_ENV_ROOT="${CONDA_ENV_ROOT:-}"
PYTHON_BIN="${PYTHON_BIN:-}"
FORCE="${FORCE:-0}"

truthy() {
  [[ "${1:-}" == "1" || "${1:-}" == "true" || "${1:-}" == "yes" ]]
}

jsonl_rows() {
  local path="$1"
  if [[ -f "${path}" ]]; then
    wc -l < "${path}" | tr -d ' '
  else
    echo 0
  fi
}

structure_count() {
  local path="$1"
  if [[ -d "${path}" ]]; then
    find "${path}" -maxdepth 1 -type f -name '*.json' | wc -l | tr -d ' '
  else
    echo 0
  fi
}

detect_python_bin() {
  if [[ -n "${PYTHON_BIN}" && -x "${PYTHON_BIN}" ]]; then
    echo "${PYTHON_BIN}"
    return 0
  fi
  if [[ -n "${CONDA_ENV_ROOT}" && -x "${CONDA_ENV_ROOT%/}/locagent/bin/python" ]]; then
    echo "${CONDA_ENV_ROOT%/}/locagent/bin/python"
    return 0
  fi
  if [[ -x "/data2/like/envs/locagent/bin/python" ]]; then
    echo "/data2/like/envs/locagent/bin/python"
    return 0
  fi
  if [[ -x "/data/like/envs/locagent/bin/python" ]]; then
    echo "/data/like/envs/locagent/bin/python"
    return 0
  fi
  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return 0
  fi
  echo "python3"
}

run_cmd() {
  echo "+ $*"
  if ! truthy "${DRY_RUN}"; then
    "$@"
  fi
}

PYTHON_BIN="$(detect_python_bin)"

cat <<EOF
OmniGIRL full Clean15 fixed re-evaluation
Root:           ${ROOT_DIR}
Benchmark:      ${BENCHMARK}
Full samples:   ${FULL_SAMPLES} ($(jsonl_rows "${FULL_SAMPLES}") rows)
Structure dir:  ${STRUCTURE_DIR} ($(structure_count "${STRUCTURE_DIR}") files)
Clean version:  ${CLEAN_VERSION}
Clean expected: ${CLEAN_EXPECTED_ROWS}
Clean samples:  ${CLEAN_SAMPLES}
Clean manifest: ${CLEAN_MANIFEST}
Eval suffix:    ${EVAL_SUFFIX}
Baselines:      ${BASELINES}
Model tag:      ${MODEL_TAG}
GALA tag:       ${GALA_MODEL_TAG}
MM-IR methods:  ${MMIR_METHODS}
Python:         ${PYTHON_BIN}
Dry run:        ${DRY_RUN}
EOF

if [[ ! -s "${FULL_SAMPLES}" ]]; then
  echo "ERROR: full samples not found: ${FULL_SAMPLES}" >&2
  exit 2
fi
if [[ ! -d "${STRUCTURE_DIR}" ]]; then
  echo "ERROR: structure dir not found: ${STRUCTURE_DIR}" >&2
  exit 2
fi

current_clean_rows="$(jsonl_rows "${CLEAN_SAMPLES}")"
if truthy "${FORCE_CLEAN_SUBSET}" || [[ "${current_clean_rows}" == "0" ]]; then
  echo
  echo "========== Build fixed Clean15 ${CLEAN_VERSION} subset =========="
  run_cmd env PYTHONUNBUFFERED=1 "${PYTHON_BIN}" "${ROOT_DIR}/scripts/build_three_level_clean_subset.py" \
    --samples "${FULL_SAMPLES}" \
    --structure-dir "${STRUCTURE_DIR}" \
    --output-prefix "${CLEAN_PREFIX}" \
    --mode "${CLEAN_MODE}" \
    --max-gold "${MAX_GOLD}" \
    --progress-interval "${CLEAN_PROGRESS_INTERVAL}" \
    --write-diagnostic
else
  echo "[clean-subset] existing fixed subset found: ${CLEAN_SAMPLES} (${current_clean_rows} rows)"
  echo "[clean-subset] use FORCE_CLEAN_SUBSET=1 to rebuild."
fi

clean_rows="$(jsonl_rows "${CLEAN_SAMPLES}")"
if ! truthy "${DRY_RUN}" && [[ "${clean_rows}" != "${CLEAN_EXPECTED_ROWS}" ]]; then
  cat >&2 <<EOF
ERROR: fixed Clean15 row count mismatch.

Expected:
  ${CLEAN_EXPECTED_ROWS}

Found:
  ${clean_rows}

Clean samples:
  ${CLEAN_SAMPLES}

This is intentionally fatal. It prevents mixing incompatible Clean15口径s
such as 445 and 458 in the same comparison.
EOF
  exit 2
fi

echo
echo "========== Fixed Clean15 subset =========="
echo "Clean rows:       ${clean_rows}"
echo "Clean samples:    ${CLEAN_SAMPLES}"
echo "Clean ids:        ${CLEAN_IDS}"
echo "Clean manifest:   ${CLEAN_MANIFEST}"
echo "Clean excluded:   ${CLEAN_EXCLUDED}"
echo "Clean diagnostic: ${CLEAN_PER_SAMPLE}"

echo
echo "========== Re-evaluate existing predictions =========="
run_cmd env \
  BENCHMARK="${BENCHMARK}" \
  SAMPLES="${FULL_SAMPLES}" \
  STRUCTURE_DIR="${STRUCTURE_DIR}" \
  CLEAN_PREFIX="${CLEAN_PREFIX}" \
  CLEAN_EXPECTED_ROWS="${CLEAN_EXPECTED_ROWS}" \
  USE_EXISTING_CLEAN_SUBSET=1 \
  SUFFIX="${EVAL_SUFFIX}" \
  BASELINES="${BASELINES}" \
  MODEL_TAG="${MODEL_TAG}" \
  GALA_MODEL_TAG="${GALA_MODEL_TAG}" \
  MMIR_METHODS="${MMIR_METHODS}" \
  CONDA_ENV_ROOT="${CONDA_ENV_ROOT}" \
  PYTHON_BIN="${PYTHON_BIN}" \
  FORCE="${FORCE}" \
  DRY_RUN="${DRY_RUN}" \
  bash "${ROOT_DIR}/scripts/reevaluate_all_existing_results_clean15.sh"

echo
echo "Done. Read metrics from:"
echo "  <baseline-result-dir>/eval_${EVAL_SUFFIX}/metrics_3level.md"
echo "  <baseline-result-dir>/eval_strict_${EVAL_SUFFIX}/metrics_3level.md"

