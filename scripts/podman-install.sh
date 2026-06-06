#!/usr/bin/env bash
set -euo pipefail

GITHUB_REPO="${OPENFLAKE_GITHUB_REPO:-zjleblanc/open-flake}"
GITHUB_REF="${OPENFLAKE_VERSION:-main}"
GITHUB_RAW="https://raw.githubusercontent.com/${GITHUB_REPO}/${GITHUB_REF}"

INSTALL_DIR="${OPENFLAKE_INSTALL_DIR:-${HOME}/.local/share/openflake}"
DOMAIN="${OPENFLAKE_DOMAIN:-localhost}"
CERT_DIR="${OPENFLAKE_CERT_DIR:-}"
IMAGE_TAG="${OPENFLAKE_IMAGE_TAG:-latest}"
REGISTRY="${OPENFLAKE_REGISTRY:-quay.io/zjleblanc}"
HTTP_ONLY=0

usage() {
  cat <<EOF
Usage: podman-install.sh [OPTIONS]

Install OpenFlake from container registry images (Quay.io by default).

Environment variables:
  OPENFLAKE_INSTALL_DIR   Install directory (default: ~/.local/share/openflake)
  OPENFLAKE_DOMAIN        Public hostname (default: localhost)
  OPENFLAKE_CERT_DIR      Path to fullchain.pem and privkey.pem (required for HTTPS)
  OPENFLAKE_IMAGE_TAG     Image tag to pull (default: latest)
  OPENFLAKE_REGISTRY      Image registry (default: quay.io/zjleblanc)
  OPENFLAKE_VERSION       Git ref for compose files (default: main)
  SECRET_KEY              Backend signing key (auto-generated if unset)
  POSTGRES_PASSWORD       Database password (default: openflake)
  ADMIN_PASSWORD          Admin user password (default: admin)

Options:
  --domain DOMAIN         Same as OPENFLAKE_DOMAIN
  --cert-dir PATH         Same as OPENFLAKE_CERT_DIR
  --tag TAG               Same as OPENFLAKE_IMAGE_TAG
  --install-dir PATH      Same as OPENFLAKE_INSTALL_DIR
  --http-only             Skip HTTPS; serve UI on port 8080 only
  -h, --help              Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain) DOMAIN="$2"; shift 2 ;;
    --cert-dir) CERT_DIR="$2"; shift 2 ;;
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
  if [[ ! -f "${dir}/fullchain.pem" || ! -f "${dir}/privkey.pem" ]]; then
    echo "TLS certificates not found in ${dir}" >&2
    echo "Expected: fullchain.pem and privkey.pem" >&2
    exit 1
  fi
}

derive_urls() {
  if [[ "${HTTP_ONLY}" -eq 1 ]]; then
    OPENFLAKE_BASE_URL="http://localhost:8000"
    OPENFLAKE_CORS_ORIGINS="http://localhost:8080,http://localhost:5173"
    return
  fi
  OPENFLAKE_BASE_URL="https://${DOMAIN}"
  OPENFLAKE_CORS_ORIGINS="https://${DOMAIN},https://${DOMAIN}:5173,http://localhost:8080,http://localhost:5173"
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

require_podman

if [[ "${HTTP_ONLY}" -eq 0 ]]; then
  if [[ -z "${CERT_DIR}" ]]; then
    echo "OPENFLAKE_CERT_DIR is required for HTTPS install (or pass --http-only)." >&2
    exit 1
  fi
  validate_certs "${CERT_DIR}"
fi

derive_urls

mkdir -p "${INSTALL_DIR}"

SECRET_KEY="${SECRET_KEY:-$(generate_secret_key)}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-openflake}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin}"

cat > "${INSTALL_DIR}/.env" <<EOF
OPENFLAKE_REGISTRY=${REGISTRY}
OPENFLAKE_IMAGE_TAG=${IMAGE_TAG}
OPENFLAKE_DOMAIN=${DOMAIN}
OPENFLAKE_CERT_DIR=${CERT_DIR}
OPENFLAKE_BASE_URL=${OPENFLAKE_BASE_URL}
OPENFLAKE_CORS_ORIGINS=${OPENFLAKE_CORS_ORIGINS}
SECRET_KEY=${SECRET_KEY}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
ADMIN_USERNAME=admin
ADMIN_PASSWORD=${ADMIN_PASSWORD}
TRUSTED_PROXIES=*
EOF

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
echo "Pulling images..."
run_compose "${COMPOSE_FILES[@]}" --env-file "${INSTALL_DIR}/.env" pull

echo "Starting OpenFlake..."
run_compose "${COMPOSE_FILES[@]}" --env-file "${INSTALL_DIR}/.env" up -d

echo "${IMAGE_TAG}" > "${INSTALL_DIR}/installed-version"

if [[ "${HTTP_ONLY}" -eq 1 ]]; then
  UI_URL="http://localhost:8080"
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
