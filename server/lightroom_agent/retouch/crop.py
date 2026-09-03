"""Map on-screen crop (top/left/bottom/right) to Lightroom SDK Crop* (orientation AB)."""
from __future__ import annotations

from typing import Dict, Mapping

# SDK Crop* is always relative to unrotated pixels (AB).
# Visual sides are what you see after orientation.
# Mapping copied from stecman AutoCrop.rotateCropForOrientation.


class CropError(ValueError):
    pass


def visual_crop_to_sdk(
    top: float,
    left: float,
    bottom: float,
    right: float,
    orientation: str,
) -> Dict[str, float]:
    if not 0.0 <= top < bottom <= 1.0:
        raise CropError(f"visual top < bottom in [0,1], got {top}, {bottom}")
    if not 0.0 <= left < right <= 1.0:
        raise CropError(f"visual left < right in [0,1], got {left}, {right}")
    code = (orientation or "AB").upper()
    if code == "AB":
        return {"CropLeft": left, "CropTop": top, "CropRight": right, "CropBottom": bottom}
    if code == "BC":
        return {
            "CropLeft": top,
            "CropTop": 1.0 - right,
            "CropRight": bottom,
            "CropBottom": 1.0 - left,
        }
    if code == "CD":
        return {
            "CropLeft": 1.0 - right,
            "CropTop": 1.0 - bottom,
            "CropRight": 1.0 - left,
            "CropBottom": 1.0 - top,
        }
    if code == "DA":
        return {
            "CropLeft": 1.0 - bottom,
            "CropTop": left,
            "CropRight": 1.0 - top,
            "CropBottom": right,
        }
    raise CropError(f"unknown orientation {orientation!r}")


def exif_to_lr_orientation(exif_orientation: int) -> str:
    """TIFF/EXIF orientation → Lr two-letter code."""
    return {1: "AB", 3: "CD", 6: "DA", 8: "BC"}.get(int(exif_orientation), "AB")


# width / height. Portrait 2:3 is the native Nikon still.
STANDARD_ASPECTS = {
    "1:1": 1.0,
    "4:5": 4 / 5,
    "5:4": 5 / 4,
    "2:3": 2 / 3,
    "3:2": 3 / 2,
    "3:4": 3 / 4,
    "4:3": 4 / 3,
    "9:16": 9 / 16,
    "16:9": 16 / 9,
}


def _ratio_value(ratio: str) -> float:
    if ratio not in STANDARD_ASPECTS:
        raise CropError(
            f"crop ratio {ratio!r} is not standard; use "
            + ", ".join(STANDARD_ASPECTS)
        )
    return STANDARD_ASPECTS[ratio]


def aspect_crop_window(
    image_width: int,
    image_height: int,
    ratio: str,
    *,
    anchor: str = "center",
    scale: float = 1.0,
) -> Dict[str, float]:
    """Largest (or scaled) window of a standard ratio, in visual 0–1 coords.

    scale=1 fills the frame as much as the ratio allows. scale<1 zooms in.
    anchor: center | top | bottom | left | right.
    """
    if image_width <= 0 or image_height <= 0:
        raise CropError("image size must be positive")
    if not 0.05 <= scale <= 1.0:
        raise CropError("scale must be in (0.05, 1]")
    target = _ratio_value(ratio)
    frame = image_width / image_height
    if target >= frame:
        win_w = scale
        win_h = (frame / target) * scale
    else:
        win_h = scale
        win_w = (target / frame) * scale
    ax, ay = 0.5, 0.5
    if "left" in anchor:
        ax = 0.0
    elif "right" in anchor:
        ax = 1.0
    if "top" in anchor:
        ay = 0.0
    elif "bottom" in anchor:
        ay = 1.0
    left = (1.0 - win_w) * ax
    top = (1.0 - win_h) * ay
    return {
        "top": round(top, 6),
        "left": round(left, 6),
        "bottom": round(top + win_h, 6),
        "right": round(left + win_w, 6),
    }


def infer_orientation(display_width: int, display_height: int,
                      sensor_width: int, sensor_height: int) -> str:
    """Heuristic when EXIF is missing. Portrait display + landscape sensor → DA (Nikon 竖拍常见)."""
    display_portrait = display_width < display_height
    sensor_landscape = sensor_width > sensor_height
    if display_portrait and sensor_landscape:
        return "DA"
    if display_width > display_height and sensor_width < sensor_height:
        return "BC"
    return "AB"
