# HANDOFF — 修图任务交接（给 grok build / 任何接手 agent）

> 目标：把 JUN_3939 这张照片修好（四项已诊断的调整），
> 并解决"为什么我调不了 Lightroom 参数"的工具链问题。
> 今天是 2026-09-03，机器是 macOS（用户 jungod）。

## 一、你要达成的结果

照片 **JUN_3939**（Lightroom id `346763`，8/3 21:06 威尼斯夜景，ISO 8000）已完成**分析诊断**（直方图基线），
处方（四项相对调整，全部已确认合理）：

| 参数（SDK 名） | 当前值 | 目标调整 | 理由 |
|---|---|---|---|
| Exposure2012 | 0 | **+0.15** | 暗部占比高，整体微提 |
| Blacks2012 | -13 | **+18 → +5** | 红通道暗部堆积，拉开黑场 |
| Temperature | 5600 | **+250 → 5850** | B-G +20.5 过冷，向暖中和 |
| SaturationAdjustmentBlue | 0 | **-15** | 压制夜景蓝紫过度 |

**验证**：调整后导出 1080px JPEG → 用自研分析 `analyze_photo` 对比基线
（基线：Lum mean 84.77/median 68，B-G +20.5，R 通道 sh_clip 2.13%，EV 3.31）。
预期：均值略升、R 阴影 2.13% 下降、B-G 差值收敛。

## 二、架构速览（30 秒）

```
WorkBuddy(或其他 MCP 客户端)
   └─ mcp__lightroom__*     传输层：automaat/lightroom-mcp（MIT，Node server + LrC Lua 插件）
   └─ mcp__lightroom-analysis__*  分析层（自研）~/Projects/lightroom-agent
```

- 传输层代码：`~/repositories/lightroom-mcp-automaat/server`（v0.13.0，已 build）
- LrC 插件：`~/Library/Application Support/Adobe/Lightroom/Modules/LightroomMCP.lrplugin`
- 插件监听：localhost `58763`(request) `58764`(response)；token 文件 `~/.config/lightroom-mcp/token`
- 自研仓库：`~/Projects/lightroom-agent`（analysis 层 + WIP gateway；GitHub Jungod1121/lightroom-agent）
- 关键文档：`~/Projects/lightroom-agent/archive/README.md`（LrSocket 踩坑）、`docs/gateway-status.md`（gateway WIP）
- 插件日志：`~/Library/Logs/Adobe/Lightroom/LrClassicLogs/LightroomMCP.log`

## 三、为什么"调参"现在做不了（核心障碍，已排查殆尽）

调参需要调用 automaat 的 `adjust_develop_settings` 或 `set_develop_settings`（MCP tools），
当前**三条路全堵**：

### 障碍 A：WorkBuddy 客户端 bug（当前正在用）
- `set_develop_settings` 的 schema 每个参数是 `oneOf:[number|string|boolean]`，
  **WorkBuddy 校验器无法通过任何值**（数字/字符串都报 "must match exactly one schema"）。
- `adjust_develop_settings` 在 WorkBuddy 工具索引中**加载不出来**（ToolSearch 总是错误返回别的工具）。
- 影响：WorkBuddy 会话里能读照片/导出/建预设，**唯独不能数值调参**。
- 已确认 WorkBuddy 里能用的工具：get_selected_photos、search_photos、get_photo_metadata、
  export_photos、list/apply/get/export/create_develop_preset、copy_develop_settings（schema 均为简单类型）。

### 障碍 B：单实例锁（automaat 架构限制）
- automaat server 有单实例锁（`~/.config/lightroom-mcp/bridge-58763-58764.lock`，pid 文件）。
- WorkBuddy 持锁进程被杀后**立即守护复活** → 任何第三方（python/CLI/脚本）抢不到锁。
- 用 WorkBuddy 时，外部进程全部被拒："Another Lightroom MCP bridge is already running (pid X)"。
- **要让外部进程用：先在 WorkBuddy 连接器管理停用 `lightroom`，再运行外部脚本。**

