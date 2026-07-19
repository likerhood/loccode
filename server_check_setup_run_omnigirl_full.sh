#!/usr/bin/env bash
set -euo pipefail

# Server-side OmniGIRL full-candidates runner.
#
# This mirrors the server_check_setup_run_* wrappers used for SWE60/Omni60,
# but targets the runnable OmniGIRL full-candidates set used by
# run_omnigirl_full_baselines*.sh.
#
# Important: this is the current runnable full-candidates benchmark口径
# (normally 631 samples), not the raw OmniGIRL 959 source. The runner first
# checks prepared samples.jsonl/repo_structures. If they are missing, it can
# prepare the fixed runnable candidate set and build repo_structures by cloning
# the referenced repositories, matching the behavior of the SWE60/Omni60 server
# wrappers.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export GITHUB_MIRROR_PREFIX="${GITHUB_MIRROR_PREFIX:-${REPO_GITHUB_MIRROR_PREFIX:-https://gh.xmly.dev}}"

warn() {
  echo "[warn] $*" >&2
}

detect_conda_sh() {
  local candidate
  for candidate in \
    "${HOME}/miniconda3/etc/profile.d/conda.sh" \
    "${HOME}/anaconda3/etc/profile.d/conda.sh" \
    "/data2/like/miniconda3/etc/profile.d/conda.sh" \
    "/data/like/miniconda3/etc/profile.d/conda.sh" \
    "/opt/conda/etc/profile.d/conda.sh"; do
    if [[ -f "${candidate}" ]]; then
      echo "${candidate}"
      return 0
    fi
  done
  return 1
}

detect_conda_env_root() {
  local candidate
  if [[ "${ROOT_DIR}" == /data2/like/* && -d "/data2/like" ]]; then
    echo "/data2/like/envs"
    return 0
  fi
  if [[ "${ROOT_DIR}" == /data/like/* && -d "/data/like" ]]; then
    echo "/data/like/envs"
    return 0
  fi
  for candidate in \
    "${HOME}/miniconda3/envs" \
    "${HOME}/anaconda3/envs" \
    "/data2/like/envs" \
    "/data/like/envs"; do
    if [[ -d "${candidate}" ]]; then
      echo "${candidate}"
      return 0
    fi
  done
  return 1
}

is_truthy() {
  [[ "${1:-}" == "1" || "${1:-}" == "true" || "${1:-}" == "yes" ]]
}

require_nonempty() {
  local name="$1"
  local value="$2"
  if [[ -z "${value}" ]]; then
    cat >&2 <<EOF
ERROR: ${name} is required because at least one LLM baseline is selected.
Example:
  export BASE_URL='https://token-plan-cn.xiaomimimo.com/v1'
  export API_KEY='...'
  export MODEL_NAME='mimo-v2.5'
EOF
    exit 2
  fi
}

api_host_from_url() {
  local url="${1:-}"
  url="${url#*://}"
  url="${url%%/*}"
  url="${url%%@}"
  url="${url%%:*}"
  echo "${url}"
}

append_csv_unique() {
  local current="$1"
  local item part found
  shift || true
  for item in "$@"; do
    [[ -z "${item}" ]] && continue
    found=0
    IFS=',' read -r -a _parts <<< "${current}"
    for part in "${_parts[@]}"; do
      if [[ "${part}" == "${item}" ]]; then
        found=1
        break
      fi
    done
    if [[ "${found}" == "0" ]]; then
      current="${current:+${current},}${item}"
    fi
  done
  echo "${current}"
}

build_api_no_proxy() {
  local base hosts host
  base="${NO_PROXY:-${no_proxy:-}}"
  hosts="${API_NO_PROXY_HOSTS:-$(api_host_from_url "${BASE_URL:-}")}"
  hosts="${hosts//,/ }"
  for host in ${hosts}; do
    base="$(append_csv_unique "${base}" "${host}")"
  done
  echo "${base}"
}

redact_api_key() {
  local key="${1:-}"
  if [[ "${#key}" -le 10 ]]; then
    echo "<hidden>"
  else
    echo "${key:0:4}...${key: -4}"
  fi
}

declare -a LLM_ENDPOINT_NAMES=()
declare -a LLM_ENDPOINT_BASE_URLS=()
declare -a LLM_ENDPOINT_API_KEYS=()
declare -a LLM_ENDPOINT_MODELS=()
SELECTED_LLM_ENDPOINT_INDEX=-1

parse_llm_endpoints() {
  local raw="${LLM_ENDPOINTS:-}"
  local entry name base_url api_key model
  LLM_ENDPOINT_NAMES=()
  LLM_ENDPOINT_BASE_URLS=()
  LLM_ENDPOINT_API_KEYS=()
  LLM_ENDPOINT_MODELS=()
  [[ -z "${raw}" ]] && return 0

  IFS=';' read -r -a _llm_endpoint_entries <<< "${raw}"
  for entry in "${_llm_endpoint_entries[@]}"; do
    [[ -z "${entry//[[:space:]]/}" ]] && continue
    IFS='|' read -r name base_url api_key model _extra <<< "${entry}"
    if [[ -z "${name:-}" || -z "${base_url:-}" || -z "${api_key:-}" || -z "${model:-}" || -n "${_extra:-}" ]]; then
      cat >&2 <<EOF
ERROR: invalid LLM_ENDPOINTS entry:
  ${entry}

Expected format:
  name|base_url|api_key|model;name2|base_url2|api_key2|model2
EOF
      exit 2
    fi
    LLM_ENDPOINT_NAMES+=("${name}")
    LLM_ENDPOINT_BASE_URLS+=("${base_url}")
    LLM_ENDPOINT_API_KEYS+=("${api_key}")
    LLM_ENDPOINT_MODELS+=("${model}")
  done
}

llm_endpoint_count() {
  echo "${#LLM_ENDPOINT_NAMES[@]}"
}

apply_llm_endpoint() {
  local idx="$1"
  SELECTED_LLM_ENDPOINT_INDEX="${idx}"
  BASE_URL="${LLM_ENDPOINT_BASE_URLS[$idx]}"
  API_KEY="${LLM_ENDPOINT_API_KEYS[$idx]}"
  MODEL_NAME="${LLM_ENDPOINT_MODELS[$idx]}"
  LITELLM_MODEL_NAME="${MODEL_NAME}"
  if [[ "${LITELLM_MODEL_NAME}" != */* ]]; then
    LITELLM_MODEL_NAME="openai/${LITELLM_MODEL_NAME}"
  fi
  API_NO_PROXY_VALUE="${NO_PROXY:-${no_proxy:-}}"
  if [[ "${LLM_BASELINE_SELECTED}" == "1" ]] && is_truthy "${API_NO_PROXY}"; then
    API_NO_PROXY_VALUE="$(build_api_no_proxy)"
  fi
}

