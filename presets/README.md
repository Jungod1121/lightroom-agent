# Presets

Hand-crafted city photography presets extracted from rated reference photos via
`create_develop_preset` (automaat/lightroom-mcp preset round-trip).

## Jungod Urban Teal v1

Extracted from `JUN_3390` (4★, Venice, 2026-08-02). Signature look: warm-shifted
white balance over a teal-skewed HSL palette, lifted shadows, compressed highlights,
custom RGB tone curve with a blue-channel dip.

Key values:

| Group | Values |
|---|---|
| White balance | Temp 7500 · Tint +28 (Auto WB shifted warm) |
| Tone | Exposure −0.6 · Contrast −8 · Highlights −62 · Shadows +70 · Whites −45 · Blacks +48 |
| Presence | Texture −5 · Clarity −15 · Saturation −16 |
| HSL hue | Aqua +30 · Blue −44 · Green −38 · Yellow −44 · Red +10 |
| HSL sat | Green −48 · Aqua −18 · Red −18 · Orange −15 |
| HSL lum | Aqua +32 · Green +28 · Red −15 · Blue/Orange/Yellow +5 |
| Parametric | Darks −40 · Lights +8 · Highlights −8 |
| Tone curve | Custom: shadow lift, highlight roll-off, blue-channel dip at 115–127 |

## Install

1. Open Lightroom Classic → `Develop` module → `Presets` panel → `+` → **Import Presets**
2. Select `Jungod Urban Teal v1.lrtemplate`
3. Or copy the file to
   `~/Library/Application Support/Adobe/CameraRaw/Settings/Develop Presets/`

## Notes

- Works on any raw/JPEG; designed for urban night & water scenes (Nikon Z system)
- Check highlights after applying — the base photo already sits at −62 highlights
