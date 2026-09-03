"""AI masks and gradients via the Lightroom plugin (Develop module)."""
from __future__ import annotations

from typing import Any, Dict, Optional

from lightroom_agent.retouch.prescription import validate_settings
from lightroom_agent.retouch.transport import plugin_call as default_plugin_call

AI_TYPES = frozenset({"subject", "sky", "background", "objects", "people", "landscape"})


def create_ai_mask(photo_id: str, mask_type: str, operation: str = "new",
                   plugin_call=default_plugin_call) -> Dict[str, Any]:
    if mask_type not in AI_TYPES:
        raise ValueError(f"mask_type must be one of {sorted(AI_TYPES)}")
    return plugin_call(
        "create_ai_mask",
        {"photo_id": str(photo_id), "mask_type": mask_type, "operation": operation},
    )


def create_gradient_mask(photo_id: str, kind: str = "linear",
                         plugin_call=default_plugin_call) -> Dict[str, Any]:
    if kind not in ("linear", "radial"):
        raise ValueError("kind must be linear or radial")
    return plugin_call(
        "create_gradient_mask",
        {"photo_id": str(photo_id), "kind": kind},
    )


def list_masks(photo_id: str, plugin_call=default_plugin_call) -> Dict[str, Any]:
    return plugin_call("list_masks", {"photo_id": str(photo_id)})


def set_mask_settings(photo_id: str, settings: Dict[str, Any],
                      mask_id: Optional[Any] = None,
                      plugin_call=default_plugin_call) -> Dict[str, Any]:
    cleaned = validate_settings(settings)
    params: Dict[str, Any] = {"photo_id": str(photo_id), "settings": cleaned}
    if mask_id is not None:
        params["mask_id"] = mask_id
    return plugin_call("set_mask_settings", params)
