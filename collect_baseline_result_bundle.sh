#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${OUTPUT_DIR:-${ROOT_DIR}/result_archives}"
PACKAGE_NAME="${PACKAGE_NAME:-baseline_results_$(hostname -s 2>/dev/null || echo host)_$(date +%Y%m%d_%H%M%S)}"
INCLUDE_LARGE=0
DRY_RUN=0
REDACT=1
GIT_COMMIT=0
GIT_PUSH=0
GIT_REMOTE="${GIT_REMOTE:-origin}"
GIT_BRANCH="${GIT_BRANCH:-}"
GIT_MESSAGE="${GIT_MESSAGE:-Add baseline result bundle ${PACKAGE_NAME}}"
declare -a MATCH_PATTERNS=()

usage() {
  cat <<'EOF'
Usage:
  bash collect_baseline_result_bundle.sh [options]

Packages baseline outputs, trajectories, metrics, and run logs into a tar.gz.
By default it creates a compact bundle with common result artifacts only.

Options:
  --name NAME          Package/archive name without .tar.gz
  --output-dir DIR     Archive output directory (default: ./result_archives)
  --include-large      Include full result trees under */results (can be large)
  --match TEXT         Keep only paths containing TEXT. Can be repeated (OR match)
  --no-redact          Do not redact API keys/tokens from copied text files
  --dry-run            Print what would be packaged, do not create archive
  --git-commit         git add -f and commit the archive + manifest
  --git-push           Push after committing. Implies --git-commit
  --remote NAME        Git remote for push (default: origin)
  --branch NAME        Git branch for push (default: current branch)
  -h, --help           Show this help

Examples:
  bash collect_baseline_result_bundle.sh
  bash collect_baseline_result_bundle.sh --name swe60_qwen40 --match swebench_multimodal-60
  bash collect_baseline_result_bundle.sh --include-large --git-commit --git-push
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --name)
      PACKAGE_NAME="$2"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR="$2"
      shift 2
      ;;
    --include-large)
      INCLUDE_LARGE=1
      shift
      ;;
    --match)
      MATCH_PATTERNS+=("$2")
      shift 2
      ;;
    --no-redact)
      REDACT=0
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --git-commit)
      GIT_COMMIT=1
      shift
      ;;
    --git-push)
      GIT_PUSH=1
      GIT_COMMIT=1
      shift
      ;;
    --remote)
      GIT_REMOTE="$2"
      shift 2
      ;;
    --branch)
      GIT_BRANCH="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

LIST_FILE="$(mktemp)"
trap 'rm -f "${LIST_FILE}"' EXIT

add_if_file() {
  local rel="$1"
  [[ -f "${ROOT_DIR}/${rel}" ]] && printf '%s\n' "$rel" >>"${LIST_FILE}"
}

find_compact_results() {
  local root="$1"
  [[ -d "${ROOT_DIR}/${root}" ]] || return 0
  find "${ROOT_DIR}/${root}" -type f \
    \( \
      -name 'loc_results.json' -o \
      -name 'loc_outputs.jsonl' -o \
      -name 'loc_trajs.jsonl' -o \
      -name 'metrics_3level.md' -o \
      -name 'metrics_3level.json' -o \
      -name '*traj*.json' -o \
      -name '*traj*.jsonl' -o \
      -name '*trajectory*.json' -o \
      -name '*trajectory*.jsonl' -o \
      -name '*summary*.json' -o \
      -name '*summary*.md' \
    \) \
    ! -path '*/data/*' \
    ! -path '*/repo_structures/*' \
    ! -path '*/repo_playground/*' \
    ! -path '*/repo_work/*' \
    ! -path '*/repos/*' \
    ! -path '*/repo_cache/*' \
    ! -path '*/__pycache__/*' \
    | sed "s#^${ROOT_DIR}/##" >>"${LIST_FILE}"
}

