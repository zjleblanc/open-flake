#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${OPENFLAKE_INSTALL_DIR:-${SCRIPT_DIR}}"
QUADLET_SRC="${INSTALL_DIR}/quadlets"
SYSTEMD_SCOPE=""

usage() {
  cat <<EOF
Usage: openflake-quadlets.sh {generate|deploy|install|pull|start|stop|restart|status}

Manage the OpenFlake Podman Quadlet deployment in ${INSTALL_DIR}.

  generate   Write quadlet and env files to ${QUADLET_SRC}
  deploy     Copy quadlets to the systemd search path and reload systemd
  install    deploy, enable lingering, enable units, and start services
  pull       Pull container images from ${INSTALL_DIR}/.env
  start      Start enabled quadlet services
  stop       Stop application container services
  restart    stop then start
  restart-apps  Restart backend and frontend only (for upgrades)
  status     Show OpenFlake containers

Environment variables:
  OPENFLAKE_INSTALL_DIR   Install directory (default: directory containing this script)
EOF
}

require_install() {
  if [[ ! -f "${INSTALL_DIR}/.env" ]]; then
    echo "No install found at ${INSTALL_DIR}/.env" >&2
    exit 1
  fi
  if [[ ! -f "${INSTALL_DIR}/pg_hba.conf" ]]; then
    echo "Missing ${INSTALL_DIR}/pg_hba.conf" >&2
    exit 1
  fi
}

load_env() {
  set -a
  # shellcheck source=/dev/null
  source "${INSTALL_DIR}/.env"
  set +a
  REGISTRY="${OPENFLAKE_REGISTRY:-quay.io/zleblanc}"
  IMAGE_TAG="${OPENFLAKE_IMAGE_TAG:-latest}"
  POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-openflake}"
  SECRET_KEY="${SECRET_KEY:-change-me-in-production}"
  ADMIN_USERNAME="${ADMIN_USERNAME:-admin}"
  ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin}"
  SSL_DIR="${OPENFLAKE_SSL_DIR:-${OPENFLAKE_CERT_DIR:-}}"
  SSL_CERT="${OPENFLAKE_SSL_CERT:-fullchain.pem}"
  SSL_KEY="${OPENFLAKE_SSL_KEY:-privkey.pem}"
  HTTPS_PORT="${OPENFLAKE_HTTPS_PORT:-8443}"
  BASE_URL="${OPENFLAKE_BASE_URL:-http://localhost:8000}"
  CORS_ORIGINS="${OPENFLAKE_CORS_ORIGINS:-http://localhost:8080,http://localhost:5173}"
  TRUSTED_PROXIES="${TRUSTED_PROXIES:-*}"
  ATTACHMENTS_DIR="${OPENFLAKE_ATTACHMENTS_DIR:-}"
  USE_SSL=0
  if [[ -n "${SSL_DIR}" && -f "${SSL_DIR}/${SSL_CERT}" && -f "${SSL_DIR}/${SSL_KEY}" ]]; then
    USE_SSL=1
  fi
}

podman_is_rootless() {
  podman info --format '{{.Host.Security.Rootless}}' 2>/dev/null | grep -Fx true
}

detect_systemd_scope() {
  if podman_is_rootless; then
    SYSTEMD_SCOPE="user"
  else
    SYSTEMD_SCOPE="system"
  fi
}

quadlet_systemd_dir() {
  if podman_is_rootless; then
    echo "${HOME}/.config/containers/systemd"
  else
    echo "/etc/containers/systemd"
  fi
}

write_file() {
  local path="$1"
  shift
  mkdir -p "$(dirname "${path}")"
  printf '%s\n' "$@" > "${path}"
}

