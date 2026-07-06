#!/usr/bin/env bash
set -euo pipefail

# Convenience wrapper: baseline-level parallel run for SWE-bench Multimodal 60.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export EXP_NAME="${EXP_NAME:-swebench_multimodal-60}"
export SAMPLE_SIZE="${SAMPLE_SIZE:-60}"
export USED_LIST="${USED_LIST:-newtest_instances}"

exec "${ROOT_DIR}/run_swebench_multimodal_full_dev_baselines_parallel.sh"
