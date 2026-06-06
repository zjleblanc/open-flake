#!/bin/sh
set -e

CONF="/etc/nginx/conf.d/default.conf"
FLAG="/var/run/nginx-ssl-enabled"
SSL_DIR="/etc/nginx/certs"
SSL_CERT="${OPENFLAKE_SSL_CERT:-fullchain.pem}"
SSL_KEY="${OPENFLAKE_SSL_KEY:-privkey.pem}"
CERT_PATH="${SSL_DIR}/${SSL_CERT}"
KEY_PATH="${SSL_DIR}/${SSL_KEY}"
HTTPS_PORT="${OPENFLAKE_HTTPS_PORT:-8443}"

https_port_suffix() {
  if [ "${HTTPS_PORT}" = "443" ]; then
    echo ""
  else
    echo ":${HTTPS_PORT}"
  fi
}

fail_ssl() {
  echo "$1" >&2
  exit 1
}

if [ -f "${CERT_PATH}" ] && [ -f "${KEY_PATH}" ]; then
  if [ ! -r "${CERT_PATH}" ] || [ ! -r "${KEY_PATH}" ]; then
    # shellcheck source=/dev/null
    . /docker-entrypoint.d/ssl-readability-hint.sh
    ssl_print_unreadable_hint "${SSL_DIR}" "${SSL_CERT}" "${SSL_KEY}"
    exit 1
  fi
  echo "SSL certificates found; enabling HTTPS on port 443"
  echo "  certificate: ${CERT_PATH}"
  echo "  key: ${KEY_PATH}"
  PORT_SUFFIX="$(https_port_suffix)"
  sed \
    -e "s|__SSL_CERT__|${CERT_PATH}|g" \
    -e "s|__SSL_KEY__|${KEY_PATH}|g" \
    /etc/nginx/templates/ssl.conf > /tmp/ssl.conf
  sed "s|__HTTPS_PORT_SUFFIX__|${PORT_SUFFIX}|g" \
    /etc/nginx/templates/http-redirect.conf > /tmp/http-redirect.conf
  cat /tmp/http-redirect.conf /tmp/ssl.conf > "$CONF"
  touch "$FLAG"
  nginx -t
elif [ "${OPENFLAKE_SSL_REQUIRED:-0}" = "1" ]; then
  fail_ssl "OPENFLAKE_SSL_REQUIRED is set but TLS files are missing in ${SSL_DIR}.
Expected: ${CERT_PATH} and ${KEY_PATH}"
else
  echo "No SSL certificates found; serving HTTP only on port 8080"
  echo "  expected certificate: ${CERT_PATH}"
  echo "  expected key: ${KEY_PATH}"
  cp /etc/nginx/templates/http.conf "$CONF"
  rm -f "$FLAG"
  nginx -t
fi
