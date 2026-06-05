#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"

if [[ ! -x ".venv/bin/python" ]]; then
  echo "Backend venv not found. Run: cd backend && python -m venv .venv && pip install -e '.[dev]'"
  exit 1
fi

if ! (echo >/dev/tcp/localhost/5432) 2>/dev/null; then
  echo "PostgreSQL is not reachable on localhost:5432."
  echo "Run the 'Ensure PostgreSQL (Podman)' task first, or: podman start openflake-postgres"
  exit 1
fi

exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
