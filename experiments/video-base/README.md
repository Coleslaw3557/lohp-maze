# AI video base loops for the Cuddle floor show

Offline-generated looping BASE textures that play under the untouched
procedural reactive layer (stones/snakes/scarabs/traps stay live — see
`projection_engine.py`'s `_base` slot and the per-theme `VIDEO_OWNS`
lists). Runtime streaming from a GPU box was investigated and REJECTED
2026-07-24 (no warp needed, no latency win, no 3090 on the playa); this
directory is the offload that works.

## What's tracked vs regenerable

Tracked in git: the scripts, prompt files, job logs (each generation's
payload + cost), the skin packs (`*.npz`), the eyeball sheets
(`*_sheet.png`), the loop-seam anchors (`anchor_*.png`) and the
browser-served `base_loop_<theme>.mp4` assets the sim plays.

Ignored (regenerable, ~1 GB): raw generated clips (`clip_*_raw.mp4`),
production frame stacks (`base_loop_*_192.npy` — rebuild with
`prep_loop.py` from the raws or re-generate), previews, archives, and
scratch pngs. Re-running a job log's payload against the same seed gets a
close-enough clip.

## Generation pipeline (bridge-loop, 2026-07-24 motion rework)

Same-image first+last frame made the model minimize motion — every theme
read as a still. The fix is a two-clip bridge, driven by `run_bridge.sh`:

    run_bridge.sh <theme> <anchor.png> <prompt.txt> <seed> a|b|finish

- `a`: clip A free-runs from `first_frame = anchor` (real motion).
- `b`: clip B is generated with `first = A's last frame`,
  `last = anchor` — it bridges home.
- `finish`: `prep_loop.py --clip-b` stitches A+B with crossfades into
  `base_loop_<theme>_192.npy` (20 fps, 192×144 area-scale, tail→head
  seam lands on the anchor) + preview + `make_browser_asset.py` mp4, and
  prints the motion score (mean |Δframe|/px/255 — healthy loops run
  ~0.3–0.8; ~0.05 is the stills bug).

`PAIR=2|3|4…` names extra bridge pairs; every pair starts AND ends on the
anchor so pairs concatenate via `prep_loop --clips`.

**Recipes** (learned the expensive way, 2026-07-25):

- **New look**: TEXT-ONLY probe first (`submit_seedance.py --text-only`),
  take the probe's FIRST frame as the anchor, then phase `b` bridges its
  last frame home. Do NOT condition on an engine texture export — the
  model faithfully keeps the synthetic look and kills the motion
  (chamber's conditioned attempt: 0.15/255, wasted ~$2.25).
- **Engine-aligned understudies** (lava/water stone spots): condition on
  `export_conditioning.py`'s engine export so baked features land where
  the engine expects them.

Prompts must keep light FLAT and SHADOWLESS (the engine multiplies its
own light ramp), the camera absolutely locked top-down, and the ground
running past every edge. ~$2.25 per 15 s 960×720 seedance-2.0 clip via
OpenRouter (`OPENROUTER_API_KEY`), ~$0.60 for a 4 s plate.

## Skins (chroma-plate pipeline)

Prompt a subject on a flat pure-green background, then sample:

- `build_snake_strips.py` — three-snake plate (`clip_snakes3.mp4`:
  tzabcan / cantil / coral, heads RIGHT) → per-arc color strips
  (`snake_strips.npz`) the jungle page draws.
- `build_stone_skins.py` — carved-relic plates → `stone_skin_<theme>.npz`
  stacks (name a DISTINCT motif per grid slot or the model repeats one).
  Jungle pack = 4 tablets; skulls (07-24) and monkey heads (07-25) were
  cut on Tim's call and archived beside it.
- `build_spider_skin.py` / `build_plate_skin.py` — spider gait frames and
  single-frame plates (kukulkan/croc heads).

Large features survive the 192×144 downscale; fine detail dies.

## Sim integration

`sim_ui.py` serves `/sim/base_loop/<theme>` when
`base_loop_<theme>.mp4` exists and advertises it in the projection hello
(+ `video_palette`, `video_owns`); the page multiply-blends the light
field over the looping video (`btn-vidbase` toggles back to the static
base for A/B). npz/mp4 changes load at show init — restart the sim server
(kill + relaunch `run_server.py` from `sim/`; the pkill self-match gotcha:
run the kill and the relaunch as separate commands).
