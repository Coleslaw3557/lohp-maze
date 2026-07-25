# Cuddle Cross JUNGLE floor projection — plan (2026-07-23)

The second theme for the Cuddle Cross floor projection (same rig, same
engine skeleton as the lava show — `wiring-guides/cuddle-lava-plan.md`).
Tim's content call 2026-07-23: **Mayan jungle, snake themed**. The maze is
Mayan-temple themed; this is the temple floor the jungle took back. (The
Aku-Aku-homage flying tiki mask shipped with v1 and was CUT the same day on
Tim's call — resurrect from commit 4018bd8 if ever wanted.)

## Themes: one engine, three shows (lava / jungle / temple)

`projection_engine.py` now holds a `FloorShow` base (deck geometry + mask,
drifting noise field, walker tracks, presence/fade, events, patch toolbox)
and subclasses `LavaShow`, `JungleShow`, `TempleShow` (`wiring-guides/cuddle-temple-plan.md`), registry `THEMES`. The
refactor is provably invisible to the lava show (golden-frame hash of
render+state+textures identical before/after).

- **Sim**: the active theme is shared server state, like the one real deck.
  The header **Floor** button cycles it for every tab (`{'theme': name}` over
  `WS /sim/projection`); the server re-hellos each client with the new
  palette + artwork. Inactive themes keep their world frozen and resume on
  switch-back; a switch mid-show carries the cue so the new theme fades
  straight in.
- **Production — live switch (2026-07-23)**: the renderer prebuilds every
  theme at startup and runs a tiny HTTP control channel
  (`--ctl-port 5002`, 0 disables):
  `GET /theme` reports, `POST /theme/<name>` switches instantly. The sim's
  Floor button forwards each switch to `RPI_HOST:5002` best-effort (env
  `RPI_PROJ_PORT`), so the button drives the REAL projector when the Pi is
  reachable — verified end-to-end 07-23 (journal `theme -> jungle`, fb
  readback green-dominant). Manual:
  `curl -X POST http://lohp-server.local:5002/theme/jungle`. `--theme` only
  picks the boot theme now.

## The show

The deck is an **open mossy clearing floor** (2026-07-25 rework — Tim's
call: the wall-to-wall carpet looks, both the painted leaf-litter and the
lush AI video, read as a plant WALL, not a floor, and camouflaged the
snakes): dark humus mostly swallowed by patchy moss, a few weathered
stones sunk flush, two rooty runs wandering across, and scattered single
fallen leaves as accents. The drifting light field multiplies over it
through a green-shadow→warm-gold ramp (`_JUNGLE_STOPS` is a LIGHT ramp —
same octave machinery as the lava heat). Heavier canopy dapple hugs the
deck rim, and a **sun-pool follows each tracked walker** (the canopy opens
over you). Leaf-accent knob: `LEAF_DENSITY` (now sparse). The AI video
base (`base_loop_jungle_192.npy`, 28.9 s bridge loop, motion 0.71/255)
matches: mossy ground, flush stones, roots, ferns, drifting leaves.

- **Snakes** (the heart of it): three procedural snakes, all real venomous
  regional species — **2026-07-25 pass (Tim): smaller bodies, new skins**
  (supersedes the 07-23 colorways; strips resampled from a fresh AI plate,
  `clip_snakes3.mp4` → `snake_strips.npz`): a **tzabcan rattlesnake** (the
  Yucatán diamondback, now 1.05 m — sandy grey-tan, cream-edged chocolate
  diamond chain, pale flank line, and a segmented buff-keratin **rattle**
  held wider than a tail point that **buzzes** — flicker shimmer + a
  rattle log line — when it flees), a **Yucatán cantil** (Agkistrodon
  russeolus, 0.85 m — copper red-brown with cream-edged chocolate
  crossbands pinching at the flanks; replaces the flat-gold eyelash
  viper), and the **coral snake** (red/yellow/black rings — red widest,
  "red touches yellow" — black snout, 0.68 m). All amber-eyed. They
  slither goal-to-goal across the deck with a weaving,
  burst-and-glide gait
  (heading oscillation + speed pulsing; the spine is a trail the body
  follows). **v2 body render (07-23, Tim: "more realistic")**: not discs —
  a distance field to the spine polyline carrying arc length, so each snake
  is one smooth body with a real silhouette (narrow snout → spade-flared
  jaw → neck pinch → body → tail tapering to a point, np.interp width
  knots), arc-driven skin pattern, rounded-body dorsal shading + scale
  speckle, gold eyes set on the spade sides. The sim page draws the same
  silhouette as per-point width-offset polygon quads from per-index
  colors/widths in the hello. They steer around the mast, turn back at the
  deck edge, flick forked tongues, and leave a faint parted-grass glow wake
  in the field. Walk within ~0.75 m and the snake **darts away** (flee
  speed 0.62 m/s, hysteresis to 1.2 m so it actually escapes, per-snake
  event cooldown 4 s so the log doesn't spam). Placement/self-respect rules
  keep them off the altar and out from underfoot.
- **Fallen glyph stones**: three mossy carved ruin stones drawn from the
  generated skin pack (`experiments/video-base/stone_skin_jungle.npz` —
  four carved TABLETS: spiral / concentric rings / stepped pyramid /
  radiant sun; the skull variants were cut 07-24 and the monkey-head
  variants 07-25, both archived beside the pack), procedural mossified
  rock as the fallback. No counting marks — decorative ruins, not the lava
  chain's wayfinding numerals. Approach one and it glints leaf-gold (same
  glint logic as the stones).
- **Fireflies**: up to seven, blinking on/off, wandering the lit deck —
  each glows in the field (gold through the palette) with a bright core dot.
- **The altar**: the same carved sun-stone around the mast base, mossier
  colors.
- Presence cue + 60 s timeout, identical to lava.

## Events (sim log + fx rings)

`snake_flee` (the rattler's log line rattles) — jungle fx rings render
leaf-gold instead of lava orange.

## Perf (Pi-tuned 2026-07-23 — Tim: "it's feeling sluggish")

First real measurement on the 3B+ showed the show had been running ~4–6 fps:
engine 106 ms (lava) / 193 ms (jungle) + 59 ms of numpy fb packing. The fix
landed in three layers, now measured **locked 20.0 fps** on the Pi (journal
heartbeat `fps 20.0 (engine 40 ms, blit 1 ms)`), no thermal throttle:

- **Engine math** (both themes, dev-verified visuals): octaves precompute a
  full-res tileable image and scroll it with 3 np.rolls + bilinear mix per
  frame (was a fancy-index bilerp of the coarse grid — 30 ms/octave on the
  Pi, the single hottest thing); gamma via exact sqrt identities (1.5 =
  h·√h, jungle now 1.25 = h·√√h); dapple+mask folded into one static
  multiply; big field blobs from a cached sprite table.
- **Snakes**: the distance field batches all segments in one broadcast pass
  on a half-res lattice; distance + arc (smooth fields) bilinear-upsample
  to full res, so the silhouette/alpha stays crisp (upsampling alpha
  fragmented the tail); pattern/shading computed on the lattice (reads as
  scale texture); every 3rd spine point (chord error < 0.5 px). 46 →
  ~10 ms/snake on the Pi.
- **Display**: legacy firmware framebuffer at exactly the render grid
  (192×144, config in `tools/rpi-projection-setup.sh`) — the VideoCore
  scaler does the whole upscale to the projector with smoothing, so the
  blit is a 1 ms pack (was 59 ms of repeat+RGB565 math at 1024×768). This
  is the usable "GPU acceleration" on a 3B+: its GLES stack refused kmsdrm
  here, but the firmware scaler is free.

Service runs `--grid 192 --fps 20` (engine-only capability: lava ~49 fps,
jungle ~20 fps at that grid; 256 remains the sim's grid). Watch the
journal's once-a-minute `fps` heartbeat if it ever feels slow again.

## Tuning knobs (constants in projection_engine.py)

`SNAKE_*` (specs, seg 0.032 m, cruise 0.13–0.24 m/s, flee 0.55 m/s at
0.75 m w/ 1.6× calm hysteresis, weave 1.3–2.4 rad/s at 0.55–1.0 Hz),
`TONGUE_*`, `WAKE_*`, `SUN_*` (0.42 m pool), `FIREFLY_*`, `GLYPH_*`,
`RATTLE_*` (0.085 m), `SNAKE_CANTIL_PER_M`, `_JUNGLE_STOPS` palette.

## Test

`sim/tools/lava_test.py` sections 8–12: snakes placed/slither/stay on
deck, flee event + escape, fireflies spawn and blink, texture export
shapes, green-floor render check, perf budget.
