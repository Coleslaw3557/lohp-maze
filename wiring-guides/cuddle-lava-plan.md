# Cuddle Cross LAVA floor projection — plan (2026-07-22)

The content plan for the Cuddle Cross floor projection (rig geometry, mount
optimization and tracker: `sim/maze_layout.json` `projection` key +
`sim/README.md` "Planned: Cuddle Cross floor projection"). Tim's content call
2026-07-22: **stepping stones on lava**, supersedes the placeholder snakes.

**2026-07-23: lava is now one of three selectable themes.** The engine grew a
`FloorShow` base + `THEMES` registry; the JUNGLE theme (snakes on leaf
litter, `wiring-guides/cuddle-jungle-plan.md`) and the TEMPLE theme
(torch-lit flagstones, `wiring-guides/cuddle-temple-plan.md`) share the
skeleton. Switch
in the sim with the header **Floor** button (shared across tabs; it also
forwards to the Pi renderer's live control port :5002 when reachable), in
production with `curl -X POST http://<pi>:5002/theme/<name>` — `--theme`
sets only the boot theme. The refactor left this show's output
byte-identical (golden-frame verified).

## The show

The deck is molten lava (flowing heat field, masked to the deck outline as
always — off-deck pixels black). Across it: a **walkable chain of ~5 grey
stepping stones** running door sliver to door sliver (Cuddle CROSS is a
crossing — the goal is to *walk across the stones*), stride-spaced (~0.6 m)
and bending around the mast island, which sits dead on the straight line.
Stones read as plain grey rock; orange/heat appears only while one is
actually sinking or rising (Tim, 2026-07-22 v2: fewer stones, grey stones,
no idle glow). The LD2450 tracks walkers; the show plays with them:

**v3 theme pass (Tim: "Mayan temple in the forest"):** rocks are textured —
wobbled outlines, grey mottle, long crack veins, soft key light — and each
chain stone carries a chiseled **Mayan numeral in walking order** (dots and
bars, 1 at the east door … 5 at the west; the spare wears the shell-zero).
Cracks fade inside the glyph zone so numerals stay legible (the mason dressed
the surface). The mast island is a carved **sun-stone altar** (two rings,
twelve ticks, center pit). Canopy-shadow dapple hugs the deck rim (the
jungle pressing in); ember sparks drift over the lava. Walk near a stone and
its glyph glints faint amber; a sinking stone's glyph heats FIRST — a beat of
warning before the melt. All stone/altar artwork is precomputed in the engine
and shipped to the sim page in the hello message, so both displays show
identical rock.

- **The mischief mechanic** (the heart of it): watch each tracked walker's
  heading. When someone is clearly walking *toward* a stone (heading cone +
  0.7 s dwell), that stone **sinks** — rim glows, melts under — while another
  stone **rises** somewhere off to the side of their path, redirecting them.
  Cooldowns keep it playful, not hostile: per-stone 8 s, global 3 s, and never
  fewer than 5 stones up.
- **Bubbles**: ambient lava bubbles pop constantly; bursts cluster around
  sinking/rising stones.
- **Recoil glow**: lava brightens softly around each tracked walker's feet
  (a gaussian warm-up, NOT a hard ring — the v1 max-heat ring also exposed a
  uint8 additive-overflow rainbow glitch; stones now replace-composite and
  render() clips before quantizing).
- **Presence cue**: show starts on presence (or the `Cuddle Cross LT`
  trigger), fades out 60 s after presence is lost — same cue model the sim
  already previews.
- The center mast base is a content island (ring around the real pole flange).
  Production does NOT paint a mast shadow — the pole casts a real one; only
  the sim draws it, as environmental preview.

## The monster (v4): Kukulkan shows his head occasionally

Asset search came up empty (top-down lava-breach sprites don't exist in the
free-asset world, and pixel-art would clash + need an image decoder), so the
feathered serpent is procedural like everything else. Every 45–100 s while
the show is on (first appearance ~20 s in): a dark mass swims under the
crust with a faint bow-glow, then the head breaches — obsidian scales with a
spine ridge, ember rim-light where it meets the melt, jade feather crest,
amber eyes with white-hot cores that pulse while he looks around (±25° scan,
2–4 s) — then sinks in bubbles. Breach spot is clear of stones/altar and
~1.6 m from tracked walkers (visible, never underfoot). Head geometry is
analytic, so production precomputes 16 orientations; the sim gets one patch
and rotates on canvas. Knobs: MONSTER_* constants.

## Architecture — one engine, two displays

`projection_engine.py` (repo root, production code): pure numpy simulation +
renderer. Grid 256×192 (the LS625X is XGA; content upscales 4×). Everything
behavioral lives here: geometry (ported from the sim's `toPx` mapping + deck
mask polygon), stones, mischief, bubbles, presence/fade. Inputs are tracked
positions in world meters; output is an RGB frame plus a JSON-able state dict.

- **Sim** (design surface): the engine runs inside the sim server;
  `WS /sim/projection` streams state (stones/events/fade + the heat field as
  base64) at ~15 fps and receives the page's lagged avatar position as the
  virtual LD2450 track (the page keeps the existing 150 ms first-order lag
  before sending, so hardware feel is preserved). The page is a thin view of
  engine state — same idiom as the `/sim/dmx` feed.
- **Production** (`projection_renderer.py` + `tools/lohp-projection.service`):
  the same engine writes the server Pi's framebuffer (`/dev/fb0`) — since
  2026-07-23 a LEGACY firmware fb at exactly the render grid (192×144) that
  the VideoCore scaler stretches to the LS625X's native 1024×768 (the KMS
  fb needed ~60 ms/frame of numpy upscale+pack; no SDL/EGL/GL in the chain
  either way — the vc4 EGL stack refused kmsdrm on the 3B+, 2026-07-22, and
  fewer layers is playa-robust anyway). Runs OUTSIDE the Docker container;
  venv at `/opt/lohp-projection-venv`; the unit unbinds fbcon while running.
  Perf (re-measured 2026-07-23 — the original "25 fps" was never real; it
  ran ~6 fps): after the octave-roll/sqrt-gamma/blob-cache engine pass and
  the GPU-scaler display path the service holds a locked 20 fps at
  `--grid 192` (lava engine capable of ~49) — details in
  wiring-guides/cuddle-jungle-plan.md "Perf".
  Track sources, pluggable:
  - `--source demo` — phantom walkers wander the deck (bench/attract mode,
    works TODAY with no sensor)
  - `--source esphome` — aioesphomeapi subscription to the cuddle node's
    LD2450 target entities (UNTESTED until the LD2450 is wired into the node
    UART1 on hardware day)

## Rollout

1. Engine + headless test (`sim/tools/lava_test.py`): mask ratio sane, a
   synthetic walker provokes sink+rise, perf budget (step+render must hold
   30 fps on a Pi 3B+ — verify ≥120 fps on the dev box as proxy).
2. Sim integration: engine stream + page renderer replace the snakes.
3. Pi: `tools/rpi-projection-setup.sh` (KMS overlay check — DietPi ships with
   the vc4 overlay off; enabling needs one reboot — venv, unit), deploy, demo
   mode on the real projector.
4. Hardware day: LD2450 into the cuddle node (ESPHome `ld2450` component),
   flip the service to `--source esphome`, tune stone count/cooldowns on the
   real deck.

## Tuning knobs (all constants at the top of projection_engine.py)

approach cone dot ≥ 0.68, approach window 0.35–1.7 m, dwell 0.7 s,
sink 1.3 s / rise 1.6 s, stone radius 0.19 m, chain stride 0.62 m
(± 0.10 m jitter), min stones up 3, bubble rate ~0.6/s, walker speed
gate 0.15 m/s, recoil glow r 0.35 m amount 0.28.
