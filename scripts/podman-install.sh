#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "${SCRIPT_DIR}/openflake.env" ]]; then
  # shellcheck source=/dev/null
  source "${SCRIPT_DIR}/openflake.env"
fi

GITHUB_REPO="${OPENFLAKE_GITHUB_REPO:-zjleblanc/open-flake}"
GITHUB_REF="${OPENFLAKE_VERSION:-main}"
GITHUB_RAW="https://raw.githubusercontent.com/${GITHUB_REPO}/${GITHUB_REF}"

INSTALL_DIR="${OPENFLAKE_INSTALL_DIR:-${HOME}/.local/share/openflake}"
DOMAIN="${OPENFLAKE_DOMAIN:-localhost}"
SSL_DIR="${OPENFLAKE_SSL_DIR:-${OPENFLAKE_CERT_DIR:-}}"
SSL_CERT="${OPENFLAKE_SSL_CERT:-fullchain.pem}"
SSL_KEY="${OPENFLAKE_SSL_KEY:-privkey.pem}"
ATTACHMENTS_DIR="${OPENFLAKE_ATTACHMENTS_DIR:-}"
IMAGE_TAG="${OPENFLAKE_IMAGE_TAG:-latest}"
REGISTRY="${OPENFLAKE_REGISTRY:-quay.io/zleblanc}"
HTTPS_PORT="${OPENFLAKE_HTTPS_PORT:-8443}"
HTTP_ONLY=0

usage() {
  cat <<EOF
Usage: podman-install.sh [OPTIONS]

Install OpenFlake from container registry images (Quay.io by default).

Environment variables:
  OPENFLAKE_INSTALL_DIR   Install directory (default: ~/.local/share/openflake)
  OPENFLAKE_DOMAIN        Public hostname (default: localhost)
  OPENFLAKE_HTTPS_PORT    Host HTTPS port (default: 8443; rootless-safe, maps to container 443)
  OPENFLAKE_SSL_DIR       TLS certificate directory (required for HTTPS)
  OPENFLAKE_SSL_CERT      Certificate filename in SSL_DIR (default: fullchain.pem)
  OPENFLAKE_SSL_KEY       Private key filename in SSL_DIR (default: privkey.pem)
  OPENFLAKE_ATTACHMENTS_DIR  Host path for attachment storage
  OPENFLAKE_IMAGE_TAG     Image tag to pull (default: latest)
  OPENFLAKE_REGISTRY      Image registry (default: quay.io/zleblanc)
  OPENFLAKE_VERSION       Git ref for compose files (default: main)
  SECRET_KEY              Backend signing key (auto-generated if unset)
  POSTGRES_PASSWORD       Database password (default: openflake)
  ADMIN_PASSWORD          Admin user password (default: admin)

If openflake.env exists next to this script, it is sourced before options and env vars above.

Options:
  --domain DOMAIN         Same as OPENFLAKE_DOMAIN
  --ssl-dir PATH          Same as OPENFLAKE_SSL_DIR
  --ssl-cert NAME         Same as OPENFLAKE_SSL_CERT
  --ssl-key NAME          Same as OPENFLAKE_SSL_KEY
  --attachments-dir PATH  Same as OPENFLAKE_ATTACHMENTS_DIR
  --cert-dir PATH         Deprecated alias for --ssl-dir
  --tag TAG               Same as OPENFLAKE_IMAGE_TAG
  --install-dir PATH      Same as OPENFLAKE_INSTALL_DIR
  --http-only             Skip HTTPS; serve UI on port 8080 only
  -h, --help              Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain) DOMAIN="$2"; shift 2 ;;
    --ssl-dir) SSL_DIR="$2"; shift 2 ;;
    --ssl-cert) SSL_CERT="$2"; shift 2 ;;
    --ssl-key) SSL_KEY="$2"; shift 2 ;;
    --attachments-dir) ATTACHMENTS_DIR="$2"; shift 2 ;;
    --cert-dir) SSL_DIR="$2"; shift 2 ;;
    --tag) IMAGE_TAG="$2"; shift 2 ;;
    --install-dir) INSTALL_DIR="$2"; shift 2 ;;
    --http-only) HTTP_ONLY=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 1 ;;
  esac
