"""bridge.py — 与 LightroomAgent Lua 插件的桥接客户端（NDJSON，自研）

连接模型（对齐 shiyiai daemon 实证）：两个持久 socket，各自独立自动重连。
- req：发请求。首次建立会触发插件对 response listener 的一次性 rebind。
- resp：收响应。后台常驻连接 + 读循环；断开后仅重连 resp，绝不重建 req
  （否则每次重建都触发 rebind，导致 resp 永远被关）。
- client 侧绝不频繁开关连接（LrSocket send-mode 感知不到 client 断开，
  插件端会留下"假死"连接对象导致后续 send 永久挂起）。
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

PORTS_FILE = "/tmp/lightroom_agent_ports.json"
RECONNECT_DELAY = 1.0


class BridgeError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message


class LightroomBridge:
    def __init__(self, host: str = "localhost"):
        self.host = host
        self._req_w: Optional[asyncio.StreamWriter] = None
        self._token: Optional[str] = None
        self._pending: Dict[str, asyncio.Future] = {}
        self._resp_ok = asyncio.Event()
        self._resp_task: Optional[asyncio.Task] = None
        self._line_buffer = b""
        self._lock = asyncio.Lock()

    @staticmethod
    def _read_ports() -> Optional[Dict[str, Any]]:
        try:
            with open(PORTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return None

    # ---- req 通道（发请求；保持）----
    async def _ensure_req(self) -> None:
        if self._req_w is not None:
            return
        for _ in range(5):
            ports = self._read_ports()
            if ports and "request" in ports:
                try:
                    _, w = await asyncio.open_connection(self.host, int(ports["request"]))
                    self._req_w = w
                    self._token = ports.get("token")
                    log.info("request channel established")
                    return
                except OSError as e:
                    log.warning("req connect failed: %s", e)
            await asyncio.sleep(RECONNECT_DELAY)
        raise BridgeError("NOT_CONNECTED", "request channel unreachable")

    # ---- resp 通道（收响应；常驻后台任务，独立重连）----
    async def _resp_loop(self) -> None:
        while True:
            ports = self._read_ports()
            reader = None
            if ports and "response" in ports:
                try:
                    reader, _ = await asyncio.open_connection(self.host, int(ports["response"]))
                except OSError as e:
                    log.warning("resp connect failed: %s", e)
            if reader is None:
                await asyncio.sleep(RECONNECT_DELAY)
                continue
            self._resp_ok.set()
            log.info("response channel established")
            try:
                while True:
                    data = await reader.read(65536)
                    if not data:
                        break
                    self._line_buffer += data
                    while b"\n" in self._line_buffer:
                        line, self._line_buffer = self._line_buffer.split(b"\n", 1)
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            msg = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        msg_id = msg.get("id")
                        if msg_id and msg_id in self._pending:
                            fut = self._pending.pop(msg_id)
                            if not fut.done():
                                fut.set_result(msg)
            except (OSError, ConnectionError) as e:
                log.warning("resp read error: %s", e)
            finally:
                self._resp_ok.clear()
                log.info("response channel lost, reconnecting...")
                await asyncio.sleep(RECONNECT_DELAY)

    def start_resp_loop(self) -> None:
        if self._resp_task is None or self._resp_task.done():
            self._resp_task = asyncio.create_task(self._resp_loop())

    # ---- 主调用 ----
    async def call(self, command: str, params: Optional[Dict] = None,
                   timeout: float = 60.0) -> Dict[str, Any]:
        last_err: Optional[Exception] = None
        for attempt in range(4):
            try:
                self.start_resp_loop()  # 确保 resp 常驻连接任务在跑
                await self._ensure_req()
                # 等待 resp 通道就绪（最长 timeout 的一半）
                try:
                    await asyncio.wait_for(self._resp_ok.wait(), timeout=min(timeout, 20))
                except asyncio.TimeoutError:
                    raise BridgeError("NOT_CONNECTED", "response channel not ready")
                assert self._req_w is not None
                msg_id = uuid.uuid4().hex
                frame: Dict[str, Any] = {"v": 1, "id": msg_id, "command": command,
                                         "params": params or {}}
                if self._token:
                    frame["token"] = self._token
                fut: asyncio.Future = asyncio.get_running_loop().create_future()
                self._pending[msg_id] = fut
                try:
                    self._req_w.write((json.dumps(frame, ensure_ascii=False) + "\n").encode("utf-8"))
                    await self._req_w.drain()
                    resp = await asyncio.wait_for(fut, timeout=timeout)
                finally:
                    self._pending.pop(msg_id, None)
                if not resp.get("success"):
                    err = resp.get("error") or {}
                    raise BridgeError(err.get("code", "SDK_ERROR"), err.get("message", "unknown error"))
                return resp.get("result") or {}
            except BridgeError:
                raise
            except (OSError, ConnectionError) as e:
                last_err = e
                log.warning("call attempt %d failed: %s", attempt + 1, e)
                self._reset_req()
                await asyncio.sleep(0.5)
        raise BridgeError("NOT_CONNECTED", f"cannot reach plugin: {last_err}")

    def _reset_req(self) -> None:
        if self._req_w:
            try:
                self._req_w.close()
            except Exception:
                pass
        self._req_w = None

    async def close(self) -> None:
        self._reset_req()
        if self._resp_task:
            self._resp_task.cancel()
            self._resp_task = None
