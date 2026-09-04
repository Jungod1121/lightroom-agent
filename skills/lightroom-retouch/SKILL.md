---
name: lightroom-retouch
description: >
  把 Lightroom Classic 里一张原图修好并给用户看。先看再写：全局、AI 蒙版（天空/主体/对象/景观）、渐变、例图分区、Lr Auto。
  触发：修图、修这张、修一下、retouch、Lightroom 调色、例图风格。
---

# Lightroom 修图（先看 → 再修 → 给你看）

交付物是修后 JPEG 出现在对话里，目录里已是修后参数。

先 `scripts/start-gateway.sh`（独占插件口）。Unknown action → 让用户 **Plug-in Manager → Reload**。

## 三拍

1. `prepare_retouch_photo(photo_id)` — 不改目录。
2. **先看** `jpeg_path`（或 analysis）。
3. 全局 `apply_retouch_photo`；分区则 `create_ai_mask_photo`（sky / subject / background / objects / people / landscape）+ `set_mask_settings_photo`。
4. 贴 `after_path`。撤：`restore_retouch_photo`。

蒙版：局部滑块 0–1（曝光是 EV），默认写最后一组；指定组用 CLI `group_index`。`objects` 要用户点图；景观「水面」要用户勾选，不要替点 UI。

例图：`propose_style_match_photo` 返回 `settings`（全局）以及 `sky` / `water`（给蒙版）。先看两张图再写。

Lr 自动：`apply_auto_tone_photo`（Sensei 8 滑块，不是例图）。

## 规则

- 口令 > 例图 > 独立判断。夜景蓝/青橙不是故障。
- 裁切只走 `aspect_crop_window` + `visual_crop_to_sdk`，标准比例。禁止裸 CropTop。
- 曲线：`ToneCurvePV2012` 0–255 成对。
- 渐变：`create_gradient_mask_photo`（linear/radial），几何用 Lr 默认（线性多为自上而下）。不画笔。

## 不要

- 没看图就 apply
- 把 suggestions 当处方
- `adjust_develop_settings`
- python `gateway_daemon`
- WorkBuddy 直连 automaat（改连本仓库 MCP / gateway）
