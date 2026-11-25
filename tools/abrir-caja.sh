#!/usr/bin/env bash
# Levanta la caja si no está arriba y abre el navegador en ella.
set -euo pipefail
cd "$(dirname "$0")/.."
PORT="${PORT:-8787}"

if ! curl -sf --max-time 2 "http://127.0.0.1:$PORT/api/ping" >/dev/null 2>&1; then
  setsid python3 tools/caja.py --port "$PORT" >> /tmp/brilint-caja.log 2>&1 < /dev/null &
  for _ in $(seq 1 40); do
    if curl -sf --max-time 1 "http://127.0.0.1:$PORT/api/ping" >/dev/null 2>&1; then break; fi
    sleep 0.25
  done
fi

exec xdg-open "http://127.0.0.1:$PORT/"
