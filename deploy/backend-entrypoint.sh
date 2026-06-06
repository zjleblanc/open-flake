#!/bin/sh
set -e

SSL_DIR="/etc/openflake/certs"
RUN_SSL_DIR="/run/openflake/certs"
SSL_CERT="${OPENFLAKE_SSL_CERT:-fullchain.pem}"
SSL_KEY="${OPENFLAKE_SSL_KEY:-privkey.pem}"
CERT_PATH="${SSL_DIR}/${SSL_CERT}"
KEY_PATH="${SSL_DIR}/${SSL_KEY}"

run_uvicorn() {
  exec gosu openflake uvicorn app.main:app "$@"
}

if [ -f "${CERT_PATH}" ] && [ -f "${KEY_PATH}" ]; then
  if [ ! -r "${CERT_PATH}" ] || [ ! -r "${KEY_PATH}" ]; then
    # shellcheck source=/dev/null
    . /app/ssl-readability-hint.sh
    ssl_print_unreadable_hint "${SSL_DIR}" "${SSL_CERT}" "${SSL_KEY}"
    exit 1
  fi
  install -d -o openflake -g openflake -m 750 "${RUN_SSL_DIR}"
  install -o openflake -g openflake -m 640 "${CERT_PATH}" "${RUN_SSL_DIR}/${SSL_CERT}"
  install -o openflake -g openflake -m 640 "${KEY_PATH}" "${RUN_SSL_DIR}/${SSL_KEY}"
  echo "SSL certificates found; enabling HTTPS on port 8000"
  echo "  certificate: ${RUN_SSL_DIR}/${SSL_CERT}"
  echo "  key: ${RUN_SSL_DIR}/${SSL_KEY}"
  run_uvicorn \
    --host 0.0.0.0 \
    --port 8000 \
    --ssl-certfile "${RUN_SSL_DIR}/${SSL_CERT}" \
    --ssl-keyfile "${RUN_SSL_DIR}/${SSL_KEY}"
fi

if [ "${OPENFLAKE_SSL_REQUIRED:-0}" = "1" ]; then
  echo "OPENFLAKE_SSL_REQUIRED is set but TLS files are missing in ${SSL_DIR}." >&2
  echo "  expected certificate: ${CERT_PATH}" >&2
  echo "  expected key: ${KEY_PATH}" >&2
  echo "  OPENFLAKE_SSL_CERT=${SSL_CERT} OPENFLAKE_SSL_KEY=${SSL_KEY}" >&2
  if [ -d "${SSL_DIR}" ]; then
    echo "  contents of ${SSL_DIR}:" >&2
    ls -la "${SSL_DIR}" >&2 || true
  else
    echo "  ${SSL_DIR} does not exist (certificate volume may not be mounted)." >&2
  fi
  echo "On the host, confirm OPENFLAKE_SSL_DIR has those files and .env includes:" >&2
  echo "  OPENFLAKE_SSL_BACKEND_MOUNT=<that-dir>:/etc/openflake/certs:ro" >&2
  echo "Then recreate: source .env && podman-compose -f podman-compose.registry.yaml -f podman-compose.ssl.yaml up -d --force-recreate backend" >&2
  exit 1
fi

echo "No SSL certificates found; serving HTTP only on port 8000"
echo "  expected certificate: ${CERT_PATH}"
echo "  expected key: ${KEY_PATH}"
run_uvicorn --host 0.0.0.0 --port 8000
