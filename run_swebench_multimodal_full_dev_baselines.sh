#!/usr/bin/env bash
set -euo pipefail

# Run all localization baselines on the full SWE-bench Multimodal dev split.
#
# This script is designed for server runs after cloning this repository. It:
#   1. prepares one canonical SWE-bench Multimodal dev sample file;
#   2. builds one shared repo_structures directory;
#   3. runs LocAgent / CoSIL / GraphLocator / GALA;
#   4. runs MM-IR with BM25, E5, Jina-Code-v2, CodeSage-large-v2, CodeRankEmbed;
#   5. writes both relaxed eval/ and strict eval_strict/ metrics;
#   6. skips baselines whose relaxed and strict metrics already exist.
#
# Common server usage:
#   cd /path/to/locCode
#   export LOCAGENT_PY=/data2/like/envs/locagent/bin/python
#   export COSIL_PY=/data2/like/envs/cosil/bin/python
#   export GRAPHLOCATOR_PY=/data2/like/envs/graphlocator/bin/python
#   export GALA_PY=/data2/like/envs/gala/bin/python
#   export MMIR_PY=/data2/like/envs/mmir/bin/python
#   export OPENAI_API_BASE=http://your-vllm-host:8002/v1
#   export OPENAI_API_KEY=dummy
#   export MODEL=openai/qwen3-vl-8b
#   export VLM_MODEL=qwen3-vl-8b
#   export DENSE_DEVICE=cuda
#   bash run_swebench_multimodal_full_dev_baselines.sh
#
# Useful switches:
#   DRY_RUN=1 bash run_swebench_multimodal_full_dev_baselines.sh
#   RUN_GRAPHLOCATOR=0 bash run_swebench_multimodal_full_dev_baselines.sh
#   RUN_MMIR_METHODS="bm25-mmir e5-mmir" bash run_swebench_multimodal_full_dev_baselines.sh
#   MODEL=deepseek-chat TEXT_MODEL_NAME=deepseek-chat OPENAI_API_BASE=https://api.deepseek.com/v1 bash run_swebench_multimodal_full_dev_baselines.sh
#   FORCE_RERUN=1 bash run_swebench_multimodal_full_dev_baselines.sh
#   FORCE_PREPARE=1 FORCE_STRUCTURES=1 bash run_swebench_multimodal_full_dev_baselines.sh

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export GITHUB_MIRROR_PREFIX="${GITHUB_MIRROR_PREFIX:-${REPO_GITHUB_MIRROR_PREFIX:-https://gh.xmly.dev}}"

EXP_NAME="${EXP_NAME:-swebench_multimodal-full-dev}"
BENCHMARK="swebench_multimodal"
DATASET="${DATASET:-SWE-bench/SWE-bench_Multimodal}"
SPLIT="${SPLIT:-dev}"
SAMPLE_SIZE="${SAMPLE_SIZE:-102}"
SEED="${SEED:-20260614}"
USED_LIST="${USED_LIST:-swebench_multimodal_full_dev_instances}"