preflight_llm_endpoint() {
  local idx="$1"
  local name base_url api_key model host output status
  name="${LLM_ENDPOINT_NAMES[$idx]}"
  base_url="${LLM_ENDPOINT_BASE_URLS[$idx]}"
  api_key="${LLM_ENDPOINT_API_KEYS[$idx]}"
  model="${LLM_ENDPOINT_MODELS[$idx]}"
  host="$(api_host_from_url "${base_url}")"

  echo "[llm-endpoint] checking ${name}: base=${base_url} model=${model} key=$(redact_api_key "${api_key}")"
  if is_truthy "${DRY_RUN}"; then
    echo "[llm-endpoint] dry-run selects ${name}"
    return 0
  fi

  set +e
  output="$(
    NO_PROXY="$(append_csv_unique "${NO_PROXY:-${no_proxy:-}}" "${host}")" \
    no_proxy="$(append_csv_unique "${NO_PROXY:-${no_proxy:-}}" "${host}")" \
    "${PYTHON:-python3}" "${ROOT_DIR}/scripts/check_openai_compatible_api.py" \
      --base-url "${base_url}" \
      --api-key "${api_key}" \
      --model "${model#openai/}" \
      --timeout "${API_PREFLIGHT_TIMEOUT}" 2>&1
  )"
  status=$?
  set -e
  if [[ "${status}" == "0" ]]; then
    echo "[llm-endpoint] ${name} preflight OK"
    return 0
  fi
  echo "[llm-endpoint] ${name} preflight failed: ${output}" >&2
  return 1
}

select_working_llm_endpoint_from() {
  local start_idx="${1:-0}"
  local count idx
  count="$(llm_endpoint_count)"
  [[ "${count}" -eq 0 ]] && return 1
  for ((idx=start_idx; idx<count; idx++)); do
    if preflight_llm_endpoint "${idx}"; then
      apply_llm_endpoint "${idx}"
      echo "[llm-endpoint] selected ${LLM_ENDPOINT_NAMES[$idx]}: base=${BASE_URL} model=${MODEL_NAME} key=$(redact_api_key "${API_KEY}")"
      return 0
    fi
  done
  return 1
}

quota_or_auth_failure_in_logs() {
  local path="$1"
  [[ -e "${path}" ]] || return 1
  rg -i \
    "insufficient[_ -]?quota|quota exceeded|quota_exceeded|insufficient balance|balance not enough|no credit|credit exhausted|out of quota|余额不足|额度不足|额度已用完|欠费|invalid api key|unauthorized|authentication failed|permission denied|HTTP[^[:alnum:]]*(401|403)|\\b(401|403)\\b" \
    "${path}" >/dev/null 2>&1
}

env_python() {
  local env_name="$1"
  echo "${CONDA_ENV_ROOT%/}/${env_name}/bin/python"
}

env_missing() {
  local env_name="$1"
  [[ ! -x "$(env_python "${env_name}")" ]]
}

baseline_enabled() {
  local target="$1"
  local selected
  for selected in ${BASELINES}; do
    if [[ "${selected}" == "${target}" ]]; then
      return 0
    fi
  done
  return 1
}

count_jsonl_rows() {
  local path="$1"
  if [[ -f "${path}" ]]; then
    wc -l < "${path}" | tr -d ' '
  else
    echo 0
  fi
}

count_structures() {
  local path="$1"
  if [[ -d "${path}" ]]; then
    find "${path}" -maxdepth 1 -type f -name '*.json' | wc -l | tr -d ' '
  else
    echo 0
  fi
}

resolve_local_omni_full_source() {
  local candidate
  local -a candidates=(
    "${OMNIGIRL_SOURCE_JSONL:-}"
    "${ROOT_DIR}/MM-IR/data/omnigirl-full-candidates/source_omnigirl_full.jsonl"
    "${ROOT_DIR}/OmniGIRL/omnigirl/harness/benchmark/OmniGIRL.json"
  )
  for candidate in "${candidates[@]}"; do
    if [[ -n "${candidate}" && -s "${candidate}" ]]; then
      echo "${candidate}"
      return 0
    fi
  done
  echo ""
}

hf_dataset_available() {
  if ! command -v curl >/dev/null 2>&1; then
    return 1
  fi
  curl -fsSL --connect-timeout 10 --max-time 30 "${HF_DATASET_API_URL}" >/dev/null 2>&1
}

graphlocator_env_unhealthy() {
  local py
  py="$(env_python graphlocator)"
  if [[ ! -x "${py}" ]]; then
    return 0
  fi
  if ! "${py}" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)
PY
  then
    return 0
  fi
  if ! "${py}" - <<'PY' >/dev/null 2>&1
import dataclasses_json
import tree_sitter
PY
  then
    return 0
  fi
  if [[ -f "${ROOT_DIR}/GraphLocator/newtest/scripts/ensure_tree_sitter_lib.py" ]]; then
    if ! "${py}" "${ROOT_DIR}/GraphLocator/newtest/scripts/ensure_tree_sitter_lib.py" --no-build >/dev/null 2>&1; then
      return 0
    fi
  fi
  return 1
}

