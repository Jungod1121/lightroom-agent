<div align="center">

# Lightroom Agent

**Give AI agents eyes for Lightroom — verifiable photo analysis, not guesswork.**

[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org)
[![MCP](https://img.shields.io/badge/protocol-MCP-green)](https://modelcontextprotocol.io)
[![GitHub](https://img.shields.io/github/stars/Jungod1121/lightroom-agent?style=flat)](https://github.com/Jungod1121/lightroom-agent/stargazers)

</div>

---

Existing Lightroom MCP servers (e.g. [automaat/lightroom-mcp](https://github.com/automaat/lightroom-mcp)) can *operate* Lightroom — read settings, apply presets, export, undo — but they are **blind**: they never tell you whether an image is overexposed, which channel is clipping, or which photo in a batch is tonally off.

**Lightroom Agent is the analysis layer.** It turns a rendered photo into verifiable numbers — histogram, Adams 11 zones, 5×5 zone-metering grid, color cast, dynamic range — and emits actionable, checkable suggestions. Combined with a transport layer, an agent can run the full loop **see → judge → adjust → verify** without a human watching the screen.

<p align="center">
  <img src="docs/architecture.svg" alt="architecture" width="760">
</p>

## Features

- 🔍 **`analyze_photo`** — per-channel (R/G/B/Lum) histogram & stats, highlight/shadow clipping, Adams 11-zone exposure distribution, 5×5 metering grid, color cast, effective dynamic range (EV), rule-based suggestions
- 📊 **`batch_analyze`** — scan a directory of renders, flag tonal outliers, check batch consistency
- 🧮 **Self-built algorithms** — pure numpy vectorization, no third-party analysis libraries
- 🔌 **Standalone** — pure Python MCP server; works offline once a render exists
- ✅ **No hallucinated vision** — every output is a number you can verify

## Installation

```bash
git clone https://github.com/Jungod1121/lightroom-agent.git
cd lightroom-agent/server
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

Register the MCP server in your client (Claude Desktop, Claude Code, Cursor, VS Code, WorkBuddy, …):

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

## Quick start

Or skip MCP entirely and call the analyzer directly:

```bash
$ cd lightroom-agent/server
$ ./.venv/bin/python -c "
from lightroom_agent.analysis.histogram import analyze
r = analyze('photo.jpg')
print(r.to_dict()['suggestions'])
"
['overall cool-toned (R-G delta -42.3): adjust temperature unless intended',
 'overall dark (mean 81.3): consider Exposure +0.2~0.4']
```

With a transport layer installed (see [automaat/lightroom-mcp](https://github.com/automaat/lightroom-mcp)), the full loop runs inside one conversation:

```
get_selected_photos → export JPEG → analyze_photo → adjust_develop_settings
→ re-export → analyze again (clipping fixed?)
```

Runnable scripts live in [`scripts/`](scripts/):

```bash
scripts/demo1_diagnose.py   # single-photo diagnose loop (needs LrC + transport layer)
scripts/demo2_batch.py      # batch consistency scan (offline)
scripts/demo3_verify.py     # before/after verification with auto-undo
```

## Output reference

| Field | Meaning |
|---|---|
| `statistics` | per-channel mean / median / highlight & shadow clipping % / peak bin |
| `bins64` | 64-bin histogram per channel |
| `zones_pct` | Adams 11-zone pixel distribution |
| `grid5_lum` | 5×5 grid luminance means (composition lighting) |
| `color_cast` | mid-gray R/G/B deltas (cast evidence) |
| `range_ev` | effective dynamic range (p2–p98, EV) |
| `suggestions` | rule-based, actionable items |

## Honest limitations

Analysis on deliberately-styled images (teal & orange, B&W) produces **false-positive suggestions** — cross-check against develop parameters before acting. Inputs are 8-bit renders (same pipeline as the LrC UI histogram, slightly different bit depth). This repo deliberately contains **no** Lightroom operation logic — that belongs to the transport layer.

## Research archive

[`archive/`](archive/README.md) documents our attempt to build the transport layer from scratch — 9 hard-won lessons about LrSocket (sandbox limitations, ghost connections, rebind races). Read it before touching Lightroom plugin sockets.

## Roadmap

- [ ] Region histograms (mask / crop aware)
- [ ] Style fingerprinting & clustering from reference images
- [ ] Before/after verification reports
- [ ] Auto-culling scoring engine

## Contributing

Issues and PRs are welcome.

## License

[Apache-2.0](LICENSE) © lightroom-agent contributors