find_large_results() {
  local root="$1"
  [[ -d "${ROOT_DIR}/${root}" ]] || return 0
  find "${ROOT_DIR}/${root}" -type f \
    ! -path '*/data/*' \
    ! -path '*/repo_structures/*' \
    ! -path '*/repo_playground/*' \
    ! -path '*/repo_work/*' \
    ! -path '*/repos/*' \
    ! -path '*/repo_cache/*' \
    ! -path '*/node_modules/*' \
    ! -path '*/__pycache__/*' \
    ! -name '*.safetensors' \
    ! -name '*.bin' \
    ! -name '*.pt' \
    ! -name '*.pth' \
    ! -name '*.ckpt' \
    ! -name '*.onnx' \
    ! -name '*.gguf' \
    | sed "s#^${ROOT_DIR}/##" >>"${LIST_FILE}"
}

find_logs() {
  local root="$1"
  [[ -d "${ROOT_DIR}/${root}" ]] || return 0
  find "${ROOT_DIR}/${root}" -type f \
    ! -path '*/__pycache__/*' \
    | sed "s#^${ROOT_DIR}/##" >>"${LIST_FILE}"
}

collect_file_list() {
  add_if_file "EXPERIMENT_BASELINE_SUMMARY.md"
  add_if_file "EXPERIMENT_60_BASELINE_SUMMARY.md"
  add_if_file "SYMPTOM_MECHANISM_GRAPH_DESIGN.md"

  find "${ROOT_DIR}" -maxdepth 1 -type f \
    \( -name 'run_*.sh' -o -name 'server_*.sh' -o -name 'setup_*.sh' -o -name 'package_*.sh' -o -name 'collect_*.sh' \) \
    | sed "s#^${ROOT_DIR}/##" >>"${LIST_FILE}"

  if [[ "${INCLUDE_LARGE}" == "1" ]]; then
    find_large_results "LocAgent/newtest"
    find_large_results "CoSIL/newtest"
    find_large_results "GraphLocator/newtest"
    find_large_results "GALA/mytest"
    find_large_results "MM-IR/results"
  else
    find_compact_results "LocAgent/newtest"
    find_compact_results "CoSIL/newtest"
    find_compact_results "GraphLocator/newtest"
    find_compact_results "GALA/mytest"
    find_compact_results "MM-IR/results"
  fi

  find_logs "baseline_run_logs"
  find_logs "logs"

  sort -u "${LIST_FILE}" -o "${LIST_FILE}"

  if [[ "${#MATCH_PATTERNS[@]}" -gt 0 ]]; then
    local filtered
    filtered="$(mktemp)"
    : >"${filtered}"
    local pat
    for pat in "${MATCH_PATTERNS[@]}"; do
      grep -F "${pat}" "${LIST_FILE}" >>"${filtered}" || true
    done
    sort -u "${filtered}" -o "${LIST_FILE}"
    rm -f "${filtered}"
  fi
}

