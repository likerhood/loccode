#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Full relaxed OmniGIRL baseline:
# - allow samples without images;
# - allow non-JS/TS/non-GALA-compatible patch files;
# - still require gold patch files so localization can be evaluated.
#
# This is intentionally a stress test for GALA. It can expose failures in
# repository parsing, code graph construction, and visual-code alignment across
# languages and file types beyond the original front-end setting.
export TEST_NAME="${TEST_NAME:-omnigirl-full-relaxed-60}"
export ALLOW_NO_IMAGES="${ALLOW_NO_IMAGES:-1}"
export ALLOW_NON_GALA_FILES="${ALLOW_NON_GALA_FILES:-1}"

exec bash "${SCRIPT_DIR}/run_gala_omnigirl_js_ts_60_localization.sh"
