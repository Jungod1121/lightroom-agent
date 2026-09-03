"""main.py — 分析 + 先看再修再给你看（prepare / apply / restore）

分析层不依赖 Lightroom。prepare/apply 经 node CLI 直连 LrC 插件，
不走 python MCP SDK，也不 spawn automaat。
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

from fastmcp import FastMCP

from lightroom_agent.analysis.histogram import analyze
from lightroom_agent.retouch.loop import (
    apply_auto_tone,
    apply_retouch,
    prepare_retouch,
    restore_retouch,
)
from lightroom_agent.retouch.style import propose_style_match
from lightroom_agent.retouch.masks import (
    create_ai_mask,
    create_gradient_mask,
    list_masks,
    set_mask_settings,
)
from lightroom_agent.retouch.prescription import PrescriptionError
from lightroom_agent.retouch.transport import PluginError, plugin_call

logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s",
                    stream=sys.stderr)
log = logging.getLogger("lightroom-analysis")

mcp = FastMCP("Lightroom Analysis (self-built)")

SUPPORTED = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".dng")


def _ok(data: Dict[str, Any]) -> Dict[str, Any]:
    return {"ok": True, **data}


def _err(msg: str) -> Dict[str, Any]:
    return {"ok": False, "error": {"message": msg}}


def _caught(fn, *args, **kwargs) -> Dict[str, Any]:
    try:
        return _ok(fn(*args, **kwargs))
    except (PrescriptionError, PluginError, FileNotFoundError, ValueError) as e:
        return _err(str(e))
    except Exception as e:
        log.exception("retouch failed")
        return _err(str(e))


@mcp.tool
def analyze_photo(path: str) -> Dict[str, Any]:
    """分析一张照片/渲染图：输出直方图统计、溢出检测、11 区曝光分布、5×5 分区测光、
    色偏判断、有效动态范围，并给出可执行的调参建议（suggestions）。"""
    p = Path(path)
    if not p.exists():
        return _err(f"file not found: {path}")
    try:
        hist = analyze(str(p))
        return _ok(hist.to_dict())
    except Exception as e:
        log.exception("analyze failed")
        return _err(f"analyze failed: {e}")


@mcp.tool
def batch_analyze(directory: str, limit: int = 50) -> Dict[str, Any]:
    """分析目录下全部图片，返回每张的亮度均值/中位数、溢出比例、色偏差与建议条数。
    适合批量选片与风格一致性检查。"""
    d = Path(directory)
    if not d.is_dir():
        return _err(f"not a directory: {directory}")
    files = sorted([f for f in d.iterdir() if f.suffix.lower() in SUPPORTED])[:limit]
    rows: List[Dict[str, Any]] = []
    for f in files:
        try:
            h = analyze(str(f))
            stats = h.statistics["Lum"]
            cast = h.cast
            rows.append({
                "file": f.name,
                "lum_mean": stats["mean"],
                "lum_median": stats["median"],
                "hl_clip_pct": stats["hl_clip_pct"],
                "sh_clip_pct": stats["sh_clip_pct"],
                "stops": h.range_ev.get("stops", 0),
                "delta_rmg": cast.get("delta_rmg"),
                "suggestions": h.suggestions[:2],
            })
        except Exception as e:
            rows.append({"file": f.name, "error": str(e)})
    return _ok({"count": len(rows), "rows": rows})


@mcp.tool
def get_selected_photos(limit: int = 20) -> Dict[str, Any]:
    """读取 Lightroom 当前选中的照片（id / filename）。修图前用这个拿到 photo_id。"""
    return _caught(plugin_call, "get_selected_photos", {"limit": limit})


@mcp.tool
def prepare_retouch_photo(photo_id: str) -> Dict[str, Any]:
    """修图第一拍：导出当前图、分析、快照 develop。不改目录。
    调用方必须先阅读返回的 jpeg_path（能看图）或 analysis（不能看图），才允许 apply。"""
    return _caught(prepare_retouch, photo_id)


@mcp.tool
def apply_retouch_photo(photo_id: str, settings: Dict[str, Any],
                        snapshot_id: str) -> Dict[str, Any]:
    """修图第二拍：写入白名单 develop（含裁切 0–1）并导出 after.jpg。
    必须带 prepare 返回的 snapshot_id。调用后必须把 after_path 展示给用户。"""
    return _caught(apply_retouch, photo_id, settings, snapshot_id)


@mcp.tool
def restore_retouch_photo(photo_id: str, snapshot_id: str) -> Dict[str, Any]:
    """把照片 develop 写回 prepare 时的快照（用户说「撤」时用）。"""
    return _caught(restore_retouch, photo_id, snapshot_id)


@mcp.tool
def apply_auto_tone_photo(photo_id: str, snapshot_id: str = "",
                          white_balance: bool = False) -> Dict[str, Any]:
    """点 Lightroom Develop 的 Auto（Sensei：8 个影调滑块）。不改白平衡除非 white_balance=true。
    照片会被选中并切到 Develop。snapshot_id 来自 prepare，用于撤。"""
    sid = snapshot_id or None
    return _caught(apply_auto_tone, photo_id, sid, white_balance)


@mcp.tool
def create_ai_mask_photo(photo_id: str, mask_type: str,
                         operation: str = "new") -> Dict[str, Any]:
    """在 Develop 里创建 AI 蒙版：sky / subject / background / landscape / people / objects。
    之后用 set_mask_settings_photo 对该蒙版写局部滑块。插件需 Reload。"""
    return _caught(create_ai_mask, photo_id, mask_type, operation)


@mcp.tool
def create_gradient_mask_photo(photo_id: str, kind: str = "linear") -> Dict[str, Any]:
    """线性或径向渐变蒙版（Lightroom 默认几何，通常线性为自上而下）。"""
    return _caught(create_gradient_mask, photo_id, kind)


@mcp.tool
def list_masks_photo(photo_id: str) -> Dict[str, Any]:
    """列出当前照片的蒙版。"""
    return _caught(list_masks, photo_id)


@mcp.tool
def set_mask_settings_photo(photo_id: str, settings: Dict[str, Any],
                            mask_id: str = "") -> Dict[str, Any]:
    """对当前（或 mask_id）蒙版写入白名单滑块。"""
    mid = mask_id or None
    return _caught(set_mask_settings, photo_id, settings, mid)


@mcp.tool
def propose_style_match_photo(photo_id: str, reference_path: str) -> Dict[str, Any]:
    """对照一张例图 JPEG，算出当前照片该往哪边走的 develop 处方。不改目录。
    调用方必须先看返回的 jpeg_path 和例图，再 apply_retouch_photo。"""
    return _caught(propose_style_match, photo_id, reference_path)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
