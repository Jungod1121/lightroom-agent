#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lightroom_agent.retouch.style import StyleFingerprint, settings_from_gap


def _fp(**kwargs):
    base = dict(
        lum_mean=110, lum_median=100, delta_rmg=-10, delta_bmg=10,
        stops=4.2, hl_clip=0.0, sh_clip=1.0, zone_hi=20.0, zone_lo=20.0,
    )
    base.update(kwargs)
    return StyleFingerprint(**base)


class SettingsFromGapTest(unittest.TestCase):
    def test_brighter_reference_raises_exposure(self):
        src = _fp(lum_mean=100)
        ref = _fp(lum_mean=145)
        out = settings_from_gap(src, ref, {"Exposure2012": 0.0})
        self.assertGreater(out["Exposure2012"], 0.2)

    def test_airier_reference_lowers_contrast_and_dehaze(self):
        src = _fp(stops=4.5, zone_hi=15)
        ref = _fp(stops=3.3, zone_hi=35)
        out = settings_from_gap(src, ref, {"Contrast2012": 10, "Dehaze": 20})
        self.assertLess(out["Contrast2012"], 10)
        self.assertLess(out["Dehaze"], 20)

    def test_cooler_reference_drops_temperature(self):
        src = _fp(delta_rmg=-10)
        ref = _fp(delta_rmg=-26)
        out = settings_from_gap(src, ref, {"Temperature": 5350})
        self.assertLess(out["Temperature"], 5350)

    def test_bands_sky_brighter_than_water(self):
        import tempfile
        from pathlib import Path
        import numpy as np
        from PIL import Image
        from lightroom_agent.retouch.style import fingerprint_bands

        arr = np.zeros((90, 60, 3), dtype=np.uint8)
        arr[:30] = 200
        arr[60:] = 40
        arr[30:60] = 100
        path = Path(tempfile.mkdtemp()) / "bands.jpg"
        Image.fromarray(arr).save(path)
        bands = fingerprint_bands(str(path))
        self.assertGreater(bands["sky"].lum_mean, bands["water"].lum_mean)


if __name__ == "__main__":
    unittest.main()
