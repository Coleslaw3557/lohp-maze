# Cuddle Cross projector mount — VIVO mount + enclosure build (2026-08-11 rev)

The physical mounting of the ViewSonic LS625X so the floor image lands where
the sim's projection mapping puts it. The sim's **Mount** button draws this
hardware and its dimensions in 3D (`sim/maze_layout.json` `projection` key is
the single source). Cut files: `enclosure/projector-shroud.scad` →
`python3 enclosure/export-shroud.py` → `projector-shroud.svg` (black = cut,
red = score, same XCS convention as the node boxes).

**2026-08-11 revision — the plywood corner arm is RETIRED.** Tim's call:
mounting moves to a COTS **VIVO MOUNT-VP01B** universal projector mount
(Amazon B01014CD0O), hose-clamped to the corner leg pair; the shroud stays
and its **rear wall becomes the mount interface**. Optics, datums, and deck
marks below are unchanged; the beam / cradle-rib / carriage sections are
gone (git history has the old build if it's ever wanted back).

## VIVO MOUNT-VP01B facts (Amazon listing + vivo-us.com, 2026-08-11)

- All-steel, rated **30 lb / 13.6 kg** — unit 6.2 kg + shroud/plenum ≈ 9 kg
  total, comfortable margin.
- Articulation **±15° tilt, ±15° swivel, 360° rotation** (collar on the
  pole axis).
- **FIXED 6 in / 152 mm profile** (ceiling-plate face → projector boss
  face). There is no radial/length adjustment on this model (the extending
  version is the VP02).
- Universal spider: 4 slotted arms, fits boss-hole spreads **5.25–12.5 in /
  133–318 mm**. The LS625X 223 × 150 pattern spans 268.8 mm diagonally —
  fits with margin. Arms are removable (mini-projector mode — unused here).
- Ships with 4 sizes of projector screws + ceiling hardware; hex tool
  included.
- Review intel: first fit is fiddly (~30 min of arm repositioning), then
  detach/reattach ≈ 3 min; several reviewers call the tilt lock weak —
  torque it hard and re-check after transport. Plate/hub dimensions are
  NOT published — measure the real unit before cutting standoff blocks.

## How it hangs (replaces beam / ribs / carriage)

1. Projector stays **NOSE-DOWN**, optics unchanged (window 1455, lens
   plumb ~250). Nose-down the ceiling-boss face is VERTICAL and faces the
   corner — the shroud rear wall lies against it.
2. The spider feet land **OUTSIDE the shroud rear wall**; their M4 screws
   pass through the 2.9 mm ply into the chassis bosses — the wall is
   **sandwiched** between feet and bosses and the shroud (+ plenum) hangs
   on those four screws. Included screws are sized for feet-on-bosses:
   through the wall they need **~3 mm more length — verify boss depth, do
   NOT bottom out**. Drill the wall from the unit on the bench (10 mm grid
   + nominal 223 × 150 rectangle etched on the wall).
3. Pole horizontal on the corner bisector; the ceiling plate hose-clamps
   to the paired 43 mm legs, bands threaded through the plate's lag slots.
   The **360° collar rolls the unit nose-down**; tilt + swivel are the
   fine aim trim the old ±80 mm slot used to be.
4. **The plate cannot sit flat on the legs** — two reasons, one fix:
   - *Radial*: profile is fixed at 152 mm and the boss face wants to be
     ~176 mm inboard of the corner, while the legs' SW faces stand ~18 mm
     outside it → a **~40 mm gap** between plate and steel.
   - *Steel*: the pole axis exits at boss-pattern center ≈ **1603 mm above
     deck — inside the 1600–1619 header band**; a plate centered there
     spans the band and would foul the header ends beside the legs.
   Fix: **two standoff blocks** (ply stack / hardwood, ~40 mm — thickness
   cut on site AFTER the test grid) between plate and legs at the
   member-free bands: **~1530–1560** (below the brace studs) and
   **~1625–1665** (inside the 1619–1696 rail–header gap). Clamps wrap
   leg + block + plate at those bands. One set of blocks solves the radial
   shortfall and the header clash at once.
5. Lateral: center the **LENS** on the string line, not the chassis (lens
   sits off-center in the 383.7 width) — a plate-position call made with
   the unit hanging.
6. **Safety lanyard** from the VIVO pole/plate around the top rail. Torque
   the rotation collar hard — the intake plenum hangs asymmetric off the
   right side and wants to roll the rig.

Adjustability delta vs the old arm: the ±80 mm radial slot is gone. Radial
= block thickness; vertical = clamp height on the legs; angles = VP01B
joints. The guide's 3% optical tolerance (±67 mm of image) that the slot
used to absorb now lands on block thickness ± the projector's own corner
adjustment — another reason blocks get cut after the projected test grid,
not before.

## Bottom window + cable bay (2026-08-11b)

Tim: close the bottom — open defeats the dust purpose — and the cables
have to plug in somewhere.

**Bottom = screw-on window panel.** The open bottom is gone: a flat panel
rides under the rim on a glued 2-ply perimeter ring (20 mm strips, flush
outer; 6× #4 wood screws up through the panel into the ring). ONE
opening — the **lens aperture, EXACT: 117 across × 120 high**, starting
**56 mm from the chassis edge on the exhaust flank's side** (viewer-RIGHT
facing the lens head-on = side L in the cut file). Nothing else on the
front (Tim). Its vertical position on the 147.7 mm face is assumed
CENTERED (not measured) — **lay the unit on the panel and verify against
the etched 10 mm ruler before glue-up**; the panel is a 5-minute re-cut
if it's off.

**Cable bay.** LATENT BUG in every rev before this one: nose-down the
connector panel (chassis rear, guide p.5) faces **UP**, and the cavity
gave it 4.5 mm — no plug on earth fits. The cavity is now `cable_bay`
(35 mm default) taller above the body: room for right-angle HDMI + power
+ DB9 serial heads, which then run to a **55 × 30 mm slot** high in the
mount wall (bottom edge ~5 mm above the body top, outboard of the spider
feet) — pass the heads through one at a time and cover the hole (Tim).

**THE ROOF TRADE — read before changing `cable_bay`.** The shroud top is
pinned ~6 mm under the 1760 soffit, so the bay cannot grow upward: every
millimeter of bay pushes the whole box, window and image DOWN:

    window = 1455 − cable_bay        image width = window / 0.49

At the default 35: **window 1420, image 2898 × 2174** (was 2969 × 2227),
near edge ≈ 195 from plumb → deck marks become ~**250 / 445 / 1532 /
2619** (far tip 429 shy of the SW corner), body top 1713.5, and the pole
axis drops to ≈ **1568 — below the brace studs (1574) and OUT of the
header band**, so the standoff-block bands shift down with it (the
1530–1560 / 1625–1665 bands in the diagram above are the bay=0 baseline —
re-derive against the real plate once the bay is fixed). Coverage loses
roughly 2 points. **Bench task that sets the real number: plug everything
into the unit with right-angle adapters and measure the tallest head
above the chassis rear face — set `cable_bay` to that + a few mm and
re-export.** If the LS625X connector bay turns out to be recessed, this
shrinks toward zero and the old numbers come back. The sim layout
(`maze_layout.json` projection key) still draws the bay=0 optics (window
1455) — update it when the bench measurement lands.

**2026-08-01 revision — official dimensions + offset correction.** Two
errors found against the official user guide (84-page LS625X/LS625W guide +
ViewSonic datasheet; Tim confirmed the model on the unit):

1. **The chassis was drawn at ~0.76× real size.** Official (guide p.56):
   **383.7 wide × 291.5 deep × 147.7 tall, net 6.2 kg**, ceiling bosses
   **4× M4 on a 223.0 × 150.0 mm pattern**. The earlier 293 × 221.5 × 114.6
   envelope was a bad source. Nose-down, the 291.5 mm depth hangs vertical —
   the body no longer fits under the roof at the old window height, so the
   **window drops 1525 → 1455 mm** and the image shrinks with it (throw
   ratio is fixed): **3112 × 2334 → 2969 × 2227 mm**.
2. **The lens-offset convention was misread.** The guide's throw table
   (p.13) gives vertical offset (d) = lens axis to image NEAR edge =
   **8.95% of image height** (e.g. 13.6 cm on a 152 cm-tall 100" image).
   "118% offset" means *image center over half-height* (50% + 8.95% ≈ 118%
   of h/2). The July math used 18% of full height — double. The image sits
   ~200 mm closer to the corner than previously mapped.

Net effect: lens plumb moves to **250 mm** from the corner and nominal lit
coverage **improves to 90.2%** (was 88.1% under the misread offset) because
the corrected offset re-centers the smaller image on the deck.

## Optics used (ViewSonic LS625X user guide p.13 + datasheet)

Throw ratio 0.49:1 (distance ÷ image width), XGA 4:3, offset: near edge
8.95% of image height from the lens axis. Window height 1455 mm →
image on the deck **2969 × 2227 mm**, near edge 199 mm from the lens plumb.
The guide notes **3% tolerance among these numbers due to optical component
variations** and recommends physically testing size/distance in situ before
permanent install — that is exactly what the calibration section below and
the cut-on-site standoff blocks are for. Everything below derives from the
image; if the image moves in the layout, these numbers move.

## Datums — measure from these, nothing else

1. **The NE deck corner** — the Cuddle deck ply corner at the hex vertex
   (the paired hose-clamped 1-11/16 in / 43 mm legs stand just *outside*
   this ply corner; the ply corner is the datum, not a tube).
2. **The string line** — that corner to the opposite (SW) corner: 3048 mm.
   This is the throw axis, and the beam's centerline sits ON it in plan —
   the **corner bisector, 60.0° to each frame face**.
3. **The deck surface** (ply top). All heights are above this.

## The calculated position

Bay=0 baseline — the built sheet carries `cable_bay` 35, which lowers the
window and every height below it by 35 (see Bottom window + cable bay).

| What | Where |
|---|---|
| Lens plumb point | ON the string line, **250 mm** in from the corner |
| Lens window (glass, facing straight down) | **1455 mm** above the deck |
| Body envelope, nose-down | 384 across the line × 148 along it × 292 tall |
| Body top | **1746.5 mm** — shroud top 1754, ~6 mm under the 1760 soffit (**verify the real soffit**) |
| Rear face (chassis bottom, boss face) | **~176 mm** in from the corner (lens assumed centered along-throw — MEASURE, see below) |
| Shroud rear corners vs frame planes | 47 mm inside worst-case → **25 mm clear of the rail tube** even if the frames stand ON the deck edge |

Orientation: pitch the unit 90° nose-down, lens face parallel to the deck.
The chassis **top** face looks SW down the line (the lens offset throws the
image that way); the chassis **bottom** — the ceiling-boss face — looks NE
at the corner and takes the VIVO spider feet through the shroud rear wall.
Level the shroud to the deck in both axes (fixed optics: any tilt is
keystone you cannot dial out — the VP01B's tilt/swivel are for truing back
to plumb, not for aiming).

**MEASURE FROM THE UNIT before drilling the wall** (the guide draws
neither): ① lens center from the boss face along the 147.7 mm chassis
height — assumed centered (74 mm) everywhere here; a different value shifts
the rear-face/steel numbers and the block thickness absorbs it. ② lens
center across the 383.7 mm width — it sits visibly OFF-CENTER (front view,
guide p.5): the etched grid tells you where the pattern actually landed so
the plate/blocks can be placed to put the **LENS** on the string line with
the body hanging offset. ③ boss thread depth (M4 through spider foot +
2.9 mm wall + washers must not bottom out — the stock screws are sized
without the wall in the stack). ④ plugged-connector stack: right-angle
HDMI + power + DB9 in, tallest head above the chassis rear face →
`cable_bay` (roof trade! see the Bottom window + cable bay section).
⑤ positions not yet measured: the lens aperture's place along the
147.7 face, and where each 9 × 3.5 flank grille sits along the 291.5
depth (lateral lens numbers are bench-done 2026-08-11: 117 × 120 @ 56) —
all drawn centered; lay the unit on the bottom panel / against the side
vents to confirm before glue-up.

Deck verification marks, taped from the corner along the string line:
**250** (lens plumb) / **449** (image near edge) / **1563** (image center) /
**2676** (far edge — 372 mm shy of the SW corner). Image width 2969,
centered on the line.

## The hardware at the corner

The steel facts that shaped the old arm still constrain WHERE the VIVO
lands: the frame planes meet at 120°, the header and rail cross the corner
zone, and anything flat that touches the leg pair crosses those members'
ends within ~40 mm laterally. The VP01B deals with it by standing off the
legs on the two blocks at member-free heights:

```
ELEVATION at the corner (heights above deck)
1790  coupling collars
1760  roof soffit — shroud top 1754, body top 1746.5
1715  ══ top rail ══   (frame member — do not touch)
1696 ─┐
      │ 77 mm rail–header gap → standoff block B ~1625–1665, clamps here
1619 ─┘
1603  ── VP01B pole axis (boss-pattern center, nominal) — lands INSIDE
1600  ══ header ══      the header band: the blocks keep the plate ~40 mm
                        off the steel so the header ends never touch it
1574  ● brace studs
1560 ┌ block A ┐   ← below the studs, clamps here
1530 └─────────┘
1455  ── projection window / shroud bottom rim
```

- **VIVO VP01B**: plate against the two blocks, blocks against the paired
  43 mm legs (nominal centers ±22.5), hose clamps wrapping leg + block +
  plate at both bands. Pole on the corner bisector, spider feet on the
  chassis bosses through the shroud rear wall (M4, see MEASURE box).
- **Shroud**: finger-jointed sleeve, inner cavity 391.7 × 156.1 ×
  (296 + cable_bay). **95 × 235 vent windows, one per flank**, over the
  real 9 × 3.5 in grilles (Tim bench 2026-08-11): **side R = intake**
  (plenum gaskets over it), **side L = exhaust** (open — coarse screen at
  most, never MERV). Rear wall = mount wall (etched drill grid + nominal
  boss rectangle) + the 55 × 30 cable slot mid-bay, and a **screw-on
  bottom window panel** with the lens aperture as the ONLY front opening
  (see the Bottom window + cable bay section). Top panel rides ~6 mm
  under the roof slab — service by unscrewing the spider feet or slacking
  the clamps.
- **Filtered powered intake**: `enclosure/projector-shroud.scad` also cuts
  the intake cartridge for the on-hand **9.5 x 9.5 x 0.75 in MERV
  filter** and the optional **ARCTIC P14 Pro**.
  Airflow **bench-measured 2026-08-11**: BOTH flanks carry a **9 × 3.5 in
  grille**. Facing the lens head-on, the viewer-LEFT flank = **intake** —
  the plenum gaskets over the 95 × 235 vent on that side (side R in the
  cut file). The other flank — the one next to the off-center lens —
  = **exhaust**, same size, out the matching side-L vent (open; coarse
  screen at most, never MERV — do not choke it). The front face has the
  lens aperture ONLY. Stack: room air -> MERV -> P14 -> shroud ->
  projector intake -> out the side-L exhaust vent (box runs slightly
  positive, as intended). Plenum mount pilots moved to FLANK the taller
  vent (±64/±100 — the old ±108 verticals would land inside the opening).
  The plenum is 265 mm square and overhangs the shroud side; verify
  corner/frame clearance before glue, and seal the back panel to the
  shroud with foam tape so the fan cannot pull dusty bypass air around
  the filter.
- **Fan power**: the LS625X has USB-A power at **5 V / 1.5 A**, but the P14
  Pro is a **12 V, 0.35 A** PC fan. Do not plug the P14 directly into USB.
  Preferred: run it from an independent 12 V supply or the camp 12 V bus
  with a local 1 A fuse, tied to the projector's switched AC if you want it
  to follow projector power. The projector's 12 V trigger is a control
  output, not fan power. A USB-to-12 V boost converter is electrically
  possible but is the least preferred field option: fuse it, expect startup
  margin to be thin, and do not hang anything else from that USB port.
- Load path: bosses → M4 (through the shroud wall) → spider arms → hub →
  ball → pole → plate → blocks + hose clamps → legs. **The real unit is
  6.2 kg**: glue every ply joint (structural — Titebond III), run clamps at
  both bands, and fit the **safety lanyard** from the VIVO pole/plate
  around the top rail before hanging the unit.

Assembly order: glue the shroud + plenum on the bench; slip the shroud
over the nose-down chassis; transfer-drill the 4 boss holes (etched grid);
splay the spider arms to the pattern and screw the feet through the wall
into the bosses (longer M4s, washers, no bottoming); clamp plate + blocks
to the legs at the two bands; mate the spider to the ball, roll nose-down
on the 360° collar, level the shroud both axes; dress power + HDMI out the
Ø16 grommet and down a leg.

## On-site calibration

1. String line corner to corner; tape marks at 250 / 449 / 1563 / 2676 mm.
2. Rough-clamp the plate on TEMPORARY blocks (~40 mm scrap); hang the
   unit; set the window 1455 mm above deck with the clamp height, roll
   nose-down on the collar, and level the shroud both axes with
   tilt/swivel (level = plumb, NOT an aiming knob).
3. Power a test grid. Near edge on 449, far edge on 2676, width 2969
   centered on the line. The **near edge** is the offset-sensitive edge:
   true it by changing **block thickness** (the guide's 3% optical
   tolerance is ±67 mm of image — that is the range block sizing must
   absorb, which is why final blocks get cut now, not on the bench).
4. Coverage barely moves across small radial shifts (90.2 ± 0.1%), so
   blocks are NOT a coverage knob — use them to true the near edge and to
   keep the shroud's rear corners **≥ 25 mm off the nearest steel**
   (rail/header tubes; the real leg ring stands ~40 mm outside the
   idealized corner, so there is usually room).
5. Square: both image edges must cross the string line at 90° (spin the
   360° collar in hairs). Cut + fit the final blocks, re-clamp, torque
   every VP01B joint + both clamp bands, re-check the grid. Trust the
   projected edges on the deck marks over any tape on the steel.
