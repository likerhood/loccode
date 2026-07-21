#!/usr/bin/env bash
set -euo pipefail

# Server-side SWE-bench Multimodal full-dev runner.
#
# This mirrors server_check_setup_run_swe60.sh, but targets the complete
# SWE-bench Multimodal dev split used by run_swebench_multimodal_full_dev_*.sh.
# It is meant for server use after git clone/pull:
#   1. check API/model config only when LLM baselines are selected;
#   2. create/repair only the selected baseline conda envs;
#   3. check whether canonical full-dev samples/repo_structures are present;
#   4. run the sequential or baseline-parallel full-dev runner with resume logic.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export GITHUB_MIRROR_PREFIX="${GITHUB_MIRROR_PREFIX:-${REPO_GITHUB_MIRROR_PREFIX:-https://gh.xmly.dev}}"

warn() {
  echo "[warn] $*" >&2
}

detect_conda_sh() {
  local candidate
  for candidate in \
    "${HOME}/miniconda3/etc/profile.d/conda.sh" \
    "${HOME}/anaconda3/etc/profile.d/conda.sh" \
    "/data2/like/miniconda3/etc/profile.d/conda.sh" \
    "/opt/conda/etc/profile.d/conda.sh"; do
    if [[ -f "${candidate}" ]]; then
      echo "${candidate}"
      return 0
    fi
  done
  return 1
}

