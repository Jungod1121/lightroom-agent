<div align="center">

# Lightroom Agent

**An agent that can see a Lightroom photo, edit it, and show you the result.**

**English** · [简体中文](README.zh-CN.md)

[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org)
[![MCP](https://img.shields.io/badge/protocol-MCP-green)](https://modelcontextprotocol.io)

[Features](#features) · [Install](#installation) · [Usage](#usage) · [Docs](#documentation) · [Limitations](#limitations)

</div>

Lightroom MCP bridges can move sliders. They cannot tell you if the sky is clipping, if a portrait RAW’s `CropTop` is actually the left edge, or how far this harbor is from a JPEG you dropped in chat.

This repo is the **eyes and hands** for an agent sitting in Lightroom Classic: export a render, measure it (or look at it), write allowlisted develop settings, export again, show the after. Undo is a snapshot of the previous develop state.

<p align="center">
  <img src="docs/architecture.svg" alt="architecture" width="820">
</p>

## Features

- **See** — histogram, clip, Adams 11 zones, 5×5 metering, color cast, EV range on an 8-bit render
- **Edit** — basic panel, HSL, point curves, Lightroom Auto (Sensei), standard-ratio crop
- **Mask** — AI types sky / subject / background / objects / people / landscape; add / subtract / intersect; linear / radial gradients; per-group local sliders
- **Match** — fingerprint a reference JPEG and emit a develop prescription
- **Loop** — prepare (no write) → apply → restore
- **Talk to LrC** — `scripts/lr-plugin-call.mjs` over the Classic plugin sockets

## Installation

Needs **macOS**, **Lightroom Classic** with the MCP plugin **Start Server**, **Python 3.11+**, **Node 18+**. No GPU.

```bash
git clone https://github.com/Jungod1121/lightroom-agent.git
cd lightroom-agent
chmod +x scripts/*.sh
./scripts/install.sh
./scripts/start-gateway.sh
# Lightroom → Plug-in Manager → Lightroom MCP → Start Server, then Reload
node scripts/lr-plugin-call.mjs ping
```

MCP client:

```json
{
  "mcpServers": {
    "lightroom-analysis": {
      "command": "/absolute/path/to/lightroom-agent/server/.venv/bin/python",
      "args": ["-m", "lightroom_agent.main"],
      "env": { "PYTHONPATH": "/absolute/path/to/lightroom-agent/server" }
    }
  }
}
```

If automaat’s `server/dist` is not at `~/repositories/lightroom-mcp-automaat/server/dist`, set `LRMCP_AUTOMAAT_DIST`. Only one process may hold the plugin sockets.

## Usage

Analyze a JPEG (Lightroom not required):

```bash
cd lightroom-agent/server
./.venv/bin/python -c "
from lightroom_agent.analysis.histogram import analyze
print(analyze('harbor.jpg').to_dict()['statistics']['Lum'])
"
# {'mean': 125.37, 'median': 136.0, 'hl_clip_pct': 0.0, 'sh_clip_pct': 0.45, ...}
```

Talk to Lightroom:

```bash
node scripts/lr-plugin-call.mjs ping
node scripts/lr-plugin-call.mjs get_photo_metadata '{"photo_id":"7007"}'
```

Retouch loop (agent skill: [`skills/lightroom-retouch/SKILL.md`](skills/lightroom-retouch/SKILL.md)):

```
get_selected_photos
→ prepare_retouch_photo      # export + snapshot; catalog unchanged
→ look at jpeg_path
→ apply_retouch_photo(...)   # allowlisted develop + crop
→ show after_path
```

Match a reference still, or run Classic Auto:

```
propose_style_match_photo(photo_id, "/path/to/reference.jpg")
apply_auto_tone_photo(photo_id, snapshot_id)   # Develop Auto button
```

Masks (Develop; **Reload** the plugin once after install):

```
create_ai_mask_photo(photo_id, "sky")
create_ai_mask_photo(photo_id, "objects")      # user clicks the object in the photo
create_ai_mask_photo(photo_id, "landscape")    # then ask the user to check Water / 水面
create_ai_mask_photo(photo_id, "sky", "subtract")
# last group; most sliders 0–1 (0.28 = UI +28); exposure is EV
set_mask_settings_photo(photo_id, {"Shadows2012": 0.40, "Exposure2012": 0.12})
```

Target a specific group from the CLI (`group_index` is 1-based):

```bash
node scripts/lr-plugin-call.mjs set_mask_settings \
  '{"photo_id":"7007","group_index":4,"settings":{"Shadows2012":0.4,"Exposure2012":0.12}}'
```

Crop uses on-screen top/left/bottom/right, mapped through Lr orientation. Ratios: `1:1` `2:3` `3:2` `3:4` `4:3` `4:5` `16:9` `9:16`.

```bash
cd server && ./.venv/bin/python -m unittest discover -s tests
```

## Related work

Hands-only Lightroom MCP (catalog / develop / export, no analysis of its own): [automaat/lightroom-mcp](https://github.com/automaat/lightroom-mcp), [shiyiai/lightroom-mcp](https://github.com/shiyiai/lightroom-mcp), [drshy-org/lightroom-py](https://github.com/drshy-org/lightroom-py).

Agents that also close a loop: [John-owo/photo-agent](https://github.com/John-owo/photo-agent) (analyze → plan → apply on a Virtual Copy), [Birni/lightroom-mcp](https://github.com/Birni/lightroom-mcp) (pixel analysis + develop), [YaddyVirus/darktable-mcp](https://github.com/YaddyVirus/darktable-mcp) (same idea on darktable). Codex driving Photoshop Camera Raw is GUI automation, not a catalog API.

This repo’s bet is **measurable renders + LrC develop writes + a user-supplied style JPEG**, not a downloaded “master photo” corpus.

## Limitations

- Plugin sockets are **1:1** at the Lua layer. Run `scripts/start-gateway.sh` so CLI and MCP share one owner; point WorkBuddy at this repo’s MCP, not automaat.
- Style match moves global tone/color. It does not copy composition.
- Histogram suggestions misfire on night / teal looks — evidence, not a prescription.
- No brush, healing, or spot removal.
- **Objects:** `objects` opens Select Objects. The SDK cannot pick “the bed” by name — the user clicks. A new group exists only after that click.
- **Landscape water:** there is no reliable `water` subtype. Ask the user to check Water / 水面, then create. Do not click the Lightroom UI.
- Mask sliders write the **last** group unless `group_index` is passed on the plugin call. MCP `set_mask_settings_photo` does not take `group_index` yet.
- Local sliders are 0–1 (`0.28` = UI +28). Local exposure is EV. `list_masks_photo` currently returns little from the live plugin.
- AI masks, gradients, and Auto need a plugin **Reload** after install. `apply_auto_tone_photo` is Classic’s Auto (8 sliders).

## Documentation

- [Architecture](docs/architecture.svg) ([中文](docs/architecture.zh-CN.svg))
- [Tone, curves, crop, style](docs/knowledge/README.md)
- [Plugin socket notes](archive/README.md)

## Contributing

Issues and PRs welcome. Keep `README.md` / `README.zh-CN.md` and `docs/architecture.svg` / `docs/architecture.zh-CN.svg` in lockstep — if you change one, change the other. Run tests from `server/`:

```bash
./.venv/bin/python -m unittest discover -s tests
```

## License

[Apache-2.0](LICENSE) © lightroom-agent contributors
