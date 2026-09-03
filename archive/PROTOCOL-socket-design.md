# LightroomAgent 通信协议（自研）

LrC 插件与 Python server 之间通过 TCP 通信。协议为 **NDJSON over TCP**：
每条消息是一个 UTF-8 JSON 对象，以单个 `\n` 结尾；接收端按行解析。

## 传输模型

LrSocket（Adobe SDK）单连接在多数版本上是半双工安全模型，
本项目采用**双通道**规避歧义（通道 A / 通道 B），两通道各自 bind 在 localhost 随机端口：

- **请求通道**（server → 插件）：Python 写入请求帧，插件读取。
- **响应通道**（插件 → server）：插件写入响应帧，Python 读取。

> 双通道属于 Adobe LrSocket 的实际行为约束下的工程选择，帧格式、生命周期与
> 错误语义为本项目自定义。

## 端口发现

插件启动时若端口被占用则 +1 重试（最多 20 次），最终把实际端口写入：

```
~/.config/lightroom-agent/ports.json   →   {"request": 54331, "response": 54332}
```

Python server 每次连接先读该文件；连接失败时删除本地缓存并重试，直到插件就绪。

## 帧格式

### 请求（Python → 插件）

```json
{"v": 1, "id": "uuid", "command": "system.ping", "params": {}}
```

### 响应（插件 → Python）

```json
{"v": 1, "id": "uuid", "success": true, "result": {...}}
{"v": 1, "id": "uuid", "success": false, "error": {"code": "NO_PHOTO_SELECTED", "message": "..."}}
```

### 事件（插件主动推送，可选）

```json
{"v": 1, "event": "catalog.selectionChanged", "data": {"photo_id": 123}}
```

事件没有 `id`；Python 端按 `id` 是否缺失区分事件与响应。

## 命令命名空间

| 前缀 | 用途 |
|---|---|
| `system.*` | ping / status / shutdown / reset-socket |
| `catalog.*` | 选中照片 / 搜索 / 收藏夹 / 关键词 / 评分 |
| `develop.*` | 读全量设置 / 写 key / 快照 / 撤销 / 预设 |
| `render.*` | 渲染当前编辑态预览（JPEG/TIFF）/ 直方图原始数据 |

## 错误码约定

| code | 含义 |
|---|---|
| `NOT_CONNECTED` | server 未连接插件 |
| `NO_PHOTO_SELECTED` | 操作需要选中照片 |
| `BAD_PARAMETER` | 参数不合法（含越界） |
| `SDK_ERROR` | Lightroom SDK 抛错（附 message） |
| `TIMEOUT` | 插件处理超时 |
| `BUSY` | 插件正忙（队列保护） |
