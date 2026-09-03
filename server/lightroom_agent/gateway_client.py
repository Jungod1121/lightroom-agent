"""gateway_client.py — Lightroom Gateway 客户端库（自研）

任意进程连到常驻 Gateway（127.0.0.1:58766），获得 Lightroom 访问能力，
无需直接与 automaat/插件争锁。可被脚本、demo、其它 agent 复用。

用法：
  from lightroom_agent.gateway_client import LightroomGateway
  gw = LightroomGateway()
  sel = await gw.call("get_selected_photos", {})
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Optional

log = logging.getLogger("lr-gateway-client")

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 58766


class GatewayError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message


class LightroomGateway:
    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
        self.host = host
        self.port = port

    @staticmethod
    async def ping_host(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT,
                        timeout: float = 2.0) -> bool:
        """探测 gateway 是否在运行（用于脚本提示先启动 gateway）"""
        try:
            r, w = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=timeout)
            w.close()
            return True
        except (OSError, asyncio.TimeoutError):
            return False

    async def call(self, tool: str, args: Optional[Dict[str, Any]] = None,
                   timeout: float = 120.0, retries: int = 3,
                   retry_delay: float = 2.0) -> Dict[str, Any]:
        last: Optional[Exception] = None
        for attempt in range(retries):
            try:
                return await self._call_once(tool, args or {}, timeout)
            except (ConnectionError, OSError, asyncio.IncompleteReadError) as e:
                last = e
                log.warning("gateway call attempt %d failed: %s", attempt + 1, str(e)[:100])
                await asyncio.sleep(retry_delay + attempt)
        raise GatewayError("UNREACHABLE", f"gateway not reachable: {last}")

    async def _call_once(self, tool: str, args: Dict[str, Any],
                         timeout: float) -> Dict[str, Any]:
        import uuid
        reader, writer = await asyncio.open_connection(self.host, self.port)
        try:
            req_id = uuid.uuid4().hex
            frame = {"id": req_id, "tool": tool, "args": args}
            writer.write((json.dumps(frame, ensure_ascii=False) + "\n").encode("utf-8"))
            await writer.drain()
            data = await asyncio.wait_for(reader.readline(), timeout=timeout)
            if not data:
                raise ConnectionError("gateway closed connection")
            resp = json.loads(data.decode("utf-8"))
            if not resp.get("ok"):
                err = resp.get("error") or {}
                raise GatewayError(err.get("code", "GATEWAY"),
                                   err.get("message", "unknown gateway error"))
            return resp.get("result") or {}
        finally:
            try:
                writer.close()
            except Exception:
                pass
