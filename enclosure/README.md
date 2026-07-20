# Room-node enclosure (one design, every room)

`node-enclosure.scad` is the single parametric enclosure for all 15 room
nodes. Exterior ~109 × 77 × 39 mm plus mounting tabs — sized to be as small
as reasonable around the standard node build:

| Inside the box | Mount |
|---|---|
| XIAO ESP32-S3 | friction cradle, USB-C aligned to the right-wall slot |
| PCM5102A DAC | 4 posts (M2 self-tap), 3.5 mm jack aligned to the right-wall hole |
| LD2410C radar and/or LD2450 (Cuddle) and/or VL53L1X ToF | shelf behind the window, zip-tie slots |

## IO — everything leaves through a connector

| Where | Connector | Carries |
|---|---|---|
| floor (faces down — dust/rain smart) | 1× GX16-8 | up to 6 arcade buttons + common (Gate 6, DPH 5, hex station 4, Bike 4) |
| floor | 3× GX12-2 | Porto piezos ×3, single buttons, spares |
| right wall | USB-C slot | XIAO power |
| right wall | 6.5 mm hole | DAC 3.5 mm line-out → Creative Pebble |
| right wall | 6.5 mm hole | XIAO external antenna pigtail |

Unused holes get a blank GX plug or a printed cap — that's what makes one
design serve every room.

## Sensor window

The front face has a 56 × 24 mm aperture with a recessed ledge that seats a
**64 × 32 mm, 3 mm laser-cut panel** (M2.5 screws into the 4 pilot holes;
outline exports from this same file):

- **Radar rooms (LD2410C / LD2450):** plain 3 mm acrylic — 24 GHz passes
  right through it. No paint, nothing metallic on or behind the panel.
- **ToF rooms (Entrance / Exit / Guy Line / VMM):** 940 nm does NOT pass
  plain acrylic or ply — cut the marked aperture through the panel (uncomment
  the `OPTIONAL ToF aperture` line in `panel_2d()`), or use IR-pass acrylic.
- **Cuddle:** LD2410C + LD2450 sit side by side behind the one window.

## Files

- `node-enclosure.scad` — the design; every dimension is a named parameter
- `box.stl`, `lid.stl` — print-ready exports
- `window-panel.dxf` — the laser-cut panel outline
- `box.png`, `lid.png`, `window-panel.png` — per-part renders
- `preview-inside.png`, `preview-assembly.png` — overview renders

Re-export after edits (PNG needs a display; headless use `xvfb-run -a openscad …`):

```bash
openscad -D 'part="box"'   -o box.stl          node-enclosure.scad
openscad -D 'part="lid"'   -o lid.stl          node-enclosure.scad
openscad -D 'part="panel"' -o window-panel.dxf node-enclosure.scad
openscad -D 'part="box"'   --autocenter --viewall --imgsize=1200,900 -o box.png node-enclosure.scad
```

## Print & assembly

- PETG or ASA (playa heat — PLA sags in an August car, let alone on-site),
  0.2 mm layers, 3–4 perimeters, no supports (both parts print flat as
  modeled: box open-face up, lid top-down).
- Assembly: DAC on its posts → XIAO into the cradle (dab of VHB under it) →
  sensor zip-tied to the shelf, boresight out the window → GX connectors
  nutted into the floor holes, pigtails to the boards → panel screwed into
  the recess → lid on (4× M3 into the corner posts).
- Mounting: two vertical back tabs (5 mm holes) screw it flat to wood/plate,
  or run an SAE#24 hose clamp through the two back-wall strap slots to hug a
  scaffold tube — same mounting standard as before.

The wooden 17×22×10 cm box construction this replaces is superseded; the
per-room mounting positions, boresight yaw/tilt angles, and the mock-bay
tuning protocol in `../wiring-guides/room-node-enclosure-plan.md` still
apply unchanged — this is the same box contract in a smaller printed shell.
