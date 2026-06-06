#!/bin/sh
set -e

CONF="/etc/nginx/conf.d/default.conf"
FLAG="/var/run/nginx-ssl-enabled"

if [ -f /etc/nginx/certs/fullchain.pem ] && [ -f /etc/nginx/certs/privkey.pem ]; then
    echo "SSL certificates found; enabling HTTPS on port 443"
    cat /etc/nginx/templates/http-redirect.conf /etc/nginx/templates/ssl.conf > "$CONF"
    touch "$FLAG"
else
    echo "No SSL certificates found; serving HTTP only on port 8080"
    cp /etc/nginx/templates/http.conf "$CONF"
    rm -f "$FLAG"
fi
