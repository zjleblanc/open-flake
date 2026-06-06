#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

MAX_WAIT_SECONDS=30

postgres_reachable() {
  (echo >/dev/tcp/localhost/5432) 2>/dev/null
}

if postgres_reachable; then
  echo "PostgreSQL already reachable on localhost:5432"
  exit 0
fi

if ! podman info >/dev/null 2>&1; then
  echo "PostgreSQL is not reachable on localhost:5432 and Podman is not running."
  echo "Start Podman with: podman machine start"
  echo "Or run PostgreSQL locally on port 5432."
  exit 1
fi

start_with_compose() {
  if command -v podman-compose >/dev/null 2>&1; then
    podman-compose -f deploy/podman-compose.yaml up -d postgres
    return 0
  fi

  if podman compose version >/dev/null 2>&1; then
    podman compose -f deploy/podman-compose.yaml up -d postgres
    return 0
  fi

  return 1
}

start_with_podman_run() {
  podman network exists openflake-net 2>/dev/null || podman network create openflake-net
  podman volume exists openflake-pg-data 2>/dev/null || podman volume create openflake-pg-data

  podman run -d \
    --name openflake-postgres \
    --network openflake-net \
    -p 5432:5432 \
    -e POSTGRES_USER=openflake \
    -e POSTGRES_PASSWORD=openflake \
    -e POSTGRES_DB=openflake \
    -v openflake-pg-data:/var/lib/postgresql/data \
    -v "$ROOT/deploy/pg_hba.conf:/etc/postgresql/pg_hba.conf:ro" \
    --health-cmd "pg_isready -U openflake -d openflake" \
    --health-interval 5s \
    --health-timeout 5s \
    --health-retries 10 \
    docker.io/library/postgres:16-alpine \
    postgres \
    -c "listen_addresses=*" \
    -c "hba_file=/etc/postgresql/pg_hba.conf"
}

if podman container exists openflake-postgres 2>/dev/null; then
  if [ "$(podman inspect -f '{{.State.Running}}' openflake-postgres)" != "true" ]; then
    echo "Starting existing PostgreSQL container..."
    podman start openflake-postgres
  else
    echo "PostgreSQL container already running"
  fi
else
  echo "Starting PostgreSQL..."
  if ! start_with_compose; then
    start_with_podman_run
  fi
fi

elapsed=0
until podman exec openflake-postgres pg_isready -U openflake -d openflake >/dev/null 2>&1; do
  if [ "$elapsed" -ge "$MAX_WAIT_SECONDS" ]; then
    echo "Timed out waiting for PostgreSQL after ${MAX_WAIT_SECONDS}s"
    exit 1
  fi
  echo "Waiting for PostgreSQL..."
  sleep 1
  elapsed=$((elapsed + 1))
done

echo "PostgreSQL is ready"
