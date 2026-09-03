#!/usr/bin/env python3
"""Prescription whitelist: unknown keys fail; crop must be 0–1."""
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lightroom_agent.retouch.prescription import PrescriptionError, validate_settings


class ValidateSettingsTest(unittest.TestCase):
    def test_keeps_allowlisted_keys(self):
        out = validate_settings({
            "Exposure2012": 0.15,
            "Blacks2012": 5,
            "Temperature": 5850,
            "SaturationAdjustmentBlue": -15,
        })
        self.assertEqual(out["Exposure2012"], 0.15)
        self.assertEqual(out["Blacks2012"], 5)
        self.assertEqual(out["Temperature"], 5850)
        self.assertEqual(out["SaturationAdjustmentBlue"], -15)

    def test_rejects_unknown_key(self):
        with self.assertRaises(PrescriptionError) as ctx:
            validate_settings({"Exposure2012": 0.1, "Sharpness": 40})
        self.assertIn("Sharpness", str(ctx.exception))

    def test_rejects_crop_outside_unit_interval(self):
        with self.assertRaises(PrescriptionError):
            validate_settings({"CropTop": -0.1})
        with self.assertRaises(PrescriptionError):
            validate_settings({"CropBottom": 1.2})

    def test_accepts_crop_unit_interval(self):
        out = validate_settings({
            "CropTop": 0.02,
            "CropLeft": 0.0,
            "CropBottom": 0.98,
            "CropRight": 1.0,
            "CropAngle": 0.4,
        })
        self.assertEqual(out["CropTop"], 0.02)
        self.assertEqual(out["CropAngle"], 0.4)

    def test_rejects_empty(self):
        with self.assertRaises(PrescriptionError):
            validate_settings({})

    def test_rejects_non_numeric(self):
        with self.assertRaises(PrescriptionError):
            validate_settings({"Exposure2012": "a bit"})

    def test_rejects_inverted_crop_box(self):
        with self.assertRaises(PrescriptionError):
            validate_settings({"CropTop": 0.8, "CropBottom": 0.2})

    def test_accepts_point_curve_pairs(self):
        out = validate_settings({
            "ToneCurveName2012": "Custom",
            "ToneCurvePV2012": [0, 0, 64, 56, 128, 128, 192, 200, 255, 255],
        })
        self.assertEqual(out["ToneCurvePV2012"][0], 0)
        self.assertEqual(out["ToneCurvePV2012"][-2], 255)

    def test_rejects_curve_not_ending_at_255(self):
        with self.assertRaises(PrescriptionError):
            validate_settings({"ToneCurvePV2012": [0, 0, 128, 128]})


if __name__ == "__main__":
    unittest.main()
