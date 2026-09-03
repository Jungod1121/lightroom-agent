#!/usr/bin/env bash
set -euo pipefail
PID_FILE="${HOME}/.config/lightroom-mcp/gateway.pid"
if [[ -f "$PID_FILE" ]]; then
  kill "$(cat "$PID_FILE")" 2>/dev/null || true
  rm -f "$PID_FILE"
fi
pkill -f "scripts/lr-gateway.mjs" 2>/dev/null || true
echo "gateway stopped"
