#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

cd "$ROOT/frontend"

if [[ ! -d node_modules ]]; then
  echo "Frontend dependencies not found. Run: cd frontend && npm install"
  exit 1
fi

exec npm run dev
