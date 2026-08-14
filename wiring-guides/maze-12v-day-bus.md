# Maze 12 V day-power bus — cut list & placement (build sheet)

2026-08-09, rev (c) — HIGH BUS + FLOOR CRATE. Hardware IN HAND: 12 V 100 Ah
LiFePO4 (lithium iron phosphate) Group 31 battery, AUTOUTLET 14.6 V/20 A
charger (Anderson SB50 output), RED WOLF 15 A manual-reset breaker (#10-32
studs), 70 ft of 14/2 tinned marine duplex, Recoil BBS43-P bus-bar pair
(4× M5 studs + 3 screw terminals each), Posi-Tap 12-18 ga ×15, PRECIHW 5/16"
rings, 12/24 V→5 V 8 A four-port USB hubs (~35 in leads, clips get cut off),
Teltonika RUT140 (its network config lives in `maze-network.md` — this sheet
is power only). Geometry from `sim/maze_layout.json` (`audio_power`); the
sim draws this exact layer behind the maze.

## Rev (c) changes (Tim 2026-08-09)

- **Hubs must be equidistant to the two boxes they serve** → hubs AND the bus
  mount at **8 ft 3 in above ground (= 22 in above the deck line)** — the
  height where ground boxes (1.55 m) and upper boxes (3.48 m) are the same
  routed USB distance (~11 ft 2 in). Every wing room = one 12 ft cable SKU.
- **No rack.** Service cluster ON THE FLOOR at the hex SW corner, directly
  under the riser: a vented ply **crate** (battery + charger + breaker + both
  bus bars), the **Pi enclosure**, and the **RUT140 enclosure** beside it.
- **One riser** climbs from the bars to a bench-soldered **tee** at bus
  height; the WEST and EAST runs split there.
- **Zero ATC fuses.** The riser is the trunk — the 15 A breaker covers
  everything. (The old riser fuse existed for a branch that no longer is one.)

## Cut list (4 pieces, ≈66 ft 5 in of the 70 ft spool — 3 ft 7 in spare)

| Piece | Cut | Runs |
|---|---|---|
| RISER | **8 ft 3 in** | crate bars → straight up the SW-corner frame → tee at 8 ft 3 in height |
| WEST | **26 ft 9 in** | tee → straight along the back wall → ends at S1 (Vertical Moop) |
| EAST | **29 ft 9 in** | tee → wraps the hex back faces → ends at S8 (Guy Line) |
| Battery jumper | **1 ft 8 in** | inside the crate: battery(+) →~6 in→ breaker IN; breaker OUT →~6 in→ (+) bar; black battery(−) → (−) bar |

## Tape marks (measure from the TEE end of each run, after a 6 in tail)

Marks include a 6 in service loop ahead of each tap — add nothing else.

**WEST:**

| Mark | Station |
|---|---|
| **4 ft 0 in** | S4 — No Friends + Photo Bomb |
| **11 ft 5½ in** | S3 — Temple + Deep Playa |
| **18 ft 11½ in** | S2 — Monkey + Bike Lock |
| cable end | S1 — Vertical Moop (hub leads bench-soldered to the end) |

**EAST:**

| Mark | Station |
|---|---|
| **5 ft 6 in** | S5 — hex S corner (Entrance/Exit/Cuddle nodes + Cuddle Pebble) |
| **10 ft 6 in** | bend flag only — hex SE corner, no tap |
| **14 ft 5½ in** | S6 — Cop Dodge + Porto |
| **21 ft 11½ in** | S7 — Gate + Sparkle Pony |
| cable end | S8 — Guy Line (hub leads bench-soldered to the end) |

Steel-truth: wing hubs are 7 ft 0 in apart at bay-pair centers; first west hub
is 3 ft 6 in from the tee; east wraps 5 ft 0 in per hex face.

## Connections

- **Posi-Taps (12 used, 3 spare):** S2–S4, S6–S7 + S5 — 2 in jacket window at
  the mark, tap red + black, hub's own leads (clips off, folded double) into
  the branch ends. Bus never cut; branch cap unscrews at teardown; bodies stay
  on the harness. Grease + tape every window.
- **Bench solder:** the riser-top tee (riser + west + east, red 3-way + black
  3-way) and the two end hubs (S1, S8) onto the cable ends.
- **Crate:** battery(+) → breaker → (+) bar; battery(−) → (−) bar. #10 rings
  on the M5 studs — the 5/16" PRECIHW rings fit only the battery studs;
  RED WOLF's included lugs are 6 AWG, wrong. Only the riser leaves the crate. S9 hub sits ON the crate, leads to the bars. RUT140
  red/black to the bars (salvage its 9 V adapter plug; chassis pin
  unconnected per the Teltonika wiki; 9–30 V DC input). Charger tail: cut the
  SB50, 5/16" rings, battery studs.
- **Crate must be vented** — the charger has a fan; drill/slot both ends.

## Fuse schedule

15 A breaker in the crate = the only protection and the master switch. Peak
computed bus load ~10.3 A; a dead short anywhere pulls 50–70 A and trips it.
Accepted (Tim): any fault drops the whole bus until found by walking the
hubs. Chafe-wrap hub leads at steel crossings. No ATC holders used — holder
10-pack + fuse kit to the parts bin.

## USB drops (5 V) — two SKUs + one short

| Load | Routed | Cable |
|---|---|---|
| ALL wing rooms (node + Pebble), Entrance/Exit nodes from S5, Entrance Pebble from S9 | ~11 ft | **12 ft** |
| VMM, Guy Line, Cuddle node + Pebble (from S5 at the corner), Exit Pebble (from S9) | 3–5 ft | **6 ft** |
| Pi from S9 | 2 ft | short + thick — fussiest 5 V load |

## Electrical sanity

Typical show load ~49 W → 46 % of the pack per 12 h day → ~2 h evening
generator to refill at 20 A. Worst-case peak drop (shared riser + far west
hub) 0.65 V → hub still sees >12 V; hubs take 8–35 V, RUT140 9–30 V; 14.6 V
while charging is fine for everything.

## Bench order

1. Cut the 4 pieces; tape-flag every mark (cumulative, double-checked).
2. Posi-Taps at the 12 marks; grease + tape.
3. Solder: tee onto the riser top (west + east), S1/S8 hubs onto their ends,
   heat-shrink.
4. Rings: 5/16" battery + charger tail; #10 breaker + bar studs.
5. Label the tee ends (`WEST — tee` / `EAST — tee`) and the riser bottom
   (`BARS`), tz-24 per `~/printer/PRINTING.md`.
6. On site: crate down at the SW corner, riser up the frame, tee at 8 ft 3 in,
   runs out along the back at that height, hubs clamped at their taps,
   breaker on.

## Still needed / confirm

- #10 rings (breaker + bar studs, 14–16 AWG barrel).
- 12 ft power-rated USB cables (~23) + 6 ft (~8) per the table.
- Vent the crate; battery stud size check before crimping (5/16" assumes M8).
- Confirm Entrance/Exit get Pebbles (open item in room-node-audio-plan.md).
