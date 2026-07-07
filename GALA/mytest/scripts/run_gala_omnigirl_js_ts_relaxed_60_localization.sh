#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# This wrapper keeps the original strict multimodal run untouched and writes to
# a separate directory. It relaxes only the image requirement, so the subset can
# include text-only OmniGIRL JS/TS cases while still requiring a patch and
# GALA-compatible modified files for evaluation.
export TEST_NAME="${TEST_NAME:-omnigirl-js-ts-relaxed-60}"
export ALLOW_NO_IMAGES="${ALLOW_NO_IMAGES:-1}"

exec bash "${SCRIPT_DIR}/run_gala_omnigirl_js_ts_60_localization.sh"
