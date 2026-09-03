"""Style fingerprint from a render, and a gap → develop-settings mapper.

This is not a generative model. It measures luminance, cast, and range on two
JPEGs and walks the Lightroom basic panel toward the reference. The LLM still
looks at both pictures; these numbers set amplitude.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Union

from lightroom_agent.analysis.histogram import HistogramResult, analyze


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


@dataclass
class StyleFingerprint:
    lum_mean: float
    lum_median: float
    delta_rmg: float
    delta_bmg: float
    stops: float
    hl_clip: float
    sh_clip: float
    zone_hi: float
    zone_lo: float


def fingerprint(src: Union[str, HistogramResult]) -> StyleFingerprint:
    hist = src if isinstance(src, HistogramResult) else analyze(src)
    lum = hist.statistics["Lum"]
    cast = hist.cast or {}
    zones = hist.zones or [0.0] * 11
    return StyleFingerprint(
        lum_mean=float(lum["mean"]),
        lum_median=float(lum["median"]),
        delta_rmg=float(cast.get("delta_rmg") or 0.0),
        delta_bmg=float(cast.get("delta_bmg") or 0.0),
        stops=float((hist.range_ev or {}).get("stops") or 0.0),
        hl_clip=float(lum.get("hl_clip_pct") or 0.0),
        sh_clip=float(lum.get("sh_clip_pct") or 0.0),
        zone_hi=float(sum(zones[7:])),
        zone_lo=float(sum(zones[:3])),
    )


def settings_from_gap(
    source: StyleFingerprint,
    reference: StyleFingerprint,
    current: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Map fingerprint gaps onto absolute develop values.

    ~80 lum ≈ 1 EV. Cooler reference (more negative R−G) lowers Temperature.
    Fewer stops / more high zones → lower Contrast and Dehaze (airier).
    """
    cur = dict(current or {})

    def g(key: str, default: float) -> float:
        val = cur.get(key, default)
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            return default
        return float(val)

    d_mean = reference.lum_mean - source.lum_mean
    exposure = _clamp(g("Exposure2012", 0.0) + d_mean / 80.0, -1.2, 1.2)

    d_stops = reference.stops - source.stops
    # fewer stops in the reference → lower Contrast (airier / flatter)
    contrast = _clamp(g("Contrast2012", 0.0) + d_stops * 18.0, -40.0, 40.0)

    d_hi = reference.zone_hi - source.zone_hi
    highlights = _clamp(g("Highlights2012", 0.0) + d_hi * 1.2, -80.0, 40.0)
    whites = _clamp(g("Whites2012", 0.0) + d_hi * 0.8, -40.0, 40.0)

    d_lo = source.zone_lo - reference.zone_lo
    blacks = _clamp(g("Blacks2012", 0.0) + d_lo * 0.6, -30.0, 40.0)
    shadows = _clamp(g("Shadows2012", 0.0) + d_lo * 0.5, -40.0, 60.0)

    d_rmg = reference.delta_rmg - source.delta_rmg
    temperature = _clamp(g("Temperature", 5200.0) + d_rmg * 18.0, 3800.0, 7500.0)

    d_bmg = reference.delta_bmg - source.delta_bmg
    tint = _clamp(g("Tint", 10.0) - d_bmg * 0.3, -30.0, 40.0)

    dehaze = _clamp(g("Dehaze", 0.0) + d_stops * 8.0 - d_hi * 0.4, -20.0, 30.0)
    clarity = _clamp(g("Clarity2012", 0.0) - d_hi * 0.35, -30.0, 20.0)

    hue_aqua = _clamp(d_bmg * 0.8 - d_rmg * 0.4, -30.0, 40.0)
    sat_aqua = _clamp(d_bmg * 0.6, -20.0, 35.0)
    lum_blue = _clamp(d_hi * 0.5, -20.0, 35.0)

    fade = reference.lum_mean > 130 and reference.stops < 3.8
    if fade:
        curve = [0, 14, 64, 74, 128, 136, 192, 188, 255, 240]
    elif reference.stops > source.stops + 0.4:
        curve = [0, 0, 64, 56, 128, 128, 192, 200, 255, 255]
    else:
        curve = [0, 8, 64, 68, 128, 130, 192, 192, 255, 248]

    return {
        "Exposure2012": round(exposure, 2),
        "Contrast2012": round(contrast, 1),
        "Highlights2012": round(highlights, 1),
        "Shadows2012": round(shadows, 1),
        "Whites2012": round(whites, 1),
        "Blacks2012": round(blacks, 1),
        "Temperature": round(temperature),
        "Tint": round(tint, 1),
        "Dehaze": round(dehaze, 1),
        "Clarity2012": round(clarity, 1),
        "HueAdjustmentAqua": round(hue_aqua, 1),
        "SaturationAdjustmentAqua": round(sat_aqua, 1),
        "LuminanceAdjustmentBlue": round(lum_blue, 1),
        "ToneCurveName2012": "Custom",
        "ToneCurvePV2012": curve,
    }


def propose_style_match(
    photo_id: str,
    reference_path: str,
    plugin_call=None,
    export_root=None,
) -> Dict[str, Any]:
    """Export the current photo, fingerprint it against a reference JPEG, return settings.

    Does not write Lightroom. Caller looks, then apply_retouch.
    """
    from pathlib import Path

    from lightroom_agent.retouch.loop import DEFAULT_EXPORT_ROOT, _export, default_plugin_call
    from lightroom_agent.retouch.snapshot import develop_from_metadata

    call = plugin_call or default_plugin_call
    root = Path(export_root) if export_root else DEFAULT_EXPORT_ROOT
    meta = call("get_photo_metadata", {"photo_id": str(photo_id)})
    jpeg = _export(call, str(photo_id), root / str(photo_id) / "style-src")
    src = fingerprint(str(jpeg))
    ref = fingerprint(reference_path)
    settings = settings_from_gap(src, ref, develop_from_metadata(meta))
    return {
        "photo_id": str(photo_id),
        "jpeg_path": str(jpeg),
        "reference_path": reference_path,
        "source": src.__dict__,
        "reference": ref.__dict__,
        "settings": settings,
        "instruction": "Look at jpeg_path and the reference, then apply_retouch with settings.",
    }
