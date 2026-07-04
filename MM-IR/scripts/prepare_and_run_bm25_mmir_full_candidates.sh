#!/usr/bin/env bash
set -euo pipefail

MMIR_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCAGENT_ROOT="${LOCAGENT_ROOT:-/home/like/locCode/LocAgent}"

# BENCHMARK must match LocAgent's preparation script choices:
#   swebench_multimodal
#   omnigirl
BENCHMARK="${BENCHMARK:-swebench_multimodal}"
SAMPLE_SIZE="${SAMPLE_SIZE:-0}"
SEED="${SEED:-20260614}"
MODE_TAG="${MODE_TAG:-full-candidates}"

DATA_DIR="${DATA_DIR:-${MMIR_ROOT}/data/${BENCHMARK}-${MODE_TAG}}"
SAMPLE_FILE="${SAMPLE_FILE:-${DATA_DIR}/samples.jsonl}"
STRUCTURE_DIR="${STRUCTURE_DIR:-${DATA_DIR}/repo_structures}"
OUTPUT_DIR="${OUTPUT_DIR:-${MMIR_ROOT}/results/${BENCHMARK}-${MODE_TAG}/bm25-mmir}"
REPO_CACHE_DIR="${REPO_CACHE_DIR:-${MMIR_ROOT}/repo_cache/${BENCHMARK}-${MODE_TAG}}"
OMNIGIRL_FULL_JSON="${OMNIGIRL_FULL_JSON:-/home/like/locCode/OmniGIRL/omnigirl/harness/benchmark/OmniGIRL.json}"

LOCAGENT_PYTHON_BIN="${LOCAGENT_PYTHON_BIN:-/home/like/miniconda3/envs/locagent/bin/python}"
MMIR_PYTHON_BIN="${MMIR_PYTHON_BIN:-/home/like/miniconda3/envs/mmir/bin/python}"

MULADAPTER_MODE="${MULADAPTER_MODE:-codev_compact}"
MULADAPTER_DEFAULT_MODE="${MULADAPTER_DEFAULT_MODE:-${MULADAPTER_MODE}}"
MULADAPTER_MODEL="${MULADAPTER_MODEL:-qwen3-vl-8b}"
MULADAPTER_BASE_URL="${MULADAPTER_BASE_URL:-http://10.102.65.40:8002/v1}"
MULADAPTER_API_KEY="${MULADAPTER_API_KEY:-dummy}"

mkdir -p "${DATA_DIR}" "${STRUCTURE_DIR}" "${OUTPUT_DIR}"

export PYTHONPATH="${LOCAGENT_ROOT}:${MMIR_ROOT}:${PYTHONPATH:-}"
export MULADAPTER_MODE MULADAPTER_DEFAULT_MODE MULADAPTER_MODEL MULADAPTER_BASE_URL MULADAPTER_API_KEY

if [[ "${BENCHMARK}" == "omnigirl" && -z "${SOURCE_JSONL:-}" ]]; then
  if [[ ! -f "${OMNIGIRL_FULL_JSON}" ]]; then
    echo "Missing OmniGIRL full source: ${OMNIGIRL_FULL_JSON}" >&2
    echo "Set SOURCE_JSONL=/path/to/full_omnigirl.jsonl or OMNIGIRL_FULL_JSON=/path/to/OmniGIRL.json." >&2
    exit 1
  fi
  SOURCE_JSONL="${DATA_DIR}/source_omnigirl_full.jsonl"
  echo "[BM25-MMIR full] converting OmniGIRL full JSON to JSONL: ${SOURCE_JSONL}"
  "${LOCAGENT_PYTHON_BIN}" - "${OMNIGIRL_FULL_JSON}" "${SOURCE_JSONL}" <<'PY'
import json
import sys
from pathlib import Path

source = Path(sys.argv[1])
target = Path(sys.argv[2])
payload = json.loads(source.read_text(encoding="utf-8"))
if isinstance(payload, dict):
    rows = next((value for value in payload.values() if isinstance(value, list)), [])
elif isinstance(payload, list):
    rows = payload
else:
    raise TypeError(f"Unsupported OmniGIRL payload type: {type(payload).__name__}")
target.parent.mkdir(parents=True, exist_ok=True)
with target.open("w", encoding="utf-8") as outfile:
    for row in rows:
        outfile.write(json.dumps(row, ensure_ascii=False) + "\n")
print(f"Wrote {len(rows)} rows to {target}")
PY
  export SOURCE_JSONL
fi

PREPARE_ARGS=(
  "${LOCAGENT_ROOT}/newtest/scripts/prepare_multimodal_localization.py"
  --benchmark "${BENCHMARK}"
  --sample-size "${SAMPLE_SIZE}"
  --seed "${SEED}"
  --output-dir "${DATA_DIR}"
  --used-list-name "mmir_full_instances"
)
if [[ -n "${DATASET:-}" ]]; then
  PREPARE_ARGS+=(--dataset "${DATASET}")
fi
if [[ -n "${SPLIT:-}" ]]; then
  PREPARE_ARGS+=(--split "${SPLIT}")
fi
if [[ -n "${SOURCE_JSONL:-}" ]]; then
  PREPARE_ARGS+=(--source-jsonl "${SOURCE_JSONL}")
fi

echo "[BM25-MMIR full] 1/4 prepare ${BENCHMARK} data"
echo "[BM25-MMIR full] sample_size=${SAMPLE_SIZE} (0 means all eligible candidates)"
"${LOCAGENT_PYTHON_BIN}" "${PREPARE_ARGS[@]}"

echo "[BM25-MMIR full] 2/4 build repo_structures"
"${LOCAGENT_PYTHON_BIN}" "${LOCAGENT_ROOT}/newtest/scripts/build_repo_structures.py" \
  --samples "${SAMPLE_FILE}" \
  --output-dir "${STRUCTURE_DIR}" \
  --repo-base-dir "${REPO_CACHE_DIR}" \
  --dataset "mmir_${BENCHMARK}_${MODE_TAG}" \
  --split train \
  --skip-existing

export METHOD=bm25-mmir
export SAMPLE_FILE
export STRUCTURE_DIR
export OUTPUT_DIR
export PYTHON_BIN="${MMIR_PYTHON_BIN}"

echo "[BM25-MMIR full] 3/4 locate"
"${MMIR_PYTHON_BIN}" -m mmir.cli locate \
  --samples "${SAMPLE_FILE}" \
  --structure-dir "${STRUCTURE_DIR}" \
  --output-dir "${OUTPUT_DIR}" \
  --method bm25-mmir \
  --limit 0

echo "[BM25-MMIR full] 4/4 evaluate"
"${MMIR_PYTHON_BIN}" -m mmir.evaluation.eval_3level \
  --samples "${SAMPLE_FILE}" \
  --predictions "${OUTPUT_DIR}/loc_results.json" \
  --structure-dir "${STRUCTURE_DIR}" \
  --output-dir "${OUTPUT_DIR}/eval" \
  --limit 0

echo "[BM25-MMIR full] Done"
echo "Samples: ${SAMPLE_FILE}"
echo "Structures: ${STRUCTURE_DIR}"
echo "Metrics: ${OUTPUT_DIR}/eval/metrics_3level.md"
