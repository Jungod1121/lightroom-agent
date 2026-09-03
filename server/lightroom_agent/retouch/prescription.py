"""Retouch prescription: allowlisted Lightroom SDK keys only."""
from __future__ import annotations

from typing import Any, Dict, Mapping

ALLOWED_KEYS = frozenset({
    "Exposure2012",
    "Contrast2012",
    "Highlights2012",
    "Shadows2012",
    "Whites2012",
    "Blacks2012",
    "Texture",
    "Clarity2012",
    "Dehaze",
    "Vibrance",
    "Saturation",
    "Temperature",
    "Tint",
    "SaturationAdjustmentRed",
    "SaturationAdjustmentOrange",
    "SaturationAdjustmentYellow",
    "SaturationAdjustmentGreen",
    "SaturationAdjustmentAqua",
    "SaturationAdjustmentBlue",
    "SaturationAdjustmentPurple",
    "SaturationAdjustmentMagenta",
    "HueAdjustmentRed",
    "HueAdjustmentOrange",
    "HueAdjustmentYellow",
    "HueAdjustmentGreen",
    "HueAdjustmentAqua",
    "HueAdjustmentBlue",
    "HueAdjustmentPurple",
    "HueAdjustmentMagenta",
    "LuminanceAdjustmentRed",
    "LuminanceAdjustmentOrange",
    "LuminanceAdjustmentYellow",
    "LuminanceAdjustmentGreen",
    "LuminanceAdjustmentAqua",
    "LuminanceAdjustmentBlue",
    "LuminanceAdjustmentPurple",
    "LuminanceAdjustmentMagenta",
    "CropTop",
    "CropLeft",
    "CropBottom",
    "CropRight",
    "CropAngle",
    "ParametricShadows",
    "ParametricDarks",
    "ParametricLights",
    "ParametricHighlights",
    "ToneCurveName2012",
    "ToneCurvePV2012",
    "ToneCurvePV2012Red",
    "ToneCurvePV2012Green",
    "ToneCurvePV2012Blue",
})

CROP_BOX_KEYS = ("CropTop", "CropLeft", "CropBottom", "CropRight")
CROP_UNIT_KEYS = frozenset(CROP_BOX_KEYS)
POINT_CURVE_KEYS = frozenset({
    "ToneCurvePV2012",
    "ToneCurvePV2012Red",
    "ToneCurvePV2012Green",
    "ToneCurvePV2012Blue",
})
STRING_KEYS = frozenset({"ToneCurveName2012"})


class PrescriptionError(ValueError):
    pass


def _as_number(key: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PrescriptionError(f"{key} must be numeric, got {type(value).__name__}")
    return float(value)


def _as_point_curve(key: str, value: Any) -> list:
    if not isinstance(value, (list, tuple)):
        raise PrescriptionError(f"{key} must be a list of 0-255 int pairs")
    nums = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise PrescriptionError(f"{key} values must be numbers")
        n = int(item)
        if n != item or n < 0 or n > 255:
            raise PrescriptionError(f"{key} values must be integers 0-255")
        nums.append(n)
    if len(nums) < 4 or len(nums) > 64 or len(nums) % 2 != 0:
        raise PrescriptionError(f"{key} must contain 2-32 input/output pairs")
    if nums[0] != 0 or nums[-2] != 255:
        raise PrescriptionError(f"{key} must start at input 0 and end at input 255")
    prev = None
    for i in range(0, len(nums), 2):
        if prev is not None and nums[i] <= prev:
            raise PrescriptionError(f"{key} input values must be strictly increasing")
        prev = nums[i]
    return nums


def validate_settings(settings: Mapping[str, Any]) -> Dict[str, Any]:
    if not settings:
        raise PrescriptionError("settings must contain at least one key")
    unknown = [k for k in settings if k not in ALLOWED_KEYS]
    if unknown:
        raise PrescriptionError(f"keys not allowlisted: {', '.join(sorted(unknown))}")

    out: Dict[str, Any] = {}
    for key, raw in settings.items():
        if key in POINT_CURVE_KEYS:
            out[key] = _as_point_curve(key, raw)
            continue
        if key in STRING_KEYS:
            if not isinstance(raw, str) or not raw:
                raise PrescriptionError(f"{key} must be a non-empty string")
            out[key] = raw
            continue
        val = _as_number(key, raw)
        if key in CROP_UNIT_KEYS and not 0.0 <= val <= 1.0:
            raise PrescriptionError(f"{key} must be in [0, 1], got {val}")
        out[key] = val

    top, bottom = out.get("CropTop"), out.get("CropBottom")
    if top is not None and bottom is not None and top >= bottom:
        raise PrescriptionError("CropTop must be < CropBottom")
    left, right = out.get("CropLeft"), out.get("CropRight")
    if left is not None and right is not None and left >= right:
        raise PrescriptionError("CropLeft must be < CropRight")
    return out
