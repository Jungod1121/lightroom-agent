<div align="center">

# Lightroom Agent

**让 AI 真正"看懂"照片的 Lightroom 分析层** — 直方图 · 分区测光 · 色偏诊断 · 批量一致性检查

Python MCP 服务 · 零 Lightroom 插件依赖 · 全自研分析算法

</div>

---

## 这是什么

Lightroom 生态的 MCP 方案（如 [automaat/lightroom-mcp](https://github.com/automaat/lightroom-mcp)，MIT；
同类衍生品有 shiyiai/lightroom-mcp 等）解决了"怎么操作 Lightroom"（读写参数、导出、套预设、撤销）——
但它们对照片内容**是盲的**：不会告诉你这张曝光如何、高光有没有溢出、哪张影调离群。

**Lightroom Agent 补上"怎么知道该操作什么"**：把照片转成可验证的结构化数据
（直方图、11 区曝光、5×5 分区测光、色偏、有效动态范围），并给出可执行的调参建议。
两者结合，AI 才能在没有人工盯着屏幕的情况下跑通
**看 → 判断 → 调 → 验证** 的完整闭环。

> 设计哲学：**各得其所**。传输层（LrSocket 插件）是 Adobe 平台深水区，复用 MIT 成熟实现
> （源仓库 automaat/lightroom-mcp）；
> 分析层是判断力所在，全部自研。

## 架构

```
┌────────────────────────────────────────────────────────────────┐
│ AI Client (any MCP client)                                      │
├──────────────────────┬─────────────────────────────────────────┤
│ mcp__lightroom__*    │   mcp__lightroom-analysis__*            │
│ (传输层 · 第三方)     │   (分析层 · 本仓库)                       │
│ automaat/lightroom-mcp│  analyze_photo(path)                   │
│ · 目录/参数读写       │   batch_analyze(directory)               │
│ · 导出 JPEG          │   └─ histogram.py (numpy 向量化, 自研)     │
│ · 预设/快照/撤销      │                                         │
└──────────┬───────────┴──────────────────────┬──────────────────┘
           │ export 渲染图                     │
           ▼                                  ▼
┌──────────────────────┐            ┌────────────────────────────┐
│ Lightroom Classic    │──渲染图──▶ │ 本地分析 (无需 Lightroom 在线)│
│ (LrC 插件 LightroomMCP)│            │                            │
└──────────────────────┘            └────────────────────────────┘
```

## 特性

- **单张诊断** `analyze_photo`：RGB/亮度直方图（64 档聚合）、溢出/死黑检测、亚当斯 11 区曝光分布、5×5 网格分区测光、中段灰度色偏判断、有效动态范围（EV），附规则引擎诊断建议
- **批量一致性** `batch_analyze`：扫描整个目录，输出每张的亮度均值/中位数、溢出比例、色偏差、建议——适合批量选片与风格一致性检查
- **自研算法**：全部统计 numpy 向量化实现，无 UI 依赖、无第三方分析库
- **零插件依赖**：纯 Python MCP 服务，输入是渲染图路径，随时可独立运行
- **诚实可验证**：输出均为结构化数值，杜绝"看图说话"式幻觉

## 系统能力全景

本仓库（分析层）与传输层（automaat/lightroom-mcp）组合后，可对 Lightroom 完成：

| 能力 | 归属 | 说明 |
|---|---|---|
| 看：把照片变数据 | 分析层 | 直方图/11 区/5×5 测光/色偏/EV/诊断（本仓库核心） |
| 批量风格一致性扫描 | 分析层 | 一批素材中找影调/色偏离群者 |
| 读/写照片与目录 | 传输层 | 选中照片、搜索、元数据、收藏夹、关键词、星级 |
| develop 全量参数 | 传输层 | 180+ 键读写、相对增量调整、曲线 |
| 预设体系 | 传输层 | 应用/创建检查点/预设间 diff/导出（preset round-trip） |
| 快照/撤销 | 传输层 | 改前建快照，undo/redo 一键回滚 |
| 批量同步 | 传输层 | 一套参数/预设应用到多张 |

→ 完整闭环：**export 渲染图 → 分析出问题 → 读取参数甄别 → 调参/套预设 → 再导出验证**

## 快速开始

### 依赖

- Python ≥ 3.11
- Lightroom Classic
- [automaat/lightroom-mcp](https://github.com/automaat/lightroom-mcp)（传输层，MCP server + LrC 插件，按官方 README 安装并 Start Server）

### 安装

```bash
cd ~/Projects/lightroom-agent/server
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

### 配置到 MCP 客户端（完整双 server 示例）

任意 MCP 客户端的 server 配置（Claude Desktop 的 claude_desktop_config.json、Claude Code / Cursor / VS Code 的 mcp 配置、WorkBuddy 的 ~/.workbuddy/mcp.json 等）：

```json
{
  "mcpServers": {
    "lightroom": {
      "command": "/path/to/node",
      "args": ["/path/to/lightroom-mcp/server/dist/index.js"]
    },
    "lightroom-analysis": {
      "command": "/Users/jungod/Projects/lightroom-agent/server/.venv/bin/python",
      "args": ["-m", "lightroom_agent.main"],
      "env": { "PYTHONPATH": "/Users/jungod/Projects/lightroom-agent/server" }
    }
  }
}
```

修改配置后重启客户端应用。本仓库提供两个工具：`analyze_photo`、`batch_analyze`。

> 使用提示（传输层 automaat 版）：插件带空闲心跳检测（约 91s 无活动会重启连接）。
> 若会话空闲较久后第一次调用超时，**重试一次即可**（连接自动重建后即正常）。

### 本地直接运行（无需 MCP 客户端）

```bash
cd ~/Projects/lightroom-agent/server
./.venv/bin/python -c "
from lightroom_agent.analysis.histogram import analyze
r = analyze('/path/to/photo.jpg')
print(r.to_dict())
"
```

## 工具文档

### `analyze_photo(path)`

分析单张照片，返回结构化 JSON：

| 字段 | 说明 |
|---|---|
| `image` | 宽/高 |
| `statistics` | 每通道（R/G/B/Lum）均值、中位数、高光/阴影溢出比例、峰值档位 |
| `bins64` | 每通道 64 档直方图（每档 4 bin 聚合） |
| `zones_pct` | 亚当斯 11 区像素占比 |
| `grid5_lum` | 5×5 网格亮度均值（构图亮度分布） |
| `color_cast` | 中段灰度区 R/G/B 均值与差（色偏依据） |
| `range_ev` | 有效动态范围（p2–p98，EV 近似） |
| `suggestions` | 规则引擎给出的可执行建议列表 |

### `batch_analyze(directory, limit=50)`

批量分析目录内图片，逐张给出亮度/溢出/色偏摘要 + 建议——用于：
- 批量选片（找曝光异常的）
- 风格一致性（找影调离群的）
- 调色前摸底（一批素材的基线）

## 典型工作流

```
1. 导出：传输层 export 当前照片为 1080px JPEG
2. 分析：analyze_photo(导出的 JPEG)   → 得到直方图 + 建议
3. 判断：结合 develop 参数（传输层读取）甄别建议（排除刻意风格的误报）
4. 调整：传输层 adjust_develop_settings / apply preset
5. 验证：再次导出 + analyze，对比高光/阴影溢出是否改善
```

## 能力与边界

- ✅ 可验证：所有输出是数值，判断链可复核
- ✅ 支持 jpg/png/tiff/dng（PIL 可解码即可）
- ✅ 分析独立于 Lightroom：只要拿到渲染图即可运行（离线/批量皆可）
- ⚠️ 诊断规则是**启发式**：对刻意风格（如青橙/黑白）存在误报，需结合参数甄别
- ⚠️ 输入是渲染图（8bit JPEG/TIFF），与 LrC UI 直方图同源（同一渲染管线）但位深/色彩空间可能略异；如需更高精度可导出 TIFF
- ⚠️ 不包含 Lightroom 操作能力（读写参数/导出/预设）——那些由传输层提供，本仓库专注分析
- ⚠️ 纯文本 LLM 下"看图"不可靠：本仓库的价值就是把"看"变成数值，让判断不依赖视觉猜测

## 与现有开源的关系（不抄袭声明）

| 组件 | 来源 | 说明 |
|---|---|---|
| 分析层（本仓库全部代码） | 自研，Apache-2.0 | histogram.py 算法、MCP 工具、诊断规则均为独立实现 |
| 传输层 | [automaat/lightroom-mcp](https://github.com/automaat/lightroom-mcp)（MIT，**源仓库**） | 运行时外部依赖，按 MIT 条款使用，未并入本仓库代码 |
| 归档研发记录 | 本仓库 archive/ | 自研 Lua 插件尝试与 LrSocket 踩坑记录，供参考不供使用 |

> 溯源说明：Lightroom MCP 类项目的源头是 [automaat/lightroom-mcp](https://github.com/automaat/lightroom-mcp)
> （MIT，维护者 Marcin Skalski）。社区中的同类仓库（如 shiyiai/lightroom-mcp）为其衍生品。
> 本项目引用一律以源仓库为准。

## Roadmap（集大成路线）

- [x] 单张直方图/曝光/色偏诊断
- [x] 批量一致性分析
- [ ] 选区直方图（结合蒙版/裁剪区域分析）
- [ ] 风格度量与自动聚类（从标杆图提炼风格指纹 → 找风格匹配素材）
- [ ] 调参效果回归验证（调前/调后指标对比报告）
- [ ] 自动选片规则引擎（曝光/色偏/动态范围多维评分）

## Demo 演示

三支可复跑脚本见 [scripts/](scripts/)（demo1 单张诊断 / demo2 批量扫描 / demo3 调参验证），讲解要点与录制注意事项见 [docs/DEMO.md](docs/DEMO.md)；架构图生图提示词见 [docs/ARCHITECTURE-PROMPT.md](docs/ARCHITECTURE-PROMPT.md)，覆盖：
单张诊断闭环 / 批量一致性扫描 / 调参效果验证（含录制前注意事项）。

## 开发

```bash
cd ~/Projects/lightroom-agent/server
./.venv/bin/pip install -r requirements.txt
./.venv/bin/python -m lightroom_agent.main   # 启动 MCP server（stdio）
```

测试（直方图算法）：
```bash
./.venv/bin/python -c "
from lightroom_agent.analysis.histogram import analyze
import json; print(json.dumps(analyze('test.jpg').to_dict(), ensure_ascii=False))
"
```

## License

- 本仓库代码：Apache-2.0
- 归档目录（archive/）内容：仅供学习参考，包含第三方项目源码片段时以原项目许可证为准
