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
ALLOW_HF_PREPARE="${ALLOW_HF_PREPARE:-auto}"
HF_DATASET_ID="${HF_DATASET_ID:-SWE-bench/SWE-bench_Multimodal}"
HF_DATASET_API_URL="${HF_DATASET_API_URL:-https://huggingface.co/api/datasets/${HF_DATASET_ID}}"
SWE60_INPUT_TAR="${SWE60_INPUT_TAR:-${ROOT_DIR}/swebench_multimodal_60_inputs.tar.gz}"
LOG_DIR="${LOG_DIR:-${ROOT_DIR}/logs/server_swe60_$(date +%Y%m%d_%H%M%S)}"
BASELINE_ENVS="${BASELINE_ENVS:-locagent cosil graphlocator gala mmir}"
SWE60_SAMPLES="${ROOT_DIR}/LocAgent/newtest/swebench_multimodal-60/data/samples.jsonl"
SWE60_STRUCTURES="${ROOT_DIR}/LocAgent/newtest/swebench_multimodal-60/repo_structures"

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
import tree_sitter
PY
  then
    return 0
  fi
  if ! "${py}" "${ROOT_DIR}/GraphLocator/newtest/scripts/ensure_tree_sitter_lib.py" --no-build >/dev/null 2>&1; then
    return 0
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
  if is_truthy "${DRY_RUN}"; then
    echo "+ $*"
  else
    "$@" 2>&1 | tee "${logfile}"
  fi
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

count_swe60_samples() {
  if [[ -f "${SWE60_SAMPLES}" ]]; then
    wc -l < "${SWE60_SAMPLES}" | tr -d ' '
  else
    echo 0
  fi
}

count_swe60_structures() {
  if [[ -d "${SWE60_STRUCTURES}" ]]; then
    find "${SWE60_STRUCTURES}" -maxdepth 1 -type f -name '*.json' | wc -l | tr -d ' '
  else
    echo 0
  fi
}

maybe_unpack_swe60_inputs() {
  local sample_count structure_count
  sample_count="$(count_swe60_samples)"
  structure_count="$(count_swe60_structures)"
  if [[ "${sample_count}" -ge 60 && "${structure_count}" -ge 60 ]]; then
    return 0
  fi
  if [[ -f "${SWE60_INPUT_TAR}" ]]; then
    echo "[data] Found SWE60 input archive: ${SWE60_INPUT_TAR}"
    echo "[data] Unpacking it into ${ROOT_DIR}"
    if ! is_truthy "${DRY_RUN}"; then
      tar -xzf "${SWE60_INPUT_TAR}" -C "${ROOT_DIR}"
    fi
  fi
}

hf_dataset_available() {
  if ! command -v curl >/dev/null 2>&1; then
    return 1
  fi
  curl -fsSL --connect-timeout 10 --max-time 30 "${HF_DATASET_API_URL}" >/dev/null 2>&1
}

require_swe60_inputs_or_explain() {
  local sample_count structure_count
  sample_count="$(count_swe60_samples)"
  structure_count="$(count_swe60_structures)"
  if [[ "${sample_count}" -ge 60 && "${structure_count}" -ge 60 ]]; then
    echo "[data] SWE60 local inputs ready: samples=${sample_count}, repo_structures=${structure_count}"
    return 0
  fi
  if is_truthy "${ALLOW_HF_PREPARE}"; then
    echo "[data] Local SWE60 inputs incomplete: samples=${sample_count}, repo_structures=${structure_count}"
    echo "[data] ALLOW_HF_PREPARE=1, so the runner may try HuggingFace preparation."
    return 0
  fi
  if [[ "${ALLOW_HF_PREPARE}" == "auto" ]]; then
    echo "[data] Local SWE60 inputs incomplete: samples=${sample_count}, repo_structures=${structure_count}"
    echo "[data] Checking HuggingFace dataset endpoint: ${HF_DATASET_API_URL}"
    if hf_dataset_available; then
      echo "[data] HuggingFace dataset endpoint is reachable."
      echo "[data] The runner will download/prepare samples and clone/build repo_structures as needed."
      return 0
    fi
    echo "[data] HuggingFace dataset endpoint is not reachable from this shell."
  fi

  cat >&2 <<EOF
ERROR: SWE-bench Multimodal 60 local inputs are incomplete.

Found:
  samples rows:      ${sample_count}
  repo_structures:   ${structure_count}

Expected:
  ${SWE60_SAMPLES}
  ${SWE60_STRUCTURES}/*.json  (60 files)

Why this matters:
  The prepared data/repo_structures are intentionally ignored by git because
  they are large. If they are missing, the runner falls back to HuggingFace.
  Your server log shows HuggingFace is unavailable or uncached, so preparation
  fails before any baseline can run.

Recommended fix on the local machine where the data already exists:
  cd /home/like/locCode
  bash package_swe60_inputs.sh
  scp swebench_multimodal_60_inputs.tar.gz <server>:/data2/like/loccode/

Then on the server:
  cd /data2/like/loccode
  bash server_check_setup_run_swe60.sh

Alternative, only if the server can access HuggingFace:
  ALLOW_HF_PREPARE=1 bash server_check_setup_run_swe60.sh
EOF
  exit 2
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
Allow HF prepare: ${ALLOW_HF_PREPARE}
HF dataset endpoint: ${HF_DATASET_API_URL}
Log dir: ${LOG_DIR}
EOF

if [[ ! -f "${CONDA_SH}" ]]; then
  echo "ERROR: CONDA_SH does not exist: ${CONDA_SH}" >&2
  echo "Set CONDA_SH=/path/to/miniconda3/etc/profile.d/conda.sh" >&2
  exit 2
fi

maybe_unpack_swe60_inputs
require_swe60_inputs_or_explain

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