write_container_env_files() {
  local pg_env="${QUADLET_SRC}/postgres.env"
  local backend_env="${QUADLET_SRC}/backend.env"
  local frontend_env="${QUADLET_SRC}/frontend.env"

  write_file "${pg_env}" \
    "POSTGRES_USER=openflake" \
    "POSTGRES_PASSWORD=${POSTGRES_PASSWORD}" \
    "POSTGRES_DB=openflake"

  if [[ "${USE_SSL}" -eq 1 ]]; then
    write_file "${backend_env}" \
      "DATABASE_URL=postgresql+asyncpg://openflake:${POSTGRES_PASSWORD}@postgres:5432/openflake" \
      "SECRET_KEY=${SECRET_KEY}" \
      "BASE_URL=${BASE_URL}" \
      "ADMIN_USERNAME=${ADMIN_USERNAME}" \
      "ADMIN_PASSWORD=${ADMIN_PASSWORD}" \
      "ATTACHMENTS_PATH=/data/attachments" \
      "CORS_ORIGINS=${CORS_ORIGINS}" \
      "TRUSTED_PROXIES=${TRUSTED_PROXIES}" \
      "OPENFLAKE_SSL_CERT=${SSL_CERT}" \
      "OPENFLAKE_SSL_KEY=${SSL_KEY}" \
      "OPENFLAKE_SSL_REQUIRED=1"
    write_file "${frontend_env}" \
      "OPENFLAKE_SSL_CERT=${SSL_CERT}" \
      "OPENFLAKE_SSL_KEY=${SSL_KEY}" \
      "OPENFLAKE_HTTPS_PORT=${HTTPS_PORT}" \
      "OPENFLAKE_SSL_REQUIRED=1"
  else
    rm -f "${frontend_env}"
    write_file "${backend_env}" \
      "DATABASE_URL=postgresql+asyncpg://openflake:${POSTGRES_PASSWORD}@postgres:5432/openflake" \
      "SECRET_KEY=${SECRET_KEY}" \
      "BASE_URL=${BASE_URL}" \
      "ADMIN_USERNAME=${ADMIN_USERNAME}" \
      "ADMIN_PASSWORD=${ADMIN_PASSWORD}" \
      "ATTACHMENTS_PATH=/data/attachments" \
      "CORS_ORIGINS=${CORS_ORIGINS}" \
      "TRUSTED_PROXIES=${TRUSTED_PROXIES}"
  fi
}

backend_volume_lines() {
  if [[ -n "${ATTACHMENTS_DIR}" ]]; then
    echo "Volume=${ATTACHMENTS_DIR}:/data/attachments"
  else
    echo "Volume=openflake-attachments.volume:/data/attachments"
  fi
}

backend_ssl_lines() {
  if [[ "${USE_SSL}" -eq 1 ]]; then
    echo "Volume=${SSL_DIR}:/etc/openflake/certs:ro"
  fi
}

frontend_publish_lines() {
  if [[ "${USE_SSL}" -eq 1 ]]; then
    echo "PublishPort=${HTTPS_PORT}:443"
    echo "PublishPort=8080:8080"
  else
    echo "PublishPort=8080:8080"
  fi
}

frontend_ssl_lines() {
  if [[ "${USE_SSL}" -eq 1 ]]; then
    echo "Volume=${SSL_DIR}:/etc/nginx/certs:ro"
  fi
}

frontend_health_lines() {
  # Port 8080 is always bound (HTTP or redirect); keep the health check simple for Quadlets.
  echo "HealthCmd=/usr/bin/wget -q --spider http://127.0.0.1:8080/"
  echo "HealthInterval=10s"
  echo "HealthTimeout=5s"
  echo "HealthRetries=3"
  if [[ "${USE_SSL}" -eq 1 ]]; then
    echo "HealthStartPeriod=30s"
  fi
}

backend_health_lines() {
  echo "HealthCmd=/app/backend-healthcheck.sh"
  echo "HealthInterval=10s"
  echo "HealthTimeout=5s"
  if [[ "${USE_SSL}" -eq 1 ]]; then
    echo "HealthRetries=8"
    echo "HealthStartPeriod=90s"
  else
    echo "HealthRetries=5"
    echo "HealthStartPeriod=15s"
  fi
}

