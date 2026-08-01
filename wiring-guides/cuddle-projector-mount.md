# Cuddle Cross projector mount — arm/enclosure build (2026-08-01 real-dims rev)

The physical mounting of the ViewSonic LS625X so the floor image lands where
the sim's projection mapping puts it. The sim's **Mount** button draws this
hardware and its dimensions in 3D (`sim/maze_layout.json` `projection` key is
the single source). Cut files: `enclosure/projector-shroud.scad` →
`python3 enclosure/export-shroud.py` → `projector-shroud.svg` (black = cut,
red = score, same XCS convention as the node boxes).

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
the carriage's ±80 mm slot are for. Everything below derives from the image;
if the image moves in the layout, these numbers move.

## Datums — measure from these, nothing else

1. **The NE deck corner** — the Cuddle deck ply corner at the hex vertex
   (the paired hose-clamped 1-11/16 in / 43 mm legs stand just *outside*
   this ply corner; the ply corner is the datum, not a tube).
2. **The string line** — that corner to the opposite (SW) corner: 3048 mm.
   This is the throw axis, and the beam's centerline sits ON it in plan —
   the **corner bisector, 60.0° to each frame face**.
3. **The deck surface** (ply top). All heights are above this.

## The calculated position

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
at the corner and takes the carriage plate. Level the shroud to the deck in
both axes (fixed optics: any tilt is keystone you cannot dial out).

**MEASURE FROM THE UNIT before cutting the carriage** (the guide draws
neither): ① lens center from the boss face along the 147.7 mm chassis
height — assumed centered (74 mm) everywhere here; a different value shifts
the rear-face/steel numbers and the slot absorbs it. ② lens center across
the 383.7 mm width — it sits visibly OFF-CENTER (front view, guide p.5):
when bench-drilling the boss pattern, place the **LENS** on the plate's
etched centerline, not the chassis middle, so the lens lands on the string
line and the body hangs offset. ③ boss thread depth (M4×16 through the
8.7 mm plate stack + washers must not bottom out).

Deck verification marks, taped from the corner along the string line:
**250** (lens plumb) / **449** (image near edge) / **1563** (image center) /
**2676** (far edge — 372 mm shy of the SW corner). Image width 2969,
centered on the line.

## The mount — why it's shaped this way

The corner is hostile to flat plates: the frame planes meet at 120°, only
30° off anything facing the corner, so any wide plate that touches the leg
pair crosses the rail/header **ends** within ~40 mm laterally. The mount
therefore touches the legs only at **member-free heights**, and keeps all
vertical structure ≥ 65 mm inboard of the corner:

```
ELEVATION at the corner (heights above deck)        PLAN at the beam band
                                                              deck corner
1790  coupling collars                                  frame ╲ 60°│60° ╱ frame
1775 ┌─ rib ─┐  ← cradle band B (above rail weld)       face   ╲   │   ╱  face
1759 └─ rib ─┘     clamps here                                  ╲ (LL) ╱   L=leg
1754  ── shroud top (soffit 1760; body top 1746.5 —              ╲═││═╱
      100+ mm inboard of the ribs, no plan conflict)        ribs ██││██
1715  ══ top rail ══  (frame member — do not touch)              │ ││ │
1696 ─┐                                                          │beam│──► SW
      │ 77 mm gap — the BEAM threads this (axis 1658)            │ on │   down
1619 ─┘                                                          │ the│   the
1600  ══ header ══    (frame member — do not touch)              │line│   line
1574  ● brace studs                                              └────┘
1560 ┌─ rib ─┐  ← cradle band A (below the studs)
1530 └─ rib ─┘     clamps here
1455  ── projection window / shroud bottom rim
```

- **Cradle ribs ×4** (horizontal ply): open Ø44 slots seat the leg pair
  (nominal centers ±22.5 — the open cradles + clamps absorb the real pair's
  spacing). A hose clamp threads the 16×5 slot inboard of each cradle,
  wraps the tube, and pulls the cradle onto the leg. Two ribs per band;
  bands **~1530–1560** and **~1745–1775** above deck.
- **Side plates ×2** (vertical, on the corner bisector at lateral ±47):
  they are the box-beam webs, rising at the corner end into 245 mm back
  frames that the rib wings cross-tenon into. Their outboard edge stops
  **65 mm inboard of the corner** — nothing vertical ever reaches the
  rail/header.
- **Box beam** 100 × 45 (top/bottom plates + the side plates + 2 internal
  ribs): centerline at **1658 mm** above deck, dead in the rail–header gap,
  front end 40 mm shy of the corner. Top/bottom plates carry the two
  **±80 mm M6 slots** — **2026-08-01: slots re-centered on the carriage's
  actual bolt line ~139 mm from the corner** (the 07-29 sheet had them at
  the beam's far inboard end, where the carriage never rides — latent
  error, nothing was built from it).
- **Carriage**: **Π-shaped vertical plate ×3 laminations, 260 × 240** —
  the real 223 × 150 boss pattern is wider than the beam and its top row
  sits above the beam underside, so the plate's ears rise beside the beam
  and the central notch floor sits at the beam bottom. **Drill the boss
  pattern on the bench, transferred from the unit** (10 mm grid etched as
  the guide; **4× M4×16 machine screws + fender washers — verify boss
  depth, do not bottom**; center the LENS on the etched line, see MEASURE
  box) — plus the top flange (×3) bolting up into the beam slots, nuts +
  fender washers inside the open beam end. Slack the two M6 and the whole
  carriage + chassis + shroud slides ±80 mm along the line.
- **Shroud**: 5-sided finger-jointed sleeve, inner cavity 391.7 × 156.1 ×
  296, open bottom flush with the window, **90 × 160 vent windows both
  sides** (filter cloth stapled outside — sized to the real side fan
  grilles), beam pass-through (center 203 mm above the rim) + Ø16 cable
  exit in the rear wall. Top panel rides ~6 mm under the roof slab —
  service by lowering the box, not lifting a lid.
- Load path: bosses → plate → flange → M6 → beam → side plates → ribs →
  4 hose clamps → legs. **The real unit is 6.2 kg** (not the featherweight
  the phantom envelope implied): glue every ply joint (structural —
  Titebond III), run all four clamps, and fit the **safety lanyard** from
  the beam around the top rail before hanging the unit.

Assembly order: glue beam + back frames + ribs on the bench; offer the
weldment up through the rail–header gap; clamps on at the two bands; hang
the carriage; slide the shroud up around the chassis and screw it to the
carriage plate; dress power + HDMI out the Ø16 grommet and down a leg.

## On-site calibration

1. String line corner to corner; tape marks at 250 / 449 / 1563 / 2676 mm.
2. Clamp the mount; hang the unit; set the window 1455 mm above deck and
   plumb the lens over the 250 mark. Level the shroud both axes.
3. Power a test grid. Near edge on 449, far edge on 2676, width 2969
   centered on the line. Slide the carriage until the **near edge** sits
   its mark (it is the offset-sensitive edge — and the guide's 3% optical
   tolerance is ±67 mm of image, which the slot absorbs).
4. Coverage is nearly flat across the slot's travel (90.2 ± 0.1%), so the
   slot is NOT a coverage knob anymore — use it to true the near edge and
   to keep the shroud's rear corners **≥ 25 mm off the nearest steel**
   (rail/header tubes; the real leg ring stands ~40 mm outside the
   idealized corner, so there is usually room).
5. Square: both image edges must cross the string line at 90°. Lock the
   M6s. Trust the projected edges on the deck marks over any tape on the
   arm.
