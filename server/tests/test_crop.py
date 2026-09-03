#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lightroom_agent.retouch.crop import visual_crop_to_sdk


class VisualCropToSdkTest(unittest.TestCase):
    def test_ab_top_crop_is_croptop(self):
        s = visual_crop_to_sdk(0.20, 0.0, 1.0, 1.0, "AB")
        self.assertAlmostEqual(s["CropTop"], 0.20)
        self.assertAlmostEqual(s["CropLeft"], 0.0)
        self.assertAlmostEqual(s["CropRight"], 1.0)
        self.assertAlmostEqual(s["CropBottom"], 1.0)

    def test_da_top_crop_is_cropright_not_croptop(self):
        # JUN_3827: writing CropTop cut the left. Visual top must move CropRight.
        s = visual_crop_to_sdk(0.20, 0.0, 1.0, 1.0, "DA")
        self.assertAlmostEqual(s["CropTop"], 0.0)
        self.assertAlmostEqual(s["CropLeft"], 0.0)
        self.assertAlmostEqual(s["CropRight"], 0.80)
        self.assertAlmostEqual(s["CropBottom"], 1.0)

    def test_native_23_full_frame(self):
        from lightroom_agent.retouch.crop import aspect_crop_window
        w = aspect_crop_window(3712, 5568, "2:3")
        self.assertAlmostEqual(w["top"], 0.0)
        self.assertAlmostEqual(w["left"], 0.0)
        self.assertAlmostEqual(w["bottom"], 1.0)
        self.assertAlmostEqual(w["right"], 1.0)

    def test_23_zoom_bottom_keeps_ratio(self):
        from lightroom_agent.retouch.crop import aspect_crop_window
        w = aspect_crop_window(3712, 5568, "2:3", anchor="bottom", scale=0.85)
        vis_w = w["right"] - w["left"]
        vis_h = w["bottom"] - w["top"]
        px_aspect = (vis_w * 3712) / (vis_h * 5568)
        self.assertAlmostEqual(px_aspect, 2 / 3, places=3)
        self.assertAlmostEqual(w["bottom"], 1.0)
        self.assertGreater(w["top"], 0.1)

    def test_rejects_nonstandard_ratio(self):
        from lightroom_agent.retouch.crop import CropError, aspect_crop_window
        with self.assertRaises(CropError):
            aspect_crop_window(3712, 5568, "5:6")


if __name__ == "__main__":
    unittest.main()
