#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

export PYTHONPATH="${PYTHONPATH:-}:${REPO_ROOT}"
PYTHON_BIN="${PYTHON_BIN:-python}"

export OPENAI_API_KEY="${OPENAI_API_KEY:-dummy}"
export OPENAI_API_BASE_URL="${OPENAI_API_BASE_URL:-http://10.102.65.40:8002/v1}"
export MULADAPTER_MODE="${MULADAPTER_MODE:-codev_compact}"
export MULADAPTER_DEFAULT_MODE="${MULADAPTER_DEFAULT_MODE:-${MULADAPTER_MODE}}"
export MULADAPTER_MODEL="${MULADAPTER_MODEL:-qwen3-vl-8b}"
export MULADAPTER_BASE_URL="${MULADAPTER_BASE_URL:-${OPENAI_API_BASE_URL}}"
export MULADAPTER_API_KEY="${MULADAPTER_API_KEY:-${OPENAI_API_KEY}}"

BENCHMARK="${BENCHMARK:-swebench_multimodal}"
SAMPLE_SIZE="${SAMPLE_SIZE:-60}"
SEED="${SEED:-20260614}"
MODEL="${MODEL:-openai/qwen3-vl-8b}"
MODEL_TAG="${MODEL//\//_}"
DATASET_NAME="${DATASET_NAME:-newtest_swebench_multimodal_60}"
SPLIT="${SPLIT:-dev}"
FINAL_STAGE="${FINAL_STAGE:-search}"
RUN_ORCALOCA="${RUN_ORCALOCA:-1}"

TEST_ROOT="${REPO_ROOT}/newtest/${BENCHMARK}-60"
DATA_DIR="${TEST_ROOT}/data"
RESULT_DIR="${TEST_ROOT}/results/${MODEL_TAG}"
EVAL_DIR="${RESULT_DIR}/eval"
STRUCTURE_DIR="${STRUCTURE_DIR:-}"
mkdir -p "${DATA_DIR}" "${RESULT_DIR}" "${EVAL_DIR}"

echo "[1/4] Prepare ${BENCHMARK} ${SAMPLE_SIZE}-sample data"
"${PYTHON_BIN}" newtest/scripts/prepare_multimodal_localization.py \
  --benchmark "${BENCHMARK}" \
  --sample-size "${SAMPLE_SIZE}" \
  --seed "${SEED}" \
  --output-dir "${DATA_DIR}"

echo "[2/4] Write OrcaLoca local dataset cache"
"${PYTHON_BIN}" newtest/scripts/make_orcar_cache_dataset.py \
  --samples "${DATA_DIR}/samples.jsonl" \
  --dataset-name "${DATASET_NAME}" \
  --split "${SPLIT}"

if [[ "${RUN_ORCALOCA}" == "1" ]]; then
  echo "[3/4] Run OrcaLoca ${FINAL_STAGE}"
  if ! "${PYTHON_BIN}" - <<'PY'
import docker  # noqa: F401
PY
  then
    echo "Missing Python dependency: docker"
    echo "Install OrcaLoca dependencies in the active environment, for example:"
    echo "  cd ${REPO_ROOT} && pip install -e ."
    echo "Or install only the missing package:"
    echo "  pip install docker"
    exit 1
  fi
  mapfile -t INSTANCE_IDS < "${DATA_DIR}/instance_ids.txt"
  "${PYTHON_BIN}" evaluation/run.py \
    --dataset "${DATASET_NAME}" \
    --split "${SPLIT}" \
    --model "${MODEL}" \
    --final_stage "${FINAL_STAGE}" \
    --instance_ids "${INSTANCE_IDS[@]}"
else
  echo "[3/4] Skip OrcaLoca run because RUN_ORCALOCA=${RUN_ORCALOCA}"
fi

echo "[4/4] Evaluate file-level localization if output exists"
if [[ -f "evaluation/output.json" ]]; then
  cp "evaluation/output.json" "${RESULT_DIR}/output.json"
  "${PYTHON_BIN}" newtest/scripts/eval_file_level.py \
    --samples "${DATA_DIR}/samples.jsonl" \
    --pred-file "${RESULT_DIR}/output.json" \
    --output-dir "${EVAL_DIR}"
  if [[ -n "${STRUCTURE_DIR}" && -d "${STRUCTURE_DIR}" ]]; then
    "${PYTHON_BIN}" newtest/scripts/eval_3level_localization.py \
      --samples "${DATA_DIR}/samples.jsonl" \
      --pred-file "${RESULT_DIR}/output.json" \
      --structure-dir "${STRUCTURE_DIR}" \
      --output-dir "${EVAL_DIR}"
    echo "Done: ${EVAL_DIR}/metrics_3level.md"
  else
    echo "Skip three-level eval because STRUCTURE_DIR is not set or not a directory."
  fi
  echo "Done: ${EVAL_DIR}/metrics.md"
else
  echo "No evaluation/output.json found. Run completed/prepared data, but no eval was generated."
fi