env_needs_setup() {
  local env_name="$1"
  if env_missing "${env_name}"; then
    return 0
  fi
  if [[ "${env_name}" == "graphlocator" ]] && graphlocator_env_unhealthy; then
    return 0
  fi
  return 1
}

run_logged() {
  local name="$1"
  shift
  local logfile="${LOG_DIR}/${name}.log"
  echo
  echo "========== ${name} =========="
  echo "[log] ${logfile}"
  printf '+'
  for arg in "$@"; do
    case "${arg}" in
      *API_KEY=*|*api_key=*|*Api-Key=*|*Authorization:*)
        printf ' %q' "${arg%%=*}=<hidden>"
        ;;
      *)
        printf ' %q' "${arg}"
        ;;
    esac
  done
  echo
  if is_truthy "${DRY_RUN}"; then
    return 0
  fi
  (
    set -o pipefail
    "$@" 2>&1 | tee "${logfile}"
  ) &
  local pid=$!
  local start now elapsed status
  start="$(date +%s)"
  while kill -0 "${pid}" >/dev/null 2>&1; do
    sleep "${SERVER_HEARTBEAT_INTERVAL}"
    if kill -0 "${pid}" >/dev/null 2>&1; then
      now="$(date +%s)"
      elapsed=$((now - start))
      echo "[still running][$((elapsed / 60))m$((elapsed % 60))s] ${name}; log=${logfile}"
      if [[ "${SERVER_HEARTBEAT_TAIL_LINES}" =~ ^[0-9]+$ ]] && [[ "${SERVER_HEARTBEAT_TAIL_LINES}" -gt 0 ]] && [[ -f "${logfile}" ]]; then
        echo "[recent log:${name}] tail -n ${SERVER_HEARTBEAT_TAIL_LINES} ${logfile}"
        tail -n "${SERVER_HEARTBEAT_TAIL_LINES}" "${logfile}" | sed "s/^/[${name}] /"
      fi
    fi
  done
  set +e
  wait "${pid}"
  status=$?
  set -e
  return "${status}"
}

setup_env() {
  local env_name="$1"
  local -a args=(--env "${env_name}")
  if is_truthy "${FORCE_RECREATE_ENVS}" || env_missing "${env_name}" || { [[ "${env_name}" == "graphlocator" ]] && graphlocator_env_unhealthy; }; then
    args+=(--recreate)
  fi
  if is_truthy "${NO_SMOKE_TEST}"; then
    args+=(--no-smoke-test)
  fi
  if is_truthy "${DRY_RUN}"; then
    args+=(--dry-run)
  fi
  run_logged "setup_${env_name}" \
    env CONDA_SH="${CONDA_SH}" CONDA_ENV_ROOT="${CONDA_ENV_ROOT}" \
      bash "${ROOT_DIR}/setup_baseline_conda_envs.sh" "${args[@]}"
}

check_python_or_die() {
  local env_name="$1"
  local py
  py="$(env_python "${env_name}")"
  if [[ ! -x "${py}" ]]; then
    if is_truthy "${DRY_RUN}"; then
      echo "[dry-run warn] ${env_name} python missing: ${py}"
      return 0
    fi
    echo "ERROR: ${env_name} python missing after setup: ${py}" >&2
    echo "Check ${LOG_DIR}/setup_${env_name}.log" >&2
    exit 2
  fi
  "${py}" -V
}

resolve_omnigirl_full_inputs() {
  local -a sample_candidates=(
    "${ROOT_DIR}/MM-IR/data/omnigirl-full-candidates/samples.jsonl"
    "${ROOT_DIR}/LocAgent/newtest/omnigirl-full-candidates/data/samples.jsonl"
  )
  local -a structure_candidates=(
    "${ROOT_DIR}/MM-IR/data/omnigirl-full-candidates/repo_structures"
    "${ROOT_DIR}/LocAgent/newtest/omnigirl-full-candidates/repo_structures"
  )
  local i
  if [[ "${SOURCE_JSONL_EXPLICIT}" != "1" || "${STRUCTURE_DIR_EXPLICIT}" != "1" ]]; then
    for i in "${!sample_candidates[@]}"; do
      if [[ -s "${sample_candidates[$i]}" && -d "${structure_candidates[$i]}" ]]; then
        if [[ "${SOURCE_JSONL_EXPLICIT}" != "1" ]]; then
          SOURCE_JSONL="${sample_candidates[$i]}"
        fi
        if [[ "${STRUCTURE_DIR_EXPLICIT}" != "1" ]]; then
          STRUCTURE_DIR="${structure_candidates[$i]}"
        fi
        break
      fi
    done
  fi
  COSIL_STRUCTURE_DIR="${COSIL_STRUCTURE_DIR:-${STRUCTURE_DIR}}"
}

require_omnigirl_full_inputs_or_explain() {
  local sample_count structure_count expected
  sample_count="$(count_jsonl_rows "${SOURCE_JSONL}")"
  structure_count="$(count_structures "${STRUCTURE_DIR}")"
  expected="${EXPECTED_SAMPLES}"
  if [[ "${expected}" == "auto" || "${expected}" == "0" ]]; then
    expected="${sample_count}"
  fi
  if [[ "${sample_count}" -gt 0 && "${structure_count}" -ge "${sample_count}" ]]; then
    echo "[data] OmniGIRL full-candidates inputs ready: samples=${sample_count}, repo_structures=${structure_count}"
    return 0
  fi
  if [[ "${sample_count}" -gt 0 && "${structure_count}" -ge "${expected}" && "${expected}" -gt 0 ]]; then
    echo "[data] OmniGIRL full-candidates inputs ready: samples=${sample_count}, repo_structures=${structure_count}"
    return 0
  fi
  cat >&2 <<EOF
ERROR: OmniGIRL full-candidates inputs are incomplete.

Found:
  samples rows:      ${sample_count}
  repo_structures:   ${structure_count}

Expected runnable full-candidates inputs:
  ${SOURCE_JSONL}
  ${STRUCTURE_DIR}/*.json

Automatic preparation is disabled for this run (ALLOW_PREPARE=0), or automatic
preparation failed before complete inputs were produced.

Fix one of these:
  1. Copy prepared MM-IR/data/omnigirl-full-candidates from a machine where it exists.
  2. Copy prepared LocAgent/newtest/omnigirl-full-candidates/data and repo_structures.
  3. Re-enable automatic preparation with ALLOW_PREPARE=1.
  4. Provide explicit paths:
       SOURCE_JSONL=/path/to/samples.jsonl STRUCTURE_DIR=/path/to/repo_structures bash ${0##*/}
