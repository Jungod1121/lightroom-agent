#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${ROOT}/server/.venv/bin/python"
echo "== lightroom-agent install =="

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This installer is macOS-only (Lightroom Classic)." >&2
  exit 1
fi

if [[ ! -x "$PY" ]]; then
  python3 -m venv "${ROOT}/server/.venv"
  PY="${ROOT}/server/.venv/bin/python"
fi
"$PY" -m pip install -q -r "${ROOT}/server/requirements.txt"

DIST_DEFAULT="${HOME}/repositories/lightroom-mcp-automaat/server/dist"
if [[ -z "${LRMCP_AUTOMAAT_DIST:-}" && -f "${DIST_DEFAULT}/plugin-socket.js" ]]; then
  echo "automaat dist: ${DIST_DEFAULT}"
elif [[ -n "${LRMCP_AUTOMAAT_DIST:-}" ]]; then
  echo "automaat dist: ${LRMCP_AUTOMAAT_DIST}"
else
  echo "WARNING: set LRMCP_AUTOMAAT_DIST to automaat server/dist (plugin-socket.js)." >&2
fi

PLUGIN="${HOME}/Library/Application Support/Adobe/Lightroom/Modules/LightroomMCP.lrplugin"
if [[ -d "$PLUGIN" ]]; then
  cp "${ROOT}/plugin/HandlerMask.lua" "${PLUGIN}/"
  cp "${ROOT}/plugin/DevelopReady.lua" "${PLUGIN}/"
  python3 - <<PY
from pathlib import Path
p = Path("${PLUGIN}/PluginInfoProvider.lua")
t = p.read_text()
if "HandlerMask" not in t:
    t = t.replace(
        "local HandlerDevelop = require 'HandlerDevelop'",
        "local HandlerDevelop = require 'HandlerDevelop'\\nlocal HandlerMask = require 'HandlerMask'",
    )
    t = t.replace(
        "    set_develop_settings = HandlerDevelop.setDevelopSettings,",
        "    set_develop_settings = HandlerDevelop.setDevelopSettings,\\n    set_auto_tone = HandlerDevelop.setAutoTone,\\n    create_ai_mask = HandlerMask.createAiMask,\\n    create_gradient_mask = HandlerMask.createGradientMask,\\n    list_masks = HandlerMask.listMasks,\\n    select_mask = HandlerMask.selectMask,\\n    set_mask_settings = HandlerMask.setMaskSettings,\\n    delete_mask = HandlerMask.deleteMask,",
    )
    p.write_text(t)
    print("patched PluginInfoProvider.lua")
else:
    print("PluginInfoProvider already has HandlerMask")
PY
  echo "Copied mask Lua into ${PLUGIN} — Reload the plugin in Lightroom."
else
  echo "WARNING: Lightroom MCP plugin not found at ${PLUGIN}" >&2
fi

SKILL_DST="${HOME}/.grok/skills/lightroom-retouch"
mkdir -p "$SKILL_DST"
cp "${ROOT}/skills/lightroom-retouch/SKILL.md" "${SKILL_DST}/SKILL.md"

mkdir -p "${HOME}/.config/lightroom-mcp"

echo
echo "MCP snippet (replace PATH):"
cat <<EOF
{
  "mcpServers": {
    "lightroom-agent": {
      "command": "${PY}",
      "args": ["-m", "lightroom_agent.main"],
      "env": { "PYTHONPATH": "${ROOT}/server" }
    }
  }
}
EOF

echo
echo "1. Lightroom → Plug-in Manager → Lightroom MCP → Start Server, then Reload."
echo "2. Start gateway (owns plugin sockets; WorkBuddy should use this MCP, not automaat):"
echo "     ${ROOT}/scripts/start-gateway.sh"
echo "3. Ping:"
echo "     node ${ROOT}/scripts/lr-plugin-call.mjs ping"
echo
echo "If set_auto_tone / create_ai_mask says Unknown action: Reload the plugin."
