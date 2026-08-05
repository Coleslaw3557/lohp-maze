# Camp sign: PSU terminal hood (2026-08-02, rev D — 4× SAE board, inlet AC, in-hood fuses)

> Companion docs: `camp-sign-plan.md` (the sign this powers — zone map, power
> tree, strip budget), `../enclosure/psu-hood.scad` →
> `../enclosure/psu-hood.svg` (full kit, 6mm) + `../enclosure/psu-hood-board.svg`
> (the DC connector board ALONE — the iterating part; same 6mm stock); previews
> `preview-assembly-psu-hood.png`, `sheet-psu-hood.png`,
> `sheet-etch-psu-hood.png`. Status: **cut-ready except the gates at the
> bottom** (PSU body + both panel devices are now calipered).

## What it is

The ABI PA-WTHR-A (12V 500W 42A rainproof, CL-500W class; body **calipered
2026-08-02: 119.05 × 54.03** — the listing's 127 × 58.4 was ~8mm oversize)
is already a metal outdoor-rated case with a built-in fan — it does **not**
go inside a box. The hood is a five-sided **6mm-ply sleeve over the terminal
end only**: ~65mm riding the body, ~112mm of connection chamber past the end
face. The recessed 9-position screw strip (AC L/N/ground + 3× V+/V− pairs +
the V-adjust pot) lands in the chamber, where the four DC circuits fuse at a
**blade-fuse block on the chamber floor** and leave through the connector
board — the sign plugs together in the field, and everything (terminals,
pot, fuses) services under the drop-in lid.

Mounted per the plan: PSU **vertical, terminal end DOWN** — hood at the
bottom, fan end + louver in open pillar air. The PSU's terminal-end mounting
ear lies flat on the hood floor inside the chamber; **bolts pass through the
ear's slots + the floor's matching cut slots + the pillar plank in one go**.
The fan-end ear lands on the cut ply shim (same sheet). A velcro one-wrap
around the tube at the mouth holds lid + body (vertical drop-in lid —
gravity doesn't).

## The DC connector board (the part expected to iterate)

The sign connectors do NOT mount in the end wall: the end wall is a fixed
**main faceplate** with **one 104 × 45 window** (2026-08-02, Tim — future
boards may carry entirely different ports; the faceplate passes whatever
the next board mounts and never re-burns) plus a **pre-cut M3 datum grid**
(4 corner holes — a deliberate exception to the no-fastener-holes house
rule: iteration needs a repeatable datum, same logic as the projector
shroud's drill grids; the window is sized to the grid, ≥4.3mm of wood
around each hole). A separate **130 × 64 board from the same 6mm stock**
carries the connectors and screws onto the faceplate from outside (M3×16
+ nylocs). To iterate the layout, edit `panel_board()` / `board_etch()`
and **re-cut `psu-hood-board.svg` alone** — the grid re-registers every
revision.

**One connector family (Tim's parts, ON HAND, calipered)**: **all four DC
circuits** use the same **SAE quick-connect flush-mount harness with
integrated 10AWG pigtails** — body through the wood 22.10 × 13.37, outer
flange 50 × 21.62 with two screw holes (**no pre-cut screw holes** — the
flange is its own jig; with the big window behind, the flange screws bite
**the board alone**, which is why the board is 6mm: wood screws grip, or
use M3 machine screws + nuts if any port ever feels loose). 50-wide
flanges don't fit the 137mm face side by side, so they mount **rotated
90° — a row of FOUR vertical dominoes** at 28mm pitch (28, not 30: at 30
the outer flanges ride under the M3 heads), etched **LEGENDS @L 10A ·
LOGO 5A · TRUNK 20A · BOX 2A**. Each body passes through a snug rect in
the board and on through the open window (outer bodies ±49 vs the
window's ±52). **BOX** (rev D — was a BTF pass-through in the left wall):
the controller-box feed rides the board like everything else; **Tim
converts SAE → the box's existing BTF pigtail at the controller-box end
of that cable**. The left wall now carries nothing but its vent slats.

**Wire**: the 10AWG harness pigtails end the SP21 era's gauge compromise —
the **trunk keeps the plan's original 10AWG end-to-end** (shop stock);
LEGENDS (14AWG) and LOGO (18AWG) runs splice onto their harness tails at
the bench (adhesive shrink).

**SAE polarity (minefield)**: wire hood V+ to each port's **recessed**
terminal so nothing hot is exposed when unmated, and verify every
harness's molded polarity BEFORE landing tails — SAE conventions vary by
vendor.

## Ports (all openings CUT, labels on the score layer)

| Where | Cut | Outside | Inside |
|---|---|---|---|
| end faceplate | **one 104 × 45 window** + 4× Ø3.4 M3 grid ("DC BOARD") | the connector board, screwed on | everything the board mounts passes through to the chamber |
| the board (6mm) | 4× 13.97 × 22.7 rects @ 28 pitch + the matching M3 grid | the four SAE faces w/ their flanges + labels (LEGENDS · LOGO · TRUNK · BOX) | 10AWG pigtails → fuse block outputs (+) and PSU V− screws (−) |
| right wall, near the front | 47.5 × 28 rectangle (`ac_style="snapin"` — calipered body 46.85 × 27.33) | **the AC INPUT**: the generator cord's female end plugs straight onto the face; outer lip lands on the wall's outside face, lip screws = part-as-jig | inlet terminals → 16AWG L/N/ground tails → PSU AC screws |
| both side walls, behind the ports | 5× 42×5 vent slats each | — | chamber ventilation (fuse block, tails); with the ~3mm body gap + the **open mouth** they also breathe the PSU's covered terminal-end slots — **never foam/seal the mouth** |

Pigtail spec is the sign-box rule verbatim: ~10cm slack tail outside, mate
on slack hand-to-hand, inside zip-tie takes the tug. **Lid**: SOLID (vents
live in the side walls; the finger pull died 08-02 too — lift the lid at
the free mouth edge), warning etch (CAMP SIGN PSU · 120V + 12V INSIDE ·
UNPLUG CORD — FUSES INSIDE). **No cord gland
anywhere** — the snap-in inlet IS the AC entry (deleted 2026-08-02).

## Fusing — the block INSIDE the hood chamber

A **blade-fuse block on the chamber floor** (etched zone 88×46 — gate the
real block's footprint): PSU V+ screws → two short 10AWG jumpers → block
feed; each output → its connector (+). PSU V− screws → connector (−)
returns direct. Same rule as ever — **fuses protect the wire**:

| Circuit | Wire | Fuse |
|---|---|---|
| "Legends of the" @ 'L' | 14AWG | 10A |
| Logo field | 18AWG | 5A |
| Trunk → right block | 10AWG | 20A |
| Controller box 12V | 18AWG | 2A |

This IS the plan's LEFT block, relocated into the hood; the 35A main is
dropped (no feeder left to protect; the PSU has internal short/overcurrent
protection). The **right block at the right pillar is unchanged**. Spare
fuses ride taped inside the lid.

## AC input (snap-in inlet on the right wall — no gland)

The generator's outdoor cord plugs **straight onto the snap-in face**;
its terminals tail 16AWG L/N/ground to the PSU's AC screws, and pulling
the cord off the face IS the plan's "accessible disconnect." Ground: cord
green → inlet ground terminal → PSU FG screw (FG bonds the chassis). Plan
stance unchanged: floating-neutral inverter, **no GFCI in the chain**.
**Bench sanity check before cutting tails**: the face must present
BLADES (male) for the cord's female end to mate — if it shows slots it's
an outlet, not an inlet, and the AC entry needs a rethink. AC dresses
along the right wall, DC to the end board — the floor etch says so.

## Caliper gates — remaining

- [ ] `t` — the actual 6mm sheet ("6mm" ply runs 5.6–6.2; every joint
      tracks `t`; set the measured value and re-export)
- [x] `psu_w` / `psu_t` — **RESOLVED 2026-08-02: 119.05 × 54.03**
- [ ] `overlap` (65) — dry-slide: no pinch
- [ ] `ear_reach` / `ear_cs` / `ear_slot_*` — the terminal-end ear's real
      slots (photo estimate: 3 slots, outer pair ±47)
- [x] `ac_*` — **RESOLVED 2026-08-02**: snap-in single, body 46.85 × 27.33
      (cutout 47.5 × 28); blade-vs-slot check at the bench
- [x] `sae_*` — **RESOLVED 2026-08-02**: body 22.10 × 13.37, flange
      50 × 21.62
- [ ] `fuse_zone_*` — the purchased block's footprint (Nilight 6-way ≈
      105mm long may crowd the inlet's rear body; a ~85mm 4-way drops in
      clean)

## BOM — almost nothing left to buy

| Part | Qty | ~Price | Why |
|---|---|---|---|
| SAE quick-connect flush-mount harness, 10AWG | **4** (+1 spare if the pack allows — confirm the pack covers 4) | **ON HAND** (Tim, calipered 08-02) | all four DC circuits |
| Snap-in 110V inlet | 1 | **ON HAND** | AC entry |
| Blade fuse block w/ cover: Nilight 6-way + negative bus (`dp/B089T47R2L`) or any ~85mm 4-way if the 6-way crowds the chamber | 1 | ~$12 | the four circuit fuses |
| BTF 2-pin 18AWG pigtail pairs (`dp/B01LCV97AY`) | 1 pack | $12.99 | the **controller-box end** of the BOX cable (SAE → BTF conversion, Tim) + spares |
| ATC blade fuses 2/5/10/20A | — | shop stock / with the block | |

≈ **$25 new spend** (the rev-A SP21 order — `dp/B0D1BGMGWS` etc. — is
**cancelled, do not buy**; the M20 glands and 12AWG-wire line items died
with the gland and the SP21 cups). Shop stock: 10/14/18AWG wire, 16AWG
for the AC tails, ring/fork crimps, adhesive heat shrink, velcro one-wrap
+ dabs, M3×16 + nylocs, M4 ear bolts/washers, 6mm ply (hood AND board —
one stock).

Connector history, for the record: barrel plugs rejected (~5A class, of
the four circuits only the 2A box feed qualifies); rev A standardized on
SP21 2-pin circulars (stock-checked live on Amazon); rev B superseded both
with Tim's on-hand SAE flush-mounts — one family, 10AWG pigtails,
nothing to buy.

## Build order

1. Remaining gates (above) → flip params → `python3
   ../enclosure/export-psu-hood.py` → eyeball the three previews.
2. Cut `psu-hood.svg` + `psu-hood-board.svg` (both 6mm); glue floor
   + end + sides (lid loose). Dry slide-fit over the terminal end BEFORE
   wiring.
3. Bench-load the board: SAE ports screwed through the board's rects (their
   screws stop in the board for now), polarity-check each harness, then
   seat the loaded board's bodies through the faceplate rects and drive the
   4 M3s + the flange screws home (flange screws bite board → faceplate).
4. Mount the snap-in inlet in the right wall; screw the fuse block to the
   floor zone (wood screws through its base holes — the block is its own
   jig).
5. Land tails: V+ ×2 jumpers → block feed; block outputs → the four SAE
   (+) pigtails; V− → (−) returns; inlet L/N/⏚ → PSU AC screws. Label
   every tail at the strip.
6. Bolt PSU + hood to the plank through the ear slots; shim the fan ear;
   strap the mouth.
7. Full-white soak per the plan §Build (fuses in, measure 12V at far
   pixels) — the hood adds no software; the sign's bench flow applies.

## Board iteration log

- rev A (2026-08-02): 3× SP21 Ø21.5 @ 38 pitch, one row, 6× M3 —
  superseded before cutting.
- rev B (2026-08-02): 3× SAE flush-mount rects 13.97 × 22.7 (vertical) @
  30 pitch, 4× M3 corners, board 130 × 64.
- rev C (2026-08-02, hood-side): faceplate's per-connector rects → **one
  104 × 45 window** (future boards free to differ) → board stock moves to
  6mm (flange screws bite the board alone now). Board geometry unchanged.
- rev D (2026-08-02): **BOX joins the board as SAE #4** — four dominoes,
  pitch 30 → 28 (M3-head clearance at the ends); the left wall's BTF Ø8
  deleted (wall is vents-only); SAE → BTF conversion at the
  controller-box end is Tim's cable. (Add a line per re-cut.)
