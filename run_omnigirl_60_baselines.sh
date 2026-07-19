#!/usr/bin/env bash
set -euo pipefail

# Convenience wrapper: run all baselines on the shared OmniGIRL unified 60 subset.
# If the unified 60 samples/structures do not exist yet, this wrapper prepares
# them via run_omnigirl_unified60_baselines.sh with all actual baselines disabled.
# Actual baseline execution then reuses run_omnigirl_full_baselines.sh, which has
# eval-only recovery, five MM-IR methods, and strict/relaxed metrics.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export GITHUB_MIRROR_PREFIX="${GITHUB_MIRROR_PREFIX:-${REPO_GITHUB_MIRROR_PREFIX:-https://gh.xmly.dev}}"

export EXP_NAME="${EXP_NAME:-omnigirl-unified60}"
export SAMPLE_SIZE="${SAMPLE_SIZE:-60}"
USER_SOURCE_JSONL="${SOURCE_JSONL:-}"
USER_STRUCTURE_DIR="${STRUCTURE_DIR:-}"
CANONICAL_SAMPLES="${ROOT_DIR}/LocAgent/newtest/${EXP_NAME}/data/samples.jsonl"
CANONICAL_STRUCTURE_DIR="${ROOT_DIR}/LocAgent/newtest/${EXP_NAME}/repo_structures"
export SOURCE_JSONL="${USER_SOURCE_JSONL:-${CANONICAL_SAMPLES}}"
export STRUCTURE_DIR="${USER_STRUCTURE_DIR:-${CANONICAL_STRUCTURE_DIR}}"
export USED_LIST="${USED_LIST:-newtest_instances}"

env_python_default() {
  local env_name="$1"
  if [[ -n "${CONDA_ENV_ROOT:-}" ]]; then
    echo "${CONDA_ENV_ROOT%/}/${env_name}/bin/python"
    return 0
  fi
  echo ""
}

export LOCAGENT_PY="${LOCAGENT_PY:-$(env_python_default locagent)}"
export COSIL_PY="${COSIL_PY:-$(env_python_default cosil)}"
export GRAPHLOCATOR_PY="${GRAPHLOCATOR_PY:-$(env_python_default graphlocator)}"
export GALA_PY="${GALA_PY:-$(env_python_default gala)}"
export MMIR_PY="${MMIR_PY:-$(env_python_default mmir)}"

is_truthy() {
  [[ "${1:-}" == "1" || "${1:-}" == "true" || "${1:-}" == "yes" ]]
}

if [[ ! -s "${SOURCE_JSONL}" || ! -d "${STRUCTURE_DIR}" || "${FORCE_PREPARE:-0}" == "1" || "${FORCE_STRUCTURES:-0}" == "1" ]]; then
  echo "Preparing OmniGIRL unified 60 canonical samples/structures..."
  if is_truthy "${DRY_RUN:-0}"; then
    echo "+ RUN_LOCAGENT=0 RUN_COSIL=0 RUN_GRAPHLOCATOR=0 RUN_GALA=0 RUN_MMIR=0 ${ROOT_DIR}/run_omnigirl_unified60_baselines.sh"
  else
    RUN_LOCAGENT=0 \
    RUN_COSIL=0 \
    RUN_GRAPHLOCATOR=0 \
    RUN_GALA=0 \
    RUN_MMIR=0 \
    SOURCE_JSONL="${USER_SOURCE_JSONL}" \
    "${ROOT_DIR}/run_omnigirl_unified60_baselines.sh"
  fi
  export SOURCE_JSONL="${USER_SOURCE_JSONL:-${CANONICAL_SAMPLES}}"
  export STRUCTURE_DIR="${USER_STRUCTURE_DIR:-${CANONICAL_STRUCTURE_DIR}}"
fi

exec "${ROOT_DIR}/run_omnigirl_full_baselines.sh"
