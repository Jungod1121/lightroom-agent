"""Look-then-edit loop: prepare (no writes) → apply (whitelist) → restore."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Optional

from lightroom_agent.analysis.histogram import analyze
from lightroom_agent.retouch.prescription import validate_settings
from lightroom_agent.retouch.snapshot import (
    DEFAULT_DIR as SNAP_DIR,
    develop_from_metadata,
    load_snapshot,
    save_snapshot,
)
from lightroom_agent.retouch.transport import plugin_call as default_plugin_call

PluginFn = Callable[..., Dict[str, Any]]

DEFAULT_EXPORT_ROOT = Path("/tmp/lr-retouch")


def _find_jpeg(directory: Path) -> Path:
    files = list(directory.glob("*.jpg")) + list(directory.glob("*.jpeg"))
    if not files:
        raise FileNotFoundError(f"no jpeg in {directory}")
    return max(files, key=lambda p: p.stat().st_mtime)


def _clear_jpegs(directory: Path) -> None:
    """Remove prior renders so LrC export will not pop a collision dialog."""
    for path in list(directory.glob("*.jpg")) + list(directory.glob("*.jpeg")):
        path.unlink(missing_ok=True)


def _export(plugin_call: PluginFn, photo_id: str, dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    _clear_jpegs(dest)
    plugin_call(
        "export_photos",
        {
            "photo_ids": [str(photo_id)],
            "destination": str(dest),
            "format": "jpeg",
            "quality": 90,
            "width": 1080,
            "height": 1080,
        },
    )
    return _find_jpeg(dest)


def prepare_retouch(
    photo_id: str,
    plugin_call: PluginFn = default_plugin_call,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    snapshot_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    photo_id = str(photo_id)
    meta = plugin_call("get_photo_metadata", {"photo_id": photo_id})
    develop = develop_from_metadata(meta)
    snapshot_id = save_snapshot(photo_id, develop, directory=snapshot_dir or SNAP_DIR)
    dest = Path(export_root) / photo_id / "before"
    jpeg = _export(plugin_call, photo_id, dest)
    analysis = analyze(str(jpeg)).to_dict()
    return {
        "photo_id": photo_id,
        "filename": meta.get("filename"),
        "jpeg_path": str(jpeg),
        "analysis": analysis,
        "develop": develop,
        "snapshot_id": snapshot_id,
        "look_first": True,
        "instruction": (
            "Read jpeg_path (or analysis if you cannot see images) before calling apply_retouch."
        ),
    }


def apply_retouch(
    photo_id: str,
    settings: Dict[str, Any],
    snapshot_id: str,
    plugin_call: PluginFn = default_plugin_call,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    snapshot_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    photo_id = str(photo_id)
    snap = load_snapshot(snapshot_id, directory=snapshot_dir or SNAP_DIR)
    if str(snap.get("photo_id")) != photo_id:
        raise ValueError(
            f"snapshot {snapshot_id} belongs to photo {snap.get('photo_id')}, not {photo_id}"
        )
    cleaned = validate_settings(settings)
    plugin_call(
        "set_develop_settings",
        {"photo_id": photo_id, "settings": cleaned},
    )
    dest = Path(export_root) / photo_id / "after"
    jpeg = _export(plugin_call, photo_id, dest)
    analysis = analyze(str(jpeg)).to_dict()
    return {
        "photo_id": photo_id,
        "after_path": str(jpeg),
        "settings": cleaned,
        "analysis": analysis,
        "snapshot_id": snapshot_id,
        "instruction": "Show after_path to the user. Do not stop at a settings summary.",
    }


def restore_retouch(
    photo_id: str,
    snapshot_id: str,
    plugin_call: PluginFn = default_plugin_call,
    snapshot_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    photo_id = str(photo_id)
    snap = load_snapshot(snapshot_id, directory=snapshot_dir or SNAP_DIR)
    if str(snap.get("photo_id")) != photo_id:
        raise ValueError(
            f"snapshot {snapshot_id} belongs to photo {snap.get('photo_id')}, not {photo_id}"
        )
    develop = snap.get("develop") or {}
    cleaned = validate_settings(develop)
    plugin_call(
        "set_develop_settings",
        {"photo_id": photo_id, "settings": cleaned},
    )
    return {
        "photo_id": photo_id,
        "restored": True,
        "settings": cleaned,
        "snapshot_id": snapshot_id,
    }


def apply_auto_tone(
    photo_id: str,
    snapshot_id: Optional[str] = None,
    white_balance: bool = False,
    plugin_call: PluginFn = default_plugin_call,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    snapshot_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Run Lightroom Classic's Auto button (Sensei) on a photo, then export.

    Needs Develop module; the plugin selects the photo. snapshot_id from
    prepare_retouch lets restore undo Auto.
    """
    photo_id = str(photo_id)
    if snapshot_id:
        snap = load_snapshot(snapshot_id, directory=snapshot_dir or SNAP_DIR)
        if str(snap.get("photo_id")) != photo_id:
            raise ValueError(
                f"snapshot {snapshot_id} belongs to photo {snap.get('photo_id')}, not {photo_id}"
            )
    plugin_call(
        "set_auto_tone",
        {"photo_id": photo_id, "white_balance": bool(white_balance)},
    )
    dest = Path(export_root) / photo_id / "auto"
    jpeg = _export(plugin_call, photo_id, dest)
    analysis = analyze(str(jpeg)).to_dict()
    return {
        "photo_id": photo_id,
        "after_path": str(jpeg),
        "analysis": analysis,
        "snapshot_id": snapshot_id,
        "white_balance": bool(white_balance),
        "instruction": "This is Lightroom Auto (Sensei), not a style match. Show after_path.",
    }
