#!/bin/sh
set -e

SSL_DIR="/etc/openflake/certs"
SSL_CERT="${OPENFLAKE_SSL_CERT:-fullchain.pem}"
SSL_KEY="${OPENFLAKE_SSL_KEY:-privkey.pem}"

if [ -f "${SSL_DIR}/${SSL_CERT}" ] && [ -f "${SSL_DIR}/${SSL_KEY}" ]; then
    exec python -c "
import ssl
import urllib.request

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
urllib.request.urlopen('https://localhost:8000/health/ready', context=ctx)
"
fi

exec python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/ready')"
