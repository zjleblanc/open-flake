#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! podman info >/dev/null 2>&1; then
  echo "Podman is not running. On macOS, start it with: podman machine start"
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
    --health-cmd "pg_isready -U openflake -d openflake" \
    --health-interval 5s \
    --health-timeout 5s \
    --health-retries 10 \
    docker.io/library/postgres:16-alpine
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

until podman exec openflake-postgres pg_isready -U openflake -d openflake >/dev/null 2>&1; do
  echo "Waiting for PostgreSQL..."
  sleep 1
done

echo "PostgreSQL is ready"
