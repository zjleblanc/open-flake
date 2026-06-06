#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$ROOT/.venv"

if [[ ! -x "$VENV/bin/python" ]]; then
  echo "Backend venv not found. Run: python -m venv .venv && pip install -e 'backend/.[dev]'"
  exit 1
fi

cd "$ROOT/backend"

if ! (echo >/dev/tcp/localhost/5432) 2>/dev/null; then
  echo "PostgreSQL is not reachable on localhost:5432."
  echo "Run the 'Ensure PostgreSQL (Podman)' task first, or: podman start openflake-postgres"
  exit 1
fi

exec "$VENV/bin/python" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
