#!/usr/bin/env bash
set -euo pipefail

# Stop the Vite dev server on the OpenFlake frontend port.
if command -v lsof >/dev/null 2>&1; then
  pids=$(lsof -tiTCP:5173 -sTCP:LISTEN 2>/dev/null || true)
  if [[ -n "${pids}" ]]; then
    while IFS= read -r pid; do
      if [[ -n "${pid}" ]]; then
        kill -TERM "${pid}" 2>/dev/null || true
      fi
    done <<< "${pids}"
    sleep 0.5
    pids=$(lsof -tiTCP:5173 -sTCP:LISTEN 2>/dev/null || true)
    if [[ -n "${pids}" ]]; then
      while IFS= read -r pid; do
        if [[ -n "${pid}" ]]; then
          kill -KILL "${pid}" 2>/dev/null || true
        fi
      done <<< "${pids}"
    fi
  fi
fi

pkill -f "vite" 2>/dev/null || true
