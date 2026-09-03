# 修图知识库（给 agent，也给人看）

来源：Adobe 社区 johnrellis 的 SDK 说明、stecman AutoCrop 的朝向换算、
SRL Lounge / 站酷 / 知乎上的影调与曲线常识。不是风格滤镜说明书。

| 文件 | 何时读 |
|---|---|
| [tone-basic.md](tone-basic.md) | 基本面板 vs 曲线，先动哪一层 |
| [curves.md](curves.md) | `ToneCurvePV2012` 点列格式、S 曲线、通道曲线 |
| [crop-orientation.md](crop-orientation.md) | 为什么 CropTop 会砍竖拍的左边；视觉裁切 → SDK；标准比例 |
| [style-match.md](style-match.md) | 例图指纹 → develop 处方；不爬网下大师图 |

修图时：**视觉方向（上/左/下/右）只通过 `visual_crop_to_sdk()` 写入**，禁止直接塞 `CropTop`。
