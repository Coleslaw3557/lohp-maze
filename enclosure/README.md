# Room-node enclosure (laser-cut, one design for every room)

`node-enclosure.scad` generates the single enclosure used by all 15 room
nodes as **laser-cut panels for the xTool**: six finger-jointed pieces that
glue together, plus the acrylic sensor-window panel. Stock is **3 mm ply**
(re-decided 2026-07-24, ending a one-day 6 mm detour; `t = 2.9` = the
sheet's 07-21 caliper — re-caliper any new batch). Outer
110 × 78 × 39.8 mm, interior 104.2 × 72.2 × 34 — as small as reasonable
around the node build. Every derived position tracks `t`
(`db9_cx`/`db9_cz`/`xlr_cz`/`dac_cy` are t-relative formulas — the 6 mm
episode's lasting gift), so re-exporting IS the thickness update. The lid
is a **drop-in tray** (07-24 rev4 — the rev3 sliding tray wedged on the
real kit: 0.4 mm channel clearance vs kerf taper and ply bow, a
108.6-wide lid guided by 2.2 mm tongues that racks under any off-center
pull, and a cap rail hanging off one 3 mm bridge; all deleted): every
wall runs full height, the lid is a floor-twin that drops straight down
with its edge tabs landing in **top notches on all four walls** — one
vertical translation, nothing to thread or rack. Finger notch at the
front edge lifts it out; two velcro dabs on the front tab shelves (strap
stash) hold it against playa wind. No fasteners.

Board footprints were measured with calipers on the real parts (2026-07-21;
the DB9 breakout PCB re-measured 2026-07-22 at 1¼" = 31.75 long, D-sub
barrel excluded). Since the 07-22 rev every port opening is pre-CUT, which
promotes two height estimates into cuts — caliper the real stack before
burning a sheet: AUX hole height (`jack_z` = 6; Ø7 vs the ~Ø6.75 jack
barrel leaves little slack) and USB slot height (`usb_z` = 3.7, assumes
~1mm VHB). The DAC's jack sits on its long edge but **~10 mm off the
board center** (07-24 dry-fit — the centered assumption put the cut hole
"about 10mm too far"): the AUX hole now cuts at `dac_cy + dac_jack_off`
and the board mounts **jack-end toward the back**; caliper the exact
offset before the next burn. Acrylic 3 nominal, velcro 20mm one-wrap.

| Inside | Mounted how |
|---|---|
| XIAO ESP32-S3 (21.46 × 17.78, USB-C on the short END +2mm) | VHB to the floor, USB end butted to the right wall (long axis into the box) so the port noses into the cut USB slot; footprint centered on the front floor-mortise tab — the tab seams at the joint line the board up |
| PCM5102A DAC (31.93 × 17.23, jack on a LONG edge +2.44mm, barrel ~10mm off board center) | screwed to the floor wherever it lands; the long jack edge butted to the right wall (board reaches only 17.23 into the box) so its **own barrel fills the AUX hole** — no separate panel jack; barrel-in-hole is the datum, hole cut at `dac_cy + dac_jack_off` (10), board mounted **jack-end toward the back** |
| LD2410C (22.14 × 16) / VL53L1X / Cuddle's 2450 + 2410C | **VHB'd to the acrylic window panel's inner face** at the footprint etched on the panel, sensor side out the wall aperture — the acrylic is the mounting plate (tape at the board edges, clear of the antennas; radar reads through the acrylic, ToF boards sit over their cut 16×16 hole) |
| MAX485 module (49.22 × 14.05 — the received 07-23 batch is the screw-terminal variant: A/B under a 2-pos screw terminal ON TOP above the VCC/B/A/GND header end, RO/RE/DE/DI at the far end, both headers factory-soldered PINS DOWN) | headers pulled (wick) or flush-clipped at the bench — there's no flat belly until they're gone — then VHB'd at the etched **RS485 floor footprint**: the lane sits 2mm behind the DB9 zone, terminal end at the A/B mark, 7mm back from the jack's ~19mm rear reach (07-24 dry-fit rearrange); the jack's pin-2/pin-3 cup pigtails land under the A/B screws, 5V/GND solder into the terminal-end holes and dress back along the wall, DI + the DE/RE tie leave the far end toward the XIAO |
| 74AHCT125 (NFM only; bare PDIP-14, ~21 × 10 over the legs) | **dead-bug at the etched AHCT zone** (back-center of the floor): glued on its back legs-up, wired per `../wiring-guides/room-games-plan.md`; the other 14 rooms leave the zone empty |

## IO — every port opening CUT in every box, labels on the score layer

**Since the 07-22 rev ALL port openings are cut in the kit: the sensor
window aperture, the two back strap slots, the wall-top lid notches
(joinery, filled by the lid's tabs), the XLR DMX barrel hole
(`../wiring-guides/dmx-over-wifi.md` — every room is its own DMX source),
the DB9 A window, the USB-C slot and the AUX hole. Nothing port-shaped is
left to open on the bench; the red/etch layer (score in XCS) is only
labels, board footprints and the DB9 floor zone:**

| Where | What | Carries |
|---|---|---|
| left wall (**CUT**) | **DMX** — Ø24 XLR barrel hole. **Caliper gate RESOLVED 2026-07-23**: the received Devinal's circular insert measures **Ø23.55** — true-D class (Neutrik's rear-mount drawing wants >Ø23.6), so the earlier Ø22 part-sized guess would never have fit; Ø24 is the D-standard cutout, 0.45 clearance before kerf, and the 31×26 flange resting on the **outside** face covers it. **Barrel only — no pre-cut screw holes**: the jack is its own jig, two short wood screws through its flange holes (jacks ship with no screws) | **the room's DMX out**: MAX485 inside → XLR3 female jack (1 = GND, 2 = Data−, 3 = Data+; cup pigtails soldered once at the bench, pins 2/3 landing under the module's A/B screws) → one standard DMX cable → the room's fixtures |
| left wall (**CUT**) | **DB9 A** — 20.3 × 11.7 window (a loose frame — the floor screws locate the PCB; screwlock holes: sit the PCB in its floor zone, mark where the posts touch, drill those 2× Ø6 — the posts pass through and cable thumbscrews grab them outside) | the field IO: one premade M-F cable to the room's button pod. Universal pinout **1 = 5V, 2 = GND, 3–9 = signals 1–7** on every box, used or not. The breakout runs as a bare PCB (1¼" long) screwed to the FLOOR in its etched zone (case off); the wall just frames the face — see `../wiring-guides/db9-field-wiring.md` |
| right wall (**CUT**) | USB-C slot 10 × 4 | XIAO power — the XIAO's own port noses into the slot, PCB flush on the wall |
| right wall (**CUT**) | AUX hole Ø7 (frames the jack's ~Ø6.75 barrel; the plug's Ø3.5 shank goes inside the barrel, its molded boot stops on the wall face) | the DAC's own 3.5mm jack → Pebble |

(The DMX cut was a second DB9 "port B" + a DB9→XLR adapter for exactly one
day — replaced 2026-07-22. A DMX port is a DMX port. The 6 mm stock detour
of 07-23 — and the port-reach counterbores it required — died 2026-07-24
with the return to 3 mm: posts, USB-C and AUX all reach normally again.)

Box side of the DB9 = screw-terminal breakout bolted through the wall by
its jackscrews; pod side = the matching breakout; cable = **straight-
through** M-F serial extension (NOT null-modem). Nothing is crimped or
soldered **in the field** — the XLR jack's three cups are a one-time bench
solder. The WiFi antenna stays **inside the box** — no hole. Only 7 of 15
rooms populate port A (Gate, DPH, Bike, NFM, Photo Bomb, Monkey, Porto —
Porto's piezos are just signals 3–5); everywhere else the pre-cut window
gets blanked (tape/cover plate) against playa dust — one cut file still
serves every room.

## Sensor window

56 × 24 aperture in the front panel; the **70 × 32 × 3 mm acrylic panel**
(`window-acrylic.svg`, its own job) screws over it — **2× M2 self-tappers
on the midline** (corner screws would leave <1mm acrylic web → cracks).

- **Radar rooms** (LD2410C / LD2450): solid plain acrylic — 24 GHz passes
  through. Nothing metallic on or behind it.
- **ToF rooms** (Entrance / Exit / Guy Line / VMM): 940 nm does NOT pass
  plain acrylic — uncomment the marked aperture in `panel_window()` and
  re-export, or use IR-pass acrylic.
- **Cuddle**: the 2450 + 2410C pair is 66.3mm wide — wider than the
  standard aperture. Cut the `-cuddle` files instead: 68-wide aperture,
  82 × 32 window, both footprints etched side by side.

## Camp-sign variant (`-sign` files — the 16th box, 2026-07-29)

The camp-sign controller (`../wiring-guides/camp-sign-plan.md`) rides in
the same shell: `node-enclosure-sign.svg` cuts the identical six-panel
box with the sign's port set instead of the room-node one — a third
variant beside standard/cuddle (`sign=true` in the .scad). One cut, one
box, mounted inside the band cavity behind the removable logo disc.
The PSU feed and the four LED strip groups plug INTO this box; nothing
sign-related lives loose in the cavity anymore.

Different from the room kit:

- **No sensor window** (front wall solid — etched **CAMP SIGN** on the
  OUTSIDE face, the fleet's one exterior ID), so **no acrylic job**; no
  DB9, no DAC/AUX, **no velcro slots** — the box screws down through its
  floor inside the wooden cavity (wood screws where they land, house
  no-pre-cut-holes rule as always).
- **XLR Ø24 = DMX IN** (same cut position as the rooms' DMX OUT): the
  Dfi RX's male stick plugs straight in if the tower-WiFi test fails —
  jack cups bench-wired to the MAX485 A/B screws exactly like a room
  box, **plus the 120Ω terminator across A/B** (the RX stub is its own
  tiny bus). WiFi ArtDMX stays primary; the populated jack just makes
  the fallback plug-and-play with zero playa soldering.
- **12V hole Ø8, left wall** (roughly where the DB9 window would be): a
  BTF 2-pin pigtail threads in to the buck's IN end, connector half
  outside — the PSU run from the LEFT-pillar fuse block (circuit C3,
  2A) plugs into it. Zip-tie knot inside = strain relief. All pigtails
  (this one, D1–D3 and BTN) keep **~10 cm slack tail outside** —
  connectors dangle and mate on slack, NEVER trimmed flush to the case
  (flush = every unmate prying against the zip-tie and the ply hole
  edge).
- **BTN hole Ø7, right wall** ("STORM" etched under it): a BTF 2-pin
  pigtail out to the arcade storm button on the sign scaffolding.
  Inside: signal → the XIAO's D3 (GPIO4, INPUT_PULLUP, the wall the
  XIAO sits against) + GND. A press POSTs `/api/sign_storm` — maze-wide
  Lightning + thunder on every speaker at once; the SERVER owns the
  30 s cooldown (`SIGN_STORM_COOLDOWN_S`, main.py).
- **D1–D3 holes Ø7, back wall**, directly behind the AHCT zone: three
  BTF 3-pin pigtails thread out, connectors outside — the strip chains
  plug in. **Under each hole the wall etches its chain and connection
  end** (2026-07-29 regroup): **D1 LEGENDS OF THE (e) · D2 LOGO ·
  D3 HIDDEN PLAYA (H)** — the logo field is its own output so the
  removable disc unplugs alone; the parenthesized letter is where that
  chain lands at band center. Power runs mirror the data (one per
  chain, entering only at word fronts/backs: 'L' / the disc / 'a' —
  camp-sign-plan.md). Hole pitch 24, pattern symmetric about the wall
  center — a flipped back wall lands the same holes and only the label
  order mirrors (cosmetic; pigtail-to-channel pairing happens inside at
  the AHCT). **Each pigtail's red +12V lead is DEAD inside the box**
  (data + GND only): chain power comes from the pillar fuse blocks,
  never through this box.
- **Floor zones**: ESP32 + RS485/A-B unchanged from the room kit (the
  validated positions); the **AHCT zone is populated here** (three
  pixel-data buffers, dead-bug, series resistors at the chip, straight
  out the D holes behind it; the chip's unused input ties to GND);
  DB9/DAC zones replaced by a **BUCK zone**
  (DIANN 12→5V, body 47 × 27 **confirmed by caliper 2026-07-29**; the
  end screw-terminal blocks overhang the zone line at BOTH ends — the
  body sits 14 off the left wall to make room for the IN-end block plus
  a straight wire run from the 12V hole. **Mount the 12V-IN end toward
  the left wall**, 5V-OUT end toward the XIAO).

Etch orientation for the sign box: floor UP, **front OUT** (CAMP SIGN),
back OUT (D1–D3), left/right forced by the pre-mirror as always.

## Cut layer vs mark layer

Each SVG carries two colours in one coordinate frame — **black = CUT,
red = ETCH**. In XCS: import the SVG, select the red objects → processing
**score** (or engrave), black → cut. **Burn the sheet exactly as
imported (no mirroring), etch face up.**

**Which face the etch lands on (07-24 — Tim's kit came out wrong):** one
sheet burns every mark on its face-up side, and the two chiral side
walls FORCE where that face ends up in the assembled box. As-drawn, the
left wall's DMX/DB9 labels landed INSIDE — so the flat outputs now ship
the **left wall pre-mirrored** (label text re-drawn un-mirrored), putting
its etch OUTSIDE like the right wall's USB/AUX. The symmetric panels are
the assembler's choice — orient them at glue-up:

- **floor**: etch (footprints) faces UP into the box
- **front**: etch (window outline + SENSOR) faces IN
- **back**: etch (VELCRO) faces OUT
- **left / right**: labels face OUT — already forced by the cut geometry

The red marks are:

- floor: DB9 PCB zone (34 × 31.75 — the port-A breakout screws down here
  in wired rooms), DAC footprint (jack edge on the wall, jack-end back),
  ESP32 footprint — the XIAO (USB end on the wall, long axis into the
  box, centered on the front floor-mortise tab), RS485 footprint
  (49.22 × 14.05, every room — lane 2mm behind the DB9 zone, long axis
  into the box, the A/B mark flagging the screw-terminal end toward the
  jack, 7mm back from its rear reach), AHCT zone (21 × 10, back-center —
  NFM's dead-bug shifter; empty in the other 14 rooms)
- left wall: the DB9 + DMX labels (both openings below them are cuts)
- front (interior face): window-panel outline + SENSOR label (the sensor
  footprints are etched on the acrylic panel itself — that's what the
  sensors mount to)
- right wall: the USB + AUX labels (slot and hole are cuts)
- back: a VELCRO label between the two strap slots
- window: the sensor footprint (radar outline, or the pair on the cuddle
  variant) + the 16×16 ToF aperture outline (cut it through for the 4
  ToF rooms; radar rooms just leave it marked) — sensors VHB to this
  panel's inner face

No screw-position marks anywhere: parts are their own jigs (drive screws
through their holes; the DB9 posts get marked from the real part). The
window M2s go on the panel MIDLINE near its ends, never the corners —
corner screws leave <1mm acrylic web and it cracks.

## Files

- `node-enclosure.scad` — the design; every dimension is a named parameter
- `node-enclosure.svg` — the PLY job: six wall panels nested on one
  ~232 × 170 mm bed, black = cut + red = etch (3 mm ply)
- `window-acrylic.svg` — the ACRYLIC job: the sensor-window panel alone
- `node-enclosure-cuddle.svg` / `window-acrylic-cuddle.svg` — Cuddle's
  wide-aperture one-off (14 rooms cut standard, 1 cuts these)
- `node-enclosure-sign.svg` — the camp-sign controller box (ply job
  only — no window/acrylic, no testfit: its new ports are wire
  pass-throughs plus the already-validated XLR + USB cuts)
- `export.py` — regenerates all the SVGs from the .scad
- `sheet.png` / `sheet-etch.png` — the two layers; `preview-assembly.png`,
  `preview-underside.png` — glued-up views; `sheet-sign.png` /
  `sheet-etch-sign.png` / `preview-assembly-sign.png` — the sign variant

The SVG is true mm scale — import straight into XCS. Cut outlines are
exact; add kerf compensation in XCS if you want piston-fit joints (glue
fills a normal kerf fine).

```bash
python3 export.py    # re-export all SVGs after editing the .scad
```

## Assembly

1. Dry-fit first. Corner fingers interlock front/back ↔ left/right; the
   floor's tabs mortise through the wall-bottom notches (flush outside).
   Handle the right wall gently until glued: the USB slot and AUX hole
   sit over floor-mortise notches, leaving thin ply bridges (~1.7mm under
   the USB slot, ~2.5 under AUX) that the floor tabs back up once
   assembled.
2. Glue everything EXCEPT the lid (wood glue for ply joints).
3. Mount the XLR jack in its cut opening (every room — it's the DMX out):
   solder short pigtails to its three cups at the bench BEFORE mounting
   (heat-shrink each), sit it in the Ø24 barrel hole latch-up, and drive
   2 short wood screws through its own flange holes (no pre-cut holes —
   the flange is the jig; it rests on the outside face). Bench-prep the
   MAX485 too: the received modules have pins-DOWN headers, so pull them
   (wick) or clip them flush, then VHB the module at its etched RS485
   footprint — terminal end at the A/B floor mark, 7mm back from the
   jack's rear reach. Pin-2/pin-3 pigtails go under the A/B screws
   (pin 1's joins node GND); 5V/GND solder into the terminal-end header
   holes and dress back along the wall, DI + the DE/RE tie leave the far
   end toward the XIAO — full recipe in `../wiring-guides/dmx-over-wifi.md`.
   NFM additionally dead-bugs its 74AHCT125 at the etched AHCT zone
   (`../wiring-guides/room-games-plan.md`).
   Wired rooms populate the pre-cut DB9 A window: sit the bare breakout
   PCB (case off) on the floor with its face through the window, mark
   where the two screwlock posts touch the wall, drill those Ø6 (posts
   stand proud outside for the cable thumbscrews), and screw the PCB down
   at its corner holes inside the etched zone. Unwired rooms blank the
   open window (tape/cover plate) against dust.
   Screw/VHB the DAC and XIAO at their footprints, tight to the right
   wall: the DAC's own jack barrel fills the AUX hole; the XIAO goes USB
   end first so the port noses into its slot, PCB flush on the wall — the
   footprint sits centered on the front floor-mortise tab, so the tab
   seams and the slot itself line it up. Then screw the window panel over
   its outline (2mm pilots for the M2s, on the midline near the panel
   ends — never the corners). Wire per `../wiring-guides/db9-field-wiring.md`
   + `../wiring-guides/dmx-over-wifi.md`.
4. Lid = the service hatch: drop it straight in — the edge tabs land in
   the walls' top notches, top face flush with the wall tops. Stick a
   velcro dab (hook on the notch shelf, loop under the tab) on the two
   front tab shelves against wind and dust-rattle; the finger notch at
   the front edge dips over the front wall's solid top center — reach in
   and lift. No glue, no fasteners.
5. Mount: thread a velcro strap through the two vertical back slots and
   wrap it around the scaffold leg at the planned clamp point.

The wooden 17×22×10 box this replaces is superseded; the mounting
positions, boresight yaw/tilt angles, and mock-bay tuning in
`../wiring-guides/room-node-enclosure-plan.md` still apply unchanged.
