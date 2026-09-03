# 裁切坐标：视觉方向 ≠ CropTop

## 事故（JUN_3827）

只写了 `CropTop = 0.15 / 0.20`，导出从 720×1080 变成 612×1080、576×1080——**宽度变了，高度没变**。用户看到的是左边被砍，不是上边。

## 原因

Nikon 竖拍 RAW 像素仍是横的（本例 sips 5568×3712），用 EXIF/Lr `orientation` 转成竖幅显示（目录 dimensions 3712×5568）。

**CropLeft/Top/Right/Bottom 永远相对未旋转的像素阵（orientation `AB`）**，不是你在屏幕上看到的上/下/左/右。
([johnrellis](https://community.adobe.com/t5/lightroom-classic-discussions/sdk-computing-the-corners-of-a-crop-rectangle/td-p/12995794)；stecman AutoCrop)

朝向码（两字母 = 像素阵底边的两个角）：

```
AB 横正常     BC 逆时针90     CD 180      DA 顺时针90（竖拍常见）
```

本机 3827：`CropTop`（SDK）= 画面**左边** → 朝向是 **DA**。

## 写法

视觉裁切（你看见的上/左/下/右，0–1，上<下，左<右）必须经
`lightroom_agent.retouch.crop.visual_crop_to_sdk()` 再写入。
四条边一起写，缺边会落到 0，裁出来是一条缝。

竖拍 DA 上裁 20%：

```
视觉 top=0.20, left=0, right=1, bottom=1
→ CropLeft=0, CropTop=0, CropRight=0.80, CropBottom=1
```

## 只许标准比例

禁止 5:6 这种随边裁。用 `aspect_crop_window(w, h, "2:3", anchor="bottom", scale=0.85)` 拿视觉窗，再 `visual_crop_to_sdk`。

允许：`1:1` `4:5` `5:4` `2:3` `3:2` `3:4` `4:3` `9:16` `16:9`。

原片已是 2:3 时，只砍一边会破坏比例——要少天就整框按 2:3 下移/略放大，左右一起收。
