#!/usr/bin/env python3
"""Characterization tests for histogram.analyze on synthetic images."""
import tempfile
import unittest
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lightroom_agent.analysis.histogram import analyze


def _save(arr: np.ndarray) -> str:
    img = Image.fromarray(arr.astype(np.uint8), mode="RGB")
    fd, path = tempfile.mkstemp(suffix=".jpg")
    Path(path).write_bytes(b"")  # touch; PIL save below
    import os
    os.close(fd)
    img.save(path, quality=95)
    return path


class HistogramAnalyzeTest(unittest.TestCase):
    def test_mid_gray_mean_near_128(self):
        arr = np.full((80, 80, 3), 128, dtype=np.uint8)
        path = _save(arr)
        r = analyze(path).to_dict()
        self.assertAlmostEqual(r["statistics"]["Lum"]["mean"], 128.0, delta=2)
        self.assertEqual(r["statistics"]["Lum"]["sh_clip_pct"], 0)
        self.assertEqual(r["statistics"]["Lum"]["hl_clip_pct"], 0)

    def test_black_frame_reports_shadow_clip(self):
        arr = np.zeros((80, 80, 3), dtype=np.uint8)
        path = _save(arr)
        r = analyze(path).to_dict()
        self.assertGreater(r["statistics"]["Lum"]["sh_clip_pct"], 90)

    def test_blue_cast_positive_b_minus_g(self):
        arr = np.zeros((120, 120, 3), dtype=np.uint8)
        arr[..., 1] = 80
        arr[..., 2] = 160
        arr[..., 0] = 80
        path = _save(arr)
        r = analyze(path).to_dict()
        self.assertGreater(r["color_cast"]["delta_bmg"], 10)


if __name__ == "__main__":
    unittest.main()
