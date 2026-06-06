#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

REGISTRY="${OPENFLAKE_REGISTRY:-quay.io/zjleblanc}"
TAG="${OPENFLAKE_IMAGE_TAG:-latest}"
PLATFORMS="${OPENFLAKE_PLATFORMS:-linux/amd64,linux/arm64}"
PUSH=0
SINGLE_ARCH=0
PLATFORM_LIST=()

usage() {
  cat <<EOF
Usage: publish-images.sh [OPTIONS]

Build OpenFlake container images locally. By default builds multi-arch
manifests for linux/amd64 and linux/arm64.

Environment variables:
  OPENFLAKE_REGISTRY    Registry prefix (default: quay.io/zjleblanc)
  OPENFLAKE_IMAGE_TAG   Image tag (default: latest)
  OPENFLAKE_PLATFORMS   Comma-separated platforms (default: linux/amd64,linux/arm64)
  QUAY_USERNAME         Registry username (required with --push)
  QUAY_TOKEN            Registry token or password (required with --push)

Options:
  --push                Login and push images after build
  --tag TAG             Same as OPENFLAKE_IMAGE_TAG
  --registry REGISTRY   Same as OPENFLAKE_REGISTRY
  --platforms LIST      Same as OPENFLAKE_PLATFORMS
  --single-arch         Build for the host architecture only (no manifest)
  -h, --help            Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --push) PUSH=1; shift ;;
    --tag) TAG="$2"; shift 2 ;;
    --registry) REGISTRY="$2"; shift 2 ;;
    --platforms) PLATFORMS="$2"; shift 2 ;;
    --single-arch) SINGLE_ARCH=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 1 ;;
  esac
done

parse_platforms() {
  PLATFORM_LIST=()
  local IFS=','
  read -ra PLATFORM_LIST <<< "${PLATFORMS}"
  for i in "${!PLATFORM_LIST[@]}"; do
    PLATFORM_LIST[$i]="${PLATFORM_LIST[$i]// /}"
  done

  if [[ "${SINGLE_ARCH}" -eq 1 ]]; then
    local host_arch
    host_arch="$(uname -m)"
    case "${host_arch}" in
      x86_64) PLATFORM_LIST=("linux/amd64") ;;
      aarch64|arm64) PLATFORM_LIST=("linux/arm64") ;;
      *) echo "Unsupported host architecture: ${host_arch}" >&2; exit 1 ;;
    esac
  fi
}

build_image() {
  local dockerfile="$1"
  local image="$2"

  if [[ "${#PLATFORM_LIST[@]}" -eq 1 ]]; then
    local platform="${PLATFORM_LIST[0]}"
    echo "Building ${image} (${platform})..."
    podman build --platform "${platform}" -f "${dockerfile}" -t "${image}" .
    if [[ "${PUSH}" -eq 1 ]]; then
      podman push "${image}"
    fi
    return
  fi

  echo "Building multi-arch manifest for ${image}..."
  podman manifest rm "${image}" 2>/dev/null || true
  podman manifest create "${image}"

  for platform in "${PLATFORM_LIST[@]}"; do
    local arch="${platform##*/}"
    local arch_image="${image}-${arch}"
    echo "  ${platform} -> ${arch_image}"
    podman build --platform "${platform}" -f "${dockerfile}" -t "${arch_image}" .
    podman manifest add "${image}" "${arch_image}"
  done

  if [[ "${PUSH}" -eq 1 ]]; then
    podman manifest push "${image}" "${image}"
  fi
}

if [[ "${PUSH}" -eq 1 ]]; then
  if [[ -z "${QUAY_USERNAME:-}" || -z "${QUAY_TOKEN:-}" ]]; then
    echo "QUAY_USERNAME and QUAY_TOKEN are required for --push" >&2
    exit 1
  fi
  echo "Logging in to ${REGISTRY%%/*}..."
  echo "${QUAY_TOKEN}" | podman login "${REGISTRY%%/*}" -u "${QUAY_USERNAME}" --password-stdin
fi

parse_platforms

BACKEND_IMAGE="${REGISTRY}/openflake-backend:${TAG}"
FRONTEND_IMAGE="${REGISTRY}/openflake-frontend:${TAG}"

build_image deploy/Containerfile.backend "${BACKEND_IMAGE}"
build_image deploy/Containerfile.frontend "${FRONTEND_IMAGE}"

echo "Built:"
echo "  ${BACKEND_IMAGE}"
echo "  ${FRONTEND_IMAGE}"
if [[ "${#PLATFORM_LIST[@]}" -gt 1 ]]; then
  echo "Platforms: $(IFS=','; echo "${PLATFORM_LIST[*]}")"
fi

if [[ "${PUSH}" -eq 1 ]]; then
  echo "Push complete."
fi
