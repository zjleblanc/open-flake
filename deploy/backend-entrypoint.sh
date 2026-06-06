#!/bin/sh
set -e

SSL_DIR="/etc/openflake/certs"
SSL_CERT="${OPENFLAKE_SSL_CERT:-fullchain.pem}"
SSL_KEY="${OPENFLAKE_SSL_KEY:-privkey.pem}"
CERT_PATH="${SSL_DIR}/${SSL_CERT}"
KEY_PATH="${SSL_DIR}/${SSL_KEY}"

if [ -f "${CERT_PATH}" ] && [ -f "${KEY_PATH}" ]; then
    if [ ! -r "${CERT_PATH}" ] || [ ! -r "${KEY_PATH}" ]; then
        echo "TLS certificate files are not readable inside the container." >&2
        exit 1
    fi
    echo "SSL certificates found; enabling HTTPS on port 8000"
    echo "  certificate: ${CERT_PATH}"
    echo "  key: ${KEY_PATH}"
    exec uvicorn app.main:app \
        --host 0.0.0.0 \
        --port 8000 \
        --ssl-certfile "${CERT_PATH}" \
        --ssl-keyfile "${KEY_PATH}"
fi

if [ "${OPENFLAKE_SSL_REQUIRED:-0}" = "1" ]; then
    echo "OPENFLAKE_SSL_REQUIRED is set but TLS files are missing in ${SSL_DIR}." >&2
    echo "  expected certificate: ${CERT_PATH}" >&2
    echo "  expected key: ${KEY_PATH}" >&2
    exit 1
fi

echo "No SSL certificates found; serving HTTP only on port 8000"
echo "  expected certificate: ${CERT_PATH}"
echo "  expected key: ${KEY_PATH}"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