EOF
  exit 2
}

omnigirl_full_inputs_ready() {
  local sample_count structure_count expected
  sample_count="$(count_jsonl_rows "${SOURCE_JSONL}")"
  structure_count="$(count_structures "${STRUCTURE_DIR}")"
  expected="${EXPECTED_SAMPLES}"
  if [[ "${expected}" == "auto" || "${expected}" == "0" ]]; then
    expected="${sample_count}"
  fi
  [[ "${sample_count}" -gt 0 && "${structure_count}" -ge "${sample_count}" ]] && return 0
  [[ "${sample_count}" -gt 0 && "${expected}" -gt 0 && "${structure_count}" -ge "${expected}" ]] && return 0
  return 1
}

prepare_python() {
  local py
  py="$(env_python locagent)"
  if [[ -x "${py}" ]]; then
    echo "${py}"
    return 0
  fi
  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return 0
  fi
  echo ""
}

prepare_omnigirl_full_inputs() {
  local sample_count structure_count expected prepare_source data_dir prep_py
  sample_count="$(count_jsonl_rows "${SOURCE_JSONL}")"
  structure_count="$(count_structures "${STRUCTURE_DIR}")"
  expected="${EXPECTED_SAMPLES}"
  if [[ "${expected}" == "auto" || "${expected}" == "0" ]]; then
    expected=631
  fi

  if ! is_truthy "${FORCE_PREPARE}" && ! is_truthy "${FORCE_STRUCTURES}" && omnigirl_full_inputs_ready; then
    echo "[data] OmniGIRL full-candidates inputs ready: samples=${sample_count}, repo_structures=${structure_count}"
    return 0
  fi

  if ! is_truthy "${ALLOW_PREPARE}"; then
    require_omnigirl_full_inputs_or_explain
  fi

  prep_py="$(prepare_python)"
  if [[ -z "${prep_py}" || ! -x "${prep_py}" ]]; then
    echo "ERROR: no usable python for OmniGIRL preparation." >&2
    echo "Expected LocAgent env python at $(env_python locagent), or python3 on PATH." >&2
    exit 2
  fi

  data_dir="$(dirname "${SOURCE_JSONL}")"
  mkdir -p "${data_dir}" "${STRUCTURE_DIR}"

  prepare_source="$(resolve_local_omni_full_source)"
  if [[ -z "${prepare_source}" ]]; then
    if is_truthy "${ALLOW_HF_PREPARE}"; then
      echo "[data] No local OmniGIRL raw source; ALLOW_HF_PREPARE=1, preparing from HuggingFace."
    elif [[ "${ALLOW_HF_PREPARE}" == "auto" ]]; then
      echo "[data] No local OmniGIRL raw source; checking HuggingFace dataset endpoint: ${HF_DATASET_API_URL}"
      if hf_dataset_available; then
        echo "[data] HuggingFace dataset endpoint is reachable; preparing from HuggingFace."
      else
        cat >&2 <<EOF
ERROR: OmniGIRL full-candidates inputs are missing and no local raw OmniGIRL source is available.

Missing prepared inputs:
  ${SOURCE_JSONL}
  ${STRUCTURE_DIR}/*.json

No local source found in:
  OMNIGIRL_SOURCE_JSONL
  ${ROOT_DIR}/MM-IR/data/omnigirl-full-candidates/source_omnigirl_full.jsonl
  ${ROOT_DIR}/OmniGIRL/omnigirl/harness/benchmark/OmniGIRL.json

HuggingFace endpoint is not reachable from this shell:
  ${HF_DATASET_API_URL}

Fix one of these:
  1. Copy prepared MM-IR/data/omnigirl-full-candidates from another machine.
  2. Copy raw OmniGIRL JSON to one of the local source paths above.
  3. Set HF_ENDPOINT=https://hf-mirror.com ALLOW_HF_PREPARE=1 and rerun.
EOF
        exit 2
      fi
    else
      echo "ERROR: local OmniGIRL source missing and ALLOW_HF_PREPARE=0." >&2
      exit 2
    fi
  else
    echo "[data] OmniGIRL raw source: ${prepare_source}"
  fi

  if is_truthy "${FORCE_PREPARE}" || [[ "$(count_jsonl_rows "${SOURCE_JSONL}")" -lt "${expected}" ]]; then
    local -a prepare_args=(
      "${ROOT_DIR}/LocAgent/newtest/scripts/prepare_multimodal_localization.py"
      --benchmark omnigirl
      --sample-size "${expected}"
      --seed "${SEED}"
      --output-dir "${data_dir}"
      --used-list-name "${USED_LIST}"
      --allow-text-only
    )
    if [[ -n "${prepare_source}" ]]; then
      prepare_args+=(--source-jsonl "${prepare_source}")
    fi
    run_logged "prepare_omnigirl_full_samples" \
      env HF_ENDPOINT="${HF_ENDPOINT}" OMNIGIRL_SOURCE_JSONL="${prepare_source}" \
        OPENAI_API_BASE="${BASE_URL}" OPENAI_API_KEY="${API_KEY}" \
        "${prep_py}" "${prepare_args[@]}"
  else
    echo "[data] Skip sample prepare: ${SOURCE_JSONL} has $(count_jsonl_rows "${SOURCE_JSONL}") rows."
  fi

  local target_structure_count
  target_structure_count="$(count_jsonl_rows "${SOURCE_JSONL}")"
  if [[ "${target_structure_count}" -le 0 ]]; then
    target_structure_count="${expected}"
  fi
  if is_truthy "${FORCE_STRUCTURES}" || [[ "$(count_structures "${STRUCTURE_DIR}")" -lt "${target_structure_count}" ]]; then
    run_logged "build_omnigirl_full_repo_structures" \
      env LOCAGENT_GIT_CLONE_RETRIES="${LOCAGENT_GIT_CLONE_RETRIES:-5}" \
          LOCAGENT_GIT_CLONE_RETRY_SLEEP="${LOCAGENT_GIT_CLONE_RETRY_SLEEP:-20}" \
        "${prep_py}" "${ROOT_DIR}/LocAgent/newtest/scripts/build_repo_structures.py" \
          --samples "${SOURCE_JSONL}" \
          --output-dir "${STRUCTURE_DIR}" \
          --repo-base-dir "${REPO_BASE_DIR:-repo_newtest_${EXP_NAME}}" \
          --dataset "newtest_${EXP_NAME}" \
          --split train \
          --skip-existing \
          --continue-on-error
  else
    echo "[data] Skip repo_structures build: ${STRUCTURE_DIR} has $(count_structures "${STRUCTURE_DIR}") files."
  fi

  if is_truthy "${DRY_RUN}"; then
    return 0
  fi

  resolve_omnigirl_full_inputs
  if ! omnigirl_full_inputs_ready; then
    require_omnigirl_full_inputs_or_explain
  fi
}

require_runtime_sources_or_explain() {
  local missing=0
  if [[ ! -f "${ROOT_DIR}/run_omnigirl_full_baselines.sh" ]]; then
    echo "ERROR: missing runner: ${ROOT_DIR}/run_omnigirl_full_baselines.sh" >&2
    missing=1
  fi
  if [[ ! -f "${ROOT_DIR}/run_omnigirl_full_baselines_parallel.sh" ]]; then
    echo "ERROR: missing runner: ${ROOT_DIR}/run_omnigirl_full_baselines_parallel.sh" >&2
    missing=1
  fi
  if baseline_enabled gala && [[ ! -f "${ROOT_DIR}/GALA/mytest/scripts/run_gala_omnigirl_js_ts_60_localization.sh" ]]; then
    echo "ERROR: missing GALA Omni runner: ${ROOT_DIR}/GALA/mytest/scripts/run_gala_omnigirl_js_ts_60_localization.sh" >&2
    echo "       Pull the latest repository. This file used to be easy to miss on servers." >&2
    missing=1
  fi
  if baseline_enabled cosil && ! grep -q "COSIL_BACKEND_MODEL" "${ROOT_DIR}/CoSIL/CoSIL/util/model.py" 2>/dev/null; then
    echo "[compat warn] CoSIL source does not contain COSIL_BACKEND_MODEL support." >&2
    echo "[compat warn] This runner will pass MODEL=${LITELLM_MODEL_NAME}, but you should pull the latest code." >&2
  fi
  if baseline_enabled graphlocator && ! grep -q "GRAPHLOCATOR_BACKEND_MODEL" "${ROOT_DIR}/GraphLocator/llms/__init__.py" 2>/dev/null; then
    echo "[compat warn] GraphLocator source does not contain GRAPHLOCATOR_BACKEND_MODEL support." >&2
    echo "[compat warn] This runner will pass MODEL=${LITELLM_MODEL_NAME}, but you should pull the latest code." >&2
  fi
  if [[ "${missing}" == "1" ]]; then
    exit 2
  fi
}

ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env.omnigirl_full}"
if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
fi

if [[ -n "${CONDA_SH:-}" && ! -f "${CONDA_SH}" ]]; then
  warn "CONDA_SH does not exist on this machine: ${CONDA_SH}"
  warn "Ignoring CONDA_SH and auto-detecting conda for the current machine."
  unset CONDA_SH
fi
CONDA_SH="${CONDA_SH:-$(detect_conda_sh || true)}"

if [[ -n "${CONDA_ENV_ROOT:-}" && ! -d "$(dirname "${CONDA_ENV_ROOT%/}")" ]]; then
  warn "CONDA_ENV_ROOT parent does not exist on this machine: $(dirname "${CONDA_ENV_ROOT%/}")"
  warn "Ignoring CONDA_ENV_ROOT and auto-detecting an env root for the current machine."
  unset CONDA_ENV_ROOT
fi
CONDA_ENV_ROOT="${CONDA_ENV_ROOT:-$(detect_conda_env_root || true)}"

BASE_URL="${BASE_URL:-}"
API_KEY="${API_KEY:-}"
MODEL_NAME="${MODEL_NAME:-}"
EXP_NAME="${EXP_NAME:-omnigirl-full-candidates}"
EXPECTED_SAMPLES="${EXPECTED_SAMPLES:-631}"
SEED="${SEED:-20260614}"
USED_LIST="${USED_LIST:-omnigirl_full_candidate_instances}"
SOURCE_JSONL_EXPLICIT=0
STRUCTURE_DIR_EXPLICIT=0
if [[ -n "${SOURCE_JSONL:-}" ]]; then
  SOURCE_JSONL_EXPLICIT=1
fi
if [[ -n "${STRUCTURE_DIR:-}" ]]; then
  STRUCTURE_DIR_EXPLICIT=1
fi
SOURCE_JSONL="${SOURCE_JSONL:-${ROOT_DIR}/MM-IR/data/omnigirl-full-candidates/samples.jsonl}"
STRUCTURE_DIR="${STRUCTURE_DIR:-${ROOT_DIR}/MM-IR/data/omnigirl-full-candidates/repo_structures}"
PARALLEL="${PARALLEL:-1}"
MAX_PARALLEL_BASELINES="${MAX_PARALLEL_BASELINES:-2}"
BASELINES="${BASELINES:-locagent cosil graphlocator gala mmir}"
BASELINE_ENVS="${BASELINE_ENVS:-${BASELINES}}"
RUN_MMIR_METHODS="${RUN_MMIR_METHODS:-bm25-mmir e5-mmir jina-code-v2-mmir codesage-large-v2-mmir coderankembed-mmir}"
HF_ENDPOINT="${HF_ENDPOINT:-}"
ALLOW_PREPARE="${ALLOW_PREPARE:-1}"
ALLOW_HF_PREPARE="${ALLOW_HF_PREPARE:-auto}"
HF_DATASET_ID="${HF_DATASET_ID:-Deep-Software-Analytics/OmniGIRL}"
HF_DATASET_API_URL="${HF_DATASET_API_URL:-https://huggingface.co/api/datasets/${HF_DATASET_ID}}"
OMNIGIRL_SOURCE_JSONL="${OMNIGIRL_SOURCE_JSONL:-}"
FORCE_PREPARE="${FORCE_PREPARE:-0}"
FORCE_STRUCTURES="${FORCE_STRUCTURES:-0}"
DENSE_DEVICE="${DENSE_DEVICE:-cuda}"
DENSE_BATCH_SIZE="${DENSE_BATCH_SIZE:-16}"
DENSE_DEVICE_AUTO_FALLBACK="${DENSE_DEVICE_AUTO_FALLBACK:-1}"
COSIL_MAX_EMPTY_RATE="${COSIL_MAX_EMPTY_RATE:-0.30}"
LLM_FAIL_FAST="${LLM_FAIL_FAST:-1}"
LLM_FAIL_FAST_PATTERNS="${LLM_FAIL_FAST_PATTERNS:-}"
SKIP_SETUP="${SKIP_SETUP:-0}"
FORCE_RECREATE_ENVS="${FORCE_RECREATE_ENVS:-0}"
NO_SMOKE_TEST="${NO_SMOKE_TEST:-0}"
DRY_RUN="${DRY_RUN:-0}"
API_PREFLIGHT="${API_PREFLIGHT:-1}"
API_PREFLIGHT_TIMEOUT="${API_PREFLIGHT_TIMEOUT:-30}"
API_NO_PROXY="${API_NO_PROXY:-1}"
API_NO_PROXY_HOSTS="${API_NO_PROXY_HOSTS:-}"
FORCE_RERUN="${FORCE_RERUN:-0}"
CLEAN_FULL="${CLEAN_FULL:-0}"
SERVER_HEARTBEAT_INTERVAL="${SERVER_HEARTBEAT_INTERVAL:-30}"
SERVER_HEARTBEAT_TAIL_LINES="${SERVER_HEARTBEAT_TAIL_LINES:-25}"
LIVE_LOGS="${LIVE_LOGS:-1}"
LIVE_LOG_LINES="${LIVE_LOG_LINES:-0}"
STATUS_INTERVAL="${STATUS_INTERVAL:-${SERVER_HEARTBEAT_INTERVAL}}"
FAIL_FAST_ON_BASELINE_FAILURE="${FAIL_FAST_ON_BASELINE_FAILURE:-1}"
LOG_DIR="${LOG_DIR:-${ROOT_DIR}/logs/server_omnigirl_full_$(date +%Y%m%d_%H%M%S)}"

resolve_omnigirl_full_inputs

if is_truthy "${ALLOW_PREPARE}" && ! omnigirl_full_inputs_ready && [[ ! " ${BASELINE_ENVS} " =~ [[:space:]]locagent[[:space:]] ]]; then
  echo "[data] Prepared OmniGIRL full inputs are incomplete; adding locagent env for data preparation."
  BASELINE_ENVS="locagent ${BASELINE_ENVS}"
fi

LLM_BASELINE_SELECTED=0
if [[ "${BASELINES}" =~ (^|[[:space:]])(locagent|cosil|graphlocator|gala)([[:space:]]|$) ]]; then
  LLM_BASELINE_SELECTED=1
fi

parse_llm_endpoints
if [[ "${LLM_BASELINE_SELECTED}" == "1" && "$(llm_endpoint_count)" -gt 0 ]]; then
  echo "[llm-endpoint] LLM_ENDPOINTS configured: $(llm_endpoint_count) endpoint(s)"
  if ! select_working_llm_endpoint_from 0; then
    echo "ERROR: no LLM endpoint passed preflight." >&2
    exit 2
  fi
fi

if [[ "${LLM_BASELINE_SELECTED}" == "1" ]]; then
  require_nonempty "BASE_URL" "${BASE_URL}"
  require_nonempty "API_KEY" "${API_KEY}"
  require_nonempty "MODEL_NAME" "${MODEL_NAME}"
else
  BASE_URL="${BASE_URL:-dummy}"
  API_KEY="${API_KEY:-dummy}"
  MODEL_NAME="${MODEL_NAME:-dummy}"
fi

LITELLM_MODEL_NAME="${LITELLM_MODEL_NAME:-${MODEL_NAME}}"
if [[ "${LITELLM_MODEL_NAME}" != */* ]]; then
  LITELLM_MODEL_NAME="openai/${LITELLM_MODEL_NAME}"