redact_text_files() {
  local stage="$1"
  [[ "${REDACT}" == "1" ]] || return 0
  find "${stage}" -type f \
    \( -name '*.log' -o -name '*.txt' -o -name '*.md' -o -name '*.json' -o -name '*.jsonl' -o -name '*.sh' -o -name '*.env' \) \
    -size -50M -print0 \
    | xargs -0 -r perl -pi -e '
      s/(OPENAI_API_KEY|API_KEY|VLM_API_KEY|TEXT_API_KEY|MULADAPTER_API_KEY)(["'\'']?\s*[:=]\s*["'\'']?)[^"'\''\s,;]+/$1$2<REDACTED>/g;
      s/\b(sk-[A-Za-z0-9_\-]{16,})\b/<REDACTED_API_KEY>/g;
      s/\b(tp-[A-Za-z0-9_\-]{16,})\b/<REDACTED_API_KEY>/g;
    '
}

write_manifest() {
  local manifest="$1"
  local archive_rel="$2"
  {
    echo "Package: ${PACKAGE_NAME}"
    echo "Created at: $(date -Is)"
    echo "Host: $(hostname -f 2>/dev/null || hostname)"
    echo "Root: ${ROOT_DIR}"
    echo "Mode: $([[ "${INCLUDE_LARGE}" == "1" ]] && echo include-large || echo compact)"
    echo "Redacted: ${REDACT}"
    echo "Archive: ${archive_rel}"
    echo
    if git -C "${ROOT_DIR}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
      echo "Git commit: $(git -C "${ROOT_DIR}" rev-parse HEAD 2>/dev/null || true)"
      echo "Git branch: $(git -C "${ROOT_DIR}" rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
      echo
      echo "Git status:"
      git -C "${ROOT_DIR}" status --short || true
      echo
    fi
    echo "Packaged files: $(wc -l <"${LIST_FILE}")"
    echo
    echo "File list:"
    sed 's#^#  #' "${LIST_FILE}"
  } >"${manifest}"
}

collect_file_list

FILE_COUNT="$(wc -l <"${LIST_FILE}")"
echo "Root: ${ROOT_DIR}"
echo "Package name: ${PACKAGE_NAME}"
echo "Output dir: ${OUTPUT_DIR}"
echo "Mode: $([[ "${INCLUDE_LARGE}" == "1" ]] && echo include-large || echo compact)"
echo "Files selected: ${FILE_COUNT}"

if [[ "${FILE_COUNT}" == "0" ]]; then
  echo "No files matched. Nothing to package." >&2
  exit 1
fi

echo
echo "First selected files:"
sed -n '1,30p' "${LIST_FILE}" | sed 's#^#  #'
if [[ "${FILE_COUNT}" -gt 30 ]]; then
  echo "  ..."
fi

if [[ "${DRY_RUN}" == "1" ]]; then
  echo
  echo "Dry run only. No archive created."
  exit 0
fi

mkdir -p "${OUTPUT_DIR}"
TMP_ROOT="$(mktemp -d)"
trap 'rm -rf "${TMP_ROOT}"; rm -f "${LIST_FILE}"' EXIT
STAGE_DIR="${TMP_ROOT}/${PACKAGE_NAME}"
mkdir -p "${STAGE_DIR}/repo"

while IFS= read -r rel; do
  mkdir -p "${STAGE_DIR}/repo/$(dirname "${rel}")"
  cp -p "${ROOT_DIR}/${rel}" "${STAGE_DIR}/repo/${rel}" 2>/dev/null || true
done <"${LIST_FILE}"

MANIFEST_IN_STAGE="${STAGE_DIR}/MANIFEST.txt"
ARCHIVE_PATH="${OUTPUT_DIR}/${PACKAGE_NAME}.tar.gz"
MANIFEST_PATH="${OUTPUT_DIR}/${PACKAGE_NAME}.manifest.txt"
write_manifest "${MANIFEST_IN_STAGE}" "${ARCHIVE_PATH}"

redact_text_files "${STAGE_DIR}"
cp -p "${MANIFEST_IN_STAGE}" "${MANIFEST_PATH}"

tar -C "${TMP_ROOT}" -czf "${ARCHIVE_PATH}" "${PACKAGE_NAME}"

echo
echo "Created:"
du -h "${ARCHIVE_PATH}" "${MANIFEST_PATH}"
echo "Archive: ${ARCHIVE_PATH}"
echo "Manifest: ${MANIFEST_PATH}"

if [[ "${GIT_COMMIT}" == "1" ]]; then
  if ! git -C "${ROOT_DIR}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "ERROR: ${ROOT_DIR} is not a git worktree; cannot commit." >&2
    exit 1
  fi
  git -C "${ROOT_DIR}" add -f "${ARCHIVE_PATH}" "${MANIFEST_PATH}"
  if git -C "${ROOT_DIR}" diff --cached --quiet; then
    echo "No staged changes to commit."
  else
    git -C "${ROOT_DIR}" commit -m "${GIT_MESSAGE}"
  fi
fi

if [[ "${GIT_PUSH}" == "1" ]]; then
  if [[ -z "${GIT_BRANCH}" ]]; then
    GIT_BRANCH="$(git -C "${ROOT_DIR}" rev-parse --abbrev-ref HEAD)"
  fi
  git -C "${ROOT_DIR}" push "${GIT_REMOTE}" "${GIT_BRANCH}"
fi
