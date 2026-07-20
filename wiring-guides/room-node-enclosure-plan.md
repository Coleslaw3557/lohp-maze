# Room node enclosures — mounting + LD2410C tuning plan

> **Box construction superseded 2026-07-20**: the shop-built 17×22×10 cm
> wooden box is replaced by the LASER-CUT universal enclosure in
> `../enclosure/` (one OpenSCAD design → xTool SVGs; finger-jointed glued
> panels, screw-off lid; GX panel connectors for all IO; swappable acrylic
> sensor-window panel). Everything else in this plan — mounting positions,
> boresight yaw/tilt angles, the mock-bay tuning protocol — still applies
> unchanged.

> Audio add-on (per-room speakers driven by the node, 2026-07-18) lives in
> `room-node-audio-plan.md` — DAC inside the box, speaker mounted off-box
> below it, plus a mock-bay baseline addition (radar baseline captured with
> audio playing).
>
> Game add-on (arcade-button room games, 2026-07-20) lives in
> `room-games-plan.md` — changes several rooms' pin fills (Gate goes exactly
> full at 11/11: 6 pads + radar + I2S; DPH 5 buttons; Bike 4; NFM ladder +
> WS2812) and adds 4 standalone battery button pucks in Moop.

Constraints this plan is built around (decided 2026-07-17):

- **No on-site tuning.** Every gate/sensitivity/timeout value is locked before
  departure via the mock-bay protocol below; geometry does the heavy lifting so
  thresholds only trim the edges.
- **One custom wooden enclosure per room** holding ALL of that room's sensing
  and electronics: XIAO ESP32-S3 node (fleet standard since the 2026-07-18
  audio revisit; C3s are bench/spares), the room's ranging sensor (LD2410C
  radar *or* VL53L1X ToF — no room needs both today), power, and screw
  terminals for the wired extras. Buttons and piezo knock pads are the one
  physical exception: they sense the surface a visitor touches, so the
  disc/switch stays at the interaction point and 2-wires back to the box
  (arcade buttons → GPIO, piezo discs → ADC front-ends; Cuddle's box also
  terminates the hex 4-button station on the back faces beside it).
- **Mounts on scaffold frames only** — legs, headers/top rails, doorway tubes.
  Never on the 7'×4' scissor cross braces (flexy, in the way, and they get
  removed/re-pinned during assembly).

## The enclosure

- **Outer size 17 × 22 × 10 cm** (W×H×D, the box the sim renders). With 6 mm
  walls the interior is ~15.8 × 20.8 × 8.8 cm — comfortable for the worst-case
  fill (Porto: node + radar + three piezo ADC front-ends + terminals + a
  20 Ah bank at 15 × 7 × 2.5 cm; depth stack at the window plane stays under
  ~6 cm of the 8.8 available).
- Wood is radar-friendly: mmWave passes plywood with a few dB loss. The **panel
  in front of the radar must be ≤6 mm ply** (or a thinned window recess),
  knot-free, **no metal** in the aperture zone — no staples, mesh, foil tape,
  or screws within ~5 cm of the radar's forward view. Paint is fine
  (non-metallic).
- **The ToF is different: 940 nm IR does NOT pass wood.** ToF boxes get a
  ~8 mm open aperture (or IR-clear window) in the panel, with the VL53L1X
  recessed a couple of cm behind it as dust shielding — plus the generous
  range thresholds from hardware-recommendations.md so dust-shortened
  readings don't false. If a box ever hosts both sensors, keep the ToF module
  (it has metal) ≥5 cm from the radar window; 24 GHz and 940 nm don't
  interfere with each other.
- Layout inside: **radar flush against the inner face of the window panel**,
  aimed out; node PCB and power behind it — their mass adds rear-lobe
  shielding, which matters because the street audience is usually *behind* the
  box.
- Mounting: two hose clamps / pipe straps around the 1.69" frame tube (top +
  bottom of the box), same clamp fleet as the rest of the build. One cable
  gland for power + button/piezo runs.
