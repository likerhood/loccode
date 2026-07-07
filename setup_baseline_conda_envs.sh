#!/usr/bin/env bash
set -euo pipefail

# Create conda environments for the localization baselines in this repository.
#
# Typical server usage:
#   cd /path/to/cloned/locCode
#   bash setup_baseline_conda_envs.sh
#
# Create only the MM-IR dense retrieval environment:
#   bash setup_baseline_conda_envs.sh --env mmir
#
# Preview commands without changing the machine:
#   bash setup_baseline_conda_envs.sh --dry-run --env mmir
#
# Recreate an environment from scratch:
#   bash setup_baseline_conda_envs.sh --recreate --env mmir

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -n "${CONDA_SH:-}" ]]; then
  if [[ ! -f "${CONDA_SH}" ]]; then
    echo "ERROR: CONDA_SH does not exist: ${CONDA_SH}" >&2
    exit 2
  fi
  # shellcheck disable=SC1090
  source "${CONDA_SH}"
elif [[ -f "${HOME}/miniconda3/etc/profile.d/conda.sh" ]]; then
  # shellcheck disable=SC1091
  source "${HOME}/miniconda3/etc/profile.d/conda.sh"
elif [[ -f "${HOME}/anaconda3/etc/profile.d/conda.sh" ]]; then
  # shellcheck disable=SC1091
  source "${HOME}/anaconda3/etc/profile.d/conda.sh"
elif [[ -f "/opt/conda/etc/profile.d/conda.sh" ]]; then
  # shellcheck disable=SC1091
  source "/opt/conda/etc/profile.d/conda.sh"
fi

if [[ -z "${CONDA_BIN:-}" ]]; then
  if [[ -n "${CONDA_EXE:-}" && -x "${CONDA_EXE}" ]]; then
    CONDA_BIN="${CONDA_EXE}"
  elif command -v conda >/dev/null 2>&1; then
    CONDA_BIN="$(command -v conda)"
  elif [[ -x "${HOME}/miniconda3/bin/conda" ]]; then
    CONDA_BIN="${HOME}/miniconda3/bin/conda"
  elif [[ -x "${HOME}/anaconda3/bin/conda" ]]; then
    CONDA_BIN="${HOME}/anaconda3/bin/conda"
  elif [[ -x "/opt/conda/bin/conda" ]]; then
    CONDA_BIN="/opt/conda/bin/conda"
  else
    CONDA_BIN="conda"
  fi
fi
PIP_INDEX_URL_ARG=()
PIP_EXTRA_INDEX_URL_ARG=()

DRY_RUN=0
RECREATE=0
RUN_SMOKE_TEST=1
SELECTED_ENVS=()
COMMAND_HEARTBEAT_INTERVAL="${COMMAND_HEARTBEAT_INTERVAL:-30}"

# If set, environments are created by prefix under this directory:
#   CONDA_ENV_ROOT=/data2/like/envs -> /data2/like/envs/mmir
# Otherwise regular named conda environments are used:
#   conda create -n mmir ...
CONDA_ENV_ROOT="${CONDA_ENV_ROOT:-}"

LOCAGENT_ENV="${LOCAGENT_ENV:-locagent}"
COSIL_ENV="${COSIL_ENV:-cosil}"
GRAPHLOCATOR_ENV="${GRAPHLOCATOR_ENV:-graphlocator}"
GALA_ENV="${GALA_ENV:-gala}"
MMIR_ENV="${MMIR_ENV:-mmir}"

LOCAGENT_PYTHON_VERSION="${LOCAGENT_PYTHON_VERSION:-3.12}"
COSIL_PYTHON_VERSION="${COSIL_PYTHON_VERSION:-3.12}"
GRAPHLOCATOR_PYTHON_VERSION="${GRAPHLOCATOR_PYTHON_VERSION:-3.12}"
GALA_PYTHON_VERSION="${GALA_PYTHON_VERSION:-3.12}"
MMIR_PYTHON_VERSION="${MMIR_PYTHON_VERSION:-3.12}"

# Optional pip mirror settings, useful on servers.
if [[ -n "${PIP_INDEX_URL:-}" ]]; then
  PIP_INDEX_URL_ARG=(--index-url "${PIP_INDEX_URL}")
fi
if [[ -n "${PIP_EXTRA_INDEX_URL:-}" ]]; then
  PIP_EXTRA_INDEX_URL_ARG=(--extra-index-url "${PIP_EXTRA_INDEX_URL}")