done

run_compose() {
  if podman compose version >/dev/null 2>&1; then
    podman compose "$@"
  elif command -v podman-compose >/dev/null 2>&1; then
    podman-compose "$@"
  else
    echo "Podman Compose is not available. Install podman-compose or use Podman 4.1+ with compose support." >&2
    exit 1
  fi
}

require_podman() {
  if ! podman info >/dev/null 2>&1; then
    echo "Podman is not running." >&2
    echo "Start it with: podman machine start" >&2
    exit 1
  fi
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
  if [[ ! -r "${dir}/${cert}" || ! -r "${dir}/${key}" ]]; then
    echo "TLS certificate files exist but are not readable by $(id -un) (uid $(id -u))." >&2
    echo "Rootless Podman bind mounts use your host user for permission checks, not container root." >&2
    echo "root:root mode 600 files (typical after copying from Let's Encrypt) cannot be read even with container_file_t." >&2
    ls -la "${dir}/${cert}" "${dir}/${key}" >&2 || true
    echo "Fix with:" >&2
    echo "  sudo chmod 644 ${dir}/${cert} ${dir}/${key}" >&2
    exit 1
  fi
}

ssl_mount_host_dir() {
  local mount_spec="$1"
  echo "${mount_spec%%:*}"
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

derive_urls() {
  if [[ "${HTTP_ONLY}" -eq 1 ]]; then
    OPENFLAKE_BASE_URL="http://localhost:8000"
    OPENFLAKE_CORS_ORIGINS="http://localhost:8080,http://localhost:5173"
    return
  fi
  local ui_origin="https://${DOMAIN}"
  if [[ "${HTTPS_PORT}" != "443" ]]; then
    ui_origin="https://${DOMAIN}:${HTTPS_PORT}"
  fi
  OPENFLAKE_BASE_URL="${ui_origin}"
  OPENFLAKE_CORS_ORIGINS="${ui_origin},https://${DOMAIN}:5173,http://localhost:8080,http://localhost:5173"
}

download_file() {
  local dest="$1"
  local url="$2"
  curl -fsSL -o "${dest}" "${url}"
}

generate_secret_key() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 32
  else
    python3 -c "import secrets; print(secrets.token_hex(32))"
  fi
}

attachments_mount() {
  local dir="$1"
  echo "${dir}:/data/attachments"
}

