#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lightroom_agent.retouch.masks import create_ai_mask, set_mask_settings
from lightroom_agent.retouch.prescription import PrescriptionError


class MasksTest(unittest.TestCase):
    def test_rejects_bad_type(self):
        with self.assertRaises(ValueError):
            create_ai_mask("1", "hair", plugin_call=lambda *a, **k: {})

    def test_create_passes_through(self):
        def plugin(action, params=None):
            self.assertEqual(action, "create_ai_mask")
            self.assertEqual(params["mask_type"], "sky")
            return {"success": True, "selected": {"id": "m1"}}
        out = create_ai_mask("7007", "sky", plugin_call=plugin)
        self.assertTrue(out["success"])

    def test_set_mask_rejects_unknown_key(self):
        with self.assertRaises(PrescriptionError):
            set_mask_settings("7007", {"Sharpness": 40}, plugin_call=lambda *a, **k: {})


if __name__ == "__main__":
    unittest.main()
