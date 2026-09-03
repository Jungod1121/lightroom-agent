#!/usr/bin/env python3
"""Snapshot develop settings for restore-after-retouch."""
import tempfile
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lightroom_agent.retouch.snapshot import (
    develop_from_metadata,
    load_snapshot,
    save_snapshot,
)


class DevelopFromMetadataTest(unittest.TestCase):
    def test_maps_aliases_and_hsl(self):
        meta = {
            "developSettings": {
                "exposure": 0.15,
                "blacks": 5,
                "temperature": 5850,
                "hsl": {"SaturationAdjustmentBlue": -15},
            }
        }
        out = develop_from_metadata(meta)
        self.assertEqual(out["Exposure2012"], 0.15)
        self.assertEqual(out["Blacks2012"], 5)
        self.assertEqual(out["Temperature"], 5850)
        self.assertEqual(out["SaturationAdjustmentBlue"], -15)

    def test_keeps_crop_if_present(self):
        meta = {"developSettings": {"CropTop": 0.1, "CropBottom": 0.9}}
        out = develop_from_metadata(meta)
        self.assertEqual(out["CropTop"], 0.1)
        self.assertEqual(out["CropBottom"], 0.9)


class SnapshotStoreTest(unittest.TestCase):
    def test_roundtrip(self):
        d = Path(tempfile.mkdtemp())
        develop = {"Exposure2012": 0.0, "Blacks2012": -13}
        sid = save_snapshot("346763", develop, directory=d)
        loaded = load_snapshot(sid, directory=d)
        self.assertEqual(loaded["photo_id"], "346763")
        self.assertEqual(loaded["develop"]["Blacks2012"], -13)

    def test_missing_raises(self):
        d = Path(tempfile.mkdtemp())
        with self.assertRaises(FileNotFoundError):
            load_snapshot("no-such-id", directory=d)


if __name__ == "__main__":
    unittest.main()
