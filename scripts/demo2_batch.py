#!/usr/bin/env python3
"""Demo 2 — 批量一致性扫描

流程：对一个目录的渲染图跑 batch_analyze，输出逐张摘要并标出离群者。

用法：
  cd ~/Projects/lightroom-agent/server
  ./.venv/bin/python ../scripts/demo2_batch.py <图片目录> [limit]

  目录里放 jpg/png/tiff（可先用传输层把一批照片导出为 JPEG）。
"""
import asyncio
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.abspath(os.path.join(HERE, "..", "server"))
ANALYSIS_PY = os.path.join(SERVER_DIR, ".venv", "bin", "python")


async def main():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    directory = sys.argv[1] if len(sys.argv) > 1 else "/tmp/lr-agent-demo"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    if not os.path.isdir(directory):
        print(f"!! 目录不存在: {directory}")
        sys.exit(1)

    aparams = StdioServerParameters(
        command=ANALYSIS_PY, args=["-m", "lightroom_agent.main"],
        env={**os.environ, "PYTHONPATH": SERVER_DIR})
    async with stdio_client(aparams) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            res = await s.call_tool("batch_analyze", {"directory": directory, "limit": limit})
            d = json.loads(res.content[0].text)

    rows = d.get("rows", [])
    print(f"== 批量分析 {d.get('count')} 张 ==")
    print(f"{'file':<36} {'lum':>6} {'hl%':>6} {'sh%':>6} {'EV':>5}  建议")
    print("-" * 92)
    for row in rows:
        if "error" in row:
            print(f"{row['file']:<36} ERROR {row['error'][:40]}")
            continue
        sugg = "; ".join(row.get("suggestions", []))[:44]
        print(f"{row['file']:<36} {row['lum_mean']:>6.1f} {row['hl_clip_pct']:>6.2f} "
              f"{row['sh_clip_pct']:>6.2f} {row['stops']:>5.2f}  {sugg}")

    # 简单离群检测：亮度均值偏离中位 >1.5EV 等效（约 40 亮度）标记
    lums = sorted(r["lum_mean"] for r in rows if "lum_mean" in r)
    if len(lums) >= 4:
        med = lums[len(lums) // 2]
        outliers = [r for r in rows if "lum_mean" in r and abs(r["lum_mean"] - med) > 35]
        print("\n== 影调离群（与中位差 > 35 亮度）==")
        if outliers:
            for r in outliers:
                print(f"   {r['file']}  lum={r['lum_mean']}")
        else:
            print("   无——这批影调一致性良好")


if __name__ == "__main__":
    asyncio.run(main())
