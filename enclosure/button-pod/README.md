# Button pod enclosure (the far end of the DB9 cable)

The room-node box's port A cable has to LAND somewhere near the buttons —
this is that box. One universal laser-cut pod for the 8 wired rooms
(`../../wiring-guides/db9-field-wiring.md`,
`../../wiring-guides/arcade-button-db9-prewire-guide.md`): the premade
straight-through M-F DB9 cable plugs into the pod's wall, and the room's
buttons/piezos plug into its 4-pin JST pigtails. Nothing is crimped or
soldered in the field — every conductor lands under a screw or mates a
JST.

Inside (all passive copper — no powered boards, no firmware):

- **DB9 MALE screw-terminal breakout** (ANMBEST, the box end's twin) —
  bare PCB, case off, screwed to the floor in its etched zone, D-sub face
  through the left-wall window, screwlock posts drilled Ø6 from the real
  part (same recipe as the node box, geometry copied from its validated
  cuts — only the along-wall position moved to the wall's back half).
- **ONE dual-row terminal block, 6 circuits, 91 × 30 × 17.60 tall
  cover-on (Tim's calipers 2026-08-15)** — flat on the floor along the
  front wall, screws up. **It is the POWER BUS only**: left 2 circuits
  jumpered = 5V, right 4 = GND (wire links or a comb); the pin-1/pin-2
  feeds from the breakout land on its back row, the JST reds, blacks
  and greens on its front. **Signals never touch it** — each JST blue
  lands straight on its DB9 pin's own screw (6 pairs can't patch 9
  conductors; the 08-15 circuit count killed the patch-row draft, and
  the direct landing is fewer joints anyway — only TWO jumpers cross
  the floor). One block per pod (10 on order for 8 pods). The earlier
  draft's WAGO 221s are OUT of the standard build — redundant with the
  block-as-bus; they stay in the kit as field splices.

OUT: **seven Ø7 pigtail holes across the front wall** — one per BTF
4-pin JST-SM pigtail (camp-sign box grammar: thread the bare ends IN,
connector half stays outside, zip-tie knot inside as strain relief,
~10 cm slack tail, never trimmed flush). **Hole n = signal n = DB9 pin
n+2**; hole 1 sits at the DB9 corner. Unused holes get taped against
dust, same as unwired node-box DB9 windows.

## Shell

The **node-box shell verbatim** (`../node-enclosure.scad`): 110 × 78 ×
39.8 outer, 3 mm ply (t = 2.9 — re-caliper new batches), 5-seg corner
fingers, floor mortise tabs, full-height walls, rev4 drop-in lid with
Ø14 finger notch. **The pod lid and the room-box lid are the SAME
part** — spares interchange. No sensor window, no XLR, no USB/AUX; the
right wall has no ports at all — the 8x project etches the ROOM NAME on
it (see the etch table below: name OUT).

Back-wall mounting, two ways (the pods zip-tie to scaffolding CROSS
MEMBERS — Tim 2026-08-15): the node-standard vertical velcro slots
(20 mm one-wrap around a vertical leg/rail; a standard 4.8 zip tie
passes them too, heavy 7.6s don't) **plus four horizontal 9 × 4 zip-tie
slots, a high/low pair at each end** — the tie enters the top slot,
crosses the wall's inner face (same 3 mm clearance lane the velcro
uses; the DB9 zone already keeps off it), exits the bottom slot and
cinches around the tube, head outside. Two ties per box kill rotation;
11" ties reach around a 48.3 scaffold tube with slack.

## Per-room population (8 pods, one cut file)

| Room | Holes used | Notes |
|---|---|---|
| Gate | 1–6 | 6 pads; heaviest fan-out — fits the 2+4 bus split because each pigtail's black+green (same net) pair under one GND screw: 6 pairs + feed on 8 screws, 7 reds on 4 |
| Deep Playa Handshake | 1–5 | 5 buttons |
| Bike Lock | 1–4 | Q1-T, Q1-F, Q2-T, Q2-F |
| Vertical Moop March | 1–4 | 4 buttons (2026-08-16 revert: the wireless battery pucks are dead — VMM wires like every other room) |
| Porto | 1–3 | piezos: JST black = piezo −  → GND, blue = piezo + → signal; red/green empty |
| No Friends Monday | 1 only | ONE 4-wire run to the truck: red = 5V, black = GND, green = signal 1 (ladder ADC), blue = signal 2 (WS2812 data) — both signal circuits feed one hole |
| Photo Bomb | 1 | shutter button |
| Monkey | 1 | pedestal switch: green/blue only (COM/NO), no LED |

Standard button JST (prewire guide): red = LED+ → 5V, black = LED− →
GND, green = switch COM → GND, blue = switch NO → signal.

## Etch orientation — differs from the node box, read before glue-up

- **front: etch OUT** (hole numerals 1–7 + BTN POD — the field wirer
  reads the wall; the node box's front etches IN, don't run on habit)
- floor: etch UP; back: etch OUT (VELCRO); left wall: pre-mirrored in
  the flat file like the node box, so DB9 lands outside — flip the
  physical part over at glue-up and it seats correctly
- right wall: no cuts; from the 8x project it carries the ROOM NAME
  etch (DM Serif outlines, the node-box precedent) — name OUT, and the
  name is what assigns a kit its room; every other panel stays
  interchangeable between kits

Burn the sheet exactly as exported: black = cut, red = score, etch face
up. Same nesting as the node box (~232 × 170, one S1 bed load).

## Bench checks before burning

- **jst_cz vs block height: RESOLVED 2026-08-15** — the block calipers
  17.60 tall cover-on; the hole row's bottom edge at 21.4 clears it by
  3.8. Burn as drawn.
- Block mounting screws are NOT pre-cut (house rule — the part is its
  own jig). Short screws only: they must not pass the 2.9 floor. VHB if
  the on-hand screws are too long. Same for the DB9 PCB corner screws.
- Ø7 for the 4-wire JST-SM bundle is the sign box's proven 3-pin bore
  with one more 22 AWG in it — low risk, but thread one before cutting
  eight boxes' worth.

## Files

- `button-pod.scad` — the design; shell numbers copied from
  `../node-enclosure.scad`, pod-specific zones parameterized on top
- `export-button-pod.py` — regenerates the SVG + previews below
- `button-pod.svg` — the ply job: six panels, black = cut / red = etch
- `make-xcs-button-pod.py` / `button-pod-8x.xs` — **the ready-to-burn
  XCS project for the S1**: all 8 pods (48 panels) band-packed into
  THREE bed loads (458 × 292, 476 × 259, and a small third — 4mm gaps),
  device/material/processing cloned from `../enclosure-3mm.xs`
  (Cop Dodge). Load 1 = 7 floors + 5 lids + 4 fronts; load 2 = 2 lids +
  5 rotated rights + the remaining walls; load 3 = the Vertical Moop
  March pod's 6 panels (added 2026-08-16 with the puck revert — loads
  1/2 stay exactly the proven 7-pod packing). Every etch label rides
  the red layer, and **each right wall carries its ROOM NAME** (DM Serif
  outlines from `../DMSerifDisplay-Regular.ttf`, node-box precedent —
  names live in the .xs, the scad/SVG stay universal). Previews:
  `sheet-pods-load1.png` / `sheet-pods-load2.png` / `sheet-pods-load3.png`
- `preview-assembly-button-pod.png` — 3D check with ghost block (gold),
  DB9 PCB + D-sub (green/silver)
- `sheet-button-pod.png` — rasterized merged SVG, the XCS ground truth

```bash
python3 export-button-pod.py      # re-export SVG + previews after scad edits
python3 make-xcs-button-pod.py    # rebuild the 8x XCS project after either
```

## Assembly

1. Dry-fit, then glue everything except the lid — identical joinery to
   the node box (`../README.md` step 1–2). Orient per the etch table
   above.
2. Screw the terminal block into its lane (mark through its own holes)
   and the DB9 breakout into its zone, face through the window; mark the
   screwlock posts on the wall, drill Ø6, posts stand proud outside for
   the cable thumbscrews.
3. Link the block into its two buses (left 2 circuits = 5V, right 4 =
   GND) and jumper DB9 pins 1/2 to their back rows. Thread each needed
   JST pigtail through its hole, knot, land red on the 5V bus,
   black+green together under one GND screw, and blue on its DB9 pin's
   own screw. Label both JST halves with room + button number
   (`GATE-1`…).
4. Tape unused holes, drop the lid in, velcro-dab the front tab
   shelves. Mount: zip ties through the horizontal slot pairs around a
   cross member, or velcro (or 4.8 ties) through the vertical slots
   around a leg/rail. Dust caps on the DB9 when torn down.
