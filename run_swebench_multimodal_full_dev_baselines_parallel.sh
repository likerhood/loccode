#!/usr/bin/env bash
set -euo pipefail

# Baseline-level parallel runner for the full SWE-bench Multimodal dev split.
#
# This supervisor script starts one background job per baseline while keeping
# each baseline internally single-sample/single-worker by default. It delegates
# real work to run_swebench_multimodal_full_dev_baselines.sh, so all resume,
# strict/relaxed eval, model/API, and output-directory logic stays in one place.
#
# Common server usage:
#   cd /path/to/locCode
#   nohup bash run_swebench_multimodal_full_dev_baselines_parallel.sh \
#     > logs/swe_full_dev_parallel_supervisor.log 2>&1 &
#
# Useful switches:
#   MAX_PARALLEL_BASELINES=3 bash run_swebench_multimodal_full_dev_baselines_parallel.sh
#   BASELINES="locagent cosil gala mmir" bash run_swebench_multimodal_full_dev_baselines_parallel.sh
#   DRY_RUN=1 bash run_swebench_multimodal_full_dev_baselines_parallel.sh

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAIN_SCRIPT="${ROOT_DIR}/run_swebench_multimodal_full_dev_baselines.sh"

BASELINES="${BASELINES:-locagent cosil graphlocator gala mmir}"
MAX_PARALLEL_BASELINES="${MAX_PARALLEL_BASELINES:-2}"
LOG_DIR="${LOG_DIR:-${ROOT_DIR}/baseline_run_logs/swebench_multimodal_full_dev_parallel_$(date +%Y%m%d_%H%M%S)}"
DRY_RUN="${DRY_RUN:-0}"

is_truthy() {
  [[ "${1:-}" == "1" || "${1:-}" == "true" || "${1:-}" == "yes" ]]
}

run_or_echo() {
  echo "+ $*"
  if ! is_truthy "${DRY_RUN}"; then
    "$@"
  fi
}

if [[ ! -x "${MAIN_SCRIPT}" ]]; then
  echo "ERROR: main runner not found or not executable: ${MAIN_SCRIPT}" >&2
  exit 2
fi

if ! [[ "${MAX_PARALLEL_BASELINES}" =~ ^[0-9]+$ ]] || [[ "${MAX_PARALLEL_BASELINES}" -lt 1 ]]; then
  echo "ERROR: MAX_PARALLEL_BASELINES must be a positive integer." >&2
  exit 2
fi

mkdir -p "${LOG_DIR}"

cat <<EOF
Parallel SWE-bench Multimodal full-dev baseline run
Root: ${ROOT_DIR}
Main script: ${MAIN_SCRIPT}
Baselines: ${BASELINES}
Max parallel baselines: ${MAX_PARALLEL_BASELINES}
Log dir: ${LOG_DIR}
Dry run: ${DRY_RUN}
EOF

echo
echo "========== Prepare shared samples and repo_structures =========="
run_or_echo env \
  RUN_LOCAGENT=0 \
  RUN_COSIL=0 \
  RUN_GRAPHLOCATOR=0 \
  RUN_GALA=0 \
  RUN_MMIR=0 \
  "${MAIN_SCRIPT}"

declare -a PIDS=()
declare -a JOB_NAMES=()
declare -A PID_TO_NAME=()

active_jobs() {
  local count=0
  local pid
  for pid in "${PIDS[@]:-}"; do
    if kill -0 "${pid}" >/dev/null 2>&1; then
      count=$((count + 1))
    fi
  done
  echo "${count}"
}

compact_jobs() {
  local -a new_pids=()
  local pid
  for pid in "${PIDS[@]:-}"; do
    if kill -0 "${pid}" >/dev/null 2>&1; then
      new_pids+=("${pid}")
    fi
  done
  PIDS=("${new_pids[@]:-}")
}

wait_for_slot() {
  while [[ "$(active_jobs)" -ge "${MAX_PARALLEL_BASELINES}" ]]; do
    if wait -n; then
      compact_jobs
    else
      local status=$?
      compact_jobs
      return "${status}"
    fi
  done
}

launch_job() {
  local name="$1"
  shift
  local logfile="${LOG_DIR}/${name}.log"
  echo
  echo "========== Launch ${name} =========="
  echo "[log] ${logfile}"
  echo "+ env $* ${MAIN_SCRIPT}"
  if is_truthy "${DRY_RUN}"; then
    return 0
  fi
  (
    set -euo pipefail
    env "$@" "${MAIN_SCRIPT}"
  ) >"${logfile}" 2>&1 &
  local pid=$!
  PIDS+=("${pid}")
  JOB_NAMES+=("${name}")
  PID_TO_NAME["${pid}"]="${name}"
  echo "[pid] ${pid}"
}

for baseline in ${BASELINES}; do
  wait_for_slot
  case "${baseline}" in
    locagent)
      launch_job "locagent" \
        RUN_LOCAGENT=1 RUN_COSIL=0 RUN_GRAPHLOCATOR=0 RUN_GALA=0 RUN_MMIR=0 \
        LOCAGENT_NUM_PROCESSES="${LOCAGENT_NUM_PROCESSES:-1}" \
        LOCAGENT_NUM_SAMPLES="${LOCAGENT_NUM_SAMPLES:-1}"
      ;;
    cosil)
      launch_job "cosil" \
        RUN_LOCAGENT=0 RUN_COSIL=1 RUN_GRAPHLOCATOR=0 RUN_GALA=0 RUN_MMIR=0 \
        NUM_THREADS="${NUM_THREADS:-1}"
      ;;
    graphlocator)
      launch_job "graphlocator" \
        RUN_LOCAGENT=0 RUN_COSIL=0 RUN_GRAPHLOCATOR=1 RUN_GALA=0 RUN_MMIR=0
      ;;
    gala)
      launch_job "gala" \
        RUN_LOCAGENT=0 RUN_COSIL=0 RUN_GRAPHLOCATOR=0 RUN_GALA=1 RUN_MMIR=0 \
        MAX_WORKERS="${MAX_WORKERS:-1}"
      ;;
    mmir)
      launch_job "mmir" \
        RUN_LOCAGENT=0 RUN_COSIL=0 RUN_GRAPHLOCATOR=0 RUN_GALA=0 RUN_MMIR=1
      ;;
    *)
      echo "ERROR: unknown baseline '${baseline}'. Valid: locagent cosil graphlocator gala mmir" >&2
      exit 2
      ;;
  esac
done

if is_truthy "${DRY_RUN}"; then
  echo
  echo "Dry run complete."
  exit 0
fi

echo
echo "========== Waiting for baseline jobs =========="
FAILED=0
for pid in "${PIDS[@]:-}"; do
  name="${PID_TO_NAME[${pid}]:-${pid}}"
  if wait "${pid}"; then
    echo "[done] ${name}"
  else
    status=$?
    echo "[failed] ${name} exited with status ${status}; see ${LOG_DIR}/${name}.log" >&2
    FAILED=1
  fi
done

echo
echo "Logs: ${LOG_DIR}"
if [[ "${FAILED}" == "0" ]]; then
  echo "All requested baseline jobs finished successfully or were skipped by the main runner."
else
  echo "Some baseline jobs failed. You can rerun this supervisor; completed jobs will be skipped/resumed." >&2
fi
exit "${FAILED}"
