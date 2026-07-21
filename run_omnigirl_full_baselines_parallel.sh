#!/usr/bin/env bash
set -euo pipefail

# Baseline-level parallel runner for OmniGIRL full-candidates.
#
# It starts one background job per baseline while keeping each baseline
# internally single-sample/single-worker by default. It delegates real work to
# run_omnigirl_full_baselines.sh, so resume and eval-only recovery stay there.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAIN_SCRIPT="${ROOT_DIR}/run_omnigirl_full_baselines.sh"

BASELINES="${BASELINES:-locagent cosil graphlocator gala mmir}"
MAX_PARALLEL_BASELINES="${MAX_PARALLEL_BASELINES:-2}"
LOG_DIR="${LOG_DIR:-${ROOT_DIR}/baseline_run_logs/omnigirl_full_parallel_$(date +%Y%m%d_%H%M%S)}"
DRY_RUN="${DRY_RUN:-0}"
LIVE_LOGS="${LIVE_LOGS:-1}"
LIVE_LOG_LINES="${LIVE_LOG_LINES:-0}"
STATUS_INTERVAL="${STATUS_INTERVAL:-30}"
FAIL_FAST_ON_BASELINE_FAILURE="${FAIL_FAST_ON_BASELINE_FAILURE:-1}"
LAST_STATUS_TS=0

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
Parallel OmniGIRL full-candidates baseline run
Root: ${ROOT_DIR}
Main script: ${MAIN_SCRIPT}
Baselines: ${BASELINES}
Max parallel baselines: ${MAX_PARALLEL_BASELINES}
Log dir: ${LOG_DIR}
Dry run: ${DRY_RUN}
Live logs: ${LIVE_LOGS}
Status interval: ${STATUS_INTERVAL}s
Fail fast on baseline failure: ${FAIL_FAST_ON_BASELINE_FAILURE}
EOF

echo
echo "========== Validate shared Omni full-candidates inputs =========="
run_or_echo env \
  RUN_LOCAGENT=0 \
  RUN_COSIL=0 \
  RUN_GRAPHLOCATOR=0 \
  RUN_GALA=0 \
  RUN_MMIR=0 \
  "${MAIN_SCRIPT}"

declare -a PIDS=()
declare -a TAIL_PIDS=()
declare -A PID_TO_NAME=()
declare -A PID_TO_STATUS_FILE=()
FAILED=0

cleanup_tails() {
  local tail_pid
  for tail_pid in "${TAIL_PIDS[@]}"; do
    kill "${tail_pid}" >/dev/null 2>&1 || true
  done
}

terminate_active_jobs() {
  local pid name
  for pid in "${PIDS[@]}"; do
    if [[ ! -f "${PID_TO_STATUS_FILE[${pid}]}" ]]; then
      name="${PID_TO_NAME[${pid}]:-${pid}}"
      echo "[stop] terminating active baseline job ${name} pid=${pid}" >&2
      kill "${pid}" >/dev/null 2>&1 || true
    fi
  done
}

trap cleanup_tails EXIT INT TERM

active_jobs() {
  local count=0
  local pid
  for pid in "${PIDS[@]}"; do
    if [[ ! -f "${PID_TO_STATUS_FILE[${pid}]}" ]]; then
      count=$((count + 1))
    fi
  done
  echo "${count}"
}

compact_jobs() {
  local -a new_pids=()
  local pid status_file status name
  for pid in "${PIDS[@]}"; do
    status_file="${PID_TO_STATUS_FILE[${pid}]}"
    name="${PID_TO_NAME[${pid}]:-${pid}}"
    if [[ -f "${status_file}" ]]; then
      status="$(cat "${status_file}" 2>/dev/null || echo 1)"
      if [[ "${status}" == "0" ]]; then
        echo "[done] ${name}"
      else
        echo "[failed] ${name} exited with status ${status}; see ${LOG_DIR}/${name}.log" >&2
        FAILED=1
      fi
    else
      new_pids+=("${pid}")
    fi
  done
  PIDS=("${new_pids[@]}")
}

print_running_status() {
  if ! [[ "${STATUS_INTERVAL}" =~ ^[0-9]+$ ]] || [[ "${STATUS_INTERVAL}" -le 0 ]]; then
    return 0
  fi
  local now
  now="$(date +%s)"
  if [[ $((now - LAST_STATUS_TS)) -lt "${STATUS_INTERVAL}" ]]; then
    return 0
  fi
  LAST_STATUS_TS="${now}"
  if [[ "${#PIDS[@]}" -eq 0 ]]; then
    return 0
  fi
  echo "[status] active baseline jobs:"
  local pid name
  for pid in "${PIDS[@]}"; do
    if [[ ! -f "${PID_TO_STATUS_FILE[${pid}]}" ]]; then
      name="${PID_TO_NAME[${pid}]:-${pid}}"
      echo "[status]   ${name}: pid=${pid}, log=${LOG_DIR}/${name}.log"
    fi
  done
}

wait_for_slot() {
  while [[ "$(active_jobs)" -ge "${MAX_PARALLEL_BASELINES}" ]]; do
    sleep 5
    compact_jobs
    if [[ "${FAILED}" != "0" ]] && is_truthy "${FAIL_FAST_ON_BASELINE_FAILURE}"; then
      terminate_active_jobs
      return 1
    fi
    print_running_status
  done
}

launch_job() {
  local name="$1"
  shift
  local logfile="${LOG_DIR}/${name}.log"
  local statusfile="${LOG_DIR}/${name}.status"
  rm -f "${statusfile}"
  echo
  echo "========== Launch ${name} =========="
  echo "[log] ${logfile}"
  echo "[status] ${statusfile}"
  echo "[watch] tail -f ${logfile}"
  echo "+ env $* ${MAIN_SCRIPT}"
  if is_truthy "${DRY_RUN}"; then
    return 0
  fi
  (
    set +e
    env "$@" "${MAIN_SCRIPT}"
    status=$?
    echo "${status}" >"${statusfile}"
    exit "${status}"
  ) >"${logfile}" 2>&1 &
  local pid=$!
  PIDS+=("${pid}")
  PID_TO_NAME["${pid}"]="${name}"
  PID_TO_STATUS_FILE["${pid}"]="${statusfile}"
  echo "[pid] ${pid}"
  if is_truthy "${LIVE_LOGS}"; then
    (
      tail -n "${LIVE_LOG_LINES}" -F "${logfile}" 2>/dev/null | sed -u "s/^/[${name}] /"
    ) &
    local tail_pid=$!
    TAIL_PIDS+=("${tail_pid}")
    echo "[live-log-pid] ${tail_pid}"
  fi
}

for baseline in ${BASELINES}; do
  if ! wait_for_slot; then
    break
  fi
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
while [[ "${#PIDS[@]}" -gt 0 ]]; do
  sleep 5
  compact_jobs
  if [[ "${FAILED}" != "0" ]] && is_truthy "${FAIL_FAST_ON_BASELINE_FAILURE}"; then
    terminate_active_jobs
    cleanup_tails
    break
  fi
  print_running_status
done

cleanup_tails
echo
echo "Logs: ${LOG_DIR}"
if [[ "${FAILED}" == "0" ]]; then
  echo "All requested baseline jobs finished successfully or were skipped by the main runner."
else
  echo "Some baseline jobs failed. You can rerun this supervisor; completed jobs will be skipped/resumed." >&2
fi
exit "${FAILED}"
