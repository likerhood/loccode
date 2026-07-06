#!/usr/bin/env bash
set -euo pipefail

# Convenience wrapper: run all baselines on the SWE-bench Multimodal 60 subset.
# It reuses the full-dev runner, but pins EXP_NAME/SAMPLE_SIZE to the 60 subset.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export EXP_NAME="${EXP_NAME:-swebench_multimodal-60}"
export SAMPLE_SIZE="${SAMPLE_SIZE:-60}"
export USED_LIST="${USED_LIST:-newtest_instances}"

exec "${ROOT_DIR}/run_swebench_multimodal_full_dev_baselines.sh"
