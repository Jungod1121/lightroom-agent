# Lightroom Agent 传输层研发记录（已归档）

## 结论先行

自研 Lightroom Lua 插件（LrSocket 双通道服务）**经多轮调试后放弃**，最终架构采用
"传输层复用成熟实现（shiyiai/lightroom-mcp，MIT）+ 分析层自研"。本目录保留全部
失败尝试与踩坑记录，供未来需要触碰 LrSocket 时参考，避免重走弯路。

## 为什么放弃（踩坑记录，耗时约 2.5h）

| # | 现象 | 根因 |
|---|---|---|
| 1 | `'<name>' expected near 'end'` | `context:end()` 中 `end` 是 Lua 保留字，须 `context["end"]()` |
| 2 | `Could not load toolkit script` | Lightroom 的 `require` 只支持插件根目录平铺模块，不支持子目录点路径 |
| 3 | `os.getenv` / `os.time` 为 nil | Lightroom Lua 沙箱裁剪 os 库；须只用 math/string/table |
| 4 | 全局 `json` 不存在 | Lightroom 无内置 JSON，须自带（本项目写过 Json.lua，可复用） |
| 5 | `context has already completed` | `LrSocket.bind` 须在 `LrFunctionContext.postAsyncTaskWithContext` 回调内**同步**调用；放入延迟 startAsyncTask 后 context 已结束 |
| 6 | bind 后 sockets 立即关闭 | bind 的 socket 须持有引用防 GC；且需在 context 内启动常驻循环（如 `while running do sleep end`）维持 context |
| 7 | 空闲 10s 后端口消失 | LrSocket 对无 client 连接的 listener 报 `timeout`，须在 `onError` 里显式 `socket:reconnect()` |
| 8 | resp 通道连接被插件端反复关闭 | send-mode listener 感知不到 client 断开（"假死"），后续 send 永久挂起；须在 request 新连接时强制 rebind response listener |
| 9 | onMessage 内 `startAsyncTask` 不执行 | LrSocket 回调环境创建的任务不被调度（同步分发可行但受 #8 阻塞） |

## 有效模式（shiyiai 已实证，可直接参考其源码）

- 生命周期：`postAsyncTaskWithContext` + 回调内同步 bind + `while running` 主循环管理
  socket 恢复（reconnect / rebind）+ `addCleanupHandler` 统一清理
- 响应发送：等待 `sendConnected` 再 send（最多 25s），5s 未连上触发自愈 rebind
- 客户端：两个 socket 独立自动重连（断开 1s 重试），发送走 request、读取走 response，
  **client 绝不频繁开关连接**（会导致插件端假死连接）

## 归档内容

- `lightroomagent-lrplugin-legacy/`：自研 Lua 插件完整源码（含可复用的 Json.lua）
- `PROTOCOL-socket-design.md`：自研 NDJSON 双通道协议设计（未启用，作参考）
- `bridge.py`：自研 Python TCP 桥（长连接/短连接/独立重连三个版本的最终版，未启用）
