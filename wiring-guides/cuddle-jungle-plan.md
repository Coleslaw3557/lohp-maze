# Cuddle Cross JUNGLE floor projection — plan (2026-07-23)

The second theme for the Cuddle Cross floor projection (same rig, same
engine skeleton as the lava show — `wiring-guides/cuddle-lava-plan.md`).
Tim's content call 2026-07-23: **Mayan jungle, snake themed**, plus "a
little flying tiki mask from Crash Bandicoot". The maze is Mayan-temple
themed; this is the temple floor the jungle took back.

## Themes: one engine, two shows

`projection_engine.py` now holds a `FloorShow` base (deck geometry + mask,
drifting noise field, walker tracks, presence/fade, events, patch toolbox)
and two subclasses: `LavaShow` and `JungleShow`, registry `THEMES`. The
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

The deck is sun-dappled undergrowth: a slow-drifting green field (same
octave-noise machinery as the lava heat, jungle palette — undergrowth dark
through leaf greens to gold), heavier canopy dapple at the deck rim, and a
**sun-pool that follows each tracked walker** (the canopy opens over you).

- **Snakes** (the heart of it): three procedural snakes — two **jade
  racers** (green with a diamond chain down the back and a pale flank
  stripe, 1.3–1.55 m) and one **coral snake** (red/yellow/black rings —
  red widest, "red touches yellow" — black snout, ~1 m) — slither
  goal-to-goal across the deck with a weaving, burst-and-glide gait
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
- **The tiki mask** (the set piece — an **Aku Aku homage**, procedural like
  Kukulkan; an asset search was already ruled out for the lava monster and
  the same reasoning holds: no image decoder anywhere in the chain, and
  actual game sprites are Activision's art): an oval wooden mask, grain and
  knots, heavy brow, **hollow eyes with a pulsing gold glow**, wide toothy
  grin, straw goatee off the chin, five red/yellow/jade feathers off the
  crown. Every 30–65 s (first visit ~15 s in) it drifts in over a deck
  edge, flies to whoever the radar sees and **orbits them** (0.72 m,
  companion-style) — or wanders a lazy lissajous around the center when the
  deck is empty — **spins** every 5–9 s (0.9 s whirl + motion rings in the
  sim), then drifts off into the canopy. Forehead + crest lead along the
  motion. Same production trick as Kukulkan: 16 precomputed orientations;
  the sim page gets angle-0 and rotates on canvas.
- **Fallen glyph stones**: three mossy carved rocks (rock-patch generator
  with moss colors + a moss pass that eats the rims green), dots-and-bars
  carvings — decorative ruins, not the lava chain's wayfinding numerals.
  Approach one and its carve glints leaf-gold (same glint logic as the
  stones).
- **Fireflies**: up to seven, blinking on/off, wandering the lit deck —
  each glows in the field (gold through the palette) with a bright core dot.
- **The altar**: the same carved sun-stone around the mast base, mossier
  colors.
- Presence cue + 60 s timeout, identical to lava.

## Events (sim log + fx rings)

`snake_flee`, `tiki_arrive`, `tiki_spin`, `tiki_leave` — jungle fx rings
render leaf-gold instead of lava orange.

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

`SNAKE_*` (specs, seg 0.045 m, cruise 0.16–0.30 m/s, flee 0.62 m/s at
0.75 m w/ 1.6× calm hysteresis, weave 1.3–2.4 rad/s), `TONGUE_*`,
`WAKE_*`, `SUN_*` (0.42 m pool), `FIREFLY_*`, `GLYPH_*`, `TIKI_*` (visit
gaps, 11–18 s stay, orbit 0.72 m @ 0.9 rad/s, spin 0.9 s, half-size
0.21×0.16 m + crest), `_JUNGLE_STOPS` palette.

## Test

`sim/tools/lava_test.py` sections 8–12: snakes placed/slither/stay on
deck, flee event + escape, tiki arrive→spin→leave + pose stream,
fireflies, texture export shapes, green-floor render check, perf budget.
