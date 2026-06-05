#!/usr/bin/env bash
set -euo pipefail

# Stop uvicorn (including --reload parent/child) on the OpenFlake dev port.
if command -v lsof >/dev/null 2>&1; then
  pids=$(lsof -tiTCP:8000 -sTCP:LISTEN 2>/dev/null || true)
  if [[ -n "${pids}" ]]; then
    kill -TERM ${pids} 2>/dev/null || true
    sleep 0.5
    pids=$(lsof -tiTCP:8000 -sTCP:LISTEN 2>/dev/null || true)
    if [[ -n "${pids}" ]]; then
      kill -KILL ${pids} 2>/dev/null || true
    fi
  fi
fi

pkill -f "uvicorn app.main:app.*127.0.0.1.*8000" 2>/dev/null || true
