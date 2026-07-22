# Room-node enclosure (laser-cut, one design for every room)

`node-enclosure.scad` generates the single enclosure used by all 15 room
nodes as **laser-cut panels for the xTool**: six finger-jointed pieces that
glue together, plus the acrylic sensor-window panel. Outer 110 × 78 × 43.8 mm
(interior 104.2 × 72.2 × 34, ply measured at **t = 2.9**) — as small as
reasonable around the node build. The lid is a **sliding tray**: it slides
in and out through a mouth in the front wall, riding through-slot channels
in the side walls — no fasteners, finger-pull notch at the front edge.

Board footprints were measured with calipers on the real parts
(2026-07-21). Remaining estimates, all etch-only so nothing cuts wrong:
AUX hole height (`jack_z` — drill after the DAC is screwed down), USB slot
height (`usb_z`, assumes ~1mm VHB), acrylic 3 nominal, velcro 20mm one-wrap.

| Inside | Mounted how |
|---|---|
| XIAO ESP32-S3 (21.46 × 17.78, USB-C on a LONG edge +2mm) | VHB to the floor, USB edge butted to the right wall |
| PCM5102A DAC (31.93 × 17.23, jack on a short edge +2.44mm) | screwed to the floor wherever it lands; jack edge butted to the right wall so its **own barrel sits behind the AUX hole** — no separate panel jack |
| LD2410C (22.14 × 16) / VL53L1X / Cuddle's 2450 + 2410C | fixed at the etched footprint behind the window (VHB or your call), sensor side out the aperture |

## IO — port B cut in every box, the rest etched + opened per room

**The cut openings in the kit are the sensor window aperture, the two back
strap slots the velcro mounting strap threads through, the lid's slide
channel/mouth (joinery, sealed by the lid itself), and — since the DMX-over-
WiFi plan (`../wiring-guides/dmx-over-wifi.md`) — the DB9 B opening + its two
jackscrew holes, because every room is now its own DMX source.** The
remaining ports are etched, labelled positions — drill just the ones a given
room uses:

| Where | What | Carries |
|---|---|---|
| left wall (**CUT**) | **DB9 B** — D-sub opening + 2 jackscrew holes | **the room's DMX out**: MAX485 inside → DB9→XLR adapter → the room's fixtures. Pinout 2 = GND, 3 = Data+, 4 = Data− (5V on 1 per the universal convention); pins 5–9 reserved — a future MCP23017's extra signals may share the shell |
| left wall (etched) | **DB9 A** — cutout rect + 2 jackscrew crosses | the field IO: one premade M-F cable to the room's button pod. Universal pinout **1 = 5V, 2 = GND, 3–9 = signals 1–7** on every box, used or not — see `../wiring-guides/db9-field-wiring.md` |
| floor (faces DOWN mounted) | SPARE ring, ~10mm grommet | wildcard for anything that isn't a DB9 someday |
| right wall | USB rectangle | XIAO power |
| right wall | AUX ring (9mm — swallows the plug sleeve) | the DAC's own 3.5mm jack → Pebble |

Box side of a DB9 = screw-terminal breakout bolted through the wall by its
jackscrews; pod side = the matching breakout; cable = **straight-through**
M-F serial extension (NOT null-modem). No crimping or soldering anywhere.
The WiFi antenna stays **inside the box** — no hole. Only 7 of 15 rooms
open port A at all (Gate, DPH, Bike, NFM, Photo Bomb, Monkey, Porto —
Porto's piezos are just signals 3–5); port A stays a mark everywhere else —
one cut file still serves every room because port B is universal.

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

- floor: SPARE grommet ring, DAC footprint (jack edge on the wall), XIAO
  footprint (USB edge on the wall)
- left wall: DB9 A cutout rect with jackscrew crosses + both port labels
  ("DB9 B DMX" marks the cut opening beside it)
- front (interior face): window-panel outline + its 2 screw positions,
  sensor footprint(s) centered in the aperture, SENSOR label
- right wall: USB rectangle, AUX ring, labelled
- back: a VELCRO label between the two strap slots
- window: its 2 screw positions + the 16×16 ToF aperture outline (cut it
  through for the 4 ToF rooms; radar rooms just leave it marked)

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
2. Glue everything EXCEPT the lid (wood glue for ply joints).
3. Bolt the port-B breakout through its cut opening (every room — it's the
   DMX out; MAX485 module VHB'd to the floor beside it). Then open the
   ports this room uses at their etched marks: wired rooms cut the DB9 A
   opening + drill its two jackscrew holes, bolt that breakout through.
   Screw/VHB boards at their footprints — DAC and XIAO tight to the right
   wall so jack barrel and USB-C land in their holes. Drill the AUX hole
   ~9mm centered on the barrel, then the window panel over its outline
   (2mm pilots for the M2s). Wire per `../wiring-guides/db9-field-wiring.md`
   + `../wiring-guides/dmx-over-wifi.md`.
4. Lid = the service hatch: slide it in through the front mouth until the
   back edge seats against the back wall; finger notch pulls it out. No
   glue, no fasteners (a dab of velcro or one bench screw through the
   front cap stops dust-rattle if needed).
5. Mount: thread a velcro strap through the two vertical back slots and
   wrap it around the scaffold leg at the planned clamp point.

The wooden 17×22×10 box this replaces is superseded; the mounting
positions, boresight yaw/tilt angles, and mock-bay tuning in
`../wiring-guides/room-node-enclosure-plan.md` still apply unchanged.
