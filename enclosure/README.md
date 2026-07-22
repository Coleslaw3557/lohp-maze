# Room-node enclosure (laser-cut, one design for every room)

`node-enclosure.scad` generates the single enclosure used by all 15 room
nodes as **laser-cut panels for the xTool**: six finger-jointed pieces that
glue together, plus the acrylic sensor-window panel. Outer 110 × 78 × 43.8 mm
(interior 104.2 × 72.2 × 34, ply measured at **t = 2.9**) — as small as
reasonable around the node build. The lid is a **sliding tray**: it slides
in and out **over the SHORT front wall** (that wall tops out at the channel
bottom, 36.9 — the 07-22 rev3 fix: a full-height wall with an entry mouth
can never pass the lid's tongues, which are wider than any mouth that
leaves the wall in one piece), riding through-slot channels in the side
walls — no fasteners, finger-pull notch at the front edge.

Board footprints were measured with calipers on the real parts (2026-07-21;
the DB9 breakout PCB re-measured 2026-07-22 at 1¼" = 31.75 long, D-sub
barrel excluded). Since the 07-22 rev every port opening is pre-CUT, which
promotes two height estimates into cuts — caliper the real stack before
burning a sheet: AUX hole height (`jack_z` = 6; Ø7 vs the ~Ø6.75 jack
barrel leaves little slack) and USB slot height (`usb_z` = 3.7, assumes
~1mm VHB). The DAC's jack position along its long edge is assumed centered
(`dac_cy` is the hole datum — caliper the real offset). Acrylic 3 nominal,
velcro 20mm one-wrap.

| Inside | Mounted how |
|---|---|
| XIAO ESP32-S3 (21.46 × 17.78, USB-C on the short END +2mm) | VHB to the floor, USB end butted to the right wall (long axis into the box) so the port noses into the cut USB slot; footprint centered on the front floor-mortise tab — the tab seams at the joint line the board up |
| PCM5102A DAC (31.93 × 17.23, jack on a LONG edge +2.44mm) | screwed to the floor wherever it lands; the long jack edge butted to the right wall (board reaches only 17.23 into the box) so its **own barrel fills the AUX hole** — no separate panel jack; barrel-in-hole is the datum, the footprint assumes the jack centered on that edge |
| LD2410C (22.14 × 16) / VL53L1X / Cuddle's 2450 + 2410C | **VHB'd to the acrylic window panel's inner face** at the footprint etched on the panel, sensor side out the wall aperture — the acrylic is the mounting plate (tape at the board edges, clear of the antennas; radar reads through the acrylic, ToF boards sit over their cut 16×16 hole) |

## IO — every port opening CUT in every box, labels on the score layer

**Since the 07-22 rev ALL port openings are cut in the kit: the sensor
window aperture, the two back strap slots, the lid's slide channels
(joinery, filled by the lid itself), the XLR DMX barrel hole
(`../wiring-guides/dmx-over-wifi.md` — every room is its own DMX source),
the DB9 A window, the USB-C slot and the AUX hole. Nothing port-shaped is
left to open on the bench; the red/etch layer (score in XCS) is only
labels, board footprints and the DB9 floor zone:**

| Where | What | Carries |
|---|---|---|
| left wall (**CUT**) | **DMX** — Ø22 XLR barrel hole, sized to the part not the D-standard (male XLR bodies run ~Ø19–19.5; the female nose just wraps that — ~Ø21 on economy jacks like the Devinal's 31×26×21). **Barrel only — no pre-cut screw holes**: the jack is its own jig, two short wood screws through its flange holes (jacks ship with no screws). **Caliper gate**: a genuine Neutrik D female needs a >Ø23.6 rear-mount cutout per their drawing — if the Devinal nose measures like a real D front, put `xlr_hole` back to 24 and re-export | **the room's DMX out**: MAX485 inside → XLR3 female jack (1 = GND, 2 = Data−, 3 = Data+, cups soldered once at the bench) → one standard DMX cable → the room's fixtures |
| left wall (**CUT**) | **DB9 A** — 20.3 × 11.7 window (a loose frame — the floor screws locate the PCB; screwlock holes: sit the PCB in its floor zone, mark where the posts touch, drill those 2× Ø6 — the posts pass through and cable thumbscrews grab them outside) | the field IO: one premade M-F cable to the room's button pod. Universal pinout **1 = 5V, 2 = GND, 3–9 = signals 1–7** on every box, used or not. The breakout runs as a bare PCB (1¼" long) screwed to the FLOOR in its etched zone (case off); the wall just frames the face — see `../wiring-guides/db9-field-wiring.md` |
| right wall (**CUT**) | USB-C slot 10 × 4 | XIAO power — the XIAO's own port noses into the slot, PCB flush on the wall |
| right wall (**CUT**) | AUX hole Ø7 (frames the jack's ~Ø6.75 barrel; the plug's Ø3.5 shank goes inside the barrel, its molded boot stops on the wall face) | the DAC's own 3.5mm jack → Pebble |

(The DMX cut was a second DB9 "port B" + a DB9→XLR adapter for exactly one
day — replaced 2026-07-22. A DMX port is a DMX port.)

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

## Cut layer vs mark layer

Each SVG carries two colours in one coordinate frame — **black = CUT,
red = ETCH**. In XCS: import the SVG, select the red objects → processing
**score** (or engrave), black → cut. The red marks are:

- floor: DB9 PCB zone (34 × 31.75 — the port-A breakout screws down here
  in wired rooms), DAC footprint (jack edge on the wall), ESP32 footprint
  — the XIAO (USB end on the wall, long axis into the box, centered on
  the front floor-mortise tab)
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
  ~231 × 178 mm bed, black = cut + red = etch (3 mm ply)
- `window-acrylic.svg` — the ACRYLIC job: the sensor-window panel alone
- `node-enclosure-cuddle.svg` / `window-acrylic-cuddle.svg` — Cuddle's
  wide-aperture one-off (14 rooms cut standard, 1 cuts these)
- `export.py` — regenerates all four SVGs from the .scad
- `sheet.png` / `sheet-etch.png` — the two layers; `preview-assembly.png`,
  `preview-underside.png` — glued-up views

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
   solder its three cups to the MAX485 leads at the bench BEFORE mounting,
   sit it in the barrel hole latch-up, and drive 2 short wood screws
   through its own flange holes (no pre-cut holes — the flange is the
   jig). Then VHB the module to the floor beside it, clear of the jack's
   rear barrel — it reaches ~19mm in.
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
4. Lid = the service hatch: slide it in over the short front wall's top
   edge (the tongues enter the side channels' open front ends) until the
   back edge seats against the back wall; finger notch on the exposed
   front edge pulls it out. No glue, no fasteners (a dab of velcro or one
   bench screw through the front cap stops dust-rattle if needed).
5. Mount: thread a velcro strap through the two vertical back slots and
   wrap it around the scaffold leg at the planned clamp point.

The wooden 17×22×10 box this replaces is superseded; the mounting
positions, boresight yaw/tilt angles, and mock-bay tuning in
`../wiring-guides/room-node-enclosure-plan.md` still apply unchanged.
