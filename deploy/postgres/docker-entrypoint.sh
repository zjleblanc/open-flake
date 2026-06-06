#!/bin/sh
set -e

HBA_SOURCE="/etc/postgresql/pg_hba.conf.ro"
HBA_DEST="/var/lib/postgresql/data/pg_hba.openflake.conf"

if [ -f "${HBA_SOURCE}" ]; then
  mkdir -p /var/lib/postgresql/data
  cp "${HBA_SOURCE}" "${HBA_DEST}"
  chown postgres:postgres "${HBA_DEST}"
  chmod 600 "${HBA_DEST}"
  exec /usr/local/bin/docker-entrypoint.sh postgres -c "hba_file=${HBA_DEST}"
fi

exec /usr/local/bin/docker-entrypoint.sh "$@"
