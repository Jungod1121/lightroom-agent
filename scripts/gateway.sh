#!/bin/bash
# gateway.sh — 启动/停止 Lightroom Gateway 常驻进程
# 用法: gateway.sh start | stop | status
set -euo pipefail

SERVER_DIR="$(cd "$(dirname "$0")/../server" && pwd)"
PY="$SERVER_DIR/.venv/bin/python"
PORT="${LRGATEWAY_PORT:-58766}"
LOG="$HOME/Library/Logs/lightroom-gateway.log"
export PYTHONPATH="$SERVER_DIR"

mkdir -p "$(dirname "$LOG")"

case "${1:-start}" in
  start)
    if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
      echo "Gateway already running on :$PORT"
    else
      nohup "$PY" -m lightroom_agent.gateway_daemon --port "$PORT" \
        >>"$LOG" 2>&1 &
      echo "Gateway starting (pid $!) ... 日志: $LOG"
      sleep 1
    fi
    ;;
  stop)
    pkill -f "lightroom_agent.gateway_daemon" 2>/dev/null && echo "Gateway stopped" || echo "not running"
    ;;
  status)
    if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
      echo "Gateway RUNNING on :$PORT"
    else
      echo "Gateway NOT running"
    fi
    ;;
  *) echo "usage: gateway.sh start|stop|status"; exit 1;;
esac
