# Room-node enclosure (laser-cut, one design for every room)

`node-enclosure.scad` generates the single enclosure used by all 15 room
nodes as **laser-cut panels for the xTool**: six finger-jointed pieces that
glue together, plus the acrylic sensor-window panel. Outer 110 × 78 × 40 mm
(interior 104 × 72 × 34) — as small as reasonable around the node build.

| Inside | Mounted how |
|---|---|
| XIAO ESP32-S3 | VHB tape to the floor, USB-C at the right-wall slot |
| PCM5102A DAC | screwed at its etched footprint marks (**verify the etched corner spacing against a real board** — `dac_hx/dac_hy` params) |
| LD2410C / VL53L1X / Cuddle's 2410+2450 | zip-tied through the front-panel holes, boresight out the window |

## IO — positions etched, opened per room on the bench

**The only cut openings in the whole kit are for the sensors** (the window
aperture + its four zip-tie holes) **and the two back strap slots the
velcro mounting strap threads through.** Every port is an etched, labelled
position instead — drill/cut just the ones a given room uses:

| Where (etched) | What | Carries |
|---|---|---|
| floor (faces DOWN mounted — dust/rain smart) | GX16-8 ring | up to 6 arcade buttons + common (Gate 6, DPH 5, hex 4, Bike 4, NFM ladder) |
| floor | 3× GX12-2 rings | Porto piezos ×3, single buttons, spares |
| right wall | USB rectangle | XIAO power |
| right wall | AUX / ANT rings | 3.5 mm line-out → Pebble; antenna pigtail |

That's what lets one cut file serve every room — a room's unused ports are
never opened at all.

## Sensor window

56 × 24 aperture in the front panel; the **64 × 32 × 3 mm acrylic panel**
(`panel-window.svg`) screws over it at the four etched positions.

- **Radar rooms** (LD2410C / LD2450): solid plain acrylic — 24 GHz passes
  through. Nothing metallic on or behind it.
- **ToF rooms** (Entrance / Exit / Guy Line / VMM): 940 nm does NOT pass
  plain acrylic — uncomment the marked aperture in `panel_window()` and
  re-export, or use IR-pass acrylic.

## Cut layer vs mark layer

**Nothing but sensor openings is cut** — no fastener holes, no port holes,
no vents, no strap slots. Screws and ports happen on the bench as needed.
Every position is on the **etch layer**: each SVG carries two colors in one
coordinate frame — **black = CUT, red = ETCH**. In XCS: import the SVG,
select the red objects → processing **score** (or engrave), black → cut.
The red marks are:

- floor: GX16 + GX12 ×3 connector rings with labels, DAC footprint + its
  4 screw corners, XIAO footprint (VHB)
- front (interior face): window-panel outline + its 4 screw positions,
  LD2410C footprint centered in the aperture, SENSOR label
- right wall: USB rectangle, AUX and ANT rings, labelled
- back: ear screw positions + a VELCRO label between the two strap slots
- lid: 4 screw positions over the wall top edges
- window: its 4 screw positions + the 16×16 ToF aperture outline (cut it
  through for the 4 ToF rooms; radar rooms just leave it marked)

## Files

- `node-enclosure.scad` — the design; every dimension is a named parameter
- `export.py` — regenerates all SVGs (renders cut + etch, merges the colors)
- `panel-{front,back,left,right,floor,lid}.svg` — wall panels (3 mm ply)
- `panel-window.svg` — the window panel (3 mm acrylic)
- `panel-sheet.svg` — all seven nested on one bed (~246 × 202 mm)
- `sheet.png` / `sheet-etch.png` — the two layers; `preview-assembly.png`,
  `preview-underside.png` — glued-up views

SVGs are true mm scale — import straight into XCS. Cut outlines are exact;
add kerf compensation in XCS if you want piston-fit joints (glue fills a
normal kerf fine).

```bash
python3 export.py    # re-export all panel SVGs after editing the .scad
```

## Assembly

1. Dry-fit first. Corner fingers interlock front/back ↔ left/right; the
   floor's tabs mortise through the wall-bottom notches (flush outside).
2. Glue everything EXCEPT the lid (wood glue for ply joints).
3. Fit connectors (GX nuts inside the floor), boards and sensor at their
   etched marks, window panel over its etched outline; route pigtails.
4. Lid = the service hatch: screw at the etched corner marks into the wall
   top edges. No glue on the lid.
5. Mount: thread a velcro strap through the two vertical back slots and
   wrap it around the scaffold leg at the planned clamp point; the ears
   with their etched screw marks stay as the screw-to-wood fallback.

The wooden 17×22×10 box this replaces is superseded; the mounting
positions, boresight yaw/tilt angles, and mock-bay tuning in
`../wiring-guides/room-node-enclosure-plan.md` still apply unchanged.
