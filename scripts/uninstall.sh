#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
"${ROOT}/scripts/stop-gateway.sh"
rm -rf "${HOME}/.grok/skills/lightroom-retouch"
echo "Removed grok skill. venv left at server/.venv — delete it yourself if you want."
