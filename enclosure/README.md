# Room-node enclosure (laser-cut, one design for every room)

`node-enclosure.scad` generates the single enclosure used by all 15 room
nodes as **laser-cut panels for the xTool**: six finger-jointed pieces that
glue together, plus the acrylic sensor-window panel. Outer 110 × 78 × 40 mm
(interior 104 × 72 × 34) — as small as reasonable around the node build.

| Inside | Mounted how |
|---|---|
| XIAO ESP32-S3 | VHB tape to the floor, USB-C at the right-wall slot |
| PCM5102A DAC | M2 screws through the floor holes (**verify hole spacing against a real board before cutting 15** — `dac_hx/dac_hy` params) |
| LD2410C / VL53L1X / Cuddle's 2410+2450 | zip-tied through the front-panel holes, boresight out the window |

## IO — everything leaves through a connector

| Where | What | Carries |
|---|---|---|
| floor (faces DOWN mounted — dust/rain smart) | 1× GX16-8 | up to 6 arcade buttons + common (Gate 6, DPH 5, hex 4, Bike 4, NFM ladder) |
| floor | 3× GX12-2 | Porto piezos ×3, single buttons, spares |
| right wall | USB-C slot | XIAO power |
| right wall | 6.5 mm holes ×2 | 3.5 mm line-out → Pebble; antenna pigtail |

Unused holes take a blank GX plug — that's what lets one design serve every room.

## Sensor window

56 × 24 aperture in the front panel; the **64 × 32 × 3 mm acrylic panel**
(`panel-window.svg`) screws over it with M2.5 into the four pilot holes.

- **Radar rooms** (LD2410C / LD2450): solid plain acrylic — 24 GHz passes
  through. Nothing metallic on or behind it.
- **ToF rooms** (Entrance / Exit / Guy Line / VMM): 940 nm does NOT pass
  plain acrylic — uncomment the marked aperture in `panel_window()` and
  re-export, or use IR-pass acrylic.

## Files

- `node-enclosure.scad` — the design; every dimension is a named parameter
- `panel-{front,back,left,right,floor,lid}.svg` — wall cuts (3 mm ply)
- `panel-window.svg` — the window panel (3 mm acrylic)
- `panel-sheet.svg` — all seven nested on one bed (~260 × 190 mm)
- `sheet.png`, `preview-assembly.png`, `preview-underside.png` — renders

SVGs export at true mm scale — import straight into xTool XCS. Outlines are
exact; add kerf compensation in XCS if you want piston-fit joints (glue
fills a normal kerf fine).

Re-export after edits:

```bash
for p in front back left right floor lid window sheet; do
  openscad -D "part=\"$p\"" -o panel-$p.svg node-enclosure.scad
done
xvfb-run -a openscad -D 'part="3d"' --autocenter --viewall --imgsize=1100,850 -o preview-assembly.png node-enclosure.scad
```

## Assembly

1. Dry-fit first. Corner fingers interlock front/back ↔ left/right; the
   floor's tabs mortise through the wall-bottom notches (flush outside).
2. Glue everything EXCEPT the lid (wood glue for ply joints).
3. Drop M3 nuts into the four T-slot pockets on the front/back top edges.
4. Fit connectors (GX nuts inside the floor), boards, sensor; window panel
   screws on (M2.5); route pigtails.
5. Lid = the service hatch: 4× M3×12 into the T-slot nuts. No glue.
6. Mount: back ears (5 mm holes) screw flat to wood/plate, or SAE#24 hose
   clamps through the back strap slots hug a scaffold tube — the existing
   mounting standard.

Hardware per box: 4× M3×12 + nuts (lid), 4× M2.5 self-tap (window), 4× M2
(DAC), zips, VHB. The wooden 17×22×10 box this replaces is superseded; the
mounting positions, boresight yaw/tilt angles, and mock-bay tuning in
`../wiring-guides/room-node-enclosure-plan.md` still apply unchanged.
