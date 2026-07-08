#!/usr/bin/env bash
set -euo pipefail

# Convenience wrapper: baseline-level parallel run for OmniGIRL unified 60.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export EXP_NAME="${EXP_NAME:-omnigirl-unified60}"
export SAMPLE_SIZE="${SAMPLE_SIZE:-60}"
USER_SOURCE_JSONL="${SOURCE_JSONL:-}"
USER_STRUCTURE_DIR="${STRUCTURE_DIR:-}"
CANONICAL_SAMPLES="${ROOT_DIR}/LocAgent/newtest/${EXP_NAME}/data/samples.jsonl"
CANONICAL_STRUCTURE_DIR="${ROOT_DIR}/LocAgent/newtest/${EXP_NAME}/repo_structures"
export SOURCE_JSONL="${USER_SOURCE_JSONL:-${CANONICAL_SAMPLES}}"
export STRUCTURE_DIR="${USER_STRUCTURE_DIR:-${CANONICAL_STRUCTURE_DIR}}"
export USED_LIST="${USED_LIST:-newtest_instances}"

if [[ ! -s "${SOURCE_JSONL}" || ! -d "${STRUCTURE_DIR}" || "${FORCE_PREPARE:-0}" == "1" || "${FORCE_STRUCTURES:-0}" == "1" ]]; then
  echo "Preparing OmniGIRL unified 60 canonical samples/structures before parallel run..."
  RUN_LOCAGENT=0 \
  RUN_COSIL=0 \
  RUN_GRAPHLOCATOR=0 \
  RUN_GALA=0 \
  RUN_MMIR=0 \
  SOURCE_JSONL="${USER_SOURCE_JSONL}" \
  "${ROOT_DIR}/run_omnigirl_60_baselines.sh"
  export SOURCE_JSONL="${USER_SOURCE_JSONL:-${CANONICAL_SAMPLES}}"
  export STRUCTURE_DIR="${USER_STRUCTURE_DIR:-${CANONICAL_STRUCTURE_DIR}}"
fi

exec "${ROOT_DIR}/run_omnigirl_full_baselines_parallel.sh"
