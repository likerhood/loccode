#!/usr/bin/env bash
set -euo pipefail

# One script for server-side SWE-bench Multimodal 60.
#
# It does three things:
#   1. checks required API/model/server configuration;
#   2. creates or repairs conda envs for all baselines;
#   3. runs the SWE-bench Multimodal 60 subset.
#
# Required env vars:
#   BASE_URL      OpenAI-compatible API base URL
#   API_KEY       API key
#   MODEL_NAME    model name, e.g. mimo-v2.5
#
# Typical usage:
#   export BASE_URL="https://token-plan-sgp.xiaomimimo.com/v1"
#   export API_KEY="..."
#   export MODEL_NAME="mimo-v2.5"
#   CONDA_SH=/data2/like/miniconda3/etc/profile.d/conda.sh \
#   CONDA_ENV_ROOT=/data2/like/envs \
#   bash server_check_setup_run_swe60.sh

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env.swe60}"
if [[ -f "${ENV_FILE}" ]]; then
  # Load local secrets/config. This file is ignored by .gitignore via .env.*.
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
fi

CONDA_SH="${CONDA_SH:-/data2/like/miniconda3/etc/profile.d/conda.sh}"
CONDA_ENV_ROOT="${CONDA_ENV_ROOT:-/data2/like/envs}"
BASE_URL="${BASE_URL:-}"
API_KEY="${API_KEY:-}"
MODEL_NAME="${MODEL_NAME:-}"
DENSE_DEVICE="${DENSE_DEVICE:-cuda}"
DENSE_BATCH_SIZE="${DENSE_BATCH_SIZE:-16}"
PARALLEL="${PARALLEL:-0}"
MAX_PARALLEL_BASELINES="${MAX_PARALLEL_BASELINES:-2}"
FORCE_RECREATE_ENVS="${FORCE_RECREATE_ENVS:-0}"
SKIP_SETUP="${SKIP_SETUP:-0}"
NO_SMOKE_TEST="${NO_SMOKE_TEST:-0}"
DRY_RUN="${DRY_RUN:-0}"
LOG_DIR="${LOG_DIR:-${ROOT_DIR}/logs/server_swe60_$(date +%Y%m%d_%H%M%S)}"
BASELINE_ENVS="${BASELINE_ENVS:-locagent cosil graphlocator gala mmir}"

is_truthy() {
  [[ "${1:-}" == "1" || "${1:-}" == "true" || "${1:-}" == "yes" ]]
}

require_nonempty() {
  local name="$1"
  local value="$2"
  if [[ -z "${value}" ]]; then
    echo "ERROR: ${name} is required." >&2
    echo "Example:" >&2
    echo "  export BASE_URL='https://token-plan-sgp.xiaomimimo.com/v1'" >&2
    echo "  export API_KEY='...'" >&2
    echo "  export MODEL_NAME='mimo-v2.5'" >&2
    exit 2
  fi
}

env_python() {
  local env_name="$1"
  echo "${CONDA_ENV_ROOT%/}/${env_name}/bin/python"
}

env_missing() {
  local env_name="$1"
  [[ ! -x "$(env_python "${env_name}")" ]]
}

run_logged() {
  local name="$1"
  shift
  local logfile="${LOG_DIR}/${name}.log"
  echo
  echo "========== ${name} =========="
  echo "[log] ${logfile}"
  if is_truthy "${DRY_RUN}"; then
    echo "+ $*"
  else
    "$@" 2>&1 | tee "${logfile}"
  fi
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

require_nonempty "BASE_URL" "${BASE_URL}"
require_nonempty "API_KEY" "${API_KEY}"
require_nonempty "MODEL_NAME" "${MODEL_NAME}"

mkdir -p "${LOG_DIR}" "${ROOT_DIR}/logs"

cat <<EOF
SWE-bench Multimodal 60 server runner
Root: ${ROOT_DIR}
Conda sh: ${CONDA_SH}
Conda env root: ${CONDA_ENV_ROOT}
Base URL: ${BASE_URL}
Model: ${MODEL_NAME}
Dense device: ${DENSE_DEVICE}
Dense batch size: ${DENSE_BATCH_SIZE}
Parallel mode: ${PARALLEL}
Max parallel baselines: ${MAX_PARALLEL_BASELINES}
Baseline envs: ${BASELINE_ENVS}
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

RUN_SCRIPT="${ROOT_DIR}/run_swebench_multimodal_60_baselines.sh"
if is_truthy "${PARALLEL}"; then
  RUN_SCRIPT="${ROOT_DIR}/run_swebench_multimodal_60_baselines_parallel.sh"
fi

run_logged "run_swebench_multimodal_60" \
  env \
    CONDA_ENV_ROOT="${CONDA_ENV_ROOT}" \
    OPENAI_API_BASE="${BASE_URL}" \
    OPENAI_API_KEY="${API_KEY}" \
    MODEL="${MODEL_NAME}" \
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
    MAX_PARALLEL_BASELINES="${MAX_PARALLEL_BASELINES}" \
    DRY_RUN="${DRY_RUN}" \
    bash "${RUN_SCRIPT}"

echo
echo "Done."
echo "Logs: ${LOG_DIR}"
