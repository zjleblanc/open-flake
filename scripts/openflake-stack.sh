#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${OPENFLAKE_INSTALL_DIR:-${SCRIPT_DIR}}"

usage() {
  cat <<EOF
Usage: openflake-stack.sh {start|stop|restart|status}

Manage the OpenFlake Podman Compose stack in ${INSTALL_DIR}.

Environment variables:
  OPENFLAKE_INSTALL_DIR   Install directory (default: directory containing this script)
EOF
}

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

load_compose_env() {
  set -a
  # shellcheck source=/dev/null
  source "${INSTALL_DIR}/.env"
  set +a
}

require_install() {
  if [[ ! -f "${INSTALL_DIR}/.env" ]]; then
    echo "No install found at ${INSTALL_DIR}/.env" >&2
    exit 1
  fi
  if [[ ! -f "${INSTALL_DIR}/podman-compose.registry.yaml" ]]; then
    echo "Missing ${INSTALL_DIR}/podman-compose.registry.yaml" >&2
    exit 1
  fi
}

require_ssl_mount_vars() {
  if [[ -z "${OPENFLAKE_SSL_BACKEND_MOUNT:-}" || -z "${OPENFLAKE_SSL_FRONTEND_MOUNT:-}" ]]; then
    echo "OPENFLAKE_SSL_BACKEND_MOUNT and OPENFLAKE_SSL_FRONTEND_MOUNT must be set in ${INSTALL_DIR}/.env" >&2
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
    exit 1
  fi
  if [[ ! -r "${dir}/${cert}" || ! -r "${dir}/${key}" ]]; then
    echo "TLS certificate files exist but are not readable by $(id -un) (uid $(id -u))." >&2
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

compose_up() {
  run_compose "${COMPOSE_FILES[@]}" --env-file "${INSTALL_DIR}/.env" "$@"
}

remove_container_if_exists() {
  local name="$1"
  if podman container exists "${name}" 2>/dev/null; then
    podman rm -f "${name}"
  fi
}

wait_for_postgres() {
  local elapsed=0
  local max_wait=60
  until podman exec openflake-postgres pg_isready -U "${POSTGRES_USER:-openflake}" -d "${POSTGRES_DB:-openflake}" >/dev/null 2>&1; do
    if [[ "${elapsed}" -ge "${max_wait}" ]]; then
      echo "Timed out waiting for PostgreSQL after ${max_wait}s" >&2
      exit 1
    fi
    sleep 1
    elapsed=$((elapsed + 1))
  done
}

prepare_ssl_env() {
  if [[ "${USE_SSL_COMPOSE}" -eq 1 ]]; then
    load_compose_env
    require_ssl_mount_vars
    validate_ssl_mount_certs "${OPENFLAKE_SSL_BACKEND_MOUNT}" "${OPENFLAKE_SSL_CERT:-fullchain.pem}" "${OPENFLAKE_SSL_KEY:-privkey.pem}"
  fi
}

cmd_start() {
  cd "${INSTALL_DIR}"
  build_compose_files
  prepare_ssl_env

  # Remove dependents first so Podman does not error when Postgres is recreated.
  remove_container_if_exists openflake-frontend
  remove_container_if_exists openflake-backend
  remove_container_if_exists openflake-postgres

  compose_up up -d --no-deps postgres
  wait_for_postgres
  compose_up up -d --no-deps backend
  compose_up up -d --no-deps frontend
}

cmd_stop() {
  cd "${INSTALL_DIR}"
  build_compose_files
  compose_up down
}

cmd_restart() {
  cmd_stop
  cmd_start
}

cmd_status() {
  podman ps --filter name=openflake- --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
}

require_install

case "${1:-}" in
  start) cmd_start ;;
  stop) cmd_stop ;;
  restart) cmd_restart ;;
  status) cmd_status ;;
  -h|--help|"") usage; exit 0 ;;
  *) echo "Unknown command: $1" >&2; usage >&2; exit 1 ;;
esac
