# Cuddle Cross projector mount — arm/enclosure build (2026-07-29, stand-off rev)

The physical mounting of the ViewSonic LS625X so the floor image lands where
the sim's projection mapping puts it. The sim's **Mount** button draws this
hardware and its dimensions in 3D (`sim/maze_layout.json` `projection` key is
the single source). Cut files: `enclosure/projector-shroud.scad` →
`python3 enclosure/export-shroud.py` → `projector-shroud.svg` (black = cut,
red = score, same XCS convention as the node boxes).

**2026-07-29 stand-off revision.** The walk-thru frames carry a **top rail
75 mm below the leg tops** and a full-width **header 190 mm down** (real
PSV-610 members). At the earlier 15 mm-off-the-legs position the body's rear
corners overhung the frame planes ~60 mm straight through both members — the
07-18 "roof-capped" height only checked the roof slab. Dropping instead of
sliding doesn't work: the 220 mm body cannot thread the 77 mm rail–header
gap, and going under the header guts the image. So the whole rig slides
**120 mm further inboard down the throw diagonal**: window height and image
size unchanged, the mapping only translates. Nominal lit coverage goes
91.2% → **88.1%**, and the arm's ±80 mm slot recovers ~1–2 points on-site
(the fab-drawing leg ring stands ~40 mm outside the idealized corner, so the
worst case rarely bites).

## Optics used (ViewSonic LS625X spec sheet)

Throw ratio 0.49:1 (distance ÷ image width), lens offset 118%, XGA 4:3.
Image on the deck: **3112 × 2334 mm**. Everything below derives from that
image — if the image moves in the layout, these numbers move.

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
| Lens plumb point | ON the string line, **220 mm** in from the corner |
| Lens window (glass, facing straight down) | **1525 mm** above the deck |
| Body envelope, nose-down | 290 across the line × 115 along it × 220 tall |
| Body top | **1745 mm** — 15 mm under the sim's roof slab (verify the real soffit) |
| Rear face (chassis bottom, boss face) | **135 mm** in from the corner |
| Rear corners vs frame planes | 44 mm inside worst-case → **25 mm clear of the rail tube** even if the frames stand ON the deck edge |

Orientation: pitch the unit 90° nose-down, lens face parallel to the deck.
The chassis **top** face looks SW down the line (the 118% offset throws the
image that way); the chassis **bottom** — the ceiling-boss face — looks NE
at the corner and takes the carriage plate. Level the shroud to the deck in
both axes (fixed optics: any tilt is keystone you cannot dial out).

Deck verification marks, taped from the corner along the string line:
**220** (lens plumb) / **640** (image near edge) / **1807** (image center) /
**2974** (far edge — 74 mm shy of the SW corner). Image width 3112, centered
on the line.

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
1760 └─ rib ─┘     clamps here                                  ╲ (LL) ╱   L=leg
1715  ══ top rail ══  (frame member — do not touch)              ╲═││═╱
1696 ─┐                                                     ribs ██││██
      │ 77 mm gap — the BEAM threads this                        │ ││ │
1619 ─┘                                                          │beam│──► SW
1600  ══ header ══    (frame member — do not touch)              │ on │   down
1574  ● brace studs                                              │ the│   the
1560 ┌─ rib ─┐  ← cradle band A (below the studs)                │line│   line
1530 └─ rib ─┘     clamps here                                   └────┘
1525  ── projection window / shroud bottom rim
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
  **±80 mm M6 slots**.
- **Carriage**: vertical plate ×3 laminations against the chassis boss
  face — **drill the LS625X ceiling-boss pattern on the bench, transferred
  from the unit** (10 mm grid etched as the guide; 3× M4 machine screws) —
  plus the top flange (×3) bolting up into the beam slots, nuts + fender
  washers inside the open beam end. Slack the two M6 and the whole
  carriage + chassis + shroud slides ±80 mm along the line.
- **Shroud**: 5-sided finger-jointed sleeve, open bottom flush with the
  window, vent windows both sides (filter cloth stapled outside), beam
  pass-through + Ø16 cable exit in the rear wall. Top panel rides ~6 mm
  under the roof slab — service by lowering the box, not lifting a lid.
- Load path: bosses → plate → flange → M6 → beam → side plates → ribs →
  4 hose clamps → legs. Glue every ply joint (structural — Titebond III).
  Add a **safety lanyard** from the beam around the top rail.

Assembly order: glue beam + back frames + ribs on the bench; offer the
weldment up through the rail–header gap; clamps on at the two bands; hang
the carriage; slide the shroud up around the chassis and screw it to the
carriage plate; dress power + HDMI out the Ø16 grommet and down a leg.

## On-site calibration

1. String line corner to corner; tape marks at 220 / 640 / 1807 / 2974 mm.
2. Clamp the mount; hang the unit; set the window 1525 mm above deck and
   plumb the lens over the 220 mark. Level the shroud both axes.
3. Power a test grid. Near edge on 640, far edge on 2974, width 3112
   centered on the line. Slide the carriage until the **near edge** sits
   its mark (it is the offset-sensitive edge).
4. Recover coverage if the steel allows: slide the carriage OUTBOARD
   (toward the corner) until the shroud's rear corners sit **25 mm off the
   nearest steel** (rail/header tubes), re-true the near edge, and let the
   software mask absorb the rest. Every 40 mm recovered ≈ +0.35 pt of deck.
5. Square: both image edges must cross the string line at 90°. Lock the
   M6s. Trust the projected edges on the deck marks over any tape on the
   arm.
