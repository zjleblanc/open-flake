#!/bin/sh
set -e

CONF="/etc/nginx/conf.d/default.conf"
FLAG="/var/run/nginx-ssl-enabled"
SSL_DIR="/etc/nginx/certs"
SSL_CERT="${OPENFLAKE_SSL_CERT:-fullchain.pem}"
SSL_KEY="${OPENFLAKE_SSL_KEY:-privkey.pem}"
CERT_PATH="${SSL_DIR}/${SSL_CERT}"
KEY_PATH="${SSL_DIR}/${SSL_KEY}"

if [ -f "${CERT_PATH}" ] && [ -f "${KEY_PATH}" ]; then
    echo "SSL certificates found; enabling HTTPS on port 443"
    echo "  certificate: ${CERT_PATH}"
    echo "  key: ${KEY_PATH}"
    sed \
        -e "s|__SSL_CERT__|${CERT_PATH}|g" \
        -e "s|__SSL_KEY__|${KEY_PATH}|g" \
        /etc/nginx/templates/ssl.conf > /tmp/ssl.conf
    cat /etc/nginx/templates/http-redirect.conf /tmp/ssl.conf > "$CONF"
    touch "$FLAG"
else
    echo "No SSL certificates found; serving HTTP only on port 8080"
    echo "  expected certificate: ${CERT_PATH}"
    echo "  expected key: ${KEY_PATH}"
    cp /etc/nginx/templates/http.conf "$CONF"
    rm -f "$FLAG"
fi