fi

API_NO_PROXY_VALUE="${NO_PROXY:-${no_proxy:-}}"
if [[ "${LLM_BASELINE_SELECTED}" == "1" ]] && is_truthy "${API_NO_PROXY}"; then
  API_NO_PROXY_VALUE="$(build_api_no_proxy)"
fi

refresh_run_model_name() {
  RUN_MODEL_NAME="${MODEL_NAME}"
  if baseline_enabled cosil && ! grep -q "COSIL_BACKEND_MODEL" "${ROOT_DIR}/CoSIL/CoSIL/util/model.py" 2>/dev/null; then
    echo "[compat warn] CoSIL does not support COSIL_BACKEND_MODEL yet; using MODEL=${LITELLM_MODEL_NAME} for this run." >&2
    RUN_MODEL_NAME="${LITELLM_MODEL_NAME}"
  fi
  if baseline_enabled graphlocator && ! grep -q "GRAPHLOCATOR_BACKEND_MODEL" "${ROOT_DIR}/GraphLocator/llms/__init__.py" 2>/dev/null; then
    echo "[compat warn] GraphLocator does not support GRAPHLOCATOR_BACKEND_MODEL yet; using MODEL=${LITELLM_MODEL_NAME} for this run." >&2
    RUN_MODEL_NAME="${LITELLM_MODEL_NAME}"
  fi
}

