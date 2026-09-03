"""
histogram.py — 直方图与曝光/色彩诊断分析（自研算法）

输入：一张渲染图（PIL Image 或路径）
输出：结构化 dict：
  - channels: R/G/B/Lum 各 256-bin 直方图（按 64 档聚合返回，避免超大 payload）
  - clipping: 各通道与亮度的高光/阴影溢出比例
  - zones: 11 区曝光分布（亚当斯分区近似）
  - grid5: 5×5 亮度均值矩阵
  - cast: 中段灰度区色偏判断
  - range_ev: 有效动态范围（p2–p98 亮度，单位 EV/stop 近似）
  - suggestions: 规则引擎给出的可执行建议

实现要点：全部统计在 numpy 上向量化；不做任何 UI/绘图依赖。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np
from PIL import Image

# Rec.709 亮度系数
_LUMA = (0.2126, 0.7152, 0.0722)
# 溢出阈值
_HL = 250
_SH = 5


@dataclass
class HistogramResult:
    width: int = 0
    height: int = 0
    bins64: Dict[str, List[int]] = field(default_factory=dict)
    clipping: Dict[str, Dict[str, float]] = field(default_factory=dict)
    zones: List[float] = field(default_factory=list)
    grid5: List[List[float]] = field(default_factory=list)
    cast: Dict[str, float] = field(default_factory=dict)
    range_ev: Dict[str, float] = field(default_factory=dict)
    statistics: Dict[str, Dict[str, float]] = field(default_factory=dict)
    suggestions: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "image": {"width": self.width, "height": self.height},
            "bins64": self.bins64,
            "clipping": self.clipping,
            "zones_pct": self.zones,
            "grid5_lum": self.grid5,
            "color_cast": self.cast,
            "range_ev": self.range_ev,
            "statistics": self.statistics,
            "suggestions": self.suggestions,
        }


def _percent(v: float) -> float:
    return round(v * 100, 2)


def _stat64(hist: np.ndarray) -> List[int]:
    """256-bin 直方图 -> 64 档（每 4 bin 求和），转 int 列表减小 payload"""
    return hist.reshape(64, 4).sum(axis=1).tolist()


def analyze(img: "Image.Image | str") -> HistogramResult:
    if isinstance(img, str):
        img = Image.open(img)
    img = img.convert("RGB")
    arr = np.asarray(img, dtype=np.uint8)
    h, w, _ = arr.shape
    res = HistogramResult(width=w, height=h)

    total = float(h * w)
    r, g, b = arr[..., 0].astype(np.int16), arr[..., 1].astype(np.int16), arr[..., 2].astype(np.int16)
    lum = (r * _LUMA[0] + g * _LUMA[1] + b * _LUMA[2]).astype(np.uint8)

    channels = {"R": r, "G": g, "B": b, "Lum": lum}

    # 1) 直方图 + 统计
    for name, ch in channels.items():
        hist = np.bincount(ch.ravel(), minlength=256).astype(np.float64)
        res.bins64[name] = _stat64(hist)
        res.statistics[name] = {
            "mean": round(float(ch.mean()), 2),
            "median": round(float(np.median(ch)), 2),
            "hl_clip_pct": _percent((ch >= _HL).sum() / total),
            "sh_clip_pct": _percent((ch <= _SH).sum() / total),
            "peak_bin": int(np.argmax(hist)),
        }

    # 2) clipping 摘要
    res.clipping = {name: res.statistics[name] for name in ("R", "G", "B", "Lum")}

    # 3) 亚当斯 11 区（0..255 均匀切 11 档，简化映射）
    zone_edges = np.linspace(0, 256, 12)
    counts, _ = np.histogram(lum.ravel(), bins=zone_edges)
    res.zones = [round(float(c) / total * 100, 2) for c in counts]

    # 4) 5×5 网格亮度均值
    g5 = []
    for gy in range(5):
        row = []
        for gx in range(5):
            cell = lum[gy * h // 5:(gy + 1) * h // 5, gx * w // 5:(gx + 1) * w // 5]
            row.append(round(float(cell.mean()), 1))
        g5.append(row)
    res.grid5 = g5

    # 5) 色偏：取中段亮度像素（避开死黑/死白）的 RGB 均值差
    mid_mask = (lum > 30) & (lum < 225)
    if mid_mask.sum() > 1000:
        mr, mg, mb = (
            float(r[mid_mask].mean()),
            float(g[mid_mask].mean()),
            float(b[mid_mask].mean()),
        )
        res.cast = {
            "r": round(mr, 1), "g": round(mg, 1), "b": round(mb, 1),
            "delta_rmg": round(mr - mg, 1),
            "delta_bmg": round(mb - mg, 1),
        }
    else:
        res.cast = {}

    # 6) 有效动态范围（EV 近似：亮度 p2–p98 的 log2 跨度）
    p2, p98 = np.percentile(lum, [2, 98])
    ev = np.log2(max(p98, 1.0) / max(p2, 1.0)) if p2 > 0 else 0.0
    res.range_ev = {
        "p2": round(float(p2), 1),
        "p98": round(float(p98), 1),
        "stops": round(float(ev), 2),
    }

    # 7) 诊断建议（简单规则引擎）
    s = res.suggestions
    lm = res.statistics["Lum"]
    if lm["sh_clip_pct"] > 5:
        s.append(f"阴影死黑 {lm['sh_clip_pct']}%：提 Shadows 或 Blacks，防止暗部细节丢失")
    elif lm["mean"] < 70:
        s.append(f"整体偏暗（均值 {lm['mean']}）：可小幅提 Exposure(+0.2~0.4)")
    if lm["hl_clip_pct"] > 1:
        s.append(f"高光溢出 {lm['hl_clip_pct']}%：压 Highlights 或检查白场")
    elif lm["mean"] > 200:
        s.append(f"整体偏亮（均值 {lm['mean']}）：考虑降曝光保留层次")
    if res.cast:
        drg, dbg = res.cast["delta_rmg"], res.cast["delta_bmg"]
        if drg > 12:
            s.append(f"整体偏暖（R-G 差 {drg}）：如非刻意风格可向冷调回调色温")
        elif drg < -12:
            s.append(f"整体偏冷（R-G 差 {drg}）：如非刻意风格可向暖调回调色温")
        if dbg > 12:
            s.append("整体偏品红倾向（B-G 差高）")
        elif dbg < -12:
            s.append("整体偏绿倾向（B-G 差负）")
    if lm["median"] < 60 and res.zones[0] + res.zones[1] > 40:
        s.append("低区占比高：典型夜景/低调片，确认主体是否淹没在暗部")
    if not s:
        s.append("曝光与色彩分布均衡，无明显溢出")

    return res


def clipping_mask(img: "Image.Image | str", mode: str = "hl") -> "Image.Image":
    """返回溢出高光(>250)或阴影(<5)的伪彩标记图（用于叠加显示），未使用时可忽略"""
    if isinstance(img, str):
        img = Image.open(img)
    arr = np.asarray(img.convert("RGB"), dtype=np.uint8)
    lum = (arr[..., 0] * _LUMA[0] + arr[..., 1] * _LUMA[1] + arr[..., 2] * _LUMA[2]).astype(np.uint8)
    mask = (lum >= _HL) if mode == "hl" else (lum <= _SH)
    out = np.zeros((*lum.shape, 3), dtype=np.uint8)
    color = (255, 60, 60) if mode == "hl" else (60, 60, 255)
    out[mask] = color
    return Image.fromarray(out)
