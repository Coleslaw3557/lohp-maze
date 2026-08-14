# Camp extension cord runs (straight runs + the water→kitchen chain)

Four home runs from the Predator 5000 plus one daisy chain: the water cord
branches at the tank into a 20 ft stinger to the kitchen — the communal's
REAR carport (the one facing the water tank, where the coffee maker lives).
Distances measured in the baked sim world frame: drop coordinates from
`sim/web/camp_layout_data.js` (the LotHP-26-v3 bake, reality-oriented) and
`sim/maze_layout.json` (`audio_power.battery` = the 12 V bus behind the hex —
the evening charger cord lands there). Rotated-zone math follows the sim
renderer's convention (THREE rotation.y). Straight lines center to drop; GFCI
is handled separately and is not covered here.

Visual plan (to-scale map + this table): the "Camp power — extension cord
runs" artifact. The runs also render in the sim's camp layer (Camp button,
overhead plan view): colored ground lines with length·gauge labels, drawn
by the cords block at the end of `sim/web/camp_layout.js`.

## Cord schedule

| Run | Drop (world x,z) | Straight | Buy | Branch | Planning load | V-drop @ load |
|---|---|---|---|---|---|---|
| Maze rear (center) — battery bus + charger | 10.04, −0.72 | 98 ft | 100 ft + 25 ft **10/3** | A (TT-30R side) | 15 A sustained | 3.1% |
| Water 500 gal — pump at tank | 13.83, −46.10 | 61 ft | 75 ft **12/3** | C | 10 A | 2.0% |
| Kitchen — rear carport, branch at the tank | 15.12, −40.17 | +20 ft | 25 ft **12/3** stinger | C (chained) | 12 A brews | 3.2% at the pot |
| Trailer + BRS | 24.79, −29.40 | 67 ft | 100 ft **10/3** | B, alone | 12.5 A, hours at a time | 2.1% |
| Black Rock shade — tent campers (rent) | 7.34, −15.24 | 50 ft | 75 ft **12/3** | D | 4 A | 0.8% |
| **Total** | | **296 ft** | **225 ft 10/3 + 175 ft 12/3** | | | |

Buy length = straight + ~6 ft end allowances + reroute margin. V-drop:
V = 2·L·R·I at 120 V copper (12 AWG 1.588 Ω/kft, 10 AWG 0.999 Ω/kft), full
purchased length. Trailer run is 10/3 because 12.5 A for hours sits at ~83%
of a 100 ft 12/3 cord's 15 A rating — no margin for hot-ground derating.

Loads per Tim (2026-08-09): trailer+BRS ~1500 W intermittent but may run
multiple hours (largest single draw); communal = a coffee pot, very
intermittent; water pump intermittent; everything else low-wattage. The maze
is the longest sustained load — all the DMX LED fixtures are AC-powered.

## What the straight lines cross (from the sim geometry)

- **Maze feed**: runs lengthwise through the tent-camper structure — dead
  center through the two excluded middle spots, but crossing the sleeping rows
  and under the ground-reaching shade skirts twice. Detour around either
  tie-down edge is only +8–10 ft; that's why the buy is 100+25 (98 ft straight
  leaves nothing for end drops on a bare 100 ft cord).
- **Water**: straight line passes under the communal's west carport; skirting
  the communal's outside edge is +3 ft (64 ft total). Branch point (12 AWG
  2-fer in a dry box) at the tank.
- **Kitchen stinger**: tank → rear carport is 20 ft of clear ground, and the
  communal's rear 8 ft entrance faces the tank — the cord walks in the door.
  Center-square lights/music (low-wattage) daisy off the kitchen strip.
- **Trailer**: clips the communal north carport corner; around the north side
  is +1 ft.
- **Tent campers**: drop lands at the two excluded middle 10×10 spots — a
  power strip there serves all 10 rented edge spots.

## Generator branches

Predator 5000 (Harbor Freight 70143/71367, per their listing): 5000 W start /
3900 W running on gasoline (3600 W propane), 120 V ≈ 32.5 A total. Panel:
2× 5-20R + 1× TT-30R; Tim's GFCI + breakout rig on the generator provides
connection points for extra runs — plugs aren't the constraint, branch
loading is.

- **Branch A (TT-30R side)**: maze 10/3 — the longest sustained load (DMX LED
  rig, every show hour). (If the pump proves ≥¾ HP, it joins this 30 A
  branch.)
- **Branch B**: trailer+BRS alone — 12.5 A that can run for hours gets its
  own branch, no sharing rules.
- **Branch C — the water chain**: pump + kitchen coffee pot share one cord to
  the tank, then split. Don't brew while the pump is filling (~22 A together
  trips a 20 A breaker, and they now share the same 75 ft leg).
- **Branch D**: tent campers, low-wattage, own breakout.

## Generator amp budget

Daytime the maze is on battery banks (power v5), so trailer/coffee/pump have
the full 32.5 A. Show hours, amps when on: maze 12–15 sustained, trailer
device 12.5 (may run hours), coffee pot 10–12 (~10 min brews), pump 8–10
(short fills), everything else 2–4. **Any two of the big four stack fine;
three at once exceed 32.5 A** — maze + trailer ≈ 27 A sustained, and a brew
or fill on top reaches ~37 A → overload shutdown. Rule: during show hours
with the trailer device on, pause it to brew or fill. Propane capacity is
3600 W (30 A), barely clearing maze + trailer alone — prefer gasoline during
show hours if the trailer device will be on.

## Buy list

- 2× 100 ft + 1× 25 ft 10/3 SJTW (maze pair + trailer; SJEOOW nicer in cold)
- 2× 75 ft + 1× 25 ft 12/3 SJTW (tents; gen→water; tank→kitchen stinger)
- 1× 12 AWG 2-fer at the tank branch point, in a dry box
- Generator-end connections covered by the existing GFCI + breakout rig
- 4× dry boxes/bags — every mid-run connection off the ground, latched (dust/rain)
- tz-24 cable labels on both ends of every cord (per ~/printer/PRINTING.md)

## Verify before buying gauge

1. **Pump nameplate** — spec assumes 120 V ≤½ HP (~10 A run). ≥¾ HP → 10/3 and
   the TT-30 branch.
2. **What the trailer's 1500 W device is** — if a compressor-type AC, confirm
   it starts cleanly through 100 ft of cord on the generator before the burn
   (the 10/3 spec covers the surge, but verify).
3. **Coffee pot stays the kitchen's only heat appliance** — the water chain
   (75 ft + 25 ft stinger, shared with the pump) is sized for exactly that; a
   second 1500 W appliance means giving the kitchen its own home run again.
