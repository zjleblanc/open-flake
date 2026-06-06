#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "${SCRIPT_DIR}/openflake.env" ]]; then
  # shellcheck source=/dev/null
  source "${SCRIPT_DIR}/openflake.env"
fi

INSTALL_DIR="${OPENFLAKE_INSTALL_DIR:-${HOME}/.local/share/openflake}"
IMAGE_TAG="${OPENFLAKE_IMAGE_TAG:-latest}"
BACKUP=0
HEALTH_TIMEOUT="${OPENFLAKE_HEALTH_TIMEOUT:-120}"

usage() {
  cat <<EOF
Usage: podman-upgrade.sh [OPTIONS]

Pull updated OpenFlake images, redeploy, and wait for database migrations.

Environment variables:
  OPENFLAKE_INSTALL_DIR   Install directory (default: ~/.local/share/openflake)
  OPENFLAKE_IMAGE_TAG     Target image tag (default: latest)
  OPENFLAKE_BACKUP=1      Create a PostgreSQL dump before upgrading
  OPENFLAKE_HEALTH_TIMEOUT Seconds to wait for backend /health/ready (default: 120)

If openflake.env exists next to this script, it is sourced before options and env vars above.

Options:
  --tag TAG               Same as OPENFLAKE_IMAGE_TAG
  --install-dir PATH      Same as OPENFLAKE_INSTALL_DIR
  --backup                Run pg_dump before upgrading
  -h, --help              Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tag) IMAGE_TAG="$2"; shift 2 ;;
    --install-dir) INSTALL_DIR="$2"; shift 2 ;;
    --backup) BACKUP=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 1 ;;
  esac
done

if [[ "${OPENFLAKE_BACKUP:-0}" == "1" ]]; then
  BACKUP=1
fi

run_compose() {
  if podman compose version >/dev/null 2>&1; then
    podman compose "$@"
  elif command -v podman-compose >/dev/null 2>&1; then
    podman-compose "$@"
  else
    echo "Podman Compose is not available." >&2
    exit 1
  fi
}

require_install() {
  if [[ ! -f "${INSTALL_DIR}/.env" ]]; then
    echo "No install found at ${INSTALL_DIR}/.env" >&2
    echo "Run scripts/podman-install.sh first." >&2
    exit 1
  fi
  if [[ ! -f "${INSTALL_DIR}/podman-compose.registry.yaml" ]]; then
    echo "Missing ${INSTALL_DIR}/podman-compose.registry.yaml" >&2
    exit 1
  fi
}

