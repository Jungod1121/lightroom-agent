#!/usr/bin/env python3
"""prepare → apply → restore orchestration with a fake plugin."""
import tempfile
import unittest
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lightroom_agent.retouch.loop import (
    apply_auto_tone,
    apply_retouch,
    prepare_retouch,
    restore_retouch,
)
from lightroom_agent.retouch.prescription import PrescriptionError


def _write_jpeg(directory: Path, name: str = "JUN_3939.jpg") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    Image.new("RGB", (40, 40), (12, 20, 40)).save(path, quality=90)
    return path


class PrepareApplyRestoreTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.calls = []

    def _plugin(self, action, params=None):
        self.calls.append((action, params or {}))
        if action == "get_photo_metadata":
            return {
                "id": 346763,
                "filename": "JUN_3939.NEF",
                "developSettings": {
                    "exposure": 0,
                    "blacks": -13,
                    "temperature": 5600,
                    "hsl": {"SaturationAdjustmentBlue": 0},
                },
            }
        if action == "export_photos":
            _write_jpeg(Path(params["destination"]))
            return {"success": True, "exported": 1}
        if action == "set_develop_settings":
            return {"success": True, "photo_id": params["photo_id"]}
        if action == "set_auto_tone":
            return {"success": True, "photo_id": params["photo_id"]}
        raise AssertionError(f"unexpected action {action}")

    def test_prepare_returns_jpeg_and_snapshot(self):
        r = prepare_retouch("346763", plugin_call=self._plugin, export_root=self.root)
        self.assertTrue(Path(r["jpeg_path"]).is_file())
        self.assertEqual(r["develop"]["Blacks2012"], -13)
        self.assertTrue(r["snapshot_id"])
        self.assertEqual(self.calls[0][0], "get_photo_metadata")
        self.assertEqual(self.calls[1][0], "export_photos")

    def test_apply_writes_allowlisted_settings_and_exports_after(self):
        prep = prepare_retouch("346763", plugin_call=self._plugin, export_root=self.root)
        out = apply_retouch(
            "346763",
            {"Exposure2012": 0.15, "Blacks2012": 5},
            prep["snapshot_id"],
            plugin_call=self._plugin,
            export_root=self.root,
        )
        self.assertTrue(Path(out["after_path"]).is_file())
        self.assertNotEqual(out["after_path"], prep["jpeg_path"])
        set_calls = [p for a, p in self.calls if a == "set_develop_settings"]
        self.assertEqual(set_calls[-1]["settings"]["Blacks2012"], 5.0)

    def test_apply_rejects_unknown_key_before_plugin(self):
        prep = prepare_retouch("346763", plugin_call=self._plugin, export_root=self.root)
        before = len(self.calls)
        with self.assertRaises(PrescriptionError):
            apply_retouch(
                "346763",
                {"Sharpness": 40},
                prep["snapshot_id"],
                plugin_call=self._plugin,
                export_root=self.root,
            )
        self.assertFalse(any(a == "set_develop_settings" for a, _ in self.calls[before:]))

    def test_apply_rejects_mismatched_snapshot(self):
        prep = prepare_retouch("346763", plugin_call=self._plugin, export_root=self.root)
        with self.assertRaises(ValueError):
            apply_retouch(
                "999",
                {"Exposure2012": 0.1},
                prep["snapshot_id"],
                plugin_call=self._plugin,
                export_root=self.root,
            )

    def test_restore_writes_snapshot_develop(self):
        prep = prepare_retouch("346763", plugin_call=self._plugin, export_root=self.root)
        apply_retouch(
            "346763",
            {"Blacks2012": 5},
            prep["snapshot_id"],
            plugin_call=self._plugin,
            export_root=self.root,
        )
        restore_retouch("346763", prep["snapshot_id"], plugin_call=self._plugin)
        last_set = [p for a, p in self.calls if a == "set_develop_settings"][-1]
        self.assertEqual(last_set["settings"]["Blacks2012"], -13.0)

    def test_auto_tone_calls_plugin_and_exports(self):
        prep = prepare_retouch("346763", plugin_call=self._plugin, export_root=self.root)
        out = apply_auto_tone(
            "346763",
            snapshot_id=prep["snapshot_id"],
            plugin_call=self._plugin,
            export_root=self.root,
        )
        self.assertTrue(Path(out["after_path"]).is_file())
        auto_calls = [p for a, p in self.calls if a == "set_auto_tone"]
        self.assertEqual(auto_calls[-1]["photo_id"], "346763")

    def test_export_deletes_existing_jpeg_before_plugin_so_lr_wont_prompt(self):
        from lightroom_agent.retouch.loop import _export

        dest = self.root / "after"
        _write_jpeg(dest, "JUN_3596.jpg")
        self.assertTrue((dest / "JUN_3596.jpg").is_file())

        def plugin(action, params=None):
            leftover = list(dest.glob("*.jpg")) + list(dest.glob("*.jpeg"))
            self.assertEqual(leftover, [], f"collision file still present: {leftover}")
            _write_jpeg(dest, "JUN_3596.jpg")
            return {"success": True}

        path = _export(plugin, "346760", dest)
        self.assertEqual(path.name, "JUN_3596.jpg")
        self.assertTrue(path.is_file())


if __name__ == "__main__":
    unittest.main()