detect_conda_env_root() {
  local candidate
  if [[ "${ROOT_DIR}" == /data2/like/* && -d "/data2/like" ]]; then
    echo "/data2/like/envs"
    return 0
  fi
  for candidate in \
    "${HOME}/miniconda3/envs" \
    "${HOME}/anaconda3/envs" \
    "/data2/like/envs"; do
    if [[ -d "${candidate}" ]]; then
      echo "${candidate}"
      return 0
    fi
  done
  return 1
}

is_truthy() {
  [[ "${1:-}" == "1" || "${1:-}" == "true" || "${1:-}" == "yes" ]]
}

require_nonempty() {
  local name="$1"
  local value="$2"
  if [[ -z "${value}" ]]; then
    cat >&2 <<EOF
ERROR: ${name} is required.
Example:
  export BASE_URL='https://token-plan-sgp.xiaomimimo.com/v1'
  export API_KEY='...'
  export MODEL_NAME='mimo-v2.5'
EOF
    exit 2
  fi
}

api_host_from_url() {
  local url="${1:-}"
  url="${url#*://}"
  url="${url%%/*}"
  url="${url%%@}"
  url="${url%%:*}"
  echo "${url}"
}

append_csv_unique() {
  local current="$1"
  local item part found
  shift || true
  for item in "$@"; do
    [[ -z "${item}" ]] && continue
    found=0
    IFS=',' read -r -a _parts <<< "${current}"
    for part in "${_parts[@]}"; do
      if [[ "${part}" == "${item}" ]]; then
        found=1
        break
      fi
    done
    if [[ "${found}" == "0" ]]; then
      current="${current:+${current},}${item}"
    fi
  done
  echo "${current}"
}

build_api_no_proxy() {
  local base hosts host
  base="${NO_PROXY:-${no_proxy:-}}"
  hosts="${API_NO_PROXY_HOSTS:-$(api_host_from_url "${BASE_URL:-}")}"
  hosts="${hosts//,/ }"
  for host in ${hosts}; do
    base="$(append_csv_unique "${base}" "${host}")"
  done
  echo "${base}"
}

env_python() {
  local env_name="$1"
  echo "${CONDA_ENV_ROOT%/}/${env_name}/bin/python"
}

env_missing() {
  local env_name="$1"
  [[ ! -x "$(env_python "${env_name}")" ]]
}

baseline_enabled() {
  local target="$1"
  local selected
  for selected in ${BASELINES}; do
    if [[ "${selected}" == "${target}" ]]; then
      return 0
    fi
  done
  return 1
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

hf_dataset_available() {
  if ! command -v curl >/dev/null 2>&1; then
    return 1
  fi
  curl -fsSL --connect-timeout 10 --max-time 30 "${HF_DATASET_API_URL}" >/dev/null 2>&1
}

graphlocator_env_unhealthy() {
  local py
  py="$(env_python graphlocator)"
  if [[ ! -x "${py}" ]]; then
    return 0
  fi
  if ! "${py}" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)
PY
  then
    return 0
  fi
  if ! "${py}" - <<'PY' >/dev/null 2>&1
import dataclasses_json
import tree_sitter
PY
  then
    return 0
  fi
  if [[ -f "${ROOT_DIR}/GraphLocator/newtest/scripts/ensure_tree_sitter_lib.py" ]]; then
    if ! "${py}" "${ROOT_DIR}/GraphLocator/newtest/scripts/ensure_tree_sitter_lib.py" --no-build >/dev/null 2>&1; then
      return 0
    fi
  fi
  return 1
}

env_needs_setup() {
  local env_name="$1"
  if env_missing "${env_name}"; then
    return 0
  fi
  if [[ "${env_name}" == "graphlocator" ]] && graphlocator_env_unhealthy; then
    return 0
  fi
  return 1
}

run_logged() {
  local name="$1"
  shift
  local logfile="${LOG_DIR}/${name}.log"
  echo
  echo "========== ${name} =========="
  echo "[log] ${logfile}"
  echo "+ $*"
  if is_truthy "${DRY_RUN}"; then
    return 0
  fi
  (
    "$@" >"${logfile}" 2>&1
  ) &
  local pid=$!
  local start now elapsed status
  start="$(date +%s)"
  while kill -0 "${pid}" >/dev/null 2>&1; do
    sleep "${SERVER_HEARTBEAT_INTERVAL}"
    if kill -0 "${pid}" >/dev/null 2>&1; then
      now="$(date +%s)"
      elapsed=$((now - start))
      echo "[still running][$((elapsed / 60))m$((elapsed % 60))s] ${name}; log=${logfile}"
      if [[ "${SERVER_HEARTBEAT_TAIL_LINES}" =~ ^[0-9]+$ ]] && [[ "${SERVER_HEARTBEAT_TAIL_LINES}" -gt 0 ]] && [[ -f "${logfile}" ]]; then
        echo "[recent log:${name}] tail -n ${SERVER_HEARTBEAT_TAIL_LINES} ${logfile}"
        tail -n "${SERVER_HEARTBEAT_TAIL_LINES}" "${logfile}" | sed "s/^/[${name}] /"
      fi
    fi
  done
  set +e
  wait "${pid}"
  status=$?
  set -e
  return "${status}"
}

run_logged_with_supervisor_retry() {
  local name="$1"
  shift
  local max_attempts="${SUPERVISOR_MAX_ATTEMPTS:-1}"
  local retry_sleep="${SUPERVISOR_RETRY_SLEEP:-120}"
  local attempt status log_name

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
      log_name="${name}_attempt${attempt}"
      echo
      echo "========== ${name} supervisor attempt ${attempt}/${max_attempts} =========="
    else
      log_name="${name}"
    fi

    set +e
    run_logged "${log_name}" "$@"
    status=$?
    set -e

    if [[ "${status}" == "0" ]]; then
      if [[ "${max_attempts}" -gt 1 ]]; then
        echo "[supervisor-retry] ${name} succeeded on attempt ${attempt}/${max_attempts}."
      fi
      return 0
    fi

    if [[ "${attempt}" -ge "${max_attempts}" ]]; then
      echo "[supervisor-retry] ${name} failed after ${attempt}/${max_attempts} attempt(s); status=${status}." >&2
      return "${status}"
    fi

    echo "[supervisor-retry] ${name} failed with status ${status}; sleep ${retry_sleep}s before retry $((attempt + 1))/${max_attempts}." >&2
    sleep "${retry_sleep}"
    attempt=$((attempt + 1))
  done
}

setup_env() {
  local env_name="$1"
  local -a args=(--env "${env_name}")
  if is_truthy "${FORCE_RECREATE_ENVS}" || env_missing "${env_name}" || { [[ "${env_name}" == "graphlocator" ]] && graphlocator_env_unhealthy; }; then
    args+=(--recreate)
  fi
  if is_truthy "${NO_SMOKE_TEST}"; then
    args+=(--no-smoke-test)
  fi
  if is_truthy "${DRY_RUN}"; then
    args+=(--dry-run)
  fi
  run_logged "setup_${env_name}" \
    env CONDA_SH="${CONDA_SH}" CONDA_ENV_ROOT="${CONDA_ENV_ROOT}" \
      bash "${ROOT_DIR}/setup_baseline_conda_envs.sh" "${args[@]}"
}

check_python_or_die() {
  local env_name="$1"
  local py
  py="$(env_python "${env_name}")"
  if [[ ! -x "${py}" ]]; then
    if is_truthy "${DRY_RUN}"; then
      echo "[dry-run warn] ${env_name} python missing: ${py}"
      return 0
    fi
    echo "ERROR: ${env_name} python missing after setup: ${py}" >&2
    echo "Check ${LOG_DIR}/setup_${env_name}.log" >&2
    exit 2
  fi
  "${py}" -V
}

require_full_dev_inputs_or_explain() {
  local sample_count structure_count
  sample_count="$(count_jsonl_rows "${FULL_DEV_SAMPLES}")"
  structure_count="$(count_structures "${FULL_DEV_STRUCTURES}")"
  if [[ "${sample_count}" -ge "${SAMPLE_SIZE}" && "${structure_count}" -ge "${SAMPLE_SIZE}" ]]; then
    echo "[data] SWE-bench Multimodal full-dev local inputs ready: samples=${sample_count}, repo_structures=${structure_count}"
    return 0
  fi
  if is_truthy "${ALLOW_HF_PREPARE}"; then
    echo "[data] Local full-dev inputs incomplete: samples=${sample_count}, repo_structures=${structure_count}"
    echo "[data] ALLOW_HF_PREPARE=1, so the runner may try HuggingFace preparation."
    return 0
  fi
  if [[ "${ALLOW_HF_PREPARE}" == "auto" ]]; then
    echo "[data] Local full-dev inputs incomplete: samples=${sample_count}, repo_structures=${structure_count}"
    echo "[data] Checking HuggingFace dataset endpoint: ${HF_DATASET_API_URL}"
    if hf_dataset_available; then
      echo "[data] HuggingFace dataset endpoint is reachable."
      echo "[data] The runner will download/prepare samples and clone/build repo_structures as needed."
      return 0
    fi
    echo "[data] HuggingFace dataset endpoint is not reachable from this shell."
  fi
  cat >&2 <<EOF
ERROR: SWE-bench Multimodal full-dev local inputs are incomplete.

Found:
  samples rows:      ${sample_count}
  repo_structures:   ${structure_count}

Expected:
  ${FULL_DEV_SAMPLES}
  ${FULL_DEV_STRUCTURES}/*.json  (${SAMPLE_SIZE} files)

Fix one of these:
  1. Allow HuggingFace preparation:
       ALLOW_HF_PREPARE=1 HF_ENDPOINT=https://hf-mirror.com bash ${0##*/}
  2. Copy prepared LocAgent/newtest/${EXP_NAME}/data and repo_structures from another machine.
  3. Provide a local source JSONL:
       SOURCE_JSONL=/path/to/swebench_multimodal_dev.jsonl bash ${0##*/}
EOF
  exit 2
}

require_runtime_sources_or_explain() {
  local missing=0
  if [[ ! -f "${ROOT_DIR}/LocAgent/newtest/scripts/prepare_multimodal_localization.py" ]]; then
    echo "ERROR: missing LocAgent prepare script." >&2
    missing=1
  fi
  if baseline_enabled gala && [[ ! -f "${ROOT_DIR}/GALA/mytest/scripts/run_gala_swebench_multimodal_60_localization.sh" ]]; then
    echo "ERROR: missing GALA SWE-bench runner: ${ROOT_DIR}/GALA/mytest/scripts/run_gala_swebench_multimodal_60_localization.sh" >&2
    echo "       Pull the latest repository. This file used to be easy to miss on servers." >&2
    missing=1
  fi
  if baseline_enabled cosil && ! grep -q "COSIL_BACKEND_MODEL" "${ROOT_DIR}/CoSIL/CoSIL/util/model.py" 2>/dev/null; then
    echo "[compat warn] CoSIL source does not contain COSIL_BACKEND_MODEL support." >&2
    echo "[compat warn] This runner will pass MODEL=${LITELLM_MODEL_NAME}, but you should pull the latest code." >&2
  fi
  if baseline_enabled graphlocator && ! grep -q "GRAPHLOCATOR_BACKEND_MODEL" "${ROOT_DIR}/GraphLocator/llms/__init__.py" 2>/dev/null; then
    echo "[compat warn] GraphLocator source does not contain GRAPHLOCATOR_BACKEND_MODEL support." >&2
    echo "[compat warn] This runner will pass MODEL=${LITELLM_MODEL_NAME}, but you should pull the latest code." >&2
  fi
  if [[ "${missing}" == "1" ]]; then
    exit 2
  fi
}

ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env.swe_full_dev}"
if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
fi

if [[ -n "${CONDA_SH:-}" && ! -f "${CONDA_SH}" ]]; then
  warn "CONDA_SH does not exist on this machine: ${CONDA_SH}"
  warn "Ignoring CONDA_SH and auto-detecting conda for the current machine."
  unset CONDA_SH
fi
CONDA_SH="${CONDA_SH:-$(detect_conda_sh || true)}"

if [[ -n "${CONDA_ENV_ROOT:-}" && ! -d "$(dirname "${CONDA_ENV_ROOT%/}")" ]]; then
  warn "CONDA_ENV_ROOT parent does not exist on this machine: $(dirname "${CONDA_ENV_ROOT%/}")"
  warn "Ignoring CONDA_ENV_ROOT and auto-detecting an env root for the current machine."
  unset CONDA_ENV_ROOT
fi
CONDA_ENV_ROOT="${CONDA_ENV_ROOT:-$(detect_conda_env_root || true)}"

BASE_URL="${BASE_URL:-}"
API_KEY="${API_KEY:-}"
MODEL_NAME="${MODEL_NAME:-}"
EXP_NAME="${EXP_NAME:-swebench_multimodal-full-dev}"
DATASET="${DATASET:-SWE-bench/SWE-bench_Multimodal}"
SPLIT="${SPLIT:-dev}"
SAMPLE_SIZE="${SAMPLE_SIZE:-102}"
SEED="${SEED:-20260614}"
USED_LIST="${USED_LIST:-swebench_multimodal_full_dev_instances}"
SOURCE_JSONL="${SOURCE_JSONL:-}"
PARALLEL="${PARALLEL:-1}"
MAX_PARALLEL_BASELINES="${MAX_PARALLEL_BASELINES:-2}"
BASELINES="${BASELINES:-locagent cosil graphlocator gala mmir}"
BASELINE_ENVS="${BASELINE_ENVS:-${BASELINES}}"
RUN_MMIR_METHODS="${RUN_MMIR_METHODS:-bm25-mmir e5-mmir jina-code-v2-mmir codesage-large-v2-mmir coderankembed-mmir}"
ALLOW_HF_PREPARE="${ALLOW_HF_PREPARE:-auto}"
HF_DATASET_ID="${HF_DATASET_ID:-SWE-bench/SWE-bench_Multimodal}"
HF_DATASET_API_URL="${HF_DATASET_API_URL:-https://huggingface.co/api/datasets/${HF_DATASET_ID}}"
HF_ENDPOINT="${HF_ENDPOINT:-}"
DENSE_DEVICE="${DENSE_DEVICE:-cuda}"
DENSE_BATCH_SIZE="${DENSE_BATCH_SIZE:-16}"
DENSE_DEVICE_AUTO_FALLBACK="${DENSE_DEVICE_AUTO_FALLBACK:-1}"
COSIL_MAX_EMPTY_RATE="${COSIL_MAX_EMPTY_RATE:-0.30}"
LLM_FAIL_FAST="${LLM_FAIL_FAST:-1}"
LLM_FAIL_FAST_PATTERNS="${LLM_FAIL_FAST_PATTERNS:-}"
SKIP_SETUP="${SKIP_SETUP:-0}"
FORCE_RECREATE_ENVS="${FORCE_RECREATE_ENVS:-0}"
NO_SMOKE_TEST="${NO_SMOKE_TEST:-0}"
DRY_RUN="${DRY_RUN:-0}"
API_PREFLIGHT="${API_PREFLIGHT:-1}"
API_PREFLIGHT_TIMEOUT="${API_PREFLIGHT_TIMEOUT:-30}"
API_NO_PROXY="${API_NO_PROXY:-1}"
API_NO_PROXY_HOSTS="${API_NO_PROXY_HOSTS:-}"
FORCE_PREPARE="${FORCE_PREPARE:-0}"
FORCE_STRUCTURES="${FORCE_STRUCTURES:-0}"
FORCE_RERUN="${FORCE_RERUN:-0}"
SERVER_HEARTBEAT_INTERVAL="${SERVER_HEARTBEAT_INTERVAL:-30}"
SERVER_HEARTBEAT_TAIL_LINES="${SERVER_HEARTBEAT_TAIL_LINES:-25}"
LIVE_LOGS="${LIVE_LOGS:-1}"
LIVE_LOG_LINES="${LIVE_LOG_LINES:-0}"
STATUS_INTERVAL="${STATUS_INTERVAL:-${SERVER_HEARTBEAT_INTERVAL}}"
FAIL_FAST_ON_BASELINE_FAILURE="${FAIL_FAST_ON_BASELINE_FAILURE:-1}"
SUPERVISOR_MAX_ATTEMPTS="${SUPERVISOR_MAX_ATTEMPTS:-1}"
SUPERVISOR_RETRY_SLEEP="${SUPERVISOR_RETRY_SLEEP:-120}"
LOG_DIR="${LOG_DIR:-${ROOT_DIR}/logs/server_swebench_multimodal_full_dev_$(date +%Y%m%d_%H%M%S)}"
GALA_SHARED_IMAGE_ROOT="${GALA_SHARED_IMAGE_ROOT:-${ROOT_DIR}/shared_assets/gala_images}"
GALA_IMAGE_DIR="${GALA_IMAGE_DIR:-${GALA_SWE_IMAGE_DIR:-${GALA_SHARED_IMAGE_ROOT}/${EXP_NAME}}}"
GALA_DOWNLOAD_IMAGES="${GALA_DOWNLOAD_IMAGES:-${DOWNLOAD_IMAGES:-1}}"
GALA_REUSE_IMAGE_IR="${GALA_REUSE_IMAGE_IR:-${REUSE_IMAGE_IR:-1}}"
GALA_RESUME_IMAGE_IR="${GALA_RESUME_IMAGE_IR:-${RESUME_IMAGE_IR:-1}}"
GALA_FORCE_IMAGE_IR="${GALA_FORCE_IMAGE_IR:-${FORCE_IMAGE_IR:-0}}"
GALA_CHECK_IMAGE_IR_COMPLETE="${GALA_CHECK_IMAGE_IR_COMPLETE:-${CHECK_IMAGE_IR_COMPLETE:-1}}"
GALA_IMAGE_DOWNLOAD_RETRIES="${GALA_IMAGE_DOWNLOAD_RETRIES:-${IMAGE_DOWNLOAD_RETRIES:-3}}"
GALA_IMAGE_DOWNLOAD_RETRY_SLEEP="${GALA_IMAGE_DOWNLOAD_RETRY_SLEEP:-${IMAGE_DOWNLOAD_RETRY_SLEEP:-10}}"
GALA_IMAGE_DOWNLOAD_BACKOFF="${GALA_IMAGE_DOWNLOAD_BACKOFF:-${IMAGE_DOWNLOAD_BACKOFF:-2}}"

FULL_DEV_SAMPLES="${ROOT_DIR}/LocAgent/newtest/${EXP_NAME}/data/samples.jsonl"
FULL_DEV_STRUCTURES="${ROOT_DIR}/LocAgent/newtest/${EXP_NAME}/repo_structures"

LLM_BASELINE_SELECTED=0
if [[ "${BASELINES}" =~ (^|[[:space:]])(locagent|cosil|graphlocator|gala)([[:space:]]|$) ]]; then
  LLM_BASELINE_SELECTED=1
fi

if [[ "${LLM_BASELINE_SELECTED}" == "1" ]]; then
  require_nonempty "BASE_URL" "${BASE_URL}"
  require_nonempty "API_KEY" "${API_KEY}"
  require_nonempty "MODEL_NAME" "${MODEL_NAME}"
else
  BASE_URL="${BASE_URL:-dummy}"
  API_KEY="${API_KEY:-dummy}"
  MODEL_NAME="${MODEL_NAME:-dummy}"
fi

LITELLM_MODEL_NAME="${LITELLM_MODEL_NAME:-${MODEL_NAME}}"
if [[ "${LITELLM_MODEL_NAME}" != */* ]]; then
  LITELLM_MODEL_NAME="openai/${LITELLM_MODEL_NAME}"
fi

API_NO_PROXY_VALUE="${NO_PROXY:-${no_proxy:-}}"
if [[ "${LLM_BASELINE_SELECTED}" == "1" ]] && is_truthy "${API_NO_PROXY}"; then
  API_NO_PROXY_VALUE="$(build_api_no_proxy)"
fi

RUN_MODEL_NAME="${MODEL_NAME}"
if baseline_enabled cosil && ! grep -q "COSIL_BACKEND_MODEL" "${ROOT_DIR}/CoSIL/CoSIL/util/model.py" 2>/dev/null; then
  echo "[compat warn] CoSIL does not support COSIL_BACKEND_MODEL yet; using MODEL=${LITELLM_MODEL_NAME} for this run." >&2
  RUN_MODEL_NAME="${LITELLM_MODEL_NAME}"
fi
if baseline_enabled graphlocator && ! grep -q "GRAPHLOCATOR_BACKEND_MODEL" "${ROOT_DIR}/GraphLocator/llms/__init__.py" 2>/dev/null; then
  echo "[compat warn] GraphLocator does not support GRAPHLOCATOR_BACKEND_MODEL yet; using MODEL=${LITELLM_MODEL_NAME} for this run." >&2
  RUN_MODEL_NAME="${LITELLM_MODEL_NAME}"
fi

mkdir -p "${LOG_DIR}" "${ROOT_DIR}/logs"

cat <<EOF
SWE-bench Multimodal full-dev server runner
Root: ${ROOT_DIR}
Conda sh: ${CONDA_SH}
Conda env root: ${CONDA_ENV_ROOT}
Experiment: ${EXP_NAME}
Dataset: ${DATASET}
Split: ${SPLIT}
Expected samples: ${SAMPLE_SIZE}
Canonical samples: ${FULL_DEV_SAMPLES} ($(count_jsonl_rows "${FULL_DEV_SAMPLES}") rows)
Canonical structures: ${FULL_DEV_STRUCTURES} ($(count_structures "${FULL_DEV_STRUCTURES}") files)
Base URL: ${BASE_URL}
Model: ${MODEL_NAME}
Run model: ${RUN_MODEL_NAME}
LiteLLM backend model: ${LITELLM_MODEL_NAME}
Dense device: ${DENSE_DEVICE}
Dense batch size: ${DENSE_BATCH_SIZE}
Dense CUDA auto fallback: ${DENSE_DEVICE_AUTO_FALLBACK}
Parallel mode: ${PARALLEL}
Max parallel baselines: ${MAX_PARALLEL_BASELINES}
Baseline envs: ${BASELINE_ENVS}
Baselines to run: ${BASELINES}
MM-IR methods: ${RUN_MMIR_METHODS}
HF endpoint: ${HF_ENDPOINT:-<default>}
Allow HF prepare: ${ALLOW_HF_PREPARE}
HF dataset endpoint: ${HF_DATASET_API_URL}
CoSIL max empty rate: ${COSIL_MAX_EMPTY_RATE}
LLM fail fast: ${LLM_FAIL_FAST}
API preflight: ${API_PREFLIGHT}
API no-proxy for LLM: ${API_NO_PROXY_VALUE:-<none>} (enabled=${API_NO_PROXY})
Skip setup: ${SKIP_SETUP}
Force recreate envs: ${FORCE_RECREATE_ENVS}
Force prepare: ${FORCE_PREPARE}
Force structures: ${FORCE_STRUCTURES}
Force rerun: ${FORCE_RERUN}
Dry run: ${DRY_RUN}
Heartbeat interval: ${SERVER_HEARTBEAT_INTERVAL}s
Heartbeat tail lines: ${SERVER_HEARTBEAT_TAIL_LINES}
Inner live logs: ${LIVE_LOGS}
Inner status interval: ${STATUS_INTERVAL}s
Fail fast on baseline failure: ${FAIL_FAST_ON_BASELINE_FAILURE}
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
Log dir: ${LOG_DIR}
EOF

if [[ ! -f "${CONDA_SH}" ]]; then
  echo "ERROR: CONDA_SH does not exist: ${CONDA_SH}" >&2
  echo "Set CONDA_SH=/path/to/miniconda3/etc/profile.d/conda.sh" >&2
  exit 2
fi

require_full_dev_inputs_or_explain
require_runtime_sources_or_explain

if is_truthy "${API_PREFLIGHT}" && [[ "${BASELINES}" =~ (^|[[:space:]])(locagent|cosil|graphlocator|gala)([[:space:]]|$) ]]; then
  echo
  echo "========== API preflight =========="
  echo "+ ${PYTHON:-python3} ${ROOT_DIR}/scripts/check_openai_compatible_api.py --base-url ${BASE_URL} --api-key <hidden> --model ${LITELLM_MODEL_NAME#openai/} --timeout ${API_PREFLIGHT_TIMEOUT}"
  if ! is_truthy "${DRY_RUN}"; then
    NO_PROXY="${API_NO_PROXY_VALUE}" no_proxy="${API_NO_PROXY_VALUE}" \
    "${PYTHON:-python3}" "${ROOT_DIR}/scripts/check_openai_compatible_api.py" \
      --base-url "${BASE_URL}" \
      --api-key "${API_KEY}" \
      --model "${LITELLM_MODEL_NAME#openai/}" \
      --timeout "${API_PREFLIGHT_TIMEOUT}"
  fi
fi

if ! is_truthy "${SKIP_SETUP}"; then
  for env_name in ${BASELINE_ENVS}; do
    if is_truthy "${FORCE_RECREATE_ENVS}" || env_needs_setup "${env_name}"; then
      echo "[setup] ${env_name} needs setup/recreate."
      setup_env "${env_name}"
    else
      echo "[setup] ${env_name} exists: $(env_python "${env_name}")"
    fi
  done
else
  echo "[setup] skipped because SKIP_SETUP=${SKIP_SETUP}"
fi

echo
echo "========== Verify baseline Python interpreters =========="
for env_name in ${BASELINE_ENVS}; do
  check_python_or_die "${env_name}"
done

RUN_SCRIPT="${ROOT_DIR}/run_swebench_multimodal_full_dev_baselines.sh"
if is_truthy "${PARALLEL}"; then
  RUN_SCRIPT="${ROOT_DIR}/run_swebench_multimodal_full_dev_baselines_parallel.sh"
fi

run_logged_with_supervisor_retry "run_swebench_multimodal_full_dev" \
  env \
    NO_PROXY="${API_NO_PROXY_VALUE}" \
    no_proxy="${API_NO_PROXY_VALUE}" \
    CONDA_ENV_ROOT="${CONDA_ENV_ROOT}" \
    EXP_NAME="${EXP_NAME}" \
    DATASET="${DATASET}" \
    SPLIT="${SPLIT}" \
    SAMPLE_SIZE="${SAMPLE_SIZE}" \
    SEED="${SEED}" \
    USED_LIST="${USED_LIST}" \
    SOURCE_JSONL="${SOURCE_JSONL}" \
    BASELINES="${BASELINES}" \
    RUN_LOCAGENT="$(baseline_enabled locagent && echo 1 || echo 0)" \
    RUN_COSIL="$(baseline_enabled cosil && echo 1 || echo 0)" \
    RUN_GRAPHLOCATOR="$(baseline_enabled graphlocator && echo 1 || echo 0)" \
    RUN_GALA="$(baseline_enabled gala && echo 1 || echo 0)" \
    RUN_MMIR="$(baseline_enabled mmir && echo 1 || echo 0)" \
    RUN_MMIR_METHODS="${RUN_MMIR_METHODS}" \
    COSIL_MAX_EMPTY_RATE="${COSIL_MAX_EMPTY_RATE}" \
    LLM_FAIL_FAST="${LLM_FAIL_FAST}" \
    LLM_FAIL_FAST_PATTERNS="${LLM_FAIL_FAST_PATTERNS}" \
    API_PREFLIGHT=0 \
    HF_ENDPOINT="${HF_ENDPOINT}" \
    OPENAI_API_BASE="${BASE_URL}" \
    OPENAI_API_KEY="${API_KEY}" \
    MODEL="${RUN_MODEL_NAME}" \
    LITELLM_MODEL="${LITELLM_MODEL_NAME}" \
    LOCAGENT_BACKEND_MODEL="${LITELLM_MODEL_NAME}" \
    COSIL_BACKEND_MODEL="${LITELLM_MODEL_NAME}" \
    GRAPHLOCATOR_BACKEND_MODEL="${LITELLM_MODEL_NAME}" \
    VLM_MODEL="${MODEL_NAME}" \
    TEXT_MODEL_NAME="${MODEL_NAME}" \
    MULADAPTER_MODEL="${MODEL_NAME}" \
    MULADAPTER_BASE_URL="${BASE_URL}" \
    MULADAPTER_API_KEY="${API_KEY}" \
    VLM_BASE_URL="${BASE_URL}" \
    VLM_API_KEY="${API_KEY}" \
    TEXT_BASE_URL="${BASE_URL}" \
    TEXT_API_KEY="${API_KEY}" \
    GALA_IMAGE_DIR="${GALA_IMAGE_DIR}" \
    GALA_DOWNLOAD_IMAGES="${GALA_DOWNLOAD_IMAGES}" \
    GALA_REUSE_IMAGE_IR="${GALA_REUSE_IMAGE_IR}" \
    GALA_RESUME_IMAGE_IR="${GALA_RESUME_IMAGE_IR}" \
    GALA_FORCE_IMAGE_IR="${GALA_FORCE_IMAGE_IR}" \
    GALA_CHECK_IMAGE_IR_COMPLETE="${GALA_CHECK_IMAGE_IR_COMPLETE}" \
    GALA_IMAGE_DOWNLOAD_RETRIES="${GALA_IMAGE_DOWNLOAD_RETRIES}" \
    GALA_IMAGE_DOWNLOAD_RETRY_SLEEP="${GALA_IMAGE_DOWNLOAD_RETRY_SLEEP}" \
    GALA_IMAGE_DOWNLOAD_BACKOFF="${GALA_IMAGE_DOWNLOAD_BACKOFF}" \
    DENSE_DEVICE="${DENSE_DEVICE}" \
    DENSE_BATCH_SIZE="${DENSE_BATCH_SIZE}" \
    DENSE_DEVICE_AUTO_FALLBACK="${DENSE_DEVICE_AUTO_FALLBACK}" \
    FORCE_PREPARE="${FORCE_PREPARE}" \
    FORCE_STRUCTURES="${FORCE_STRUCTURES}" \
    FORCE_RERUN="${FORCE_RERUN}" \
    MAX_PARALLEL_BASELINES="${MAX_PARALLEL_BASELINES}" \
    LIVE_LOGS="${LIVE_LOGS}" \
    LIVE_LOG_LINES="${LIVE_LOG_LINES}" \
    STATUS_INTERVAL="${STATUS_INTERVAL}" \
    FAIL_FAST_ON_BASELINE_FAILURE="${FAIL_FAST_ON_BASELINE_FAILURE}" \
    DRY_RUN="${DRY_RUN}" \
    bash "${RUN_SCRIPT}"

echo
echo "Done."
echo "Logs: ${LOG_DIR}"
