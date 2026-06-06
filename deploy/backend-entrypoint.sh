#!/bin/sh
set -e

SSL_DIR="/etc/openflake/certs"
SSL_CERT="${OPENFLAKE_SSL_CERT:-fullchain.pem}"
SSL_KEY="${OPENFLAKE_SSL_KEY:-privkey.pem}"
CERT_PATH="${SSL_DIR}/${SSL_CERT}"
KEY_PATH="${SSL_DIR}/${SSL_KEY}"

if [ -f "${CERT_PATH}" ] && [ -f "${KEY_PATH}" ]; then
    echo "SSL certificates found; enabling HTTPS on port 8000"
    echo "  certificate: ${CERT_PATH}"
    echo "  key: ${KEY_PATH}"
    exec uvicorn app.main:app \
        --host 0.0.0.0 \
        --port 8000 \
        --ssl-certfile "${CERT_PATH}" \
        --ssl-keyfile "${KEY_PATH}"
fi

echo "No SSL certificates found; serving HTTP only on port 8000"
echo "  expected certificate: ${CERT_PATH}"
echo "  expected key: ${KEY_PATH}"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
