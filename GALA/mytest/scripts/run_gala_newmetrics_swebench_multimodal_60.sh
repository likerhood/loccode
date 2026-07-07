#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# SWE-bench Multimodal 60 with the unified localization metrics:
# - Acc@1..Acc@15, MRR@15, MAP@15, Empty
# - Set Metrics @10 and @15
# - GALA is evaluated as file-level native output; module/function are N/A.
#
# The default output directory is intentionally under mytest/test1/ so the
# script does not overwrite previous mytest/swebench-multimodal-60 results.
export TEST_NAME="${TEST_NAME:-test1/swebench-multimodal-60}"
export DATASET="${DATASET:-SWE-bench/SWE-bench_Multimodal}"
export SPLIT="${SPLIT:-dev}"
export SAMPLE_SIZE="${SAMPLE_SIZE:-60}"
export VLM_MODEL="${VLM_MODEL:-qwen3-vl-8b}"
export VLM_BASE_URL="${VLM_BASE_URL:-http://10.102.65.40:8002/v1}"
export TEXT_MODEL_NAME="${TEXT_MODEL_NAME:-${VLM_MODEL}}"
export TEXT_BASE_URL="${TEXT_BASE_URL:-${VLM_BASE_URL}}"

exec bash "${SCRIPT_DIR}/run_gala_swebench_multimodal_60_localization.sh"