refresh_run_model_name

mkdir -p "${LOG_DIR}" "${ROOT_DIR}/logs"

cat <<EOF
OmniGIRL full-candidates server runner
Root: ${ROOT_DIR}
Conda sh: ${CONDA_SH}
Conda env root: ${CONDA_ENV_ROOT}
Experiment: ${EXP_NAME}
Expected samples: ${EXPECTED_SAMPLES}
Source samples: ${SOURCE_JSONL} ($(count_jsonl_rows "${SOURCE_JSONL}") rows)
Structure dir: ${STRUCTURE_DIR} ($(count_structures "${STRUCTURE_DIR}") files)
Base URL: ${BASE_URL}
Model: ${MODEL_NAME}
Run model: ${RUN_MODEL_NAME}
LiteLLM backend model: ${LITELLM_MODEL_NAME}
Dense device: ${DENSE_DEVICE}
Dense batch size: ${DENSE_BATCH_SIZE}
Dense CUDA auto fallback: ${DENSE_DEVICE_AUTO_FALLBACK}
Parallel mode: ${PARALLEL}
Max parallel baselines: ${MAX_PARALLEL_BASELINES}
Baseline envs: ${BASELINE_ENVS}
Baselines to run: ${BASELINES}
MM-IR methods: ${RUN_MMIR_METHODS}
HF endpoint: ${HF_ENDPOINT:-<default>}
Allow prepare: ${ALLOW_PREPARE}
Allow HF prepare: ${ALLOW_HF_PREPARE}
HF dataset endpoint: ${HF_DATASET_API_URL}
Local Omni source: $(resolve_local_omni_full_source || true)
Force prepare: ${FORCE_PREPARE}
Force structures: ${FORCE_STRUCTURES}
CoSIL max empty rate: ${COSIL_MAX_EMPTY_RATE}
LLM fail fast: ${LLM_FAIL_FAST}
API preflight: ${API_PREFLIGHT}
API no-proxy for LLM: ${API_NO_PROXY_VALUE:-<none>} (enabled=${API_NO_PROXY})
Skip setup: ${SKIP_SETUP}
Force recreate envs: ${FORCE_RECREATE_ENVS}
Force rerun: ${FORCE_RERUN}
Clean full outputs: ${CLEAN_FULL}
Dry run: ${DRY_RUN}
Heartbeat interval: ${SERVER_HEARTBEAT_INTERVAL}s
Heartbeat tail lines: ${SERVER_HEARTBEAT_TAIL_LINES}
Inner live logs: ${LIVE_LOGS}
Inner status interval: ${STATUS_INTERVAL}s
Fail fast on baseline failure: ${FAIL_FAST_ON_BASELINE_FAILURE}
Log dir: ${LOG_DIR}
EOF

