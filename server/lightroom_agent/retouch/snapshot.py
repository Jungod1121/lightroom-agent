"""Persist a develop snapshot so retouch can be undone without LrC undo API."""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from lightroom_agent.retouch.prescription import ALLOWED_KEYS

DEFAULT_DIR = Path("/tmp/lr-retouch/snapshots")

# get_photo_metadata uses camelCase aliases for the basic panel.
_ALIAS_TO_SDK = {
    "exposure": "Exposure2012",
    "contrast": "Contrast2012",
    "highlights": "Highlights2012",
    "shadows": "Shadows2012",
    "whites": "Whites2012",
    "blacks": "Blacks2012",
    "temperature": "Temperature",
    "tint": "Tint",
    "texture": "Texture",
    "clarity": "Clarity2012",
    "dehaze": "Dehaze",
    "vibrance": "Vibrance",
    "saturation": "Saturation",
}


def develop_from_metadata(meta: Mapping[str, Any]) -> Dict[str, float]:
    ds = meta.get("developSettings") or {}
    if not isinstance(ds, dict):
        ds = {}
    out: Dict[str, float] = {}

    for alias, sdk in _ALIAS_TO_SDK.items():
        val = ds.get(alias)
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            out[sdk] = float(val)

    hsl = ds.get("hsl") or {}
    if isinstance(hsl, dict):
        for key, val in hsl.items():
            if key in ALLOWED_KEYS and isinstance(val, (int, float)) and not isinstance(val, bool):
                out[key] = float(val)

    for key, val in ds.items():
        if key in ALLOWED_KEYS and isinstance(val, (int, float)) and not isinstance(val, bool):
            out[key] = float(val)

    return out


def save_snapshot(photo_id: str, develop: Mapping[str, Any],
                  directory: Optional[Path] = None) -> str:
    directory = Path(directory) if directory is not None else DEFAULT_DIR
    directory.mkdir(parents=True, exist_ok=True)
    snapshot_id = uuid.uuid4().hex
    payload = {
        "id": snapshot_id,
        "photo_id": str(photo_id),
        "develop": dict(develop),
        "created_at": time.time(),
    }
    (directory / f"{snapshot_id}.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return snapshot_id


def load_snapshot(snapshot_id: str, directory: Optional[Path] = None) -> Dict[str, Any]:
    directory = Path(directory) if directory is not None else DEFAULT_DIR
    path = directory / f"{snapshot_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"snapshot not found: {snapshot_id}")
    return json.loads(path.read_text(encoding="utf-8"))
