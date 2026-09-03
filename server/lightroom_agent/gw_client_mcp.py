"""gw_client_mcp.py — Lightroom Gateway 客户端 MCP server（自研）

供任意 MCP 客户端（WorkBuddy / Claude Desktop / Cursor 等）配置为 "lightroom"
连接器：stdio 进程内部连常驻 Gateway → 再到 automaat → Lightroom。
由此终结多客户端争锁问题；schema 为本仓库自研简化版（无 oneOf 陷阱）。

mcp.json:
  "lightroom": {
    "command": "python", "args": ["-m", "lightroom_agent.gw_client_mcp"],
    "env": {"PYTHONPATH": ".../server"}
  }
"""
from __future__ import annotations

import logging
import sys
from typing import Any, Dict, List, Optional, Union

from fastmcp import FastMCP

from lightroom_agent.gateway_client import LightroomGateway, GatewayError

logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
mcp = FastMCP("Lightroom Gateway (lightroom-agent)")
gw = LightroomGateway()

Num = Union[int, float]
SettingValue = Union[int, float, str, bool]


def _safe(fn):
    import functools
    import inspect

    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        try:
            return {"ok": True, **await fn(*args, **kwargs)}
        except GatewayError as e:
            return {"ok": False, "error": {"code": e.code, "message": e.message}}
        except Exception as e:
            return {"ok": False, "error": {"code": "ERROR", "message": str(e)}}

    wrapper.__signature__ = inspect.signature(fn)
    return wrapper


# ---- 目录/元数据 ----

@mcp.tool
@_safe
async def get_selected_photos(limit: int = 100, offset: int = 0) -> Dict[str, Any]:
    """读取 Lightroom 中当前选中的照片列表。"""
    return {"result": await gw.call("get_selected_photos", {"limit": limit, "offset": offset})}


@mcp.tool
@_safe
async def search_photos(filename: Optional[str] = None, rating: Optional[int] = None,
                        start_date: Optional[str] = None, end_date: Optional[str] = None,
                        limit: int = 100, offset: int = 0) -> Dict[str, Any]:
    """按条件搜索 Lightroom 目录照片（文件名/星级/日期）。"""
    args: Dict[str, Any] = {"limit": limit, "offset": offset}
    if filename: args["filename"] = filename
    if rating is not None: args["rating"] = rating
    if start_date: args["start_date"] = start_date
    if end_date: args["end_date"] = end_date
    return {"result": await gw.call("search_photos", args)}


@mcp.tool
@_safe
async def get_photo_metadata(photo_id: str) -> Dict[str, Any]:
    """读取照片详细元数据（EXIF/GPS/develop 参数等）。photo_id 为 Lightroom 照片 ID 或文件路径。"""
    return {"result": await gw.call("get_photo_metadata", {"photo_id": photo_id})}


@mcp.tool
@_safe
async def export_photos(photo_ids: List[str], destination: str,
                        format: str = "jpeg", quality: int = 92,
                        width: Optional[int] = None, height: Optional[int] = None) -> Dict[str, Any]:
    """把照片导出为 JPEG/TIFF 到目标目录（分析层喂图入口）。"""
    args: Dict[str, Any] = {"photo_ids": photo_ids, "destination": destination,
                            "format": format, "quality": quality}
    if width: args["width"] = width
    if height: args["height"] = height
    return {"result": await gw.call("export_photos", args)}


# ---- Develop 参数 ----

@mcp.tool
@_safe
async def set_develop_settings(photo_id: str, settings: Dict[str, SettingValue]) -> Dict[str, Any]:
    """设置照片的 develop 参数（键用 SDK 名：Exposure2012/Highlights2012/Temperature/...）。"""
    return {"result": await gw.call("set_develop_settings",
                                    {"photo_id": photo_id, "settings": settings})}


@mcp.tool
@_safe
async def adjust_develop_settings(photo_ids: List[str],
                                  adjustments: Dict[str, Num]) -> Dict[str, Any]:
    """对照片 develop 参数做相对增量调整（如 {"Exposure2012": 0.15} 表示 +0.15EV）。"""
    return {"result": await gw.call("adjust_develop_settings",
                                    {"photo_ids": photo_ids, "adjustments": adjustments})}


@mcp.tool
@_safe
async def copy_develop_settings(source_id: str, target_ids: List[str],
                                settings: Optional[List[str]] = None) -> Dict[str, Any]:
    """把一张照片的 develop 参数复制到其它照片（可限定参数白名单）。"""
    args: Dict[str, Any] = {"source_id": source_id, "target_ids": target_ids}
    if settings: args["settings"] = settings
    return {"result": await gw.call("copy_develop_settings", args)}


@mcp.tool
@_safe
async def apply_develop_settings_to_selected(source_id: Optional[str] = None,
                                             settings: Optional[List[str]] = None,
                                             include_source: bool = False) -> Dict[str, Any]:
    """把源照片（默认选中第一张）的 develop 参数同步到其余选中照片。"""
    args: Dict[str, Any] = {"include_source": include_source}
    if source_id: args["source_id"] = source_id
    if settings: args["settings"] = settings
    return {"result": await gw.call("apply_develop_settings_to_selected", args)}


# ---- 预设 ----

@mcp.tool
@_safe
async def list_develop_presets() -> Dict[str, Any]:
    """列出 Lightroom 可见预设与插件管理的预设检查点。"""
    return {"result": await gw.call("list_develop_presets", {})}


@mcp.tool
@_safe
async def apply_develop_preset(photo_ids: List[str], preset_name: str,
                               preset_uuid: Optional[str] = None,
                               preset_scope: Optional[str] = None) -> Dict[str, Any]:
    """对照片套用指定 develop 预设（可用 UUID 精确匹配）。"""
    args: Dict[str, Any] = {"photo_ids": photo_ids, "preset_name": preset_name}
    if preset_uuid: args["preset_uuid"] = preset_uuid
    if preset_scope: args["preset_scope"] = preset_scope
    return {"result": await gw.call("apply_develop_preset", args)}


# ---- 保护与撤销 ----

@mcp.tool
@_safe
async def create_develop_snapshot(photo_ids: List[str], name: str) -> Dict[str, Any]:
    """为照片创建 develop 快照（修改前保护）。"""
    return {"result": await gw.call("create_develop_snapshot",
                                    {"photo_ids": photo_ids, "name": name})}


@mcp.tool
@_safe
async def undo_last_mcp_develop_edit() -> Dict[str, Any]:
    """撤销最近一次 MCP 发起的 develop 修改。"""
    return {"result": await gw.call("undo_last_mcp_develop_edit", {})}


@mcp.tool
@_safe
async def lightroom_undo_status() -> Dict[str, Any]:
    """查询 Lightroom 撤销/重做可用性。"""
    return {"result": await gw.call("lightroom_undo_status", {})}


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
