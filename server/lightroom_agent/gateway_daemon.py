"""gateway_daemon.py — Lightroom Gateway 守护进程（自研）

唯一持有 automaat 连接（单实例锁）的常驻进程，对多个客户端提供 TCP line-JSON 入口。
连接由单例后台任务维护（生命周期不跨任务，避免 anyio cancel-scope 竞态），
断开自动重连并释放锁。

协议（TCP 127.0.0.1:58766，一行 JSON）：
  请求 : {"id": "...", "tool": "get_selected_photos", "args": {...}}
  响应 : {"id": "...", "ok": true, "result": {...}}
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import signal
import sys
from typing import Any, Dict, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

log = logging.getLogger("lr-gateway")

NODE = os.environ.get("LRMCP_NODE", "node")
AUTOMAAT_SERVER = os.environ.get(
    "LRMCP_AUTOMAAT_SERVER",
    os.path.expanduser("~/repositories/lightroom-mcp-automaat/server/dist/index.js"),
)
SHIYIAI_SERVER = os.path.expanduser(
    "~/repositories/lightroom-mcp-shiyiai/server/dist/index.js")
if not os.path.exists(AUTOMAAT_SERVER) and os.path.exists(SHIYIAI_SERVER):
    AUTOMAAT_SERVER = SHIYIAI_SERVER  # 自动回退到 daemon 变体（若 automaat 缺失）


class Connection:
    """单例后台连接：enter/init/持有全在 task_loop 内完成"""

    def __init__(self) -> None:
        self._ready = asyncio.Event()
        self._session: Optional[ClientSession] = None
        self._task: Optional[asyncio.Task] = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._task_loop())

    async def _task_loop(self) -> None:
        attempt = 0
        while True:
            try:
                params = StdioServerParameters(command=NODE, args=[AUTOMAAT_SERVER])
                async with stdio_client(params) as (r, w):
                    session = ClientSession(r, w)
                    await session.initialize()
                    self._session = session
                    self._ready.set()
                    log.info("connected to automaat (instance lock held)")
                    attempt = 0
                    # 持有连接直到断开/进程退出（async with 退出自动清理子进程释放锁）
                    await asyncio.Event().wait()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self._session = None
                self._ready.clear()
                attempt += 1
                delay = min(1.0 * attempt, 6.0)
                log.warning("automaat connection lost (%s), retry in %.1fs",
                            str(e)[:100], delay)
                await asyncio.sleep(delay)

    async def call(self, tool: str, args: Dict[str, Any],
                   timeout: float = 120.0) -> Dict[str, Any]:
        if not self._ready.is_set():
            await asyncio.wait_for(self._ready.wait(), timeout=30)
        session = self._session
        if session is None:
            return {"ok": False, "error": {"code": "NOT_CONNECTED",
                                           "message": "transport not ready"}}
        try:
            res = await asyncio.wait_for(
                session.call_tool(tool, args), timeout=timeout)
        except Exception as e:
            return {"ok": False, "error": {"code": "BRIDGE", "message": str(e)[:300]}}
        if not res.content:
            return {"ok": False, "error": {"code": "EMPTY", "message": "no content"}}
        text = res.content[0].text
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = {"raw": text}
        if res.isError or (isinstance(payload, dict) and payload.get("ok") is False):
            return {"ok": False,
                    "error": {"code": "LR_ERROR", "message": text[:500]}}
        return {"ok": True, "result": payload}

    async def close(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None


class Gateway:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.conn = Connection()

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        try:
            while True:
                line = await reader.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    req = json.loads(line)
                except json.JSONDecodeError:
                    await self._send(writer, {"id": None, "ok": False,
                                              "error": {"code": "BAD_JSON"}})
                    continue
                req_id = req.get("id")
                tool = req.get("tool")
                if not tool:
                    await self._send(writer, {"id": req_id, "ok": False,
                                              "error": {"code": "NO_TOOL"}})
                    continue
                resp = await self.conn.call(tool, req.get("args") or {})
                resp["id"] = req_id
                await self._send(writer, resp)
        except (ConnectionError, asyncio.IncompleteReadError):
            pass
        except Exception as e:
            log.error("handler error: %s", e)
        finally:
            try:
                writer.close()
            except Exception:
                pass

    @staticmethod
    async def _send(writer: asyncio.StreamWriter, obj: Dict[str, Any]) -> None:
        writer.write((json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8"))
        await writer.drain()

    async def run(self) -> None:
        self.conn.start()
        server = await asyncio.start_server(self.handle, self.host, self.port)
        log.info("Lightroom Gateway listening on %s:%s", self.host, self.port)
        async with server:
            await server.serve_forever()

    async def shutdown(self) -> None:
        log.info("shutting down gateway")
        await self.conn.close()


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=58766)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s",
                        stream=sys.stderr)
    gateway = Gateway(args.host, args.port)
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(gateway.shutdown()))
        except NotImplementedError:
            pass
    try:
        await gateway.run()
    finally:
        await gateway.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
