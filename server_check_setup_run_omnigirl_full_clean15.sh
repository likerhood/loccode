#!/usr/bin/env bash
set -euo pipefail

# Server-side OmniGIRL full-candidates Clean15 runner.
#
# This script intentionally does not modify or replace
# server_check_setup_run_omnigirl_full.sh. It is a thin wrapper that:
#   1. makes sure the runnable OmniGIRL full-candidates inputs exist;
#   2. builds a Clean15 samples.jsonl from those full inputs;
#   3. runs the normal OmniGIRL full runner on the smaller Clean15 sample set.
#
# Clean15 default policy:
#   keep samples whose gold file/module/function counts are all in [1, 15].
#
# Result directories default to a separate experiment name:
#   omnigirl-full-candidates-clean15

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FULL_RUNNER="${ROOT_DIR}/server_check_setup_run_omnigirl_full.sh"
CLEAN_BUILDER="${ROOT_DIR}/scripts/build_three_level_clean_subset.py"
export GITHUB_MIRROR_PREFIX="${GITHUB_MIRROR_PREFIX:-${REPO_GITHUB_MIRROR_PREFIX:-https://gh.xmly.dev}}"

is_truthy() {
  [[ "${1:-}" == "1" || "${1:-}" == "true" || "${1:-}" == "yes" ]]
}

count_jsonl_rows() {
  local path="$1"
  if [[ -f "${path}" ]]; then
    wc -l < "${path}" | tr -d ' '
  else
    echo 0
  fi
}

count_structures() {
  local path="$1"
  if [[ -d "${path}" ]]; then
    find "${path}" -maxdepth 1 -type f -name '*.json' | wc -l | tr -d ' '
  else
    echo 0
  fi
}

detect_python_bin() {
  if [[ -n "${PYTHON_BIN:-}" && -x "${PYTHON_BIN}" ]]; then
    echo "${PYTHON_BIN}"
    return 0
  fi
  if [[ -n "${CONDA_ENV_ROOT:-}" && -x "${CONDA_ENV_ROOT%/}/locagent/bin/python" ]]; then
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
  if ! is_truthy "${DRY_RUN:-0}"; then
    "$@"
  fi
}

run_cmd_with_supervisor_retry() {
  local label="$1"
  shift
  local max_attempts="${SUPERVISOR_MAX_ATTEMPTS:-1}"
  local retry_sleep="${SUPERVISOR_RETRY_SLEEP:-120}"
  local attempt status

  if ! [[ "${max_attempts}" =~ ^[0-9]+$ ]] || [[ "${max_attempts}" -lt 1 ]]; then
    echo "ERROR: SUPERVISOR_MAX_ATTEMPTS must be a positive integer." >&2
    exit 2
  fi
  if ! [[ "${retry_sleep}" =~ ^[0-9]+$ ]] || [[ "${retry_sleep}" -lt 0 ]]; then
    echo "ERROR: SUPERVISOR_RETRY_SLEEP must be a non-negative integer seconds value." >&2
    exit 2
  fi

  attempt=1
  while [[ "${attempt}" -le "${max_attempts}" ]]; do
    if [[ "${max_attempts}" -gt 1 ]]; then
      echo
      echo "========== ${label} supervisor attempt ${attempt}/${max_attempts} =========="
    fi

    set +e
    run_cmd "$@"
    status=$?
    set -e

    if [[ "${status}" == "0" ]]; then
      if [[ "${max_attempts}" -gt 1 ]]; then
        echo "[supervisor-retry] ${label} succeeded on attempt ${attempt}/${max_attempts}."
      fi
      return 0
    fi

    if [[ "${attempt}" -ge "${max_attempts}" ]]; then
      echo "[supervisor-retry] ${label} failed after ${attempt}/${max_attempts} attempt(s); status=${status}." >&2
      return "${status}"
    fi

    echo "[supervisor-retry] ${label} failed with status ${status}; sleep ${retry_sleep}s before retry $((attempt + 1))/${max_attempts}." >&2
    sleep "${retry_sleep}"
    attempt=$((attempt + 1))
  done
}

if [[ ! -f "${FULL_RUNNER}" ]]; then
  echo "ERROR: missing full runner: ${FULL_RUNNER}" >&2
  exit 2
