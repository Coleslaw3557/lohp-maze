# Camp layout in the sim (4:30 & B)

The whole camp lot from Jen's placement drawing (`LotHP-26-v3.svg`, repo root)
renders around the maze in the sim at true scale, behind the **Camp** button
(default on, choice sticks per browser). Address: **4:30 & B Plaza, at the
plaza's own 2:15 position**. `sim_camp.jpeg` is a top-view screenshot.

**The drawing is MIRRORED vs reality** (Tim 2026-08-06): the bake tool
reflects the whole plot left/right around the maze (the maze itself never
moves), putting B street on the maze's +x side. Don't "fix" the SVG — the
reflection lives in the tool.

**Plan re-seat** (Tim 2026-08-06): the drawn maze bar is shorter than the
real one and offset within it, so after the flip the bake also slides the
plan so the real maze bar centers in the drawn maze mark (computed each
bake, currently −2.13 m) and pulls it 0.8 m frontage-ward so the maze sits
near the drawing's ~7 ft setback from the 50' arc. Hard limit on "closer":
the entrance towers at z=5.6 must stay inside the plaza rim. The bake prints
the re-seat offsets; containment of the maze corners + towers was verified.

The plaza is drawn from the address: the frontage arc's 75-ft circle is the
plaza rim; plaza mini-clocks point 12:00 AT the Man (radially inward), so
"camp @ 2:15" = the Man lies 67.5° counterclockwise around from the camp's
rim bearing. That convention is pinned by geometry, not looked up: with it
(and the flip), the B-ring tangent it predicts parallels Jen's drawn B-street
edge to 9.8° — the alternative absolute-clock reading misses by ~55°. The
skew prints on every bake as a regression check. The sim draws the rim, the
4:30-radial + B-ring road bands crossing at the plaza, a center marker, and
a dashed Man sight-line with a beacon (direction exact; beacon drawn ~130 m
out, true distance ≈950 m ≈ the B-ring radius — approximate).

## What renders

| Drawing | Reality | Sim |
|---|---|---|
| lot boundary | 50' plaza arc / 175' B / 150' neighbor / 100' BDS edges | orange line + tint, frontage labels |
| Black Rock shade (both) | EMT-conduit shade structure, aluminet; angled shade panels off every roof edge run to the GROUND ~6' out at the tie-down line | flat roof + perimeter legs + ground-reaching skirt panels + corner guys |
| tent-camper BRS | 30×40 structure, 8' tall; drawn 45×55 zone = structure + ~6' tie-downs each side | as described |
| tent spots | 12 spots (4×3, 10×10 each) subdividing the STRUCTURE; middle 2 EXCLUDED, only the 10 edge spots used | grid + orange X on the middle pair |
| Trailer + BRS | cargo trailer under a 10×20 Black Rock shade, 10' tall; drawn 22×32 zone = structure + ~6' tie-downs | 8.5×20 trailer under the 10×20 canopy |
| Camp Communal Space | one 10×20 Costco carport centered on each side of the 40×40, corners touching at (±10,±10) — no overlap — 20×20 open square in the middle; Black Rock shade over the square, LEVEL with the canopy (eave height, continuous coverage); sidewalls on every outward face, inward faces open; 8' entrances front (maze side) and rear (facing the water tank); floors under the carports | as described |
| Water | 500-gallon tank | tank + pad circle |
| Small Generator | Predator 5000 inverter | red box + 5×5 pad |
| pink strip + circles | 18' band + fuel depot shared with Blazing Death Ship | tinted strip, pad + 25' dashed ring |
| Car ×6, OSS Container, Shower & Evap, Bike Rack ×2 | — | boxes at drawn spots |

The maze, towers, and camp sign are NOT drawn by this layer — the sim already
has the real ones; the drawing's maze/sign marks are used only for anchoring.

## Files — the separation contract

- `sim/web/camp_layout_data.js` — GENERATED baked world-space geometry. Never hand-edit.
- `sim/web/camp_layout.js` — self-contained renderer (all camp visuals live here).
- `sim/tools/camp_from_svg.py` — the bake tool.
- `sim/web/app.js` — only ~15 hook lines (`buildCampLayout` / `setCampVisible` / `btn-camp`).

**Normal sessions should not need to open any of these.** The layer is done;
only touch it when the placement drawing revs or the camp visuals themselves
need changing.

## Drawing rev workflow

1. Drop the new SVG in the repo root, update the `SVG` path at the top of
   `sim/tools/camp_from_svg.py` (and this doc + the app.js/index.html tooltip
   if the version string matters).
2. `python3 sim/tools/camp_from_svg.py` — rebakes `camp_layout_data.js`,
   prints every zone/item with sizes and world positions for eyeballing. It
   exits loudly on any shape it can't classify (new/renamed items need a new
   size or class rule in the tool).
3. Reload the sim page.

## How the anchoring works

- Drawing scale: 1 ft = 1 mm at 72 dpi (2.83465 SVG units/ft); the labeled
  175' B-street edge and 100'/150' edges confirm it.
- The drawing's maze hex centroid maps onto `maze_layout.json` `hex_center`
  (10.044, 1.26); the maze wing axis (−26.536° in the SVG) maps to world +x,
  the plaza side to +z. So B street truly runs 26.5° off the maze axis — the
  lot renders diagonally, that's correct.
- Wing-length cross-check at bake time landed within ~1 ft of the sim maze
  bar on both ends.
