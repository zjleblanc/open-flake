#!/usr/bin/env bash
set -euo pipefail

# Tear down an active OpenFlake Podman (Quadlet or Compose) deployment so
# podman-install.sh can run cleanly after a DB schema reset.
# Does NOT modify any .env files.
# Safe to run multiple times (idempotent).

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${OPENFLAKE_INSTALL_DIR:-${HOME}/.local/share/openflake}"
REMOVE_ATTACHMENTS=0
DRY_RUN=0

usage() {
  cat <<EOF
Usage: podman-cleanup.sh [OPTIONS]

Remove an active OpenFlake deployment (containers, volumes, network, quadlets)
in preparation for a fresh podman-install.sh run after a DB schema reset.

Does NOT touch env files (openflake.env or INSTALL_DIR/.env).
Safe to run repeatedly — already-removed resources are skipped.

Options:
  --install-dir PATH       Override OPENFLAKE_INSTALL_DIR (default: ~/.local/share/openflake)
  --remove-attachments     Also remove the openflake-attachments volume
  --dry-run                Print what would be done without executing
  -h, --help               Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install-dir) INSTALL_DIR="$2"; shift 2 ;;
    --remove-attachments) REMOVE_ATTACHMENTS=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 1 ;;
  esac
done

run() {
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    echo "[dry-run] $*"
  else
    echo "=> $*"
    "$@"
  fi
}

# Best-effort run — logs failure but does not exit the script.
run_safe() {
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    echo "[dry-run] $*"
  else
    echo "=> $*"
    "$@" || echo "  (command failed; continuing)"
  fi
}

run_quiet() {
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    echo "[dry-run] $*"
  else
    "$@" || true
  fi
}

has_podman() {
  command -v podman >/dev/null 2>&1 && podman info >/dev/null 2>&1
}

podman_is_rootless() {
  podman info --format '{{.Host.Security.Rootless}}' 2>/dev/null | grep -Fxq true
}

run_systemctl() {
  if podman_is_rootless; then
    systemctl --user "$@"
  elif [[ "${EUID}" -ne 0 ]]; then
    sudo systemctl "$@"
  else
    systemctl "$@"
  fi
}

quadlet_systemd_dir() {
  if podman_is_rootless; then
    echo "${HOME}/.config/containers/systemd"
  else
    echo "/etc/containers/systemd"
  fi
}

# --- Preflight: verify podman is usable ---

if ! has_podman; then
  echo "Podman is not available or not running. Nothing to clean up." >&2
  exit 0
fi

# --- Detect deployment method ---

DEPLOY_METHOD=""
if [[ -f "${INSTALL_DIR}/.env" ]]; then
  DEPLOY_METHOD="$(grep -s '^OPENFLAKE_DEPLOY_METHOD=' "${INSTALL_DIR}/.env" | cut -d= -f2 || true)"
fi

echo "=== OpenFlake Cleanup ==="
echo "Install dir: ${INSTALL_DIR}"
echo "Deploy method: ${DEPLOY_METHOD:-compose (default)}"
echo ""

# --- 1. Stop services ---

echo "--- Stopping services ---"

if [[ "${DEPLOY_METHOD}" == "quadlet" ]] && command -v systemctl >/dev/null 2>&1; then
  run_quiet run_systemctl stop openflake-frontend.service 2>/dev/null
  run_quiet run_systemctl stop openflake-backend.service 2>/dev/null
  run_quiet run_systemctl stop openflake-postgres.service 2>/dev/null
elif [[ -f "${INSTALL_DIR}/podman-compose.registry.yaml" && -f "${INSTALL_DIR}/.env" ]]; then
  compose_cmd=""
  if podman compose version >/dev/null 2>&1; then
    compose_cmd="podman compose"
  elif command -v podman-compose >/dev/null 2>&1; then
    compose_cmd="podman-compose"
  fi
  if [[ -n "${compose_cmd}" ]]; then
    COMPOSE_FILES=(-f "${INSTALL_DIR}/podman-compose.registry.yaml")
    if [[ -f "${INSTALL_DIR}/podman-compose.ssl.yaml" ]]; then
      COMPOSE_FILES+=(-f "${INSTALL_DIR}/podman-compose.ssl.yaml")
    fi
    run_quiet "${compose_cmd}" "${COMPOSE_FILES[@]}" --env-file "${INSTALL_DIR}/.env" down 2>/dev/null
  fi
else
  echo "  (no services to stop)"
fi

# --- 2. Remove containers (force, in case stop didn't fully clean up) ---

echo "--- Removing containers ---"

for ctr in openflake-frontend openflake-backend openflake-postgres; do
  if podman container exists "${ctr}" 2>/dev/null; then
    run_safe podman rm -f "${ctr}"
  else
    echo "  (${ctr} not present)"
  fi
done

# --- 3. Remove volumes ---

echo "--- Removing volumes ---"

if podman volume exists openflake-pg-data 2>/dev/null; then
  run_safe podman volume rm -f openflake-pg-data
else
  echo "  (openflake-pg-data not present)"
fi

if [[ "${REMOVE_ATTACHMENTS}" -eq 1 ]]; then
  if podman volume exists openflake-attachments 2>/dev/null; then
    run_safe podman volume rm -f openflake-attachments
  else
    echo "  (openflake-attachments not present)"
  fi
else
  echo "  (keeping openflake-attachments — pass --remove-attachments to remove)"
fi

# --- 4. Remove network ---

echo "--- Removing network ---"

if podman network exists openflake-net 2>/dev/null; then
  run_safe podman network rm -f openflake-net
else
  echo "  (openflake-net not present)"
fi

# --- 5. Remove quadlet systemd units (if applicable) ---

if [[ "${DEPLOY_METHOD}" == "quadlet" ]] && command -v systemctl >/dev/null 2>&1; then
  echo "--- Removing quadlet units ---"

  SYSTEMD_DIR="$(quadlet_systemd_dir)"
  removed=0
  for pattern in openflake-*.container openflake-*.network openflake-*.volume; do
    for f in "${SYSTEMD_DIR}"/${pattern}; do
      [[ -f "${f}" ]] || continue
      run_safe rm -f "${f}"
      removed=1
    done
  done
  if [[ -d "${INSTALL_DIR}/quadlets" ]]; then
    run_safe rm -rf "${INSTALL_DIR}/quadlets"
  fi
  if [[ "${removed}" -eq 1 || "${DRY_RUN}" -eq 1 ]]; then
    echo "  Reloading systemd daemon..."
    run_quiet run_systemctl daemon-reload 2>/dev/null
    run_quiet run_systemctl reset-failed 2>/dev/null
  else
    echo "  (no quadlet files found in ${SYSTEMD_DIR})"
  fi
fi

# --- 6. Clean install dir (keep .env for reference, remove generated files) ---

echo "--- Cleaning install directory ---"

cleaned=0
for f in \
  pg_hba.conf \
  podman-compose.registry.yaml \
  podman-compose.ssl.yaml \
  openflake-stack.sh \
  openflake-quadlets.sh \
  podman-upgrade.sh \
  podman-update-scripts.sh \
  installed-version; do
  if [[ -f "${INSTALL_DIR}/${f}" ]]; then
    run_safe rm -f "${INSTALL_DIR}/${f}"
    cleaned=1
  fi
done
if [[ "${cleaned}" -eq 0 ]]; then
  echo "  (no generated files to remove)"
fi

echo ""
echo "=== Cleanup complete ==="
echo ""
echo "Ready to run:"
echo "  ${SCRIPT_DIR}/podman-install.sh"