### 障碍 C：python MCP SDK × automaat 兼容问题
- python mcp 包（4.0.2）作为 stdio client 连 automaat：spawn 后 automaat 立即收
  "stdin ended (client exited)" 退出；连上 request 端口但 response 端口握不上手，
  报 "Lightroom plugin not connected"；伴随 anyio cancel-scope 跨任务异常。
- WorkBuddy（非 python 客户端）直连同一 automaat 正常 → 问题在 python SDK 组合。
- 手写 JSON-RPC stdio 客户端也失败（initialize 时 server stdout 关闭 —— 因为锁被 WorkBuddy 占）。

### 已尝试的自研仲裁方案（WIP，勿重复踩）
`~/Projects/lightroom-agent/server/lightroom_agent/gateway_daemon.py`（常驻独占 automaat + TCP 多客户端）
被障碍 C 挡住（python SDK）。复活路径在 `docs/gateway-status.md`：
- 用 **node** 写 gateway（node MCP SDK 与 automaat 同生态，大概率无 C 问题）；或
- gateway 直连插件 socket（NDJSON+token，见 archive/ 协议设计）；或
- 等 python MCP SDK 修复。

## 四、请你尝试的路径（按推荐顺序）

1. **修 WorkBuddy 侧**：如果 grok build 能改 WorkBuddy 客户端/或写一个 schema 修复层——
   `oneOf` 校验 bug 是最大杠杆（修好后 WorkBuddy 内直接 adjust）。
2. **node gateway**：照 `gateway-status.md` 复活路径写 node 版 daemon（30-50 行内可行原型），
   使 python/脚本也能经它调参 → 多客户端问题一并解决。
3. **WorkBuddy 停用 lightroom 连接器后**，用以下任一外部通道调参（此时锁空闲）：
   - `python mcp` 直连 automaat（若 SDK 兼容问题只出现在锁竞争时，可能解锁后可用）
   - 手写 stdio JSON-RPC（`/tmp/quick_adjust.py` 有半成品，需先确认无锁竞争）
   - 或 automaat 源码级：`~/repositories/lightroom-mcp-automaat/server/dist`（node）——
     直接在 node 里 require dist 的模块做单次 adjust 调用（最贴近 automaat 自身实现，最可能成功）
4. **最保底**：让用户手动在 LrC 拨 4 个值（见第一节表格，位置：基本面板曝光/黑场/色温 + HSL 蓝饱和度）≈20 秒。

## 五、可复用的自研资产（不要重写）

- 分析：`~/Projects/lightroom-agent/server/lightroom_agent/analysis/histogram.py` + MCP `main.py`
  （`analyze_photo` / `batch_analyze`，numpy 实现，独立可用）
- 风格预设已提炼：`~/Projects/lightroom-agent/presets/Jungod Urban Teal v1.lrtemplate`
- demo 脚本：`~/Projects/lightroom-agent/scripts/demo1-3`
- 自研 MCP 客户端包装（schema 已修好无 oneOf，可作 WorkBuddy 替代配置）：
  `server/lightroom_agent/gw_client_mcp.py`（13 工具，已通过枚举验证）
- gateway 三件套：`gateway_daemon.py` / `gateway_client.py` / `scripts/gateway.sh`

## 六、验证命令（修完后跑）

```bash
# 1) 读回参数确认
# 2) 导出（destination 目录需先 mkdir -p）
# 3) 分析对比基线
cd ~/Projects/lightroom-agent/server
./.venv/bin/python -c "
from lightroom_agent.analysis.histogram import analyze
print(analyze('/tmp/lr-retouch/JUN_3939.jpg').to_dict()['statistics']['Lum'])
"
```

## 七、规矩

- **不要改 LrC Modules 里的插件文件**（除非要换插件版本并重启 LrC）
- 改 `~/.workbuddy/mcp.json` 后**必须重启 WorkBuddy** 才生效
- 外部进程用传输层前，确认锁空闲（`cat ~/.config/lightroom-mcp/bridge-58763-58764.lock`）
- LrSocket 深水区先读 `archive/README.md` 的 9 条踩坑再动手
- 用户核心诉求排序：**先把 3939 修好（可接受手动 20 秒兜底）→ 再解决调参通道的易用性**
