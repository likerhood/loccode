#!/usr/bin/env bash
set -euo pipefail

# Overnight sequential runner for the two 60-sample experiments with one model.
#
# Runs in order:
#   1. SWE-bench Multimodal 60
#   2. OmniGIRL unified 60
#
# It does not run baselines in parallel. Each underlying runner still supports
# resume/eval-only recovery, so rerunning this script is safe.
#
# Required environment variables:
#   BASE_URL      OpenAI-compatible API base URL
#   API_KEY       API key
#   MODEL_NAME    model name, e.g. mimo-v2.5
#
# Optional:
#   CONDA_ENV_ROOT=/data2/like/envs
#   RUN_SETUP=1              run setup_baseline_conda_envs.sh before experiments
#   RECREATE_ENVS=1          pass --recreate to setup script
#   RUN_SWE60=0              skip SWE 60
#   RUN_OMNI60=0             skip Omni 60

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CONDA_ENV_ROOT="${CONDA_ENV_ROOT:-/data2/like/envs}"
CONDA_SH="${CONDA_SH:-/data2/like/miniconda3/etc/profile.d/conda.sh}"
BASE_URL="${BASE_URL:-}"
API_KEY="${API_KEY:-}"
MODEL_NAME="${MODEL_NAME:-}"
RUN_SETUP="${RUN_SETUP:-0}"
RECREATE_ENVS="${RECREATE_ENVS:-0}"
RUN_SWE60="${RUN_SWE60:-1}"
RUN_OMNI60="${RUN_OMNI60:-1}"
DENSE_DEVICE="${DENSE_DEVICE:-cuda}"
DENSE_BATCH_SIZE="${DENSE_BATCH_SIZE:-16}"
LOG_DIR="${LOG_DIR:-${ROOT_DIR}/logs/mimo60_sequential_$(date +%Y%m%d_%H%M%S)}"

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

check_env_python() {
  local env_name="$1"
  local py="${CONDA_ENV_ROOT%/}/${env_name}/bin/python"
  if [[ ! -x "${py}" ]]; then
    echo "ERROR: missing python for ${env_name}: ${py}" >&2
    echo "Run setup first, for example:" >&2
    echo "  CONDA_SH='${CONDA_SH}' CONDA_ENV_ROOT='${CONDA_ENV_ROOT}' bash setup_baseline_conda_envs.sh" >&2
    echo "If the environment is half-created, use:" >&2
    echo "  CONDA_SH='${CONDA_SH}' CONDA_ENV_ROOT='${CONDA_ENV_ROOT}' bash setup_baseline_conda_envs.sh --recreate" >&2
    exit 2
  fi
}

run_step() {
  local name="$1"
  shift
  local logfile="${LOG_DIR}/${name}.log"
  echo
  echo "========== ${name} =========="
  echo "[log] ${logfile}"
  "$@" 2>&1 | tee "${logfile}"
}

require_nonempty "BASE_URL" "${BASE_URL}"
require_nonempty "API_KEY" "${API_KEY}"
require_nonempty "MODEL_NAME" "${MODEL_NAME}"

mkdir -p "${LOG_DIR}"

cat <<EOF
Sequential MIMO 60 runner
Root: ${ROOT_DIR}
Conda env root: ${CONDA_ENV_ROOT}
Base URL: ${BASE_URL}
Model: ${MODEL_NAME}
Dense device: ${DENSE_DEVICE}
Dense batch size: ${DENSE_BATCH_SIZE}
Log dir: ${LOG_DIR}
Run setup: ${RUN_SETUP}
Run SWE60: ${RUN_SWE60}
Run Omni60: ${RUN_OMNI60}
EOF

if is_truthy "${RUN_SETUP}"; then
  SETUP_ARGS=()
  if is_truthy "${RECREATE_ENVS}"; then
    SETUP_ARGS+=(--recreate)
  fi
  run_step "setup_envs" \
    env CONDA_SH="${CONDA_SH}" CONDA_ENV_ROOT="${CONDA_ENV_ROOT}" \
      bash "${ROOT_DIR}/setup_baseline_conda_envs.sh" "${SETUP_ARGS[@]}"
fi

check_env_python locagent
check_env_python cosil
check_env_python graphlocator
check_env_python gala
check_env_python mmir

COMMON_ENV=(
  CONDA_ENV_ROOT="${CONDA_ENV_ROOT}"
  OPENAI_API_BASE="${BASE_URL}"
  OPENAI_API_KEY="${API_KEY}"
  MODEL="${MODEL_NAME}"
  VLM_MODEL="${MODEL_NAME}"
  TEXT_MODEL_NAME="${MODEL_NAME}"
  MULADAPTER_MODEL="${MODEL_NAME}"
  MULADAPTER_BASE_URL="${BASE_URL}"
  MULADAPTER_API_KEY="${API_KEY}"
  VLM_BASE_URL="${BASE_URL}"
  VLM_API_KEY="${API_KEY}"
  TEXT_BASE_URL="${BASE_URL}"
  TEXT_API_KEY="${API_KEY}"
  DENSE_DEVICE="${DENSE_DEVICE}"
  DENSE_BATCH_SIZE="${DENSE_BATCH_SIZE}"
  MAX_PARALLEL_BASELINES=1
)

if is_truthy "${RUN_SWE60}"; then
  run_step "swebench_multimodal_60" \
    env "${COMMON_ENV[@]}" bash "${ROOT_DIR}/run_swebench_multimodal_60_baselines.sh"
fi

if is_truthy "${RUN_OMNI60}"; then
  run_step "omnigirl_60" \
    env "${COMMON_ENV[@]}" bash "${ROOT_DIR}/run_omnigirl_60_baselines.sh"
fi

echo
echo "All requested sequential jobs finished."
echo "Logs: ${LOG_DIR}"