fi
if [[ ! -f "${CLEAN_BUILDER}" ]]; then
  echo "ERROR: missing Clean15 builder: ${CLEAN_BUILDER}" >&2
  exit 2
fi

FULL_EXP_NAME="${FULL_EXP_NAME:-omnigirl-full-candidates}"
CLEAN_EXP_NAME="${CLEAN_EXP_NAME:-omnigirl-full-candidates-clean15}"
FULL_EXPECTED_SAMPLES="${FULL_EXPECTED_SAMPLES:-631}"
FULL_SOURCE_JSONL="${FULL_SOURCE_JSONL:-${ROOT_DIR}/MM-IR/data/omnigirl-full-candidates/samples.jsonl}"
FULL_STRUCTURE_DIR="${FULL_STRUCTURE_DIR:-${ROOT_DIR}/MM-IR/data/omnigirl-full-candidates/repo_structures}"

CLEAN_MODE="${CLEAN_MODE:-three-level}"
MAX_GOLD="${MAX_GOLD:-15}"
CLEAN_SUFFIX="${CLEAN_SUFFIX:-clean15}"
CLEAN_PREFIX="${CLEAN_PREFIX:-${ROOT_DIR}/clean_subsets/${FULL_EXP_NAME}.${CLEAN_SUFFIX}}"
CLEAN_SOURCE_JSONL="${CLEAN_SOURCE_JSONL:-${CLEAN_PREFIX}.samples.jsonl}"
CLEAN_IDS="${CLEAN_PREFIX}.ids.txt"
CLEAN_MANIFEST="${CLEAN_PREFIX}.manifest.json"
CLEAN_EXCLUDED="${CLEAN_PREFIX}.excluded.jsonl"
CLEAN_PER_SAMPLE="${CLEAN_PREFIX}.per_sample.jsonl"

PREPARE_FULL_INPUTS="${PREPARE_FULL_INPUTS:-1}"
FORCE_CLEAN_SUBSET="${FORCE_CLEAN_SUBSET:-0}"
DRY_RUN="${DRY_RUN:-0}"
BASELINES="${BASELINES:-locagent cosil graphlocator gala mmir}"
BASELINE_ENVS="${BASELINE_ENVS:-${BASELINES}}"
CLEAN_PROGRESS_INTERVAL="${CLEAN_PROGRESS_INTERVAL:-25}"
SUPERVISOR_MAX_ATTEMPTS="${SUPERVISOR_MAX_ATTEMPTS:-1}"
SUPERVISOR_RETRY_SLEEP="${SUPERVISOR_RETRY_SLEEP:-120}"
GALA_SHARED_IMAGE_ROOT="${GALA_SHARED_IMAGE_ROOT:-${ROOT_DIR}/shared_assets/gala_images}"
GALA_IMAGE_DIR="${GALA_IMAGE_DIR:-${GALA_OMNI_IMAGE_DIR:-${GALA_SHARED_IMAGE_ROOT}/${FULL_EXP_NAME}}}"
GALA_DOWNLOAD_IMAGES="${GALA_DOWNLOAD_IMAGES:-${DOWNLOAD_IMAGES:-1}}"
GALA_REUSE_IMAGE_IR="${GALA_REUSE_IMAGE_IR:-${REUSE_IMAGE_IR:-1}}"
GALA_RESUME_IMAGE_IR="${GALA_RESUME_IMAGE_IR:-${RESUME_IMAGE_IR:-1}}"
GALA_FORCE_IMAGE_IR="${GALA_FORCE_IMAGE_IR:-${FORCE_IMAGE_IR:-0}}"
GALA_CHECK_IMAGE_IR_COMPLETE="${GALA_CHECK_IMAGE_IR_COMPLETE:-${CHECK_IMAGE_IR_COMPLETE:-1}}"
GALA_IMAGE_DOWNLOAD_RETRIES="${GALA_IMAGE_DOWNLOAD_RETRIES:-${IMAGE_DOWNLOAD_RETRIES:-3}}"
GALA_IMAGE_DOWNLOAD_RETRY_SLEEP="${GALA_IMAGE_DOWNLOAD_RETRY_SLEEP:-${IMAGE_DOWNLOAD_RETRY_SLEEP:-10}}"
GALA_IMAGE_DOWNLOAD_BACKOFF="${GALA_IMAGE_DOWNLOAD_BACKOFF:-${IMAGE_DOWNLOAD_BACKOFF:-2}}"