- Angles are built into the box, not adjusted on-site: cut the mounting cleat
  so the window panel faces the aim direction below (azimuth) and shim the
  cleat for the down-tilt. Label each box with room name before departure.
  The per-room numbers live in `sim/maze_layout.json` (`sensors` entries:
  `yaw_deg`/`tilt_deg`/`fov_deg`/`range_m`, pos = the box) and render in the
  sim as each box's detection wedge + boresight — the cut list:

| Box (room) | Level | Sensor | Azimuth* | Down-tilt | Reach |
|---|---|---|---|---|---|
| Monkey / Temple / NFM / Cop Dodge / Gate | ground | LD2410C | +124° (into the room, at the far back corner) | 10° | gates 0–3, 3.0 m |
| Bike Lock / Deep Playa / Photo Bomb / Porto / Sparkle | upper | LD2410C | −124° (mirrored) | 5° | gates 0–3, 3.0 m |
| Cuddle Cross (hex back corner, 1.5 m) | upper | LD2410C | 0° (across the deck at the front corner) | 0° | gate 4, 3.0 m |
| Entrance (back leg) | ground | VL53L1X | −18° (out through the START arch) | 10° | range gate 2.1 m |
| Exit (back leg) | ground | VL53L1X | +18° (out through the FINISH arch) | 10° | range gate 2.1 m |
| Guy Line Climb (entry-side front leg) | ground | VL53L1X | −174° (diagonally across the entry arch) | 0° | 1.05 m (far door tube = baseline) |
| Vertical Moop March (entry-side front leg) | upper | VL53L1X | +174° (mirrored) | 0° | 1.05 m |

\* azimuth 0° = straight out toward the street (+z), positive toward east —
same convention as `yaw_deg` in the sim layout.

## Standard wing bay (10 rooms)

Bay: 7 ft wide × 5 ft deep × 6'4" tall (2.13 × 1.52 × 1.93 m). Visitors enter
through a side-frame walk-thru arch; the street face is open (audience!); the
back plane is canvas with backstage behind it.

**Mount: the front leg of the ENTRY-side frame, radar centerline at 1.55 m,
aimed at the diagonally-opposite BACK corner (≈35° into the room off the frame
plane), 10° down-tilt (ground floor) / 5° (upper floor).**

- Ground-floor bays are all entered from their **west** door, upper bays from
  their **east** door — so it's one bracket design, mirrored per level.
- Why this spot wins: the visitor appears at gate 0–1 the instant they step
  through the entry arch (fast trigger); the boresight diagonal (2.62 m) ends
  at the back canvas, so **overshoot lands in backstage** — the only
  low-traffic direction available; and the **street audience sits in the
  radar's rear hemisphere**, rejected by antenna pattern + box shielding
  rather than by tuning.
- Keep the aperture clear of the leg's brace studs/scissor ends; the braces
  are static clutter at worst (calibrated out), but don't let a tube cross
  directly in front of the window.

```
        street (audience)                     z=2.02
   ─────────╥───────────────────────╥─────
            ║ [BOX] ↘                ║          BOX on entry-side front leg,
     entry  ║    ╲   boresight       ║  exit    aimed at far back corner
     arch → ║     ╲  2.62 m diag     ║  arch →
            ║      ╲                 ║
   ═════════╩═══════╲════════════════╩═════  z=0.5
        back canvas — backstage behind (overshoot zone)
```

Gate profile (0.75 m gates; radar at the corner, so distances are diagonal):

| Gates | Zone | Setting |
|---|---|---|
| 0–1 (0–1.5 m) | entry arch + near half of room | full sensitivity (move + still) |
| 2 (1.5–2.25 m) | far half of room | full move, moderate still |
| 3 (2.25–3.0 m) | far corner + first sliver of backstage | **raised threshold**, move only |
| 4–8 | backstage / neighbor bleed | **off** (max gate = 3) |

`still` max gate = 2 for entry-triggered rooms (still-detection deep in the
gate-3 zone is where backstage crew would false); dwell rooms keep still to 3.
Absence timeout: 5 s standard; 60 s on dwell rooms (No Friends Monday).
Upper-floor variant: 5° tilt (keeps the lobe off the plywood deck — radar sees
through wood to the room below) and still thresholds one notch higher on
gates 2–3.