cmd_generate() {
  require_install
  load_env
  detect_systemd_scope
  local wanted_by="default.target"
  if [[ "${SYSTEMD_SCOPE}" == "system" ]]; then
    wanted_by="multi-user.target"
  fi
  mkdir -p "${QUADLET_SRC}"
  write_container_env_files

  write_file "${QUADLET_SRC}/openflake-net.network" \
    "[Unit]" \
    "Description=OpenFlake container network" \
    "" \
    "[Network]" \
    "NetworkName=openflake-net" \
    "" \
    "[Install]" \
    "WantedBy=${wanted_by}"

  write_file "${QUADLET_SRC}/openflake-pg-data.volume" \
    "[Unit]" \
    "Description=OpenFlake PostgreSQL data" \
    "" \
    "[Volume]" \
    "VolumeName=openflake-pg-data" \
    "" \
    "[Install]" \
    "WantedBy=${wanted_by}"

  if [[ -z "${ATTACHMENTS_DIR}" ]]; then
    write_file "${QUADLET_SRC}/openflake-attachments.volume" \
      "[Unit]" \
      "Description=OpenFlake attachments storage" \
      "" \
      "[Volume]" \
      "VolumeName=openflake-attachments" \
      "" \
      "[Install]" \
      "WantedBy=${wanted_by}"
  fi

  {
    echo "[Unit]"
    echo "Description=OpenFlake PostgreSQL"
    echo "After=network-online.target"
    echo "Wants=network-online.target"
    echo ""
    echo "[Container]"
    echo "Image=docker.io/library/postgres:16-alpine"
    echo "ContainerName=openflake-postgres"
    echo "Network=openflake-net.network"
    echo "NetworkAlias=postgres"
    echo "EnvironmentFile=${QUADLET_SRC}/postgres.env"
    echo "Volume=openflake-pg-data.volume:/var/lib/postgresql/data"
    echo "Volume=${INSTALL_DIR}/pg_hba.conf:/etc/postgresql/pg_hba.conf:ro,Z"
    echo "PublishPort=5432:5432"
    echo "Exec=postgres -c listen_addresses='*' -c hba_file=/etc/postgresql/pg_hba.conf"
    echo "HealthCmd=/usr/bin/pg_isready -U openflake -d openflake"
    echo "HealthInterval=5s"
    echo "HealthTimeout=5s"
    echo "HealthRetries=10"
    echo ""
    echo "[Service]"
    echo "Restart=always"
    echo ""
    echo "[Install]"
    echo "WantedBy=${wanted_by}"
  } > "${QUADLET_SRC}/openflake-postgres.container"

  {
    echo "[Unit]"
    echo "Description=OpenFlake backend API"
    echo "After=network-online.target openflake-postgres.service"
    echo "Wants=network-online.target openflake-postgres.service"
    echo ""
    echo "[Container]"
    echo "Image=${REGISTRY}/openflake-backend:${IMAGE_TAG}"
    echo "ContainerName=openflake-backend"
    echo "Network=openflake-net.network"
    echo "EnvironmentFile=${QUADLET_SRC}/backend.env"
    backend_volume_lines
    backend_ssl_lines
    echo "PublishPort=8000:8000"
    backend_health_lines
    echo ""
    echo "[Service]"
    echo "Restart=always"
    echo ""
    echo "[Install]"
    echo "WantedBy=${wanted_by}"
  } > "${QUADLET_SRC}/openflake-backend.container"

  {
    echo "[Unit]"
    echo "Description=OpenFlake frontend UI"
    echo "After=network-online.target openflake-backend.service"
    echo "Wants=network-online.target openflake-backend.service"
    echo ""
    echo "[Container]"
    echo "Image=${REGISTRY}/openflake-frontend:${IMAGE_TAG}"
    echo "ContainerName=openflake-frontend"
    echo "Network=openflake-net.network"
    if [[ -s "${QUADLET_SRC}/frontend.env" ]]; then
      echo "EnvironmentFile=${QUADLET_SRC}/frontend.env"
    fi
    frontend_publish_lines
    frontend_ssl_lines
    frontend_health_lines
    echo ""
    echo "[Service]"
    echo "Restart=always"
    echo ""
    echo "[Install]"
    echo "WantedBy=${wanted_by}"
  } > "${QUADLET_SRC}/openflake-frontend.container"
}

run_as_systemd() {
  detect_systemd_scope
  if [[ "${SYSTEMD_SCOPE}" == "user" ]]; then
    systemctl --user "$@"
  elif [[ "${EUID}" -ne 0 ]]; then
    sudo systemctl "$@"
  else
    systemctl "$@"
  fi
}

copy_quadlets_to_systemd() {
  local dest
  dest="$(quadlet_systemd_dir)"
  if [[ "${SYSTEMD_SCOPE}" == "system" && "${EUID}" -ne 0 ]]; then
    sudo mkdir -p "${dest}"
    sudo cp "${QUADLET_SRC}/"* "${dest}/"
  else
    mkdir -p "${dest}"
    cp "${QUADLET_SRC}/"* "${dest}/"
  fi
}

