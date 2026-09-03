---
name: lightroom-retouch
description: >
  把 Lightroom Classic 里一张原图修好并给用户看。三拍：先看当前图，再写入 develop，再展示修后图。
  用户没指定风格则独立判断；指定了按口令。触发：修图、修这张、修一下、retouch、Lightroom 调色、给这张图修一下。
---

# Lightroom 修图（先看 → 再修 → 给你看）

用户把 LrC 里一张原图交给你。交付物是**修后 JPEG 出现在对话里**，并且目录里已经是修后参数。不要停在处方草稿。

## 三拍（硬闸）

1. `get_selected_photos` 或用户给的 `photo_id` → `prepare_retouch_photo(photo_id)`。
2. **先看**：能读图就把返回的 `jpeg_path` 读进上下文；不能看图就读 `analysis` + `develop`。没看过禁止 `apply`。
3. `apply_retouch_photo(photo_id, settings, snapshot_id)`，`snapshot_id` 必须来自刚才的 prepare。
4. **给你看**：把返回的 `after_path` 读进对话。只报「曝光 +0.15」算失败。
5. 用户说「撤」→ `restore_retouch_photo(photo_id, snapshot_id)`。

工具在 `lightroom-analysis` MCP（`prepare_retouch_photo` / `apply_retouch_photo` / `restore_retouch_photo`）。没有 MCP 时用仓库里同等 Python API。

WorkBuddy 若连着 automaat lightroom 连接器，插件口是 1:1，会失败。先让用户停掉那个连接器。

## 判断

| 用户说了什么 | 你怎么修 |
|---|---|
| 只给照片 | 独立判断这张怎样更好。不是套 Urban Teal，不是把夜景修成白天。 |
| 有口令（再冷 / 留蓝 / 别提亮 / 青橙…） | 口令压过独立判断。 |
| 给了例图 | `propose_style_match_photo` → 先看当前图和例图 → 再 apply。味道靠近，不是像素拷贝。 |
| 要 Lr 自动 | `apply_auto_tone_photo`：就是 Develop 里那个 Auto（Sensei 8 滑块），不是例图风格。 |

- 能看图：观感定方向，`analysis` 定幅度。
- 风格不是故障：夜景蓝、死黑多、青橙，不要当「偏色」纠正，除非用户要纠。
- 一次 ≤6 个 develop 键。裁切只在明显歪或废边时动，reasons 里写为什么。
- 顺序：影调（基本面板）→ 曲线 → HSL → 裁切（构图已经坏了则裁切提前）。
- 裁切用**视觉方向**，经 `aspect_crop_window`（标准比例）+ `visual_crop_to_sdk`。禁止只写 `CropTop`，禁止 5:6 这类随边比。允许 1:1 / 4:5 / 2:3 / 3:2 / 3:4 / 4:3 / 16:9 / 9:16。竖拍 RAW 的 CropTop 往往是画面左边。见 `docs/knowledge/crop-orientation.md`。
- 曲线用 `ToneCurvePV2012` 点列（0–255 成对，从 0 到 255）+ `ToneCurveName2012=Custom`。见 `docs/knowledge/curves.md`。

## 允许写入的键

只许这些（服务端白名单，其它键会拒绝）：

- 影调：`Exposure2012` `Contrast2012` `Highlights2012` `Shadows2012` `Whites2012` `Blacks2012`
- 存在感：`Texture` `Clarity2012` `Dehaze` `Vibrance` `Saturation`
- 白平衡：`Temperature` `Tint`
- HSL：`HueAdjustment*` `SaturationAdjustment*` `LuminanceAdjustment*`（Red/Orange/Yellow/Green/Aqua/Blue/Purple/Magenta）
- 裁切：必须四条边一起写，且来自 `visual_crop_to_sdk`（不是裸 CropTop）
- 曲线：`ToneCurvePV2012`（及可选 RGB 通道）+ `ToneCurveName2012`；或参数曲线 `Parametric*`

禁止：校准、分离色调、锐化降噪、镜头配置、蒙版。裁切不要写像素。知识库：`docs/knowledge/`。

## 不要做的

- 没看 `jpeg_path` / `analysis` 就 apply。
- 把 histogram `suggestions` 当处方（那是证据，常有夜景误报）。
- 调用不存在的 `adjust_develop_settings`。
- 启动 python `gateway_daemon`（已废弃）。
