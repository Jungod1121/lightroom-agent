"""main.py — Lightroom Agent 分析服务（自研，无插件依赖）

职责：对渲染图/照片做直方图、分区测光、色偏与曝光诊断，输出结构化建议。
配合传输层（Lightroom MCP）使用：传输层负责从 Lightroom 导出照片，
本服务负责"看懂"照片 —— 这是纯文本模型的视觉支点。

工具：
  analyze_photo(path)         分析单张照片（RGB/亮度直方图、11 区、5×5 测光、色偏、诊断）
  batch_analyze(directory)    分析目录下所有图片，返回汇总
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Union

from fastmcp import FastMCP

from lightroom_agent.analysis.histogram import analyze

logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s",
                    stream=sys.stderr)
log = logging.getLogger("lightroom-analysis")

mcp = FastMCP("Lightroom Analysis (self-built)")

SUPPORTED = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".dng")


def _ok(data: Dict[str, Any]) -> Dict[str, Any]:
    return {"ok": True, **data}


def _err(msg: str) -> Dict[str, Any]:
    return {"ok": False, "error": {"message": msg}}


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


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