## Specials

| Room | Mount | Notes |
|---|---|---|
| **Cuddle Cross** | Back-corner frame pair (the skinned faces' shared corner), 1.5 m above deck, aimed at the front corner across the deck | Max gate 4 (3.0 m = front corner; street crowd beyond and below). The 20 ft center mast sits dead-center at gate 2 — constant static reflector, so gate-2 still threshold gets set *above* its measured energy in the mock pass. Timeout 60 s+: sustained still presence = cuddling, the effect hook this room actually wants. |
| **Entrance / Exit (hex)** | Node box on the back leg, **VL53L1X inside the box** firing out through the START/FINISH arch (azimuth ∓18°, ~1.9 m to the arch, range gate 2.1 m) | Radar is wrong here: the Exit\|Entrance divider is radar-transparent, the two halves would cross-trigger. One-sided range-gating from the box needs no cross-doorway alignment; empty = no return past the gate, street crowd beyond the arch sits past the 2.1 m threshold. The 27° cone is ~0.9 m wide at the arch — full coverage of the 0.8 m opening. Exit's cone also catches arrival from No Friends Monday, preserving the old entry-trigger timing. |
| **Guy Line Climb / Vertical Moop March** | Standard entry-leg box, **VL53L1X inside the box** firing diagonally across the shaft entry arch (azimuth ∓174°, i.e. nearly parallel to the frame plane); the far doorway tube at ~1.0 m is the empty-range baseline | Full-height shafts with ropes/hanging moop that move in wind — the worst radar environment in the maze. The box sits 10 cm inside the entry plane, so the cone hugs the arch like the old cross-doorway beam and keeps today's trigger semantics with nothing to align. Radar optional later, top-down from the upper header, if a "someone is mid-climb" state earns its keep. |
| **Monkey Room** | Standard bay box + 2-wire run to the puzzle microswitch (GPIO3/GND, contract already in `packages/button_gpio_c3.example.yaml`) | Radar entry gets enabled only when a doorway effect is designed (placeholder was removed); the node + button ship regardless. |
| **Photo Bomb Room** | Standard bay box + 2-wire run to the shutter arcade button on the back scaffold | Camera + flash stay on the server side (rack is on the adjacent shared frame). |

## Sensor allocation

Radar in the 10 wing bays + Cuddle Cross = 11 positions, but Temple / Monkey /
VMM doorway effects are currently unwired (placeholders removed 2026-07-17), so
**10 LD2410C covers every live trigger** with the unwired rooms joining as
effects get designed. ToF: Entrance, Exit, Guy Line, VMM = 4 of the 6 VL53L1X,
2 spare.

## Pre-departure lock-in protocol (replaces on-site tuning)

Because thresholds can't be trimmed at the maze, they get measured at home and
locked. LD2410C units vary — **run the pass per physical unit, in its own
enclosure**, then label box + room + node together.

1. Tape a 7×5 ft bay on the floor; rig one frame section (or a 1.55 m stand)
   with the enclosure mounted at the real angles. Hang a canvas scrap at the
   back line, stand a helper at the real street line.
2. Node runs engineering mode; the dev-box harness records per-gate energy for
   the scripted positions: empty room (2 min baseline, fans on), person at
   entry arch, room center, far corner, "street" at 0.3/1.0 m beyond the face,
   "backstage" behind the canvas, "neighbor" one bay over.
3. Set each gate threshold midway (in log-energy) between the strongest
   must-ignore and the weakest must-detect for that gate. Bake the numbers
   into that room's `rooms/*.yaml` substitutions; flash; **re-run the position
   script as a pass/fail check** on the flashed unit.
4. Values live in the radar's own NVM + the YAML is the source of truth.
   Break-glass: every threshold is an ESPHome `number` entity, adjustable from
   the server laptop over the maze WiFi without reflashing — for emergencies,
   not the plan.
5. Wind rehearsal: point a box fan at the canvas during the empty-baseline
   capture — playa wind on fabric is the #1 expected false-positive source,
   and it must be inside the baseline before thresholds are set.