update_env_tag() {
  local env_file="${INSTALL_DIR}/.env"
  if grep -q '^OPENFLAKE_IMAGE_TAG=' "${env_file}"; then
    sed -i.bak "s/^OPENFLAKE_IMAGE_TAG=.*/OPENFLAKE_IMAGE_TAG=${IMAGE_TAG}/" "${env_file}"
    rm -f "${env_file}.bak"
  else
    echo "OPENFLAKE_IMAGE_TAG=${IMAGE_TAG}" >> "${env_file}"
  fi
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

ensure_ssl_mount_env() {
  local env_file="${INSTALL_DIR}/.env"
  # shellcheck source=/dev/null
  source "${env_file}"
  local ssl_dir="${OPENFLAKE_SSL_DIR:-${OPENFLAKE_CERT_DIR:-}}"
  [[ -n "${ssl_dir}" ]] || return 0
  set_env_var "${env_file}" "OPENFLAKE_SSL_BACKEND_MOUNT" "${ssl_dir}:/etc/openflake/certs:ro"
  set_env_var "${env_file}" "OPENFLAKE_SSL_FRONTEND_MOUNT" "${ssl_dir}:/etc/nginx/certs:ro"
}

load_compose_env() {
  set -a
  # shellcheck source=/dev/null
  source "${INSTALL_DIR}/.env"
  set +a
}

require_ssl_mount_vars() {
  if [[ -z "${OPENFLAKE_SSL_BACKEND_MOUNT:-}" || -z "${OPENFLAKE_SSL_FRONTEND_MOUNT:-}" ]]; then
    echo "OPENFLAKE_SSL_BACKEND_MOUNT and OPENFLAKE_SSL_FRONTEND_MOUNT must be set in ${INSTALL_DIR}/.env" >&2
    echo "Re-run scripts/podman-install.sh or add them from OPENFLAKE_SSL_DIR." >&2
    exit 1
  fi
}

ssl_mount_host_dir() {
  local mount_spec="$1"
  echo "${mount_spec%%:*}"
}

validate_certs() {
  local dir="$1"
  local cert="$2"
  local key="$3"
  if [[ ! -f "${dir}/${cert}" || ! -f "${dir}/${key}" ]]; then
    echo "TLS certificates not found in ${dir}" >&2
    echo "Expected: ${cert} and ${key}" >&2
    if [[ -d "${dir}" ]]; then
      echo "Directory contents:" >&2
      ls -la "${dir}" >&2 || true
    fi
    exit 1
  fi
}

validate_ssl_mount_certs() {
  local mount_spec="$1"
  local cert="$2"
  local key="$3"
  local host_dir
  host_dir="$(ssl_mount_host_dir "${mount_spec}")"
  if [[ -z "${host_dir}" || "${host_dir}" == "${mount_spec}" ]]; then
    echo "Invalid OPENFLAKE_SSL_BACKEND_MOUNT: ${mount_spec}" >&2
    echo "Expected format: /host/path:/etc/openflake/certs:ro" >&2
    exit 1
  fi
  validate_certs "${host_dir}" "${cert}" "${key}"
}

build_compose_files() {
  COMPOSE_FILES=(-f "${INSTALL_DIR}/podman-compose.registry.yaml")
  USE_SSL_COMPOSE=0
  if [[ -f "${INSTALL_DIR}/podman-compose.ssl.yaml" ]]; then
    # shellcheck source=/dev/null
    source "${INSTALL_DIR}/.env"
    local ssl_dir="${OPENFLAKE_SSL_DIR:-${OPENFLAKE_CERT_DIR:-}}"
    local ssl_cert="${OPENFLAKE_SSL_CERT:-fullchain.pem}"
    local ssl_key="${OPENFLAKE_SSL_KEY:-privkey.pem}"
    if [[ -n "${ssl_dir}" && -f "${ssl_dir}/${ssl_cert}" && -f "${ssl_dir}/${ssl_key}" ]]; then
      COMPOSE_FILES+=(-f "${INSTALL_DIR}/podman-compose.ssl.yaml")
      USE_SSL_COMPOSE=1
    fi
  fi
}

backup_database() {
  if ! podman container exists openflake-postgres 2>/dev/null; then
    echo "PostgreSQL container not found; skipping backup." >&2
    return 0
  fi
  local backup_dir="${INSTALL_DIR}/backups"
  local timestamp
  timestamp="$(date +%Y%m%d-%H%M%S)"
  local backup_file="${backup_dir}/openflake-${timestamp}.sql"
  mkdir -p "${backup_dir}"
  echo "Backing up database to ${backup_file}..."
  podman exec openflake-postgres pg_dump -U openflake openflake > "${backup_file}"
  echo "${backup_file}"
}

wait_for_backend() {
  local elapsed=0
  echo "Waiting for backend migrations (up to ${HEALTH_TIMEOUT}s)..."
  while [[ "${elapsed}" -lt "${HEALTH_TIMEOUT}" ]]; do
    if curl -fsS "http://localhost:8000/health/ready" >/dev/null 2>&1; then
      echo "Backend is ready."
      return 0
    fi
    sleep 2
    elapsed=$((elapsed + 2))
  done
  echo "Backend did not become ready within ${HEALTH_TIMEOUT}s." >&2
  echo "Check logs: podman logs openflake-backend" >&2
  return 1
}

require_install

CURRENT_TAG="unknown"
if [[ -f "${INSTALL_DIR}/installed-version" ]]; then
  CURRENT_TAG="$(cat "${INSTALL_DIR}/installed-version")"
fi

echo "Upgrading OpenFlake: ${CURRENT_TAG} -> ${IMAGE_TAG}"

BACKUP_PATH=""
if [[ "${BACKUP}" -eq 1 ]]; then
  BACKUP_PATH="$(backup_database)"
fi

update_env_tag
ensure_ssl_mount_env

build_compose_files

cd "${INSTALL_DIR}"

if [[ "${USE_SSL_COMPOSE}" -eq 1 ]]; then
  load_compose_env
  require_ssl_mount_vars
  validate_ssl_mount_certs "${OPENFLAKE_SSL_BACKEND_MOUNT}" "${OPENFLAKE_SSL_CERT:-fullchain.pem}" "${OPENFLAKE_SSL_KEY:-privkey.pem}"
fi

compose_up() {
  if [[ "${USE_SSL_COMPOSE}" -eq 1 ]]; then
    load_compose_env
  fi
  run_compose "${COMPOSE_FILES[@]}" --env-file "${INSTALL_DIR}/.env" "$@"
}

echo "Pulling updated images..."
compose_up pull backend frontend

echo "Recreating backend (runs database migrations on startup)..."
compose_up up -d --force-recreate --no-deps backend

wait_for_backend

echo "Recreating frontend..."
compose_up up -d --force-recreate --no-deps frontend

echo "${IMAGE_TAG}" > "${INSTALL_DIR}/installed-version"

cat <<EOF

Upgrade complete: ${CURRENT_TAG} -> ${IMAGE_TAG}
EOF

if [[ -n "${BACKUP_PATH}" ]]; then
  echo "  Backup: ${BACKUP_PATH}"
fi

cat <<EOF

Database migrations run automatically on backend startup.
Rollback: set OPENFLAKE_IMAGE_TAG to the previous version in ${INSTALL_DIR}/.env and re-run this script.
EOF