if [[ ! -f "${CONDA_SH}" ]]; then
  echo "ERROR: CONDA_SH does not exist: ${CONDA_SH}" >&2
  echo "Set CONDA_SH=/path/to/miniconda3/etc/profile.d/conda.sh" >&2
  exit 2
fi

require_runtime_sources_or_explain

if is_truthy "${API_PREFLIGHT}" && [[ "${BASELINES}" =~ (^|[[:space:]])(locagent|cosil|graphlocator|gala)([[:space:]]|$) ]]; then
  echo
  echo "========== API preflight =========="
  echo "+ ${PYTHON:-python3} ${ROOT_DIR}/scripts/check_openai_compatible_api.py --base-url ${BASE_URL} --api-key <hidden> --model ${LITELLM_MODEL_NAME#openai/} --timeout ${API_PREFLIGHT_TIMEOUT}"
  if ! is_truthy "${DRY_RUN}"; then
    NO_PROXY="${API_NO_PROXY_VALUE}" no_proxy="${API_NO_PROXY_VALUE}" \
    "${PYTHON:-python3}" "${ROOT_DIR}/scripts/check_openai_compatible_api.py" \
      --base-url "${BASE_URL}" \
      --api-key "${API_KEY}" \
      --model "${LITELLM_MODEL_NAME#openai/}" \
      --timeout "${API_PREFLIGHT_TIMEOUT}"
  fi
fi

if ! is_truthy "${SKIP_SETUP}"; then
  for env_name in ${BASELINE_ENVS}; do
    if is_truthy "${FORCE_RECREATE_ENVS}" || env_needs_setup "${env_name}"; then
      echo "[setup] ${env_name} needs setup/recreate."
      setup_env "${env_name}"
    else
      echo "[setup] ${env_name} exists: $(env_python "${env_name}")"
    fi
  done
else
  echo "[setup] skipped because SKIP_SETUP=${SKIP_SETUP}"
fi

echo
echo "========== Verify baseline Python interpreters =========="
for env_name in ${BASELINE_ENVS}; do
  check_python_or_die "${env_name}"
done

