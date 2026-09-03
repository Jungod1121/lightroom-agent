# Gateway（多客户端仲裁层）— 已废弃（python 路径）

**2026-09-03：不要再启动 `gateway_daemon.py`。** python MCP SDK × automaat 会掐 stdin，已实证。

现行修图路径：

1. `scripts/lr-plugin-call.mjs` 直连插件 socket（`LRMCP_AUTOMAAT_DIST` 指向 automaat `server/dist`）
2. Python `prepare_retouch` / `apply_retouch` / `restore_retouch`（`lightroom_agent.retouch.loop`）
3. Agent skill：`skills/lightroom-retouch/SKILL.md`（先看 before.jpg → 再写 → 把 after.jpg 给用户看）

常驻 node 多客户端 daemon 仍是下一刀，不是现在。

---

# 归档：原 WIP 状态

## 目标
解决 automaat 单客户端锁 + WorkBuddy 守护抢占导致"脚本要用必须先停 WorkBuddy"的问题：
一个常驻进程独占 automaat，对多个客户端提供统一 TCP 入口。

## 已实现（可运行代码）
- `server/lightroom_agent/gateway_daemon.py` — 常驻 TCP :58766，单例后台连接 automaat
- `server/lightroom_agent/gateway_client.py` — 客户端库
- `server/lightroom_agent/gw_client_mcp.py` — 面向 WorkBuddy 等客户端的 MCP 包装
  （13 工具，schema 自研简化版，无 oneOf 陷阱——已通过 WorkBuddy 枚举验证）
- `scripts/gateway.sh` — 启停脚本；LaunchAgent plist 模板在脚本注释中

## 阻塞问题（2026-09-03 实测）
python MCP SDK（mcp 4.0.2）作为 stdio client 连 automaat server 时：
1. automaat 进程启动后立即收到 "stdin ended (client exited)" —— SDK 侧未发出任何
   JSON-RPC 请求即关闭写端，automaat 随之退出
2. automaat 只连上 request 端口（58763），response 端口（58764）握不上手，
   报 "Lightroom plugin not connected"
3. 伴随 anyio cancel-scope 跨任务异常（连接生命周期跨 task 管理的竞态）

WorkBuddy（内建非 python MCP client）直连同一 automaat 工作正常 —— 结论：
**该问题在 python MCP SDK × automaat 组合，非 automaat 本身**。

## 复活的可能路径
- 用 node 写 gateway（node MCP SDK 与 automaat 同为 node 生态，大概率无此兼容问题）
- 或 gateway 直连插件 socket（TCP NDJSON + token + 心跳），绕开 automaat MCP 层
- 或等 python MCP SDK 修复 stdio client 兼容性后重试

## 已打通（2026-09-03，Grok 接手后）

**直连插件 socket，绕开 automaat MCP / python SDK / WorkBuddy oneOf。**

脚本：`scripts/lr-plugin-call.mjs`

协议（automaat Dispatcher 原样）：
request `:58763` 发一行 `{"hello":"<token>","id":"req_…","action":"set_develop_settings","params":{…}}`
response `:58764` 收回 `{"id":"…","result":{…}}`。token 读 `~/.config/lightroom-mcp/token`。

已实测 JUN_3939（id 346763）：
`set_develop_settings` → Exposure2012=0.15, Blacks2012=5, Temperature=5850, SaturationAdjustmentBlue=-15
→ export 1080px JPEG → analyze_photo 对比基线全部朝预期方向。

约束（与障碍 B 同类，但是 socket 层不是 lock 文件层）：
LrSocket 1:1。WorkBuddy 的 lightroom MCP 连着时本脚本连不上。
WorkBuddy 未占用时**不需要** automaat 实例锁——本脚本根本不启动 automaat。
用完即断，插件会自己 rebind request/response。

## 当前稳定链路（无 gateway）
WorkBuddy（内建 client）→ automaat server（单持有者）→ Lightroom 插件。
局限：WorkBuddy 占用期间第三方脚本需等待；WorkBuddy 的 oneOf schema 校验 bug
影响 set_develop_settings/adjust 类工具（可改用 apply preset / copy settings 规避）。
