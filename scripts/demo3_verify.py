#!/usr/bin/env python3
"""Demo 3 — 调参效果验证（调前/调后对比）

流程：分析基线 → 压高光/提阴影 → 再导出再分析 → 输出前后对比。
（演示"看 → 判断 → 调 → 验证"闭环的最后一步：用数据证明调对了。）

前置：同 demo1（LrC 在线 + 插件 Start + 选中照片）。

用法：
  cd ~/Projects/lightroom-agent/server
  ./.venv/bin/python ../scripts/demo3_verify.py
"""
import asyncio
import json
import os
import sys

NODE = "/Users/jungod/.workbuddy/binaries/node/versions/22.22.2/bin/node"
AUTOMAAT_SERVER = "/Users/jungod/repositories/lightroom-mcp-automaat/server/dist/index.js"
HERE = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.abspath(os.path.join(HERE, "..", "server"))
ANALYSIS_PY = os.path.join(SERVER_DIR, ".venv", "bin", "python")
EXPORT_DIR = "/tmp/lr-agent-demo-verify"


async def transport_lr():
    from mcp import StdioServerParameters
    from mcp.client.stdio import stdio_client
    params = StdioServerParameters(command=NODE, args=[AUTOMAAT_SERVER])
    return await stdio_client(params).__aenter__()


async def main():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    # 单实例锁检查（同 demo1）
    lock = os.path.expanduser("~/.config/lightroom-mcp/bridge-58763-58764.lock")
    if os.path.exists(lock):
        try:
            pid = int(open(lock).read().strip() or 0)
            os.kill(pid, 0)
            print("!! 传输层被其它 MCP 客户端占用（pid %d）——请在 WorkBuddy 停用 lightroom 连接器后重跑，"
                  "或直接在 WorkBuddy 会话里演示。" % pid)
            sys.exit(2)
        except (ProcessLookupError, ValueError):
            pass

    os.makedirs(EXPORT_DIR, exist_ok=True)

    async with stdio_client(StdioServerParameters(command=NODE, args=[AUTOMAAT_SERVER])) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            sel = json.loads((await s.call_tool("get_selected_photos", {})).content[0].text)
            if not sel.get("photos"):
                print("!! 请先在 Lightroom 选中一张照片"); sys.exit(1)
            pid = str(sel["photos"][0]["id"])

            # 建快照保护 + 记录基线参数
            await s.call_tool("create_develop_snapshot",
                              {"photo_ids": [pid], "name": "demo3-verify-baseline"})
            base = json.loads((await s.call_tool("get_develop_settings_raw",
                                                 {"photo_id": pid})).content[0].text)
            print("== 基线 develop 参数 ==")
            for k in ("Exposure2012", "Highlights2012", "Shadows2012"):
                print(f"   {k}: {base['settings'].get(k)}")

            # 调整：压高光 / 提阴影
            print("== 调整: Highlights2012 -25 / Shadows2012 +30 ==")
            await s.call_tool("adjust_develop_settings", {
                "photo_ids": [pid],
                "adjustments": {"Highlights2012": -25, "Shadows2012": 30}})

            # 导出调后版本
            exp = await s.call_tool("export_photos", {
                "photo_ids": [pid], "destination": EXPORT_DIR,
                "format": "jpeg", "quality": 92, "height": 1080})
            out = json.loads(exp.content[0].text)
            if not out.get("success"):
                print("!! 导出失败:", out); sys.exit(1)

    jpg = os.path.join(EXPORT_DIR, sel["photos"][0]["filename"].rsplit(".", 1)[0] + ".jpg")
    aparams = StdioServerParameters(
        command=ANALYSIS_PY, args=["-m", "lightroom_agent.main"],
        env={**os.environ, "PYTHONPATH": SERVER_DIR})
    async with stdio_client(aparams) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            d = json.loads((await s.call_tool("analyze_photo", {"path": jpg})).content[0].text)

    lum = d["statistics"]["Lum"]
    print("== 调后分析（对比调前请先跑 demo1 记录基线）==")
    print(f"   亮度均值 {lum['mean']}  高光溢出 {lum['hl_clip_pct']}%  阴影死黑 {lum['sh_clip_pct']}%")
    print(f"   动态范围 {d['range_ev']['stops']} EV")
    print("   建议:", "; ".join(d["suggestions"][:2]))

    # 撤销本次演示的调整（保持照片原状）
    async with stdio_client(StdioServerParameters(command=NODE, args=[AUTOMAAT_SERVER])) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            await s.call_tool("undo_last_mcp_develop_edit", {})
            print("\n== 已撤销演示调整（照片恢复原状）==")


if __name__ == "__main__":
    asyncio.run(main())