PYTHON_BIN_RESOLVED="$(detect_python_bin)"

full_sample_count="$(count_jsonl_rows "${FULL_SOURCE_JSONL}")"
full_structure_count="$(count_structures "${FULL_STRUCTURE_DIR}")"

cat <<EOF
OmniGIRL full-candidates Clean15 server runner
Root: ${ROOT_DIR}
Full experiment: ${FULL_EXP_NAME}
Clean experiment: ${CLEAN_EXP_NAME}
Full samples: ${FULL_SOURCE_JSONL} (${full_sample_count} rows)
Full structures: ${FULL_STRUCTURE_DIR} (${full_structure_count} files)
Clean mode: ${CLEAN_MODE}
Max gold: ${MAX_GOLD}
Clean samples: ${CLEAN_SOURCE_JSONL}
Clean manifest: ${CLEAN_MANIFEST}
Python for Clean15 builder: ${PYTHON_BIN_RESOLVED}
Prepare full inputs: ${PREPARE_FULL_INPUTS}
Force clean subset: ${FORCE_CLEAN_SUBSET}
Clean progress interval: ${CLEAN_PROGRESS_INTERVAL}
Supervisor max attempts: ${SUPERVISOR_MAX_ATTEMPTS}
Supervisor retry sleep: ${SUPERVISOR_RETRY_SLEEP}s
GALA shared image root: ${GALA_SHARED_IMAGE_ROOT}
GALA image dir: ${GALA_IMAGE_DIR}
GALA download images: ${GALA_DOWNLOAD_IMAGES}
GALA reuse image IR: ${GALA_REUSE_IMAGE_IR}
GALA resume image IR: ${GALA_RESUME_IMAGE_IR}
GALA force image IR: ${GALA_FORCE_IMAGE_IR}
GALA check image IR completeness: ${GALA_CHECK_IMAGE_IR_COMPLETE}
GALA image download retry: retries=${GALA_IMAGE_DOWNLOAD_RETRIES}, sleep=${GALA_IMAGE_DOWNLOAD_RETRY_SLEEP}s, backoff=${GALA_IMAGE_DOWNLOAD_BACKOFF}
Dry run: ${DRY_RUN}
EOF

if [[ "${full_sample_count}" -lt "${FULL_EXPECTED_SAMPLES}" || "${full_structure_count}" -lt "${full_sample_count}" ]]; then
  if ! is_truthy "${PREPARE_FULL_INPUTS}"; then
    cat >&2 <<EOF
ERROR: full OmniGIRL inputs are incomplete and PREPARE_FULL_INPUTS=0.

Found:
  samples rows:    ${full_sample_count}
  structures:      ${full_structure_count}

