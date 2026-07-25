# Cuddle Cross CHAMBER floor projection — plan (2026-07-25)

The fifth theme for the Cuddle Cross floor projection (same rig, same
`FloorShow` engine skeleton — `wiring-guides/cuddle-lava-plan.md`). Tim's
content call 2026-07-25: a floor that **belongs to the room's printed
backdrop** (`sim/web/img/backgrounds/cuddle.jpg`, the moss-swallowed Mayan
chamber under a jungle skylight) — the projected deck reads as more of that
canvas's floor stretching into the room — plus an interactive **trap door**
and **quicksand** ("reacts to presence, action").

## The show

The deck is the chamber floor: big sun-bleached limestone flags, moss
veining every joint and creeping in sheets over the faces (warmer and
mossier than the temple theme's dark swept stone), long hairline cracks.
The light ramp (`_CHAMBER_STOPS`) runs moss-shadowed stone → full skylight
sun; a **sun-shaft pool** (the backdrop's open roof) wanders a slow
lissajous near the mast with ~10 **dust motes** drifting and twinkling
inside it, and every 6–14 s a single **leaf spirals down** the shaft, rests
on the stone, and fades. Two **relief-carved slabs** (step-fret rings, no
numerals) glint gold on approach, same logic as the temple carves.

### Trap doors (the centerpiece — reacts to presence AND action)

Two square slabs (0.55 m, `TRAP_N`/`TRAP_W_M`), their seam grooves and
iron ring pulls always visible so repeat visitors learn the spots (the
scarab-mouth principle). State machine per slab:

- **Stand on one** (within 0.45 m for 0.6 s): it **shudders** first
  (`trap_tremble` — slab jitters, grinding dust), then **grinds open**
  over ~1.1 s (`trap_open`): the slab slides aside and a black pit opens
  in the floor, swallowing the light (negative field blob).
- **Sprint across it** (feet over `TRAP_FAST_MPS` = 0.9 m/s): no warning —
  it **SLAMS** open instantly (`trap_open` with `slam: 1`).
- 1.6 s after the pit opens, two **amber eyes blink open** in the dark
  below (`trap_eyes`), tracking nothing, just watching. Occasional blink.
- Walk away (past 0.95 m for 1.8 s) and the slab **grinds shut**
  (`trap_shut`), dust puffing at the seam.

### Quicksand (reacts to loitering)

One pool (`QSAND_R_M` 0.38 m) of dry sand filling a break in the flags,
wobble-edged, always visible. Stand in it 0.8 s and the sand **takes
hold** (`sand_grip`): the surface goes wet-dark, contracting rings pull
inward, slow spiral streaks turn with a swirl phase, and a **dark sink
mark grows under the feet** (with a pale tide ring) the longer they stay —
saturating at 3 s. Mud **bubbles** burp up near the feet every few seconds
(`sand_bubble`). Step out and it releases (`sand_release`), settling back
dry over ~1.6 s.

### Overlay rule (video-base compatibility)

Traps, quicksand, and the sand's idle patch are **never baked into the
base texture** — they draw as overlay sprites every frame, engine and sim
page alike. Over an AI video base the baked spots would sit at
grid-dependent positions and double up with the live ones; as overlays the
same pixels ride on either base. (Carve glints follow the temple rule
instead: skipped by the page while a video base is up.)

## Sim page

`chamber` in `FLOOR_LABEL`; hello ships per-trap slab + pit sprites (the
slab is its own patch of floor with seam + ring painted on) and the sand
patch with its corner origin; state streams per-trap
`{ph, arm, eyes, st}`, sand `{act, sw, grip, bubs}`, leaves, and motes.
Log lines: "the slab underfoot SHUDDERS…", "the TRAP DOOR grinds open!" /
"…SLAMS open under your feet!", "eyes open in the dark below…", "the floor
turns to QUICKSAND underfoot…". Chamber fx rings render pale gold-green.

## Video base

`base_loop_chamber_192.npy` / `.mp4` via the bridge-loop pipeline
(`experiments/video-base/run_bridge.sh`, prompt
`prompt_chamber_floor.txt`): photoreal moss-and-flagstone floor matching
the backdrop canvas, gentle vine/grass/leaf/dust motion, flat shadowless
light (the engine multiplies its own). Lesson (2026-07-25): conditioning
clip A on the engine's procedural base export kept the synthetic look and
killed motion (0.15/255) — the text-only probe → bridge-home flow from the
jungle rework is the recipe (first-frame anchor, `prep_loop --clip-b`).

## Tuning knobs (constants in projection_engine.py)

`TRAP_*` (count, size, arm/open/shut timing, sprint threshold, eye delay),
`QSAND_*` (radius, grip/full/release timing, bubble gaps), `SHAFT_R_M`,
`MOTE_N`, `LEAF_*`, `_CHAMBER_STOPS`, `CHAMBER_CARVES`.

## Test

`sim/tools/lava_test.py` sections 17–19: traps place/arm/open/eyes/shut,
quicksand grips + releases (render reads sunk), textures export, perf
budget. The sprint-slam path is exercised manually (fast track over the
slab → `trap_open` with `slam: 1`).
