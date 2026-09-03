#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG="${HOME}/.config/lightroom-mcp/gateway.log"
mkdir -p "$(dirname "$LOG")"
if lsof -nP -iTCP:58770 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "gateway already listening on :58770"
  exit 0
fi
nohup node "${ROOT}/scripts/lr-gateway.mjs" >>"$LOG" 2>&1 &
echo "gateway pid $!  log $LOG"
echo "stop: ${ROOT}/scripts/stop-gateway.sh"