verify_quadlet_systemd_dir() {
  local dest
  dest="$(quadlet_systemd_dir)"
  if [[ ! -d "${dest}" ]]; then
    echo "Quadlet systemd directory does not exist: ${dest}" >&2
    exit 1
  fi
  if ! compgen -G "${dest}/*.container" >/dev/null; then
    echo "No .container quadlet files in ${dest}" >&2
    echo "Expected generated files from ${QUADLET_SRC}" >&2
    ls -la "${dest}" >&2 || true
    exit 1
  fi
}

quadlet_generator_dryrun() {
  local dir="$1"
  local generator=""
  local -a generator_args=()

  if [[ ! -d "${dir}" ]]; then
    echo "Skipping generator dry-run; directory not found: ${dir}" >&2
    return 1
  fi

  if [[ "${SYSTEMD_SCOPE}" == "user" ]]; then
    if [[ -x /usr/lib/systemd/user-generators/podman-user-generator ]]; then
      generator="/usr/lib/systemd/user-generators/podman-user-generator"
    elif [[ -x /usr/lib/systemd/system-generators/podman-system-generator ]]; then
      generator="/usr/lib/systemd/system-generators/podman-system-generator"
      generator_args=(--user)
    fi
  elif [[ -x /usr/lib/systemd/system-generators/podman-system-generator ]]; then
    generator="/usr/lib/systemd/system-generators/podman-system-generator"
  fi

  if [[ -z "${generator}" ]]; then
    echo "Podman quadlet generator not found under /usr/lib/systemd/" >&2
    return 1
  fi

  echo "Running quadlet generator dry-run on ${dir}..." >&2
  QUADLET_UNIT_DIRS="${dir}" "${generator}" "${generator_args[@]}" --dryrun >&2 || true
}

