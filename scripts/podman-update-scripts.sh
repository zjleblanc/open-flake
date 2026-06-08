#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "${SCRIPT_DIR}/openflake.env" ]]; then
  # shellcheck source=/dev/null
  source "${SCRIPT_DIR}/openflake.env"
fi

GITHUB_REPO="${OPENFLAKE_GITHUB_REPO:-zjleblanc/open-flake}"
GITHUB_REF="${OPENFLAKE_BRANCH:-${OPENFLAKE_VERSION:-main}}"
INSTALL_DIR="${OPENFLAKE_INSTALL_DIR:-${HOME}/.local/share/openflake}"
DEPLOY=0

usage() {
  cat <<EOF
Usage: podman-update-scripts.sh [OPTIONS]

Download the latest OpenFlake install helper scripts into the install directory.
Does not change .env secrets, container images, or running containers unless --deploy is set.

Environment variables:
  OPENFLAKE_INSTALL_DIR   Install directory (default: ~/.local/share/openflake)
  OPENFLAKE_BRANCH        Git branch, tag, or commit on GitHub (default: main)
  OPENFLAKE_VERSION       Deprecated alias for OPENFLAKE_BRANCH
  OPENFLAKE_GITHUB_REPO   GitHub repo for raw downloads (default: zjleblanc/open-flake)

If openflake.env exists next to this script, it is sourced before options and env vars above.

Options:
  --branch REF            Same as OPENFLAKE_BRANCH (default: main)
  --ref REF               Alias for --branch
  --install-dir PATH      Same as OPENFLAKE_INSTALL_DIR
  --deploy                After updating, run openflake-quadlets.sh deploy (Quadlet installs only)
  -h, --help              Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --branch|--ref) GITHUB_REF="$2"; shift 2 ;;
    --install-dir) INSTALL_DIR="$2"; shift 2 ;;
    --deploy) DEPLOY=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 1 ;;
  esac
done

GITHUB_RAW="https://raw.githubusercontent.com/${GITHUB_REPO}/${GITHUB_REF}"

require_install() {
  if [[ ! -f "${INSTALL_DIR}/.env" ]]; then
    echo "No install found at ${INSTALL_DIR}/.env" >&2
    echo "Run scripts/podman-install.sh first." >&2
    exit 1
  fi
}

is_quadlet_install() {
  if [[ -f "${INSTALL_DIR}/.env" ]]; then
    # shellcheck source=/dev/null
    source "${INSTALL_DIR}/.env"
    [[ "${OPENFLAKE_DEPLOY_METHOD:-}" == "quadlet" ]] && return 0
  fi
  [[ -d "${INSTALL_DIR}/quadlets" && -f "${INSTALL_DIR}/openflake-quadlets.sh" ]]
}

set_env_var() {
  local env_file="$1"
  local key="$2"
  local value="$3"
  if grep -q "^${key}=" "${env_file}"; then
    sed -i.bak "s|^${key}=.*|${key}=${value}|" "${env_file}"
    rm -f "${env_file}.bak"
  else
    echo "${key}=${value}" >> "${env_file}"
  fi
}

download_file() {
  local dest="$1"
  local url="$2"
  if ! curl -fsSL -o "${dest}" "${url}"; then
    echo "Failed to download ${url}" >&2
    echo "Pass --branch REF (or OPENFLAKE_BRANCH) for a git ref that includes the file." >&2
    exit 1
  fi
}

stage_update_file() {
  local dest="$1"
  local repo_path="$2"
  local basename="${repo_path##*/}"
  local candidate

  # When run from a repo checkout (scripts/), copy local files for development.
  # When run from the install dir, always fetch from GitHub so we do not copy stale files onto themselves.
  if [[ "${SCRIPT_DIR}" != "${INSTALL_DIR}" ]]; then
    for candidate in \
      "${SCRIPT_DIR}/${basename}" \
      "${SCRIPT_DIR}/${repo_path}" \
      "${SCRIPT_DIR}/../${repo_path}"; do
      if [[ -f "${candidate}" ]]; then
        cp "${candidate}" "${dest}"
        echo "  ${basename} (from ${candidate})"
        return 0
      fi
    done
  fi

  download_file "${dest}" "${GITHUB_RAW}/${repo_path}"
  echo "  ${basename} (from GitHub ${GITHUB_REF})"
}

stage_executable() {
  local dest="$1"
  local repo_path="$2"
  stage_update_file "${dest}" "${repo_path}"
  chmod +x "${dest}"
}

update_scripts() {
  local env_file="${INSTALL_DIR}/.env"

  echo "Updating install scripts in ${INSTALL_DIR} (git ref: ${GITHUB_REF})..."

  stage_executable "${INSTALL_DIR}/podman-upgrade.sh" "scripts/podman-upgrade.sh"
  stage_executable "${INSTALL_DIR}/podman-update-scripts.sh" "scripts/podman-update-scripts.sh"
  stage_update_file "${INSTALL_DIR}/pg_hba.conf" "deploy/pg_hba.conf"

  if is_quadlet_install; then
    stage_executable "${INSTALL_DIR}/openflake-quadlets.sh" "scripts/openflake-quadlets.sh"
  elif [[ -f "${INSTALL_DIR}/podman-compose.registry.yaml" || -f "${INSTALL_DIR}/openflake-stack.sh" ]]; then
    stage_update_file "${INSTALL_DIR}/podman-compose.registry.yaml" "deploy/podman-compose.registry.yaml"
    stage_update_file "${INSTALL_DIR}/podman-compose.ssl.yaml" "deploy/podman-compose.ssl.yaml"
    stage_executable "${INSTALL_DIR}/openflake-stack.sh" "scripts/openflake-stack.sh"
  else
    stage_executable "${INSTALL_DIR}/openflake-quadlets.sh" "scripts/openflake-quadlets.sh"
    stage_update_file "${INSTALL_DIR}/podman-compose.registry.yaml" "deploy/podman-compose.registry.yaml"
    stage_update_file "${INSTALL_DIR}/podman-compose.ssl.yaml" "deploy/podman-compose.ssl.yaml"
    stage_executable "${INSTALL_DIR}/openflake-stack.sh" "scripts/openflake-stack.sh"
  fi

  set_env_var "${env_file}" "OPENFLAKE_GITHUB_REF" "${GITHUB_REF}"

  if [[ "${DEPLOY}" -eq 1 ]]; then
    if is_quadlet_install && [[ -x "${INSTALL_DIR}/openflake-quadlets.sh" ]]; then
      echo "Deploying updated Podman Quadlets..."
      "${INSTALL_DIR}/openflake-quadlets.sh" deploy
    elif is_quadlet_install; then
      echo "Skipping --deploy: ${INSTALL_DIR}/openflake-quadlets.sh not found or not executable." >&2
    else
      echo "Skipping --deploy: install is not using Podman Quadlets." >&2
    fi
  fi

  cat <<EOF

Scripts updated from ${GITHUB_REPO}@${GITHUB_REF}.
EOF

  if is_quadlet_install && [[ "${DEPLOY}" -eq 0 ]]; then
    cat <<EOF
Quadlet installs: run ${INSTALL_DIR}/openflake-quadlets.sh deploy to apply quadlet unit changes.
EOF
  fi
}

require_install
update_scripts
