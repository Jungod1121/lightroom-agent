#!/usr/bin/env python3
"""Demo 1 — 单张诊断闭环

流程：读取 Lightroom 选中照片 → 导出 1080px JPEG → 自研分析 → 输出诊断与建议。

前置条件：
  1. Lightroom Classic 已打开，Lightroom MCP 插件已 Start Server
  2. 图库中已选中一张照片
  3. 本仓库 server/.venv 已安装依赖（mcp/pillow/numpy）

用法：
  cd ~/Projects/lightroom-agent/server
  ./.venv/bin/python ../scripts/demo1_diagnose.py
"""
import asyncio
import json
import os
import sys

# Paths are overridable via env; defaults assume `node` on PATH and a local
# clone of automaat/lightroom-mcp. Example:
#   LRMCP_NODE=/usr/local/bin/node LRMCP_AUTOMAAT_SERVER=~/path/dist/index.js python demo1...
NODE = os.environ.get("LRMCP_NODE", "node")
AUTOMAAT_SERVER = os.environ.get(
    "LRMCP_AUTOMAAT_SERVER",
    os.path.expanduser("~/repositories/lightroom-mcp-automaat/server/dist/index.js"))
HERE = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.abspath(os.path.join(HERE, "..", "server"))
ANALYSIS_PY = os.path.join(SERVER_DIR, ".venv", "bin", "python")
EXPORT_DIR = "/tmp/lr-agent-demo"


async def run(transport):
    async with transport as (r, w):
        return r, w


def ensure_transport_free():
    """automaat server 有单实例锁（~/.config/lightroom-mcp/bridge-*.lock）。
    若其它客户端（如 WorkBuddy）正持有传输层，脚本无法并行使用。
    给出明确指引而不是静默失败。"""
    lock = os.path.expanduser("~/.config/lightroom-mcp/bridge-58763-58764.lock")
    if os.path.exists(lock):
        try:
            pid = int(open(lock).read().strip() or 0)
            os.kill(pid, 0)  # 进程仍活着
            print("!! 传输层正被其它 MCP 客户端占用（pid %d，如 Claude Desktop / WorkBuddy 等客户端拉起的 automaat server）。" % pid)
            print("   两种处理方式：")
            print("   a) 临时停用其它客户端的 lightroom 连接器（或退出该客户端），跑完再启用")
            print("   b) 在持有传输层的那个客户端会话里直接演示（分析层工具一样可用）")
            sys.exit(2)
        except (ProcessLookupError, ValueError):
            pass  # 陈旧锁，automaat server 会自行接管


async def call_with_retry(session, tool, args, tries=3, delay=8):
    """automaat 插件空闲 ~91s 会重启连接：首次调用可能超时，重试即成功"""
    import asyncio
    last = None
    for i in range(tries):
        try:
            return await session.call_tool(tool, args, timeout=35)
        except Exception as e:
            last = e
            print(f"   (attempt {i+1} failed: {str(e)[:60]} — retrying, plugin reconnecting)")
            await asyncio.sleep(delay)
    raise last


async def main():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    ensure_transport_free()
    os.makedirs(EXPORT_DIR, exist_ok=True)

    # ---- 传输层：读取选中照片 ----
    print("== [1/4] 读取选中照片（传输层）==")
    params = StdioServerParameters(command=NODE, args=[AUTOMAAT_SERVER])
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            sel = await call_with_retry(s, "get_selected_photos", {})
            data = json.loads(sel.content[0].text)
            photos = data.get("photos", [])
            if not photos:
                print("!! Lightroom 中没有选中照片——请在图库选中后重跑")
                sys.exit(1)
            photo = photos[0]
            print(f"   选中: {photo['filename']}  (rating={photo.get('rating')})")
            pid = str(photo["id"])

            print("== [2/4] 导出 1080px JPEG ==")
            exp = await call_with_retry(s, "export_photos", {
                "photo_ids": [pid], "destination": EXPORT_DIR,
                "format": "jpeg", "quality": 92, "height": 1080,
            })
            print("  ", json.loads(exp.content[0].text).get("message"))

    # ---- 分析层：诊断 ----
    jpg = os.path.join(EXPORT_DIR, photo["filename"].rsplit(".", 1)[0] + ".jpg")
    if not os.path.exists(jpg):
        print(f"!! 导出文件不存在: {jpg}")
        sys.exit(1)

    print("== [3/4] 自研分析（直方图/分区/色偏）==")
    aparams = StdioServerParameters(
        command=ANALYSIS_PY, args=["-m", "lightroom_agent.main"],
        env={**os.environ, "PYTHONPATH": SERVER_DIR})
    async with stdio_client(aparams) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            res = await s.call_tool("analyze_photo", {"path": jpg})
            d = json.loads(res.content[0].text)

    print("== [4/4] 诊断结果 ==")
    lum = d["statistics"]["Lum"]
    print(f"   亮度   均值 {lum['mean']} / 中位 {lum['median']}  "
          f"(高光溢出 {lum['hl_clip_pct']}%  阴影死黑 {lum['sh_clip_pct']}%)")
    for ch in ("R", "G", "B"):
        st = d["statistics"][ch]
        print(f"   {ch}     均值 {st['mean']:>6}  峰值档 {st['peak_bin']}")
    print(f"   色偏   R-G {d['color_cast'].get('delta_rmg')}  B-G {d['color_cast'].get('delta_bmg')}")
    print(f"   动态范围 {d['range_ev']['stops']} EV (p2={d['range_ev']['p2']} p98={d['range_ev']['p98']})")
    print("   建议:")
    for s_ in d["suggestions"]:
        print(f"     - {s_}")
    print(f"\n   分析 JSON 全文: {jpg} → analyze_photo")


if __name__ == "__main__":
    asyncio.run(main())