MODEL="${MODEL:-openai/qwen3-vl-8b}"
LITELLM_MODEL="${LITELLM_MODEL:-${MODEL}}"
if [[ "${LITELLM_MODEL}" != */* ]]; then
  LITELLM_MODEL="openai/${LITELLM_MODEL}"
fi
VLM_MODEL="${VLM_MODEL:-qwen3-vl-8b}"
TEXT_MODEL_NAME="${TEXT_MODEL_NAME:-${VLM_MODEL}}"
VLM_API_MODEL_NAME="${VLM_API_MODEL_NAME:-${VLM_MODEL}}"
TEXT_API_MODEL_NAME="${TEXT_API_MODEL_NAME:-${TEXT_MODEL_NAME}}"
OPENAI_API_BASE="${OPENAI_API_BASE:-http://10.102.65.40:8002/v1}"
OPENAI_API_KEY="${OPENAI_API_KEY:-dummy}"
MULADAPTER_MODEL="${MULADAPTER_MODEL:-${VLM_MODEL}}"
MULADAPTER_BASE_URL="${MULADAPTER_BASE_URL:-${OPENAI_API_BASE}}"
MULADAPTER_API_KEY="${MULADAPTER_API_KEY:-${OPENAI_API_KEY}}"
VLM_BASE_URL="${VLM_BASE_URL:-${OPENAI_API_BASE}}"
VLM_API_KEY="${VLM_API_KEY:-${OPENAI_API_KEY}}"
TEXT_BASE_URL="${TEXT_BASE_URL:-${OPENAI_API_BASE}}"
TEXT_API_KEY="${TEXT_API_KEY:-${OPENAI_API_KEY}}"

RUN_LOCAGENT="${RUN_LOCAGENT:-1}"
RUN_COSIL="${RUN_COSIL:-1}"
RUN_GRAPHLOCATOR="${RUN_GRAPHLOCATOR:-1}"
RUN_GALA="${RUN_GALA:-1}"
RUN_MMIR="${RUN_MMIR:-1}"
RUN_MMIR_METHODS="${RUN_MMIR_METHODS:-bm25-mmir e5-mmir jina-code-v2-mmir codesage-large-v2-mmir coderankembed-mmir}"

CLEAN_FULL="${CLEAN_FULL:-0}"
FORCE_RERUN="${FORCE_RERUN:-0}"
FORCE_PREPARE="${FORCE_PREPARE:-0}"
FORCE_STRUCTURES="${FORCE_STRUCTURES:-0}"
SKIP_SHARED_PREPARE="${SKIP_SHARED_PREPARE:-0}"
DRY_RUN="${DRY_RUN:-0}"
COSIL_MAX_EMPTY_RATE="${COSIL_MAX_EMPTY_RATE:-0.30}"
API_PREFLIGHT="${API_PREFLIGHT:-0}"
API_PREFLIGHT_TIMEOUT="${API_PREFLIGHT_TIMEOUT:-30}"

SOURCE_JSONL="${SOURCE_JSONL:-}"
CONDA_ENV_ROOT="${CONDA_ENV_ROOT:-}"

MODEL_TAG="${MODEL//\//_}"
GALA_MODEL_TAG="${VLM_MODEL//\//_}"
GALA_IMAGE_DIR="${GALA_IMAGE_DIR:-${IMAGE_DIR:-}}"
GALA_DOWNLOAD_IMAGES="${GALA_DOWNLOAD_IMAGES:-${DOWNLOAD_IMAGES:-1}}"
GALA_REUSE_IMAGE_IR="${GALA_REUSE_IMAGE_IR:-${REUSE_IMAGE_IR:-1}}"
GALA_RESUME_IMAGE_IR="${GALA_RESUME_IMAGE_IR:-${RESUME_IMAGE_IR:-1}}"
GALA_FORCE_IMAGE_IR="${GALA_FORCE_IMAGE_IR:-${FORCE_IMAGE_IR:-0}}"
GALA_CHECK_IMAGE_IR_COMPLETE="${GALA_CHECK_IMAGE_IR_COMPLETE:-${CHECK_IMAGE_IR_COMPLETE:-1}}"
GALA_IMAGE_DOWNLOAD_RETRIES="${GALA_IMAGE_DOWNLOAD_RETRIES:-${IMAGE_DOWNLOAD_RETRIES:-3}}"
GALA_IMAGE_DOWNLOAD_RETRY_SLEEP="${GALA_IMAGE_DOWNLOAD_RETRY_SLEEP:-${IMAGE_DOWNLOAD_RETRY_SLEEP:-10}}"
GALA_IMAGE_DOWNLOAD_BACKOFF="${GALA_IMAGE_DOWNLOAD_BACKOFF:-${IMAGE_DOWNLOAD_BACKOFF:-2}}"

CANONICAL_ROOT="${ROOT_DIR}/LocAgent/newtest/${EXP_NAME}"
CANONICAL_DATA_DIR="${CANONICAL_ROOT}/data"
CANONICAL_SAMPLES="${CANONICAL_DATA_DIR}/samples.jsonl"
CANONICAL_STRUCTURE_DIR="${CANONICAL_ROOT}/repo_structures"
COSIL_STRUCTURE_DIR="${COSIL_STRUCTURE_DIR:-${CANONICAL_STRUCTURE_DIR}}"

env_python_default() {
  local env_name="$1"
  if [[ -n "${CONDA_ENV_ROOT}" ]]; then
    echo "${CONDA_ENV_ROOT%/}/${env_name}/bin/python"
    return 0
  fi
  if command -v conda >/dev/null 2>&1; then
    local base
    base="$(conda info --base 2>/dev/null || true)"
    if [[ -n "${base}" && -x "${base}/envs/${env_name}/bin/python" ]]; then
      echo "${base}/envs/${env_name}/bin/python"
      return 0
    fi
  fi
  echo ""
}

LOCAGENT_PY="${LOCAGENT_PY:-$(env_python_default locagent)}"
COSIL_PY="${COSIL_PY:-$(env_python_default cosil)}"
GRAPHLOCATOR_PY="${GRAPHLOCATOR_PY:-$(env_python_default graphlocator)}"
GALA_PY="${GALA_PY:-$(env_python_default gala)}"
MMIR_PY="${MMIR_PY:-$(env_python_default mmir)}"

is_truthy() {
  [[ "${1:-}" == "1" || "${1:-}" == "true" || "${1:-}" == "yes" ]]
}

run_cmd() {
  echo "+ $*"
  if ! is_truthy "${DRY_RUN}"; then
    "$@"
  fi
}

run_shell() {
  local script="$1"
  echo "+ bash -lc ${script}"
  if ! is_truthy "${DRY_RUN}"; then
    bash -lc "${script}"
  fi
}

api_preflight_if_needed() {
  if ! is_truthy "${API_PREFLIGHT}"; then
    return 0
  fi
  if ! is_truthy "${RUN_LOCAGENT}" && ! is_truthy "${RUN_COSIL}" && ! is_truthy "${RUN_GRAPHLOCATOR}" && ! is_truthy "${RUN_GALA}"; then
    return 0
  fi
  run_step "API preflight" run_cmd "${PYTHON:-python3}" "${ROOT_DIR}/scripts/check_openai_compatible_api.py" \
    --base-url "${OPENAI_API_BASE}" \
    --api-key "${OPENAI_API_KEY}" \
    --model "${LITELLM_MODEL#openai/}" \
    --timeout "${API_PREFLIGHT_TIMEOUT}"
}

ensure_python() {
  local py="$1"
  local label="$2"
  if [[ -x "${py}" ]]; then
    return 0
  fi
  if is_truthy "${DRY_RUN}"; then
    echo "[dry-run warn] ${label} python not found yet: ${py:-<empty>}"
    return 0
  fi
  echo "ERROR: ${label} python not found or not executable: ${py:-<empty>}" >&2
  echo "Set ${label^^}_PY or run setup_baseline_conda_envs.sh first." >&2
  exit 2
}

ensure_import() {
  local py="$1"
  local module="$2"
  local label="$3"
  if is_truthy "${DRY_RUN}"; then
    return 0
  fi
  if ! "${py}" -c "import ${module}" >/dev/null 2>&1; then
    echo "ERROR: ${label} python is missing required module '${module}': ${py}" >&2
    exit 2
  fi
}

run_step() {
  local label="$1"
  shift
  echo
  echo "========== ${label} =========="
  "$@"
}

run_if_needed() {
  local label="$1"
  local markers="$2"
  shift 2
  if ! is_truthy "${FORCE_RERUN}"; then
    local all_done=1
    local marker
    IFS='|' read -r -a marker_list <<< "${markers}"
    for marker in "${marker_list[@]}"; do
      if [[ ! -s "${marker}" ]]; then
        all_done=0
        break
      fi
    done
    if [[ "${all_done}" == "1" ]]; then
      echo
      echo "========== Skip ${label} =========="
      echo "[skip] Found completed metrics:"
      for marker in "${marker_list[@]}"; do
        echo "[skip]   ${marker}"
      done
      echo "[skip] Use FORCE_RERUN=1 to rerun."
      return 0
    fi
  fi
  run_step "${label}" "$@"
}

sample_rows() {
  if [[ -f "${CANONICAL_SAMPLES}" ]]; then
    wc -l < "${CANONICAL_SAMPLES}" | tr -d ' '
  else
    echo 0
  fi
}

expected_sample_rows_ready() {
  local rows
  rows="$(sample_rows)"
  if [[ "${SAMPLE_SIZE}" -gt 0 ]]; then
    [[ "${rows}" == "${SAMPLE_SIZE}" ]]
  else
    [[ "${rows}" -gt 0 ]]
  fi
}

link_gala_repos_from_locagent() {
  local exp_name="$1"
  local samples_file="$2"
  local gala_repo_dir="$3"

  if ! is_truthy "${GALA_REUSE_LOCAGENT_REPOS:-1}"; then
    echo "[gala-repo-reuse] disabled by GALA_REUSE_LOCAGENT_REPOS=0"
    return 0
  fi
  if [[ ! -s "${samples_file}" ]]; then
    echo "[gala-repo-reuse] skip: samples file not found: ${samples_file}"
    return 0
  fi

  local shared_roots="${GALA_LOCAGENT_SHARED_ROOTS:-}"
  if [[ -z "${shared_roots}" ]]; then
    shared_roots="${ROOT_DIR}/LocAgent/repo_newtest_${exp_name}/_shared_worktrees"
    shared_roots="${shared_roots}:${ROOT_DIR}/LocAgent/repo_newtest_swebench_multimodal-full-dev/_shared_worktrees"
  fi

  echo "[gala-repo-reuse] samples: ${samples_file}"
  echo "[gala-repo-reuse] GALA repo dir: ${gala_repo_dir}"
  echo "[gala-repo-reuse] LocAgent shared roots: ${shared_roots}"
  if is_truthy "${DRY_RUN}"; then
    echo "[gala-repo-reuse] dry run: no symlinks created"
    return 0
  fi

  mkdir -p "${gala_repo_dir}"
  "${PYTHON:-python3}" - "${samples_file}" "${gala_repo_dir}" "${shared_roots}" "${GALA_REPO_LINK_MODE:-symlink}" <<'PY'
import json
import os
import shutil
import sys
from pathlib import Path

samples_file = Path(sys.argv[1])
gala_repo_dir = Path(sys.argv[2])
shared_roots = [Path(p) for p in sys.argv[3].split(":") if p]
link_mode = sys.argv[4].strip().lower()


def iter_records(path: Path):
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return
    if path.suffix == ".jsonl":
        for line in text.splitlines():
            line = line.strip()
            if line:
                yield json.loads(line)
        return
    data = json.loads(text)
    if isinstance(data, dict):
        yield from (v for v in data.values() if isinstance(v, dict))
    elif isinstance(data, list):
        yield from (v for v in data if isinstance(v, dict))


repos = sorted({str(row.get("repo") or "").strip() for row in iter_records(samples_file) if row.get("repo")})
linked = 0
existing = 0
missing = []

for repo in repos:
    owner = repo.split("/", 1)[0]
    repo_dir_name = repo.replace("/", "_")
    target = gala_repo_dir / owner
    if target.exists() or target.is_symlink():
        if target.is_dir() and not target.is_symlink() and not (target / ".git").exists():
            try:
                next(target.iterdir())
            except StopIteration:
                target.rmdir()
            else:
                print(f"[gala-repo-reuse] keep existing non-git non-empty dir: {target}")
                existing += 1
                continue
        else:
            existing += 1
            continue
    if target.exists() or target.is_symlink():
        existing += 1
        continue

    source = None
    for root in shared_roots:
        candidate = root / repo_dir_name
        if candidate.is_dir() and (candidate / ".git").exists():
            source = candidate
            break
    if source is None:
        missing.append(repo)
        continue

    if link_mode == "copy":
        shutil.copytree(source, target, symlinks=True)
        action = "copied"
    else:
        os.symlink(source, target, target_is_directory=True)
        action = "linked"
    linked += 1
    print(f"[gala-repo-reuse] {action}: {target} -> {source}")

print(
    "[gala-repo-reuse] summary: "
    f"repos={len(repos)} existing={existing} linked={linked} missing={len(missing)}"
)
if missing:
    print("[gala-repo-reuse] repos still need normal clone: " + ", ".join(missing[:20]))
    if len(missing) > 20:
        print(f"[gala-repo-reuse] ... and {len(missing) - 20} more")
PY
}

print_shared_input_state() {
  local samples structures
  samples="$(sample_rows)"
  structures="$(structure_rows)"
  echo "[state] EXP_NAME=${EXP_NAME}"
  echo "[state] SAMPLE_SIZE=${SAMPLE_SIZE}"
  echo "[state] FORCE_PREPARE=${FORCE_PREPARE}"
  echo "[state] FORCE_STRUCTURES=${FORCE_STRUCTURES}"
  echo "[state] SKIP_SHARED_PREPARE=${SKIP_SHARED_PREPARE}"
  echo "[state] CANONICAL_SAMPLES=${CANONICAL_SAMPLES}"
  echo "[state] sample_rows=${samples}"
  echo "[state] CANONICAL_STRUCTURE_DIR=${CANONICAL_STRUCTURE_DIR}"
  echo "[state] structure_rows=${structures}"
}

explain_prepare_decision() {
  local samples
  samples="$(sample_rows)"
  if is_truthy "${FORCE_PREPARE}"; then
    echo "[prepare reason] FORCE_PREPARE=${FORCE_PREPARE}"
    return 0
  fi
  if [[ ! -f "${CANONICAL_SAMPLES}" ]]; then
    echo "[prepare reason] canonical samples file is missing: ${CANONICAL_SAMPLES}"
    return 0
  fi
  if [[ "${SAMPLE_SIZE}" -gt 0 && "${samples}" != "${SAMPLE_SIZE}" ]]; then
    echo "[prepare reason] sample row count mismatch: rows=${samples}, expected=${SAMPLE_SIZE}"
    return 0
  fi
  if [[ "${SAMPLE_SIZE}" -le 0 && "${samples}" == "0" ]]; then
    echo "[prepare reason] SAMPLE_SIZE<=0 and sample rows are 0"
    return 0
  fi
  echo "[prepare reason] unknown; expected_sample_rows_ready returned false"
}

structure_rows() {
  if [[ -d "${CANONICAL_STRUCTURE_DIR}" ]]; then
    find "${CANONICAL_STRUCTURE_DIR}" -maxdepth 1 -type f -name '*.json' | wc -l | tr -d ' '
  else
    echo 0
  fi
}

require_shared_inputs_ready() {
  local samples structures
  samples="$(sample_rows)"
  structures="$(structure_rows)"
  if ! expected_sample_rows_ready; then
    cat >&2 <<EOF
ERROR: SKIP_SHARED_PREPARE=1 but canonical samples are not ready.

Expected:
  ${CANONICAL_SAMPLES}
  rows: ${SAMPLE_SIZE}

Found:
  rows: ${samples}

This usually means the parallel supervisor child job was started before the
shared prepare finished, or this loccode copy does not contain prepared inputs.
Run the supervisor without SKIP_SHARED_PREPARE, or prepare/copy the canonical
data first.
EOF
    exit 2
  fi
  if [[ "${samples}" == "0" || "${structures}" -lt "${samples}" ]]; then
    cat >&2 <<EOF
ERROR: SKIP_SHARED_PREPARE=1 but canonical repo_structures are not ready.

Expected:
  ${CANONICAL_STRUCTURE_DIR}/*.json
  files: at least ${samples}

Found:
  files: ${structures}

Run the supervisor once with shared preparation enabled, or copy the prepared
repo_structures into this loccode copy.
EOF
    exit 2
  fi
}

needs_locagent_python_for_shared_inputs() {
  if is_truthy "${RUN_LOCAGENT}"; then
    return 0
  fi
  if is_truthy "${FORCE_PREPARE}" || ! expected_sample_rows_ready; then
    return 0
  fi
  if is_truthy "${FORCE_STRUCTURES}"; then
    return 0
  fi
  local samples structures
  samples="$(sample_rows)"
  structures="$(structure_rows)"
  if [[ "${samples}" == "0" || "${structures}" -lt "${samples}" ]]; then
    return 0
  fi
  return 1
}

metric_pair() {
  local dir="$1"
  echo "${dir}/eval/metrics_3level.md|${dir}/eval_strict/metrics_3level.md"
}

metrics_complete() {
  local dir="$1"
  [[ -s "${dir}/eval/metrics_3level.md" && -s "${dir}/eval_strict/metrics_3level.md" ]]
}

prediction_rows() {
  local pred_file="$1"
  local python_bin="${2:-python3}"
  if [[ ! -s "${pred_file}" ]]; then
    echo 0
    return 0
  fi
  "${python_bin}" - "$pred_file" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
if path.suffix == ".jsonl":
    with path.open("r", encoding="utf-8", errors="ignore") as fh:
        print(sum(1 for line in fh if line.strip()))
    raise SystemExit

try:
    data = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    print(0)
    raise SystemExit

if isinstance(data, list):
    print(len(data))
elif isinstance(data, dict):
    if isinstance(data.get("results"), list):
        print(len(data["results"]))
    elif isinstance(data.get("loc_results"), dict):
        print(len(data["loc_results"]))
    else:
        print(len(data))
else:
    print(0)
PY
}

run_eval_if_possible() {
  local label="$1"
  local result_dir="$2"
  local pred_file="$3"
  local command="$4"
  if metrics_complete "${result_dir}" && ! is_truthy "${FORCE_RERUN}"; then
    echo
    echo "========== Skip ${label} eval =========="
    echo "[skip] Found ${result_dir}/eval/metrics_3level.md"
    echo "[skip] Found ${result_dir}/eval_strict/metrics_3level.md"
    return 0
  fi
  if [[ -s "${pred_file}" ]] && ! is_truthy "${FORCE_RERUN}"; then
    local expected_rows observed_rows
    expected_rows="$(sample_rows)"
    observed_rows="$(prediction_rows "${pred_file}" "${PYTHON_BIN:-python3}")"
    if [[ "${expected_rows}" -gt 0 && "${observed_rows}" -lt "${expected_rows}" ]]; then
      echo
      echo "========== Resume ${label} localization =========="
      echo "[resume] Existing prediction file is incomplete: ${pred_file}"
      echo "[resume] predictions=${observed_rows}, expected=${expected_rows}"
      echo "[resume] Continue localization instead of evaluating partial predictions."
      return 1
    fi
    run_step "Evaluate existing ${label} predictions" run_shell "${command}"
    return 0
  fi
  return 1
}

prediction_empty_rate() {
  local pred_file="$1"
  local field="$2"
  local python_bin="${3:-python3}"
  if [[ ! -s "${pred_file}" ]]; then
    echo "1.0"
    return 0
  fi
  "${python_bin}" - "${pred_file}" "${field}" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
field = sys.argv[2]
rows = []
for line in path.read_text(encoding="utf-8").splitlines():
    if line.strip():
        rows.append(json.loads(line))
if not rows:
    print("1.0")
else:
    empty = sum(1 for row in rows if not row.get(field))
    print(f"{empty / len(rows):.6f}")
PY
}

prune_empty_prediction_rows() {
  local pred_file="$1"
  local field="$2"
  local python_bin="${3:-python3}"
  if [[ ! -s "${pred_file}" ]]; then
    return 0
  fi
  "${python_bin}" - "${pred_file}" "${field}" <<'PY'
import json
import shutil
import sys
from pathlib import Path

path = Path(sys.argv[1])
field = sys.argv[2]
rows = []
for line in path.read_text(encoding="utf-8").splitlines():
    if line.strip():
        rows.append(json.loads(line))
kept = [row for row in rows if row.get(field)]
if len(kept) == len(rows):
    print(f"[health] no empty {field} rows to prune in {path}")
    raise SystemExit(0)
backup = path.with_suffix(path.suffix + ".before_prune_empty")
shutil.copy2(path, backup)
with path.open("w", encoding="utf-8") as f:
    for row in kept:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
print(f"[health] pruned {len(rows) - len(kept)} empty {field} rows from {path}")
print(f"[health] backup: {backup}")
PY
}

repair_cosil_if_unhealthy() {
  local pred_file="$1"
  local result_dir="$2"
  if [[ ! -s "${pred_file}" ]] || is_truthy "${FORCE_RERUN}"; then
    return 0
  fi
  local rate
  rate="$(prediction_empty_rate "${pred_file}" found_files "${COSIL_PY}")"
  echo "[health] CoSIL found_files empty rate: ${rate} (threshold ${COSIL_MAX_EMPTY_RATE})"
  if "${COSIL_PY}" - "${rate}" "${COSIL_MAX_EMPTY_RATE}" <<'PY'
import sys
rate = float(sys.argv[1])
threshold = float(sys.argv[2])
raise SystemExit(0 if rate > threshold else 1)
PY
  then
    echo "[health][warn] CoSIL predictions look incomplete; repairing for resume."
    prune_empty_prediction_rows "${pred_file}" found_files "${COSIL_PY}"
    rm -rf "${result_dir}/eval" "${result_dir}/eval_strict"
  fi
}

if needs_locagent_python_for_shared_inputs; then
  ensure_python "${LOCAGENT_PY}" "LocAgent"
fi
if is_truthy "${RUN_COSIL}"; then
  ensure_python "${COSIL_PY}" "CoSIL"
  ensure_import "${COSIL_PY}" "anthropic" "CoSIL"
fi
if is_truthy "${RUN_GRAPHLOCATOR}"; then
  ensure_python "${GRAPHLOCATOR_PY}" "GraphLocator"
fi
if is_truthy "${RUN_GALA}"; then
  ensure_python "${GALA_PY}" "GALA"
fi
if is_truthy "${RUN_MMIR}"; then
  ensure_python "${MMIR_PY}" "MM-IR"
fi

LOCAGENT_RESULT_DIR="${ROOT_DIR}/LocAgent/newtest/${EXP_NAME}/results/${MODEL_TAG}"
COSIL_RESULT_DIR="${ROOT_DIR}/CoSIL/newtest/${EXP_NAME}/results/${MODEL_TAG}"
GRAPHLOCATOR_RESULT_DIR="${ROOT_DIR}/GraphLocator/newtest/${EXP_NAME}/results/${MODEL_TAG}"
GALA_RESULT_DIR="${ROOT_DIR}/GALA/mytest/${EXP_NAME}/results/${GALA_MODEL_TAG}"

if is_truthy "${CLEAN_FULL}"; then
  echo "[clean] removing previous full-dev outputs"
  run_cmd rm -rf \
    "${ROOT_DIR}/LocAgent/newtest/${EXP_NAME}" \
    "${ROOT_DIR}/CoSIL/newtest/${EXP_NAME}" \
    "${ROOT_DIR}/GraphLocator/newtest/${EXP_NAME}" \
    "${ROOT_DIR}/GALA/mytest/${EXP_NAME}" \
    "${ROOT_DIR}/MM-IR/results/${EXP_NAME}"
fi

run_cmd mkdir -p "${CANONICAL_DATA_DIR}" "${CANONICAL_STRUCTURE_DIR}"

cat <<EOF
SWE-bench Multimodal full-dev experiment: ${EXP_NAME}
Dataset: ${DATASET}
Split: ${SPLIT}
Expected samples: ${SAMPLE_SIZE}
Canonical samples: ${CANONICAL_SAMPLES}
Canonical structures: ${CANONICAL_STRUCTURE_DIR}
OpenAI-compatible endpoint: ${OPENAI_API_BASE}
Model: ${MODEL}
VLM model: ${VLM_MODEL}
Text model: ${TEXT_MODEL_NAME}
VLM API model: ${VLM_API_MODEL_NAME}
Text API model: ${TEXT_API_MODEL_NAME}
Skip shared prepare: ${SKIP_SHARED_PREPARE}
Dry run: ${DRY_RUN}
EOF

print_shared_input_state

api_preflight_if_needed

PREPARE_ARGS=(
  newtest/scripts/prepare_multimodal_localization.py
  --benchmark "${BENCHMARK}"
  --dataset "${DATASET}"
  --split "${SPLIT}"
  --sample-size "${SAMPLE_SIZE}"
  --seed "${SEED}"
  --output-dir "${CANONICAL_DATA_DIR}"
  --used-list-name "${USED_LIST}"
)
if [[ -n "${SOURCE_JSONL}" ]]; then
  PREPARE_ARGS+=(--source-jsonl "${SOURCE_JSONL}")
fi

if is_truthy "${SKIP_SHARED_PREPARE}"; then
  echo
  echo "========== Skip shared sample/structure preparation =========="
  require_shared_inputs_ready
  echo "[skip] SKIP_SHARED_PREPARE=1."
  echo "[skip] Found ${CANONICAL_SAMPLES} with $(sample_rows) rows."
  echo "[skip] Found ${CANONICAL_STRUCTURE_DIR} with $(structure_rows) structure files."
elif ! is_truthy "${FORCE_PREPARE}" && expected_sample_rows_ready; then
  echo
  echo "========== Skip Prepare canonical SWE-bench Multimodal dev =========="
  echo "[skip] Found ${CANONICAL_SAMPLES} with $(sample_rows) rows."
  echo "[skip] Use FORCE_PREPARE=1 to regenerate canonical samples."
else
  explain_prepare_decision
  run_step "Prepare canonical SWE-bench Multimodal dev" \
    run_shell "cd '${ROOT_DIR}/LocAgent' && OPENAI_API_BASE='${OPENAI_API_BASE}' OPENAI_API_KEY='${OPENAI_API_KEY}' '${LOCAGENT_PY}' ${PREPARE_ARGS[*]}"
fi

if is_truthy "${SKIP_SHARED_PREPARE}"; then
  :
elif ! is_truthy "${FORCE_STRUCTURES}" && [[ "$(structure_rows)" -ge "$(sample_rows)" ]] && [[ "$(sample_rows)" -gt 0 ]]; then
  echo
  echo "========== Skip Build canonical repo_structures =========="
  echo "[skip] Found $(structure_rows) structure files for $(sample_rows) samples."
  echo "[skip] Use FORCE_STRUCTURES=1 to rebuild canonical structures."
else
  if is_truthy "${FORCE_STRUCTURES}"; then
    echo "[structure reason] FORCE_STRUCTURES=${FORCE_STRUCTURES}"
  else
    echo "[structure reason] structure count insufficient: structures=$(structure_rows), samples=$(sample_rows)"
  fi
  run_step "Build canonical repo_structures" \
    run_shell "cd '${ROOT_DIR}/LocAgent' && '${LOCAGENT_PY}' newtest/scripts/build_repo_structures.py \
      --samples '${CANONICAL_SAMPLES}' \
      --output-dir '${CANONICAL_STRUCTURE_DIR}' \
      --repo-base-dir 'repo_newtest_${EXP_NAME}' \
      --dataset 'newtest_${EXP_NAME}' \
      --split train \
      --skip-existing \
      --continue-on-error"
fi

CANONICAL_SAMPLE_COUNT="$(sample_rows)"
if [[ "${CANONICAL_SAMPLE_COUNT}" == "0" ]] && is_truthy "${DRY_RUN}"; then
  CANONICAL_SAMPLE_COUNT="${SAMPLE_SIZE}"
fi

if is_truthy "${RUN_LOCAGENT}"; then
  LOCAGENT_PRED="${LOCAGENT_RESULT_DIR}/location/merged_loc_outputs_mrr.jsonl"
  LOCAGENT_EVAL_CMD="cd '${ROOT_DIR}/LocAgent' && \
      '${LOCAGENT_PY}' newtest/scripts/eval_file_level.py \
        --samples '${CANONICAL_SAMPLES}' \
        --pred-file '${LOCAGENT_PRED}' \
        --output-dir '${LOCAGENT_RESULT_DIR}/eval' && \
      '${LOCAGENT_PY}' newtest/scripts/eval_3level_localization.py \
        --samples '${CANONICAL_SAMPLES}' \
        --pred-file '${LOCAGENT_PRED}' \
        --structure-dir '${CANONICAL_STRUCTURE_DIR}' \
        --output-dir '${LOCAGENT_RESULT_DIR}/eval' && \
      '${LOCAGENT_PY}' newtest/scripts/eval_3level_localization_strict.py \
        --samples '${CANONICAL_SAMPLES}' \
        --pred-file '${LOCAGENT_PRED}' \
        --structure-dir '${CANONICAL_STRUCTURE_DIR}' \
        --output-dir '${LOCAGENT_RESULT_DIR}/eval_strict'"
  if ! run_eval_if_possible "LocAgent" "${LOCAGENT_RESULT_DIR}" "${LOCAGENT_PRED}" "${LOCAGENT_EVAL_CMD}"; then
    run_if_needed "Run LocAgent on ${EXP_NAME}" "$(metric_pair "${LOCAGENT_RESULT_DIR}")" \
      run_shell "cd '${ROOT_DIR}/LocAgent' && \
      PYTHON_BIN='${LOCAGENT_PY}' \
      OPENAI_API_KEY='${OPENAI_API_KEY}' \
      OPENAI_API_BASE='${OPENAI_API_BASE}' \
      MULADAPTER_MODEL='${MULADAPTER_MODEL}' \
      MULADAPTER_BASE_URL='${MULADAPTER_BASE_URL}' \
      MULADAPTER_API_KEY='${MULADAPTER_API_KEY}' \
      MODEL='${MODEL}' \
      LOCAGENT_MODEL='${LOCAGENT_MODEL:-}' \
      LOCAGENT_BACKEND_MODEL='${LOCAGENT_BACKEND_MODEL:-${LITELLM_MODEL}}' \
      BENCHMARK='${BENCHMARK}' \
      TEST_NAME='${EXP_NAME}' \
      SAMPLE_SIZE='${CANONICAL_SAMPLE_COUNT}' \
      SEED='${SEED}' \
      SOURCE_JSONL='${CANONICAL_SAMPLES}' \
      ALLOW_TEXT_ONLY=1 \
      LOCAGENT_STRUCTURE_DIR_OVERRIDE='${CANONICAL_STRUCTURE_DIR}' \
      NUM_PROCESSES='${LOCAGENT_NUM_PROCESSES:-1}' \
      NUM_SAMPLES='${LOCAGENT_NUM_SAMPLES:-5}' \
      MAX_ATTEMPT_NUM='${LOCAGENT_MAX_ATTEMPT_NUM:-12}' \
      RERUN_EMPTY_LOCATION='${LOCAGENT_RERUN_EMPTY_LOCATION:-1}' \
      BUILD_STRUCTURES=0 \
      bash newtest/scripts/run_locagent_swebench_multimodal_60.sh"
  fi
fi

if is_truthy "${RUN_COSIL}"; then
  COSIL_PRED="${COSIL_RESULT_DIR}/file_level/loc_outputs.jsonl"
  repair_cosil_if_unhealthy "${COSIL_PRED}" "${COSIL_RESULT_DIR}"
  COSIL_EVAL_CMD="cd '${ROOT_DIR}/CoSIL' && \
      '${COSIL_PY}' newtest/scripts/eval_file_level.py \
        --samples '${CANONICAL_SAMPLES}' \
        --pred-file '${COSIL_PRED}' \
        --output-dir '${COSIL_RESULT_DIR}/eval' && \
      '${COSIL_PY}' newtest/scripts/eval_3level_localization.py \
        --samples '${CANONICAL_SAMPLES}' \
        --pred-file '${COSIL_PRED}' \
        --structure-dir '${COSIL_STRUCTURE_DIR}' \
        --output-dir '${COSIL_RESULT_DIR}/eval' && \
      '${COSIL_PY}' newtest/scripts/eval_3level_localization_strict.py \
        --samples '${CANONICAL_SAMPLES}' \
        --pred-file '${COSIL_PRED}' \
        --structure-dir '${COSIL_STRUCTURE_DIR}' \
        --output-dir '${COSIL_RESULT_DIR}/eval_strict'"
  if ! run_eval_if_possible "CoSIL" "${COSIL_RESULT_DIR}" "${COSIL_PRED}" "${COSIL_EVAL_CMD}"; then
    run_if_needed "Run CoSIL on ${EXP_NAME}" "$(metric_pair "${COSIL_RESULT_DIR}")" \
      run_shell "cd '${ROOT_DIR}/CoSIL' && \
      PYTHON_BIN='${COSIL_PY}' \
      OPENAI_API_KEY='${OPENAI_API_KEY}' \
      OPENAI_API_BASE='${OPENAI_API_BASE}' \
      MULADAPTER_MODEL='${MULADAPTER_MODEL}' \
      MULADAPTER_BASE_URL='${MULADAPTER_BASE_URL}' \
      MULADAPTER_API_KEY='${MULADAPTER_API_KEY}' \
      MODEL='${MODEL}' \
      COSIL_BACKEND_MODEL='${COSIL_BACKEND_MODEL:-${LITELLM_MODEL}}' \
      BENCHMARK='${BENCHMARK}' \
      TEST_NAME='${EXP_NAME}' \
      SAMPLE_SIZE='${CANONICAL_SAMPLE_COUNT}' \
      SEED='${SEED}' \
      SOURCE_JSONL='${CANONICAL_SAMPLES}' \
      ALLOW_TEXT_ONLY=1 \
      STRUCTURE_DIR_OVERRIDE='${COSIL_STRUCTURE_DIR}' \
      BUILD_STRUCTURES='${COSIL_BUILD_STRUCTURES:-0}' \
      REBUILD_STRUCTURES='${COSIL_REBUILD_STRUCTURES:-0}' \
      bash newtest/scripts/run_cosil_swebench_multimodal_60.sh"
  fi
fi

if is_truthy "${RUN_GRAPHLOCATOR}"; then
  GRAPHLOCATOR_PRED="${GRAPHLOCATOR_RESULT_DIR}/loc_results.json"
  GRAPHLOCATOR_EVAL_CMD="cd '${ROOT_DIR}/GraphLocator' && \
      '${GRAPHLOCATOR_PY}' newtest/scripts/eval_file_level.py \
        --samples '${CANONICAL_SAMPLES}' \
        --pred-file '${GRAPHLOCATOR_PRED}' \
        --output-dir '${GRAPHLOCATOR_RESULT_DIR}/eval' && \
      '${GRAPHLOCATOR_PY}' newtest/scripts/eval_3level_localization.py \
        --samples '${CANONICAL_SAMPLES}' \
        --pred-file '${GRAPHLOCATOR_PRED}' \
        --structure-dir '${CANONICAL_STRUCTURE_DIR}' \
        --output-dir '${GRAPHLOCATOR_RESULT_DIR}/eval' && \
      '${GRAPHLOCATOR_PY}' newtest/scripts/eval_3level_localization_strict.py \
        --samples '${CANONICAL_SAMPLES}' \
        --pred-file '${GRAPHLOCATOR_PRED}' \
        --structure-dir '${CANONICAL_STRUCTURE_DIR}' \
        --output-dir '${GRAPHLOCATOR_RESULT_DIR}/eval_strict'"
  if ! run_eval_if_possible "GraphLocator" "${GRAPHLOCATOR_RESULT_DIR}" "${GRAPHLOCATOR_PRED}" "${GRAPHLOCATOR_EVAL_CMD}"; then
    run_if_needed "Run GraphLocator on ${EXP_NAME}" "$(metric_pair "${GRAPHLOCATOR_RESULT_DIR}")" \
      run_shell "cd '${ROOT_DIR}/GraphLocator' && \
      PYTHON_BIN='${GRAPHLOCATOR_PY}' \
      OPENAI_API_KEY='${OPENAI_API_KEY}' \
      OPENAI_API_BASE='${OPENAI_API_BASE}' \
      MULADAPTER_MODEL='${MULADAPTER_MODEL}' \
      MULADAPTER_BASE_URL='${MULADAPTER_BASE_URL}' \
      MULADAPTER_API_KEY='${MULADAPTER_API_KEY}' \
      MODEL='${MODEL}' \
      GRAPHLOCATOR_BACKEND_MODEL='${GRAPHLOCATOR_BACKEND_MODEL:-${LITELLM_MODEL}}' \
      BENCHMARK='${BENCHMARK}' \
      TEST_NAME='${EXP_NAME}' \
      SAMPLE_SIZE='${CANONICAL_SAMPLE_COUNT}' \
      SEED='${SEED}' \
      SOURCE_JSONL='${CANONICAL_SAMPLES}' \
      ALLOW_TEXT_ONLY=1 \
      STRUCTURE_DIR='${CANONICAL_STRUCTURE_DIR}' \
      SKIP_EXIST='${GRAPHLOCATOR_SKIP_EXIST:-1}' \
      REBUILD_SKELETON='${GRAPHLOCATOR_REBUILD_SKELETON:-0}' \
      bash newtest/scripts/run_graphlocator_swebench_multimodal_60.sh"
  fi
fi

if is_truthy "${RUN_GALA}"; then
  GALA_PRED="${GALA_RESULT_DIR}/loc_results.json"
  GALA_SWEBENCH_RUNNER="${GALA_SWEBENCH_RUNNER:-mytest/scripts/run_gala_swebench_multimodal_60_localization.sh}"
  if [[ ! -f "${ROOT_DIR}/GALA/${GALA_SWEBENCH_RUNNER}" ]]; then
    cat >&2 <<EOF
ERROR: GALA SWE-bench runner not found:
  ${ROOT_DIR}/GALA/${GALA_SWEBENCH_RUNNER}

This usually means the repository on this machine is stale or GALA/mytest/scripts
was not tracked by git. Pull the latest repository, or set GALA_SWEBENCH_RUNNER
to an existing runner under GALA/.
EOF
    exit 2
  fi
  GALA_EVAL_CMD="cd '${ROOT_DIR}/GALA' && \
      '${GALA_PY}' mytest/scripts/eval_gala_localization.py \
        --result-dir '${GALA_RESULT_DIR}' \
        --gt-file '${ROOT_DIR}/GALA/mytest/${EXP_NAME}/data/gt_files.json' \
        --samples '${ROOT_DIR}/GALA/mytest/${EXP_NAME}/data/samples.json' \
        --output-dir '${GALA_RESULT_DIR}/eval' \
        --loc-output '${GALA_PRED}' \
        --structure-dir '${CANONICAL_STRUCTURE_DIR}' && \
      '${GALA_PY}' mytest/scripts/eval_gala_localization_strict.py \
        --result-dir '${GALA_RESULT_DIR}' \
        --gt-file '${ROOT_DIR}/GALA/mytest/${EXP_NAME}/data/gt_files.json' \
        --samples '${ROOT_DIR}/GALA/mytest/${EXP_NAME}/data/samples.json' \
        --output-dir '${GALA_RESULT_DIR}/eval_strict' \
        --loc-output '${GALA_PRED}' \
        --structure-dir '${CANONICAL_STRUCTURE_DIR}'"
  if ! run_eval_if_possible "GALA" "${GALA_RESULT_DIR}" "${GALA_PRED}" "${GALA_EVAL_CMD}"; then
    link_gala_repos_from_locagent "${EXP_NAME}" "${CANONICAL_SAMPLES}" "${ROOT_DIR}/GALA/mytest/${EXP_NAME}/repos"
    run_if_needed "Run GALA on ${EXP_NAME}" "$(metric_pair "${GALA_RESULT_DIR}")" \
      run_shell "cd '${ROOT_DIR}/GALA' && \
      PYTHON_BIN='${GALA_PY}' \
      OPENAI_API_KEY='${OPENAI_API_KEY}' \
      VLM_API_KEY='${VLM_API_KEY}' \
      TEXT_API_KEY='${TEXT_API_KEY}' \
      VLM_MODEL='${VLM_MODEL}' \
      VLM_BASE_URL='${VLM_BASE_URL}' \
      TEXT_MODEL_NAME='${TEXT_MODEL_NAME}' \
      VLM_API_MODEL_NAME='${VLM_API_MODEL_NAME}' \
      TEXT_API_MODEL_NAME='${TEXT_API_MODEL_NAME}' \
      TEXT_BASE_URL='${TEXT_BASE_URL}' \
      TEST_NAME='${EXP_NAME}' \
      IMAGE_DIR='${GALA_IMAGE_DIR}' \
      DOWNLOAD_IMAGES='${GALA_DOWNLOAD_IMAGES}' \
      REUSE_IMAGE_IR='${GALA_REUSE_IMAGE_IR}' \
      RESUME_IMAGE_IR='${GALA_RESUME_IMAGE_IR}' \
      FORCE_IMAGE_IR='${GALA_FORCE_IMAGE_IR}' \
      CHECK_IMAGE_IR_COMPLETE='${GALA_CHECK_IMAGE_IR_COMPLETE}' \
      IMAGE_DOWNLOAD_RETRIES='${GALA_IMAGE_DOWNLOAD_RETRIES}' \
      IMAGE_DOWNLOAD_RETRY_SLEEP='${GALA_IMAGE_DOWNLOAD_RETRY_SLEEP}' \
      IMAGE_DOWNLOAD_BACKOFF='${GALA_IMAGE_DOWNLOAD_BACKOFF}' \
      INPUT_FILE='${CANONICAL_SAMPLES}' \
      SAMPLE_SIZE='${CANONICAL_SAMPLE_COUNT}' \
      SEED='${SEED}' \
      ALLOW_MISSING_PATCH=1 \
      STRUCTURE_DIR='${CANONICAL_STRUCTURE_DIR}' \
      bash '${GALA_SWEBENCH_RUNNER}'"
  fi
fi

if is_truthy "${RUN_MMIR}"; then
  for MMIR_METHOD_NAME in ${RUN_MMIR_METHODS}; do
    MMIR_RESULT_DIR="${ROOT_DIR}/MM-IR/results/${EXP_NAME}/${MMIR_METHOD_NAME}"
    MMIR_PRED="${MMIR_RESULT_DIR}/loc_results.json"
    MMIR_EVAL_CMD="cd '${ROOT_DIR}/MM-IR' && \
        '${MMIR_PY}' -m mmir.evaluation.eval_3level \
          --samples '${CANONICAL_SAMPLES}' \
          --predictions '${MMIR_PRED}' \
          --structure-dir '${CANONICAL_STRUCTURE_DIR}' \
          --output-dir '${MMIR_RESULT_DIR}/eval' \
          --limit '${MMIR_LIMIT:-0}' && \
        '${MMIR_PY}' -m mmir.evaluation.eval_3level_strict \
          --samples '${CANONICAL_SAMPLES}' \
          --predictions '${MMIR_PRED}' \
          --structure-dir '${CANONICAL_STRUCTURE_DIR}' \
          --output-dir '${MMIR_RESULT_DIR}/eval_strict' \
          --limit '${MMIR_LIMIT:-0}'"
    if ! run_eval_if_possible "MM-IR ${MMIR_METHOD_NAME}" "${MMIR_RESULT_DIR}" "${MMIR_PRED}" "${MMIR_EVAL_CMD}"; then
      run_if_needed "Run MM-IR ${MMIR_METHOD_NAME} on ${EXP_NAME}" "$(metric_pair "${MMIR_RESULT_DIR}")" \
        run_shell "cd '${ROOT_DIR}/MM-IR' && \
        PYTHON_BIN='${MMIR_PY}' \
        METHOD='${MMIR_METHOD_NAME}' \
        DENSE_MODEL='${MMIR_DENSE_MODEL:-}' \
        DENSE_BATCH_SIZE='${MMIR_DENSE_BATCH_SIZE:-${DENSE_BATCH_SIZE:-16}}' \
        DENSE_DEVICE='${MMIR_DENSE_DEVICE:-${DENSE_DEVICE:-}}' \
        DENSE_DEVICE_AUTO_FALLBACK='${DENSE_DEVICE_AUTO_FALLBACK:-1}' \
        LIMIT='${MMIR_LIMIT:-0}' \
        SAMPLE_FILE='${CANONICAL_SAMPLES}' \
        STRUCTURE_DIR='${CANONICAL_STRUCTURE_DIR}' \
        OUTPUT_DIR='${MMIR_RESULT_DIR}' \
        bash scripts/run_mmir_swebench_multimodal_60.sh"
    fi
  done
fi

cat <<EOF

All requested baselines finished or were skipped for ${EXP_NAME}.

Result directories:
  LocAgent:      ${ROOT_DIR}/LocAgent/newtest/${EXP_NAME}/results
  CoSIL:         ${ROOT_DIR}/CoSIL/newtest/${EXP_NAME}/results
  GraphLocator:  ${ROOT_DIR}/GraphLocator/newtest/${EXP_NAME}/results
  GALA:          ${ROOT_DIR}/GALA/mytest/${EXP_NAME}/results
  MM-IR:         ${ROOT_DIR}/MM-IR/results/${EXP_NAME}

Each completed baseline should have:
  eval/metrics_3level.md
  eval_strict/metrics_3level.md

MM-IR methods requested:
  ${RUN_MMIR_METHODS}

EOF