collect_quadlet_files() {
  QUADLET_FILES=()
  local pattern path
  for pattern in '*.network' '*.volume' '*.container'; do
    for path in "${QUADLET_SRC}"/${pattern}; do
      [[ -f "${path}" ]] || continue
      QUADLET_FILES+=("${path}")
    done
  done
  if [[ ${#QUADLET_FILES[@]} -eq 0 ]]; then
    echo "No quadlet files found in ${QUADLET_SRC}" >&2
    exit 1
  fi
}

reload_quadlet_systemd() {
  run_as_systemd daemon-reload
}

diagnose_quadlet_failures() {
  local dest
  dest="$(quadlet_systemd_dir)"
  echo "Quadlet systemd units were not generated." >&2
  echo "Source quadlets: ${QUADLET_SRC}" >&2
  echo "Systemd quadlet dir: ${dest}" >&2
  echo "Source contents:" >&2
  ls -la "${QUADLET_SRC}" >&2 || true
  echo "Systemd dir contents:" >&2
  ls -la "${dest}" >&2 || true
  quadlet_generator_dryrun "${dest}" || quadlet_generator_dryrun "${QUADLET_SRC}" || true
  echo "Ensure Podman 4.4+ is installed and review files in ${QUADLET_SRC}." >&2
}

require_quadlet_services() {
  local unit missing=()
  for unit in openflake-postgres.service openflake-backend.service openflake-frontend.service; do
    if ! run_as_systemd cat "${unit}" >/dev/null 2>&1; then
      missing+=("${unit}")
    fi
  done
  if [[ ${#missing[@]} -gt 0 ]]; then
    echo "Missing generated units: ${missing[*]}" >&2
    diagnose_quadlet_failures
    exit 1
  fi
}

install_quadlet_files() {
  collect_quadlet_files
  copy_quadlets_to_systemd
  verify_quadlet_systemd_dir
  reload_quadlet_systemd
}

wait_for_postgres() {
  local elapsed=0
  local max_wait=60
  echo "Waiting for PostgreSQL..."
  until podman exec openflake-postgres pg_isready -U openflake -d openflake >/dev/null 2>&1; do
    if [[ "${elapsed}" -ge "${max_wait}" ]]; then
      echo "Timed out waiting for PostgreSQL after ${max_wait}s" >&2
      exit 1
    fi
    sleep 1
    elapsed=$((elapsed + 1))
  done
}

wait_for_backend() {
  require_install
  load_env
  local elapsed=0
  local max_wait="${OPENFLAKE_HEALTH_TIMEOUT:-120}"
  local curl_args=(-fsS)
  local url="http://localhost:8000/health/ready"
  if [[ "${USE_SSL}" -eq 1 ]]; then
    url="https://localhost:8000/health/ready"
    curl_args=(-fsSk)
  fi
  echo "Waiting for backend (up to ${max_wait}s)..."
  while [[ "${elapsed}" -lt "${max_wait}" ]]; do
    if curl "${curl_args[@]}" "${url}" >/dev/null 2>&1; then
      echo "Backend is ready."
      return 0
    fi
    sleep 2
    elapsed=$((elapsed + 2))
  done
  echo "Backend did not become ready within ${max_wait}s." >&2
  echo "Check logs: podman logs openflake-backend" >&2
  exit 1
}

show_unit_failure() {
  local unit="$1"
  echo "--- systemctl status ${unit} ---" >&2
  run_as_systemd status "${unit}" --no-pager >&2 || true
  echo "--- journalctl -u ${unit} (last 30 lines) ---" >&2
  if [[ "${SYSTEMD_SCOPE}" == "user" ]]; then
    journalctl --user -u "${unit}" -n 30 --no-pager >&2 || true
  else
    journalctl -u "${unit}" -n 30 --no-pager >&2 || true
  fi
}

start_stack_units() {
  detect_systemd_scope
  run_as_systemd reset-failed openflake-postgres.service openflake-backend.service openflake-frontend.service 2>/dev/null || true
  run_as_systemd start openflake-postgres.service
  wait_for_postgres
  run_as_systemd start openflake-backend.service
  wait_for_backend
  if ! run_as_systemd start openflake-frontend.service; then
    show_unit_failure openflake-frontend.service
    exit 1
  fi
  if ! podman container exists openflake-frontend 2>/dev/null; then
    echo "Frontend container did not start." >&2
    show_unit_failure openflake-frontend.service
    exit 1
  fi
  echo "Frontend is running."
}

enable_linger_if_needed() {
  if [[ "${SYSTEMD_SCOPE}" != "user" ]]; then
    return 0
  fi
  if ! command -v loginctl >/dev/null 2>&1; then
    return 0
  fi
  if loginctl show-user "$(id -un)" -p Linger 2>/dev/null | grep -q 'Linger=yes'; then
    return 0
  fi
  loginctl enable-linger "$(id -un)" 2>/dev/null || {
    echo "Enable lingering so OpenFlake starts at boot without a login session:" >&2
    echo "  sudo loginctl enable-linger $(id -un)" >&2
  }
}

cmd_pull() {
  require_install
  load_env
  podman pull docker.io/library/postgres:16-alpine
  podman pull "${REGISTRY}/openflake-backend:${IMAGE_TAG}"
  podman pull "${REGISTRY}/openflake-frontend:${IMAGE_TAG}"
}

cmd_deploy() {
  require_install
  if ! command -v systemctl >/dev/null 2>&1; then
    echo "systemctl not found; cannot deploy quadlets." >&2
    exit 1
  fi
  if [[ ! -d "${QUADLET_SRC}" ]]; then
    cmd_generate
  fi
  detect_systemd_scope
  enable_linger_if_needed
  install_quadlet_files
  require_quadlet_services
}

cmd_install() {
  cmd_deploy
  # Quadlet units are transient; [Install] in .container files is applied at
  # daemon-reload — do not run systemctl enable on them.
  start_stack_units
}

cmd_start() {
  start_stack_units
}

cmd_stop() {
  detect_systemd_scope
  run_as_systemd stop openflake-frontend.service openflake-backend.service openflake-postgres.service
}

cmd_restart() {
  cmd_stop
  cmd_start
}

cmd_restart_apps() {
  detect_systemd_scope
  run_as_systemd restart openflake-backend.service
  wait_for_backend
  if ! run_as_systemd restart openflake-frontend.service; then
    show_unit_failure openflake-frontend.service
    exit 1
  fi
}

cmd_status() {
  podman ps --filter name=openflake- --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
}

require_install

case "${1:-}" in
  generate) cmd_generate ;;
  deploy) cmd_deploy ;;
  install) cmd_install ;;
  pull) cmd_pull ;;
  start) cmd_start ;;
  stop) cmd_stop ;;
  restart) cmd_restart ;;
  restart-apps) cmd_restart_apps ;;
  status) cmd_status ;;
  -h|--help|"") usage; exit 0 ;;
  *) echo "Unknown command: $1" >&2; usage >&2; exit 1 ;;
esac