Expected:
  ${FULL_SOURCE_JSONL}
  ${FULL_STRUCTURE_DIR}/*.json

Set PREPARE_FULL_INPUTS=1, or copy prepared full-candidates inputs first.
EOF
    exit 2
  fi

  echo
  echo "========== Prepare full OmniGIRL inputs via existing runner =========="
  run_cmd env \
    EXP_NAME="${FULL_EXP_NAME}" \
    EXPECTED_SAMPLES="${FULL_EXPECTED_SAMPLES}" \
    SOURCE_JSONL="${FULL_SOURCE_JSONL}" \
    STRUCTURE_DIR="${FULL_STRUCTURE_DIR}" \
    BASELINES="__none__" \
    BASELINE_ENVS="${PREPARE_BASELINE_ENVS:-locagent}" \
    PARALLEL=0 \
    FORCE_PREPARE="${FULL_FORCE_PREPARE:-0}" \
    FORCE_STRUCTURES="${FULL_FORCE_STRUCTURES:-0}" \
    DRY_RUN="${DRY_RUN}" \
    bash "${FULL_RUNNER}"
else
  echo "[data] Full OmniGIRL inputs already ready."
fi

full_sample_count="$(count_jsonl_rows "${FULL_SOURCE_JSONL}")"
full_structure_count="$(count_structures "${FULL_STRUCTURE_DIR}")"
if [[ "${full_sample_count}" -le 0 || "${full_structure_count}" -lt "${full_sample_count}" ]]; then
  cat >&2 <<EOF
ERROR: full inputs are still incomplete after preparation.

Found:
  samples rows:    ${full_sample_count}
  structures:      ${full_structure_count}
EOF
  exit 2
fi

if is_truthy "${FORCE_CLEAN_SUBSET}" || [[ ! -s "${CLEAN_SOURCE_JSONL}" ]]; then
  echo
  echo "========== Build OmniGIRL Clean15 subset =========="
  echo "[data] This step maps gold patch lines to repo_structures. It can take several minutes on a busy CPU server."
  run_cmd env PYTHONUNBUFFERED=1 "${PYTHON_BIN_RESOLVED}" "${CLEAN_BUILDER}" \
    --samples "${FULL_SOURCE_JSONL}" \
    --structure-dir "${FULL_STRUCTURE_DIR}" \
    --output-prefix "${CLEAN_PREFIX}" \
    --mode "${CLEAN_MODE}" \
    --max-gold "${MAX_GOLD}" \
    --progress-interval "${CLEAN_PROGRESS_INTERVAL}" \
    --write-diagnostic
else
  echo "[data] Clean15 subset already exists: ${CLEAN_SOURCE_JSONL}"
  echo "[data] Use FORCE_CLEAN_SUBSET=1 to rebuild it."
fi

clean_sample_count="$(count_jsonl_rows "${CLEAN_SOURCE_JSONL}")"
if [[ "${clean_sample_count}" -le 0 ]] && ! is_truthy "${DRY_RUN}"; then
  echo "ERROR: Clean15 subset is empty or missing: ${CLEAN_SOURCE_JSONL}" >&2
  exit 2
fi

echo
echo "========== Clean15 subset summary =========="
echo "Clean samples: ${CLEAN_SOURCE_JSONL} (${clean_sample_count} rows)"
echo "Clean ids: ${CLEAN_IDS}"
echo "Clean manifest: ${CLEAN_MANIFEST}"
echo "Clean excluded: ${CLEAN_EXCLUDED}"
echo "Clean per-sample diagnostics: ${CLEAN_PER_SAMPLE}"
if [[ -s "${CLEAN_MANIFEST}" ]]; then
  sed -n '1,120p' "${CLEAN_MANIFEST}" | sed 's/^/[manifest] /'
fi

echo
echo "========== Run OmniGIRL Clean15 baselines =========="
run_cmd_with_supervisor_retry "run_omnigirl_clean15" env \
  EXP_NAME="${CLEAN_EXP_NAME}" \
  EXPECTED_SAMPLES="${clean_sample_count}" \
  SOURCE_JSONL="${CLEAN_SOURCE_JSONL}" \
  STRUCTURE_DIR="${FULL_STRUCTURE_DIR}" \
  COSIL_STRUCTURE_DIR="${FULL_STRUCTURE_DIR}" \
  SAMPLE_SIZE="${clean_sample_count}" \
  GALA_IMAGE_DIR="${GALA_IMAGE_DIR}" \
  GALA_DOWNLOAD_IMAGES="${GALA_DOWNLOAD_IMAGES}" \
  GALA_REUSE_IMAGE_IR="${GALA_REUSE_IMAGE_IR}" \
  GALA_RESUME_IMAGE_IR="${GALA_RESUME_IMAGE_IR}" \
  GALA_FORCE_IMAGE_IR="${GALA_FORCE_IMAGE_IR}" \
  GALA_CHECK_IMAGE_IR_COMPLETE="${GALA_CHECK_IMAGE_IR_COMPLETE}" \
  GALA_IMAGE_DOWNLOAD_RETRIES="${GALA_IMAGE_DOWNLOAD_RETRIES}" \
  GALA_IMAGE_DOWNLOAD_RETRY_SLEEP="${GALA_IMAGE_DOWNLOAD_RETRY_SLEEP}" \
  GALA_IMAGE_DOWNLOAD_BACKOFF="${GALA_IMAGE_DOWNLOAD_BACKOFF}" \
  BASELINES="${BASELINES}" \
  BASELINE_ENVS="${BASELINE_ENVS}" \
  FORCE_PREPARE=0 \
  FORCE_STRUCTURES=0 \
  DRY_RUN="${DRY_RUN}" \
  bash "${FULL_RUNNER}"
