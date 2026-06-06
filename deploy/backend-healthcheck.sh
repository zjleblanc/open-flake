#!/bin/sh
set -e

SSL_DIR="/etc/openflake/certs"
SSL_CERT="${OPENFLAKE_SSL_CERT:-fullchain.pem}"
SSL_KEY="${OPENFLAKE_SSL_KEY:-privkey.pem}"
TIMEOUT="${OPENFLAKE_HEALTHCHECK_TIMEOUT:-5}"

use_https=0
if [ "${OPENFLAKE_SSL_REQUIRED:-0}" = "1" ]; then
  use_https=1
elif [ -f "${SSL_DIR}/${SSL_CERT}" ] && [ -f "${SSL_DIR}/${SSL_KEY}" ]; then
  use_https=1
fi

if [ "${use_https}" -eq 1 ]; then
  exec python -c "
import ssl
import urllib.request

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
urllib.request.urlopen(
    'https://localhost:8000/health/ready',
    context=ctx,
    timeout=${TIMEOUT},
)
"
fi

exec python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/ready', timeout=${TIMEOUT})"