fi

usage() {
  cat <<'EOF'
Usage: bash setup_baseline_conda_envs.sh [options]

Options:
  --env NAME       Environment group to create. Can be repeated.
                   NAME: locagent | cosil | graphlocator | gala | mmir | all
                   Default: all
  --dry-run        Print commands without executing them.
  --recreate       Remove an existing conda env before creating it.
  --no-smoke-test  Skip post-install import checks.
  -h, --help       Show this help.

Useful environment variables:
  CONDA_BIN=/path/to/conda
  CONDA_SH=/data2/like/miniconda3/etc/profile.d/conda.sh
  CONDA_ENV_ROOT=/data2/like/envs
  PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
  PIP_EXTRA_INDEX_URL=...
  LOCAGENT_ENV=locagent
  COSIL_ENV=cosil
  GRAPHLOCATOR_ENV=graphlocator
  GALA_ENV=gala
  MMIR_ENV=mmir

CUDA note:
  This script installs the Python dependencies needed by the baselines. MM-IR
  dense retrieval uses PyTorch through sentence-transformers/transformers.
  On a CUDA server, run experiments with DENSE_DEVICE=cuda after confirming:

    conda run -n mmir python -c "import torch; print(torch.cuda.is_available())"

  If you use CONDA_ENV_ROOT, the equivalent check is:

    conda run -p /data2/like/envs/mmir python -c "import torch; print(torch.cuda.is_available())"

EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)
      if [[ $# -lt 2 ]]; then
        echo "ERROR: --env requires a value" >&2
        exit 2
      fi
      SELECTED_ENVS+=("$2")
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --recreate)
      RECREATE=1
      shift
      ;;
    --no-smoke-test)
      RUN_SMOKE_TEST=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ ${#SELECTED_ENVS[@]} -eq 0 ]]; then
  SELECTED_ENVS=(all)
fi

should_run_env() {
  local target="$1"
  local selected
  for selected in "${SELECTED_ENVS[@]}"; do
    [[ "${selected}" == "all" || "${selected}" == "${target}" ]] && return 0
  done
  return 1
}

run_cmd() {
  echo "+ $*"
  if [[ "${DRY_RUN}" != "1" ]]; then
    if [[ "${COMMAND_HEARTBEAT_INTERVAL}" =~ ^[0-9]+$ && "${COMMAND_HEARTBEAT_INTERVAL}" -gt 0 ]]; then
      local pid status start now elapsed
      start="$(date +%s)"
      "$@" &
      pid=$!
      while kill -0 "${pid}" >/dev/null 2>&1; do
        sleep "${COMMAND_HEARTBEAT_INTERVAL}"
        if kill -0 "${pid}" >/dev/null 2>&1; then
          now="$(date +%s)"
          elapsed=$((now - start))
          echo "[still running][$((elapsed / 60))m$((elapsed % 60))s] $*"
        fi
      done
      set +e
      wait "${pid}"
      status=$?
      set -e
      return "${status}"
    fi
    "$@"
  fi
}

env_prefix() {
  local env_ref="$1"
  if [[ "${env_ref}" == /* ]]; then
    echo "${env_ref}"
  elif [[ -n "${CONDA_ENV_ROOT}" ]]; then
    echo "${CONDA_ENV_ROOT%/}/${env_ref}"
  else
    echo ""
  fi
}

env_args() {
  local env_ref="$1"
  local prefix
  prefix="$(env_prefix "${env_ref}")"
  if [[ -n "${prefix}" ]]; then
    printf '%s\n' "-p" "${prefix}"
  else
    printf '%s\n' "-n" "${env_ref}"
  fi
}

env_label() {
  local env_ref="$1"
  local prefix
  prefix="$(env_prefix "${env_ref}")"
  if [[ -n "${prefix}" ]]; then
    echo "${prefix}"
  else
    echo "${env_ref}"
  fi
}

env_python_path() {
  local env_ref="$1"
  local conda_base="$2"
  local prefix
  prefix="$(env_prefix "${env_ref}")"
  if [[ -n "${prefix}" ]]; then
    echo "${prefix}/bin/python"
  else
    echo "${conda_base}/envs/${env_ref}/bin/python"
  fi
}

conda_env_exists() {
  local env_ref="$1"
  local prefix
  prefix="$(env_prefix "${env_ref}")"
  if [[ -n "${prefix}" ]]; then
    [[ -e "${prefix}" ]]
  else
    "${CONDA_BIN}" env list | awk '{print $1}' | grep -Fxq "${env_ref}"
  fi
}

remove_env_or_broken_prefix() {
  local env_ref="$1"
  local args prefix
  mapfile -t args < <(env_args "${env_ref}")
  prefix="$(env_prefix "${env_ref}")"

  if [[ -n "${prefix}" ]]; then
    if [[ -d "${prefix}/conda-meta" ]]; then
      run_cmd "${CONDA_BIN}" env remove -y "${args[@]}"
      return 0
    fi
    if [[ -e "${prefix}" ]]; then
      echo "[warn] removing broken/non-conda env directory: ${prefix}"
      run_cmd rm -rf "${prefix}"
      return 0
    fi
    return 0
  fi

  run_cmd "${CONDA_BIN}" env remove -y "${args[@]}"
}

ensure_conda() {
  if ! command -v "${CONDA_BIN}" >/dev/null 2>&1; then
    echo "ERROR: conda not found. Set CONDA_BIN=/path/to/conda." >&2
    exit 2
  fi
}

create_env() {
  local env_ref="$1"
  local py_version="$2"
  local args
  mapfile -t args < <(env_args "${env_ref}")
  if [[ "${DRY_RUN}" == "1" ]]; then
    run_cmd "${CONDA_BIN}" create -y "${args[@]}" "python=${py_version}" pip
    return 0
  fi
  if conda_env_exists "${env_ref}"; then
    if [[ "${RECREATE}" == "1" ]]; then
      remove_env_or_broken_prefix "${env_ref}"
    else
      echo "[skip] conda env exists: $(env_label "${env_ref}")"
      return 0
    fi
  fi
  run_cmd "${CONDA_BIN}" create -y "${args[@]}" "python=${py_version}" pip
}

pip_install() {
  local env_ref="$1"
  shift
  local args
  mapfile -t args < <(env_args "${env_ref}")
  run_cmd "${CONDA_BIN}" run "${args[@]}" python -m pip install "${PIP_INDEX_URL_ARG[@]}" "${PIP_EXTRA_INDEX_URL_ARG[@]}" "$@"
}

pip_install_requirements_if_present() {
  local env_name="$1"
  local req_file="$2"
  if [[ -f "${req_file}" ]]; then
    pip_install "${env_name}" -r "${req_file}"
  else
    echo "[warn] missing requirements file: ${req_file}"
  fi
}

smoke_test() {
  local env_ref="$1"
  local label="$2"
  local code="$3"
  if [[ "${RUN_SMOKE_TEST}" != "1" ]]; then
    return 0
  fi
  echo "[smoke] ${label}"
  local args
  mapfile -t args < <(env_args "${env_ref}")
  run_cmd "${CONDA_BIN}" run "${args[@]}" python -c "${code}"
}

install_locagent() {
  create_env "${LOCAGENT_ENV}" "${LOCAGENT_PYTHON_VERSION}"
  pip_install_requirements_if_present "${LOCAGENT_ENV}" "${ROOT_DIR}/LocAgent/requirements.txt"
  smoke_test "${LOCAGENT_ENV}" "LocAgent imports" \
    "import openai, datasets, tiktoken, tree_sitter; print('locagent ok')"
}

install_cosil() {
  create_env "${COSIL_ENV}" "${COSIL_PYTHON_VERSION}"
  pip_install_requirements_if_present "${COSIL_ENV}" "${ROOT_DIR}/CoSIL/requirments.txt"
  pip_install "${COSIL_ENV}" dataclasses-json unidiff tqdm pandas numpy pyarrow requests python-dotenv
  smoke_test "${COSIL_ENV}" "CoSIL imports" \
    "import anthropic, openai, litellm, libcst; print('cosil ok')"
}

install_graphlocator() {
  create_env "${GRAPHLOCATOR_ENV}" "${GRAPHLOCATOR_PYTHON_VERSION}"
  pip_install_requirements_if_present "${GRAPHLOCATOR_ENV}" "${ROOT_DIR}/GraphLocator/requirements.txt"
  pip_install "${GRAPHLOCATOR_ENV}" dataclasses-json
  # GraphLocator's original repo expected prebuilt tree-sitter language
  # libraries under rdfs/dependency_graph/lib/. Those binaries are not tracked,
  # so server clones need to recreate them during setup.
  if ! pip_install "${GRAPHLOCATOR_ENV}" tree_sitter_languages==1.10.2; then
    echo "[warn] tree_sitter_languages wheel install failed; will build GraphLocator tree-sitter library from grammar repos."
  fi
  local args
  mapfile -t args < <(env_args "${GRAPHLOCATOR_ENV}")
  run_cmd "${CONDA_BIN}" run "${args[@]}" python "${ROOT_DIR}/GraphLocator/newtest/scripts/ensure_tree_sitter_lib.py"
  smoke_test "${GRAPHLOCATOR_ENV}" "GraphLocator imports" \
    "import openai, litellm, tree_sitter, networkx, dataclasses_json; print('graphlocator ok')"
}

install_gala() {
  create_env "${GALA_ENV}" "${GALA_PYTHON_VERSION}"
  # GALA in this workspace does not ship a requirements.txt. These are the
  # packages used by the local mytest scripts and src modules.
  pip_install "${GALA_ENV}" \
    openai litellm requests beautifulsoup4 pillow numpy pandas tqdm pydantic \
    networkx matplotlib python-dotenv datasets pyarrow tiktoken unidiff dataclasses-json
  smoke_test "${GALA_ENV}" "GALA imports" \
    "import openai, requests, PIL, numpy, pandas, tqdm; print('gala ok')"
}

install_mmir() {
  create_env "${MMIR_ENV}" "${MMIR_PYTHON_VERSION}"
  pip_install "${MMIR_ENV}" numpy pandas requests tqdm pydantic beautifulsoup4 unidiff
  pip_install_requirements_if_present "${MMIR_ENV}" "${ROOT_DIR}/MM-IR/requirements-dense.txt"
  smoke_test "${MMIR_ENV}" "MM-IR dense imports" \
    "import sentence_transformers, transformers, torch, accelerate; print('mmir ok', 'cuda=', torch.cuda.is_available())"
}

main() {
  ensure_conda
  local conda_base
  conda_base="$("${CONDA_BIN}" info --base 2>/dev/null || true)"
  if [[ -z "${conda_base}" ]]; then
    conda_base="<conda-base>"
  fi
  echo "Repository root: ${ROOT_DIR}"
  echo "Conda executable: ${CONDA_BIN}"
  echo "Conda base: ${conda_base}"
  if [[ -n "${CONDA_ENV_ROOT}" ]]; then
    echo "Conda env root: ${CONDA_ENV_ROOT}"
  fi
  echo "Selected env groups: ${SELECTED_ENVS[*]}"
  echo "Dry run: ${DRY_RUN}"
  echo "Recreate: ${RECREATE}"
  echo

  if should_run_env locagent; then
    echo "========== LocAgent env: $(env_label "${LOCAGENT_ENV}") =========="
    install_locagent
  fi
  if should_run_env cosil; then
    echo "========== CoSIL env: $(env_label "${COSIL_ENV}") =========="
    install_cosil
  fi
  if should_run_env graphlocator; then
    echo "========== GraphLocator env: $(env_label "${GRAPHLOCATOR_ENV}") =========="
    install_graphlocator
  fi
  if should_run_env gala; then
    echo "========== GALA env: $(env_label "${GALA_ENV}") =========="
    install_gala
  fi
  if should_run_env mmir; then
    echo "========== MM-IR env: $(env_label "${MMIR_ENV}") =========="
    install_mmir
  fi

  local locagent_py cosil_py graphlocator_py gala_py mmir_py
  locagent_py="$(env_python_path "${LOCAGENT_ENV}" "${conda_base}")"
  cosil_py="$(env_python_path "${COSIL_ENV}" "${conda_base}")"
  graphlocator_py="$(env_python_path "${GRAPHLOCATOR_ENV}" "${conda_base}")"
  gala_py="$(env_python_path "${GALA_ENV}" "${conda_base}")"
  mmir_py="$(env_python_path "${MMIR_ENV}" "${conda_base}")"

  cat <<EOF

Done.

Recommended experiment variables on the server:
  export LOCAGENT_PY=${locagent_py}
  export COSIL_PY=${cosil_py}
  export GRAPHLOCATOR_PY=${graphlocator_py}
  export GALA_PY=${gala_py}
  export MMIR_PY=${mmir_py}

For MM-IR dense baselines on CUDA:
  export DENSE_DEVICE=cuda
  export DENSE_BATCH_SIZE=16

EOF
}

main