ssl_mounts() {
  local dir="$1"
  OPENFLAKE_SSL_BACKEND_MOUNT="${dir}:/etc/openflake/certs:ro"
  OPENFLAKE_SSL_FRONTEND_MOUNT="${dir}:/etc/nginx/certs:ro"
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

require_podman

if [[ "${HTTP_ONLY}" -eq 0 ]]; then
  if [[ -z "${SSL_DIR}" ]]; then
    echo "OPENFLAKE_SSL_DIR is required for HTTPS install (or pass --http-only)." >&2
    exit 1
  fi
  validate_certs "${SSL_DIR}" "${SSL_CERT}" "${SSL_KEY}"
fi

derive_urls

mkdir -p "${INSTALL_DIR}"

SECRET_KEY="${SECRET_KEY:-$(generate_secret_key)}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-openflake}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin}"

if [[ "${HTTP_ONLY}" -eq 0 ]]; then
  ssl_mounts "${SSL_DIR}"
fi

cat > "${INSTALL_DIR}/.env" <<EOF
OPENFLAKE_REGISTRY=${REGISTRY}
OPENFLAKE_IMAGE_TAG=${IMAGE_TAG}
OPENFLAKE_DOMAIN=${DOMAIN}
OPENFLAKE_SSL_DIR=${SSL_DIR}
OPENFLAKE_SSL_CERT=${SSL_CERT}
OPENFLAKE_SSL_KEY=${SSL_KEY}
OPENFLAKE_BASE_URL=${OPENFLAKE_BASE_URL}
OPENFLAKE_CORS_ORIGINS=${OPENFLAKE_CORS_ORIGINS}
SECRET_KEY=${SECRET_KEY}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
ADMIN_USERNAME=admin
ADMIN_PASSWORD=${ADMIN_PASSWORD}
TRUSTED_PROXIES=*
EOF
if [[ "${HTTP_ONLY}" -eq 0 ]]; then
  cat >> "${INSTALL_DIR}/.env" <<EOF
OPENFLAKE_HTTPS_PORT=${HTTPS_PORT}
OPENFLAKE_SSL_BACKEND_MOUNT=${OPENFLAKE_SSL_BACKEND_MOUNT}
OPENFLAKE_SSL_FRONTEND_MOUNT=${OPENFLAKE_SSL_FRONTEND_MOUNT}
EOF
fi
if [[ -n "${ATTACHMENTS_DIR}" ]]; then
  echo "OPENFLAKE_ATTACHMENTS_DIR=${ATTACHMENTS_DIR}" >> "${INSTALL_DIR}/.env"
  echo "OPENFLAKE_ATTACHMENTS_MOUNT=$(attachments_mount "${ATTACHMENTS_DIR}")" >> "${INSTALL_DIR}/.env"
fi

echo "Downloading compose files to ${INSTALL_DIR}..."
download_file "${INSTALL_DIR}/podman-compose.registry.yaml" \
  "${GITHUB_RAW}/deploy/podman-compose.registry.yaml"
download_file "${INSTALL_DIR}/podman-compose.ssl.yaml" \
  "${GITHUB_RAW}/deploy/podman-compose.ssl.yaml"
download_file "${INSTALL_DIR}/podman-upgrade.sh" \
  "${GITHUB_RAW}/scripts/podman-upgrade.sh"
chmod +x "${INSTALL_DIR}/podman-upgrade.sh"

COMPOSE_FILES=(-f "${INSTALL_DIR}/podman-compose.registry.yaml")
if [[ "${HTTP_ONLY}" -eq 0 ]]; then
  COMPOSE_FILES+=(-f "${INSTALL_DIR}/podman-compose.ssl.yaml")
fi

cd "${INSTALL_DIR}"
if [[ "${HTTP_ONLY}" -eq 0 ]]; then
  ensure_ssl_mount_env
  load_compose_env
  require_ssl_mount_vars
  validate_ssl_mount_certs "${OPENFLAKE_SSL_BACKEND_MOUNT}" "${SSL_CERT}" "${SSL_KEY}"
fi
echo "Pulling images..."
run_compose "${COMPOSE_FILES[@]}" --env-file "${INSTALL_DIR}/.env" pull

echo "Starting OpenFlake..."
if [[ "${HTTP_ONLY}" -eq 0 ]]; then
  load_compose_env
fi
run_compose "${COMPOSE_FILES[@]}" --env-file "${INSTALL_DIR}/.env" up -d

echo "${IMAGE_TAG}" > "${INSTALL_DIR}/installed-version"

if [[ "${HTTP_ONLY}" -eq 1 ]]; then
  UI_URL="http://localhost:8080"
elif [[ "${HTTPS_PORT}" != "443" ]]; then
  UI_URL="https://${DOMAIN}:${HTTPS_PORT}"
else
  UI_URL="https://${DOMAIN}"
fi

cat <<EOF

OpenFlake is running.

  UI:      ${UI_URL}
  API:     http://localhost:8000
  Login:   admin / (password from ADMIN_PASSWORD in ${INSTALL_DIR}/.env)
  Install: ${INSTALL_DIR}
  Data:    podman volumes openflake-pg-data, openflake-attachments
  Version: ${IMAGE_TAG}

Upgrade later with:
  OPENFLAKE_IMAGE_TAG=<new-tag> ${INSTALL_DIR}/podman-upgrade.sh
EOF
