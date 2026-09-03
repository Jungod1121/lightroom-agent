"""Call the Lightroom plugin via the node CLI (no python MCP SDK, no automaat stdio)."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, Optional

REPO_ROOT = Path(__file__).resolve().parents[3]
CLI = REPO_ROOT / "scripts" / "lr-plugin-call.mjs"


class PluginError(RuntimeError):
    pass


def _default_run(cmd: list, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=180)


def plugin_call(
    action: str,
    params: Optional[Dict[str, Any]] = None,
    runner: Optional[Callable] = None,
) -> Dict[str, Any]:
    if not CLI.is_file():
        raise PluginError(f"plugin CLI not found: {CLI}")
    node = os.environ.get("LRMCP_NODE", "node")
    cmd = [node, str(CLI), action]
    if params:
        cmd.append(json.dumps(params, ensure_ascii=False))
    env = os.environ.copy()
    run = runner or _default_run
    proc = run(cmd, env)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
        if "Unknown action" in err:
            err += " Reload Lightroom MCP in Plug-in Manager."
        raise PluginError(err[:800])
    text = (proc.stdout or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise PluginError(f"plugin returned non-JSON: {text[:400]}") from e
