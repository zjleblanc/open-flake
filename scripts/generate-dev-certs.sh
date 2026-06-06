#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CERT_DIR="${ROOT}/deploy/certs"
DOMAIN="${OPENFLAKE_DOMAIN:-localhost}"

mkdir -p "${CERT_DIR}"

openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
  -keyout "${CERT_DIR}/privkey.pem" \
  -out "${CERT_DIR}/fullchain.pem" \
  -subj "/CN=${DOMAIN}" \
  -addext "subjectAltName=DNS:${DOMAIN},DNS:localhost,IP:127.0.0.1"

chmod 600 "${CERT_DIR}/privkey.pem"
chmod 644 "${CERT_DIR}/fullchain.pem"

echo "Generated self-signed certificates in ${CERT_DIR}/"
echo "  fullchain.pem"
echo "  privkey.pem"
