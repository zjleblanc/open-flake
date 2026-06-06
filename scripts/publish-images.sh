#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

REGISTRY="${OPENFLAKE_REGISTRY:-quay.io/zjleblanc}"
TAG="${OPENFLAKE_IMAGE_TAG:-latest}"
PUSH=0

usage() {
  cat <<EOF
Usage: publish-images.sh [OPTIONS]

Build OpenFlake container images locally. Optionally push to a registry.

Environment variables:
  OPENFLAKE_REGISTRY   Registry prefix (default: quay.io/zjleblanc)
  OPENFLAKE_IMAGE_TAG  Image tag (default: latest)
  QUAY_USERNAME        Registry username (required with --push)
  QUAY_TOKEN           Registry token or password (required with --push)

Options:
  --push               Login and push images after build
  --tag TAG            Same as OPENFLAKE_IMAGE_TAG
  --registry REGISTRY  Same as OPENFLAKE_REGISTRY
  -h, --help           Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --push) PUSH=1; shift ;;
    --tag) TAG="$2"; shift 2 ;;
    --registry) REGISTRY="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 1 ;;
  esac
done

BACKEND_IMAGE="${REGISTRY}/openflake-backend:${TAG}"
FRONTEND_IMAGE="${REGISTRY}/openflake-frontend:${TAG}"

echo "Building ${BACKEND_IMAGE}..."
podman build -f deploy/Containerfile.backend -t "${BACKEND_IMAGE}" .

echo "Building ${FRONTEND_IMAGE}..."
podman build -f deploy/Containerfile.frontend -t "${FRONTEND_IMAGE}" .

echo "Built:"
echo "  ${BACKEND_IMAGE}"
echo "  ${FRONTEND_IMAGE}"

if [[ "${PUSH}" -eq 1 ]]; then
  if [[ -z "${QUAY_USERNAME:-}" || -z "${QUAY_TOKEN:-}" ]]; then
    echo "QUAY_USERNAME and QUAY_TOKEN are required for --push" >&2
    exit 1
  fi
  echo "Logging in to ${REGISTRY%%/*}..."
  echo "${QUAY_TOKEN}" | podman login "${REGISTRY%%/*}" -u "${QUAY_USERNAME}" --password-stdin
  echo "Pushing images..."
  podman push "${BACKEND_IMAGE}"
  podman push "${FRONTEND_IMAGE}"
  echo "Push complete."
fi
