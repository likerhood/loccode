#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# OmniGIRL 60 relaxed/full subset with the unified localization metrics:
# - allows text-only issues;
# - allows non-JS/TS/non-GALA-compatible patch files;
# - still requires gold patches so file-level localization can be evaluated.
#
# The default output directory is intentionally under mytest/test1/ so the
# script does not overwrite previous OmniGIRL runs.
export TEST_NAME="${TEST_NAME:-test1/omnigirl-full-relaxed-60}"
export INPUT_FILE="${INPUT_FILE:-/home/like/locCode/LocAgent/test/OmniGIRL_small60/test60/samples.jsonl}"
export SAMPLE_SIZE="${SAMPLE_SIZE:-60}"
export VLM_MODEL="${VLM_MODEL:-qwen3-vl-8b}"
export VLM_BASE_URL="${VLM_BASE_URL:-http://10.102.65.40:8002/v1}"
export TEXT_MODEL_NAME="${TEXT_MODEL_NAME:-${VLM_MODEL}}"
export TEXT_BASE_URL="${TEXT_BASE_URL:-${VLM_BASE_URL}}"

exec bash "${SCRIPT_DIR}/run_gala_omnigirl_full_relaxed_60_localization.sh"
