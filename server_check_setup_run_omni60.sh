#!/usr/bin/env bash
set -euo pipefail

# Server-side OmniGIRL unified60 runner.
#
# This mirrors server_check_setup_run_swe60.sh, but is intentionally scoped to
# OmniGIRL 60. It is safe for a fresh git clone where data/, repo_structures/,
# and local test JSONL files are absent: the downstream prepare script will use
# a local source if available, otherwise HuggingFace.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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

resolve_local_omni_source() {
  local candidate
  local candidates=(
    "${SOURCE_JSONL:-}"
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

hf_dataset_available() {
  if ! command -v curl >/dev/null 2>&1; then
    return 1
  fi
  curl -fsSL --connect-timeout 10 --max-time 30 "${HF_DATASET_API_URL}" >/dev/null 2>&1
}

require_runtime_sources_or_explain() {
  local missing=0
  if baseline_enabled gala && [[ ! -f "${ROOT_DIR}/GALA/mytest/scripts/run_gala_omnigirl_js_ts_60_localization.sh" ]]; then
    echo "ERROR: missing GALA Omni runner: ${ROOT_DIR}/GALA/mytest/scripts/run_gala_omnigirl_js_ts_60_localization.sh" >&2
    echo "       Pull the latest repository. This file used to be easy to miss on servers." >&2
    missing=1
  fi
  if [[ ! -f "${ROOT_DIR}/LocAgent/newtest/scripts/prepare_multimodal_localization.py" ]]; then
    echo "ERROR: missing LocAgent prepare script." >&2
    missing=1
  elif ! grep -q "Deep-Software-Analytics/OmniGIRL" "${ROOT_DIR}/LocAgent/newtest/scripts/prepare_multimodal_localization.py"; then
    echo "ERROR: LocAgent prepare script is stale and lacks OmniGIRL HuggingFace fallback." >&2
    echo "       Pull the latest repository before running on a fresh server clone." >&2
    missing=1
  fi
  if [[ "${missing}" == "1" ]]; then
    exit 2
  fi
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
    set -o pipefail
    "$@" 2>&1 | tee "${logfile}"
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

setup_env() {
  local env_name="$1"
  local -a args=(--env "${env_name}")
  if is_truthy "${FORCE_RECREATE_ENVS}" || env_missing "${env_name}"; then
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

ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env.omni60}"
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
PARALLEL="${PARALLEL:-1}"
MAX_PARALLEL_BASELINES="${MAX_PARALLEL_BASELINES:-2}"
BASELINES="${BASELINES:-locagent cosil graphlocator gala}"
BASELINE_ENVS="${BASELINE_ENVS:-${BASELINES}}"
RUN_MMIR_METHODS="${RUN_MMIR_METHODS:-bm25-mmir e5-mmir jina-code-v2-mmir codesage-large-v2-mmir coderankembed-mmir}"
ALLOW_HF_PREPARE="${ALLOW_HF_PREPARE:-auto}"
HF_DATASET_ID="${HF_DATASET_ID:-Deep-Software-Analytics/OmniGIRL}"
HF_DATASET_API_URL="${HF_DATASET_API_URL:-https://huggingface.co/api/datasets/${HF_DATASET_ID}}"
HF_ENDPOINT="${HF_ENDPOINT:-}"
DENSE_DEVICE="${DENSE_DEVICE:-cuda}"
DENSE_BATCH_SIZE="${DENSE_BATCH_SIZE:-16}"
DENSE_DEVICE_AUTO_FALLBACK="${DENSE_DEVICE_AUTO_FALLBACK:-1}"
SKIP_SETUP="${SKIP_SETUP:-0}"
FORCE_RECREATE_ENVS="${FORCE_RECREATE_ENVS:-0}"
NO_SMOKE_TEST="${NO_SMOKE_TEST:-0}"
DRY_RUN="${DRY_RUN:-0}"
API_PREFLIGHT="${API_PREFLIGHT:-1}"
API_PREFLIGHT_TIMEOUT="${API_PREFLIGHT_TIMEOUT:-30}"
SERVER_HEARTBEAT_INTERVAL="${SERVER_HEARTBEAT_INTERVAL:-30}"
SERVER_HEARTBEAT_TAIL_LINES="${SERVER_HEARTBEAT_TAIL_LINES:-25}"
LIVE_LOGS="${LIVE_LOGS:-1}"
LIVE_LOG_LINES="${LIVE_LOG_LINES:-0}"
STATUS_INTERVAL="${STATUS_INTERVAL:-${SERVER_HEARTBEAT_INTERVAL}}"
FAIL_FAST_ON_BASELINE_FAILURE="${FAIL_FAST_ON_BASELINE_FAILURE:-1}"
LOG_DIR="${LOG_DIR:-${ROOT_DIR}/logs/server_omni60_$(date +%Y%m%d_%H%M%S)}"

OMNI60_SAMPLES="${ROOT_DIR}/LocAgent/newtest/omnigirl-unified60/data/samples.jsonl"
OMNI60_STRUCTURES="${ROOT_DIR}/LocAgent/newtest/omnigirl-unified60/repo_structures"
LOCAL_OMNI_SOURCE="$(resolve_local_omni_source)"

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
OmniGIRL unified60 server runner
Root: ${ROOT_DIR}
Conda sh: ${CONDA_SH}
Conda env root: ${CONDA_ENV_ROOT}
Base URL: ${BASE_URL}
Model: ${MODEL_NAME}
Run model: ${RUN_MODEL_NAME}
LiteLLM backend model: ${LITELLM_MODEL_NAME}
Parallel mode: ${PARALLEL}
Max parallel baselines: ${MAX_PARALLEL_BASELINES}
Baseline envs: ${BASELINE_ENVS}
Baselines to run: ${BASELINES}
MM-IR methods: ${RUN_MMIR_METHODS}
HF endpoint: ${HF_ENDPOINT:-<default>}
Allow HF prepare: ${ALLOW_HF_PREPARE}
HF dataset endpoint: ${HF_DATASET_API_URL}
Local Omni source: ${LOCAL_OMNI_SOURCE:-<none>}
Canonical samples: ${OMNI60_SAMPLES} ($(count_jsonl_rows "${OMNI60_SAMPLES}") rows)
Canonical structures: ${OMNI60_STRUCTURES} ($(count_structures "${OMNI60_STRUCTURES}") files)
Skip setup: ${SKIP_SETUP}
Force recreate envs: ${FORCE_RECREATE_ENVS}
Dry run: ${DRY_RUN}
Log dir: ${LOG_DIR}
EOF

if [[ ! -f "${CONDA_SH}" ]]; then
  echo "ERROR: CONDA_SH does not exist: ${CONDA_SH}" >&2
  echo "Set CONDA_SH=/path/to/miniconda3/etc/profile.d/conda.sh" >&2
  exit 2
fi

if [[ "$(count_jsonl_rows "${OMNI60_SAMPLES}")" -lt 60 && -z "${LOCAL_OMNI_SOURCE}" ]]; then
  if is_truthy "${ALLOW_HF_PREPARE}"; then
    echo "[data] No local Omni source; ALLOW_HF_PREPARE=1, downstream prepare may download from HF."
  elif [[ "${ALLOW_HF_PREPARE}" == "auto" ]]; then
    echo "[data] No local Omni source; checking HuggingFace dataset endpoint: ${HF_DATASET_API_URL}"
    if hf_dataset_available; then
      echo "[data] HuggingFace dataset endpoint is reachable; downstream prepare may download."
    else
      cat >&2 <<EOF
ERROR: OmniGIRL unified60 inputs are missing and HuggingFace is not reachable.

Missing:
  ${OMNI60_SAMPLES}
  local source candidates under LocAgent/test/ or MM-IR/data/

Fix one of these:
  1. Set SOURCE_JSONL=/path/to/omnigirl_source.jsonl
  2. Set HF_ENDPOINT=https://hf-mirror.com ALLOW_HF_PREPARE=1
  3. Copy prepared LocAgent/newtest/omnigirl-unified60/data and repo_structures from another machine.
EOF
      exit 2
    fi
  else
    echo "ERROR: OmniGIRL unified60 inputs are missing and ALLOW_HF_PREPARE=0." >&2
    exit 2
  fi
fi

require_runtime_sources_or_explain

if is_truthy "${API_PREFLIGHT}" && [[ "${BASELINES}" =~ (^|[[:space:]])(locagent|cosil|graphlocator|gala)([[:space:]]|$) ]]; then
  echo
  echo "========== API preflight =========="
  echo "+ ${PYTHON:-python3} ${ROOT_DIR}/scripts/check_openai_compatible_api.py --base-url ${BASE_URL} --api-key <hidden> --model ${LITELLM_MODEL_NAME#openai/} --timeout ${API_PREFLIGHT_TIMEOUT}"
  if ! is_truthy "${DRY_RUN}"; then
    "${PYTHON:-python3}" "${ROOT_DIR}/scripts/check_openai_compatible_api.py" \
      --base-url "${BASE_URL}" \
      --api-key "${API_KEY}" \
      --model "${LITELLM_MODEL_NAME#openai/}" \
      --timeout "${API_PREFLIGHT_TIMEOUT}"
  fi
fi

if ! is_truthy "${SKIP_SETUP}"; then
  for env_name in ${BASELINE_ENVS}; do
    if is_truthy "${FORCE_RECREATE_ENVS}" || env_missing "${env_name}"; then
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

RUN_SCRIPT="${ROOT_DIR}/run_omnigirl_60_baselines.sh"
if is_truthy "${PARALLEL}"; then
  RUN_SCRIPT="${ROOT_DIR}/run_omnigirl_60_baselines_parallel.sh"
fi

run_logged "run_omnigirl_60" \
  env \
    CONDA_ENV_ROOT="${CONDA_ENV_ROOT}" \
    SOURCE_JSONL="${SOURCE_JSONL:-}" \
    OMNIGIRL_SOURCE_JSONL="${OMNIGIRL_SOURCE_JSONL:-}" \
    BASELINES="${BASELINES}" \
    RUN_LOCAGENT="$(baseline_enabled locagent && echo 1 || echo 0)" \
    RUN_COSIL="$(baseline_enabled cosil && echo 1 || echo 0)" \
    RUN_GRAPHLOCATOR="$(baseline_enabled graphlocator && echo 1 || echo 0)" \
    RUN_GALA="$(baseline_enabled gala && echo 1 || echo 0)" \
    RUN_MMIR="$(baseline_enabled mmir && echo 1 || echo 0)" \
    RUN_MMIR_METHODS="${RUN_MMIR_METHODS}" \
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
    DENSE_DEVICE="${DENSE_DEVICE}" \
    DENSE_BATCH_SIZE="${DENSE_BATCH_SIZE}" \
    DENSE_DEVICE_AUTO_FALLBACK="${DENSE_DEVICE_AUTO_FALLBACK}" \
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