echo
echo "========== Prepare/verify OmniGIRL full-candidates inputs =========="
prepare_omnigirl_full_inputs
echo "[data] Final source samples: ${SOURCE_JSONL} ($(count_jsonl_rows "${SOURCE_JSONL}") rows)"
echo "[data] Final structure dir: ${STRUCTURE_DIR} ($(count_structures "${STRUCTURE_DIR}") files)"

RUN_SCRIPT="${ROOT_DIR}/run_omnigirl_full_baselines.sh"
if is_truthy "${PARALLEL}"; then
  RUN_SCRIPT="${ROOT_DIR}/run_omnigirl_full_baselines_parallel.sh"
fi

run_omnigirl_full_once() {
  refresh_run_model_name
  echo "[llm-endpoint] running with base=${BASE_URL} model=${MODEL_NAME} key=$(redact_api_key "${API_KEY}")"
  run_logged "run_omnigirl_full" \
    env \
      NO_PROXY="${API_NO_PROXY_VALUE}" \
      no_proxy="${API_NO_PROXY_VALUE}" \
      CONDA_ENV_ROOT="${CONDA_ENV_ROOT}" \
      EXP_NAME="${EXP_NAME}" \
      SOURCE_JSONL="${SOURCE_JSONL}" \
      STRUCTURE_DIR="${STRUCTURE_DIR}" \
      COSIL_STRUCTURE_DIR="${COSIL_STRUCTURE_DIR}" \
      SAMPLE_SIZE="$(count_jsonl_rows "${SOURCE_JSONL}")" \
      SEED="${SEED}" \
      USED_LIST="${USED_LIST}" \
      BASELINES="${BASELINES}" \
      RUN_LOCAGENT="$(baseline_enabled locagent && echo 1 || echo 0)" \
      RUN_COSIL="$(baseline_enabled cosil && echo 1 || echo 0)" \
      RUN_GRAPHLOCATOR="$(baseline_enabled graphlocator && echo 1 || echo 0)" \
      RUN_GALA="$(baseline_enabled gala && echo 1 || echo 0)" \
      RUN_MMIR="$(baseline_enabled mmir && echo 1 || echo 0)" \
      RUN_MMIR_METHODS="${RUN_MMIR_METHODS}" \
      COSIL_MAX_EMPTY_RATE="${COSIL_MAX_EMPTY_RATE}" \
      LLM_FAIL_FAST="${LLM_FAIL_FAST}" \
      LLM_FAIL_FAST_PATTERNS="${LLM_FAIL_FAST_PATTERNS}" \
      API_PREFLIGHT=0 \
      HF_ENDPOINT="${HF_ENDPOINT}" \
      OPENAI_API_BASE="${BASE_URL}" \
      OPENAI_API_KEY="${API_KEY}" \
      MODEL="${RUN_MODEL_NAME}" \
      LITELLM_MODEL="${LITELLM_MODEL_NAME}" \
      LOCAGENT_BACKEND_MODEL="${LITELLM_MODEL_NAME}" \
      COSIL_BACKEND_MODEL="${LITELLM_MODEL_NAME}" \
      GRAPHLOCATOR_BACKEND_MODEL="${LITELLM_MODEL_NAME}" \
      VLM_MODEL="${MODEL_NAME}" \
      TEXT_MODEL_NAME="${MODEL_NAME}" \
      MULADAPTER_MODEL="${MODEL_NAME}" \
      MULADAPTER_BASE_URL="${BASE_URL}" \
      MULADAPTER_API_KEY="${API_KEY}" \
      VLM_BASE_URL="${BASE_URL}" \
      VLM_API_KEY="${API_KEY}" \
      TEXT_BASE_URL="${BASE_URL}" \
      TEXT_API_KEY="${API_KEY}" \
      DENSE_DEVICE="${DENSE_DEVICE}" \
      DENSE_BATCH_SIZE="${DENSE_BATCH_SIZE}" \
      DENSE_DEVICE_AUTO_FALLBACK="${DENSE_DEVICE_AUTO_FALLBACK}" \
      FORCE_RERUN="${FORCE_RERUN}" \
      CLEAN_FULL="${CLEAN_FULL}" \
      MAX_PARALLEL_BASELINES="${MAX_PARALLEL_BASELINES}" \
      LIVE_LOGS="${LIVE_LOGS}" \
      LIVE_LOG_LINES="${LIVE_LOG_LINES}" \
      STATUS_INTERVAL="${STATUS_INTERVAL}" \
      FAIL_FAST_ON_BASELINE_FAILURE="${FAIL_FAST_ON_BASELINE_FAILURE}" \
      DRY_RUN="${DRY_RUN}" \
      bash "${RUN_SCRIPT}"
}

run_status=0
while true; do
  set +e
  run_omnigirl_full_once
  run_status=$?
  set -e
  if [[ "${run_status}" == "0" ]]; then
    break
  fi

  if [[ "$(llm_endpoint_count)" -le 0 ]]; then
    exit "${run_status}"
  fi
  if ! quota_or_auth_failure_in_logs "${LOG_DIR}"; then
    echo "[llm-endpoint] run failed, but no quota/auth failure was detected in ${LOG_DIR}; not switching endpoint." >&2
    exit "${run_status}"
  fi

  next_idx=$((SELECTED_LLM_ENDPOINT_INDEX + 1))
  echo "[llm-endpoint] detected quota/auth failure in logs; trying next endpoint from index ${next_idx}."
  if ! select_working_llm_endpoint_from "${next_idx}"; then
    echo "[llm-endpoint] no remaining endpoint passed preflight after quota/auth failure." >&2
    exit "${run_status}"
  fi
  refresh_run_model_name
  echo "[llm-endpoint] rerunning failed supervisor with ${LLM_ENDPOINT_NAMES[$SELECTED_LLM_ENDPOINT_INDEX]}."
done

echo
echo "Done."
echo "Logs: ${LOG_DIR}"
