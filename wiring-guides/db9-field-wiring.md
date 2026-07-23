# DB9 field wiring standard (2026-07-21; DMX-jack rev 2026-07-22)

The traveling-maze field IO: every node box carries **one DB9 (port A) and
one XLR3 DMX jack on the left wall** (`enclosure/node-enclosure.scad`).
Port A's window is pre-cut in every box (07-22 enclosure rev2; populated
in the 7 wired rooms, blanked with tape/cover elsewhere) — the button-pod
cable. The
XLR is **cut in every box — it's the room's DMX out** (`dmx-over-wifi.md`):
the node's MAX485 drives the room's fixtures through it on a standard DMX
cable. Rapid setup = one premade DB9 cable per wired room + one DMX cable,
done.

> Rev 2026-07-22: the DMX out spent one day on paper as a second DB9
> ("port B") + a DB9→XLR adapter, justified by a no-solder-anywhere rule
> and reserved expansion pins. Both justifications were wrong — the rule
> was always **no soldering in the field** (the bench solders freely), and
> the expansion reservation wasn't worth a nonstandard connector. A DMX
> port is a DMX port.

**Field rule — nothing is crimped or soldered on playa.** Solder belongs
to the bench (the XLR jack's three cups, board headers, the sign);
everything that travels lands under screws or plugs in:

- **Box end (port A):** DB9 screw-terminal breakout (female, ANMBEST),
  run as the **bare PCB screwed to the box floor** in its etched zone
  (plastic case off — it has no floor-mount provision; fine inside a
  closed box). The D-sub face pokes through the wall window and the
  screwlock posts pass through Ø6 holes to stand ~3.4 mm proud outside
  (calipered 2026-07-22: posts protrude 6.3 mm past the face; ply is 2.9;
  connector center sits 12.2 mm up the wall = 2.9 floor + 3.89 PCB→shell
  bottom + half shell). The cable's thumbscrews lock into the posts; the
  floor screws, not the wall, hold the part. Node wires land under screws
  on the PCB (9 pins + a shell-GND terminal).
- **Cable:** premade **straight-through M-F DB9 serial extension** —
  ⚠ NOT a null-modem cable (those swap pins internally and scramble the
  map). Any length, ~$5.
- **Pod end:** DB9 screw-terminal breakout (male) inside the button
  cluster. Button/piezo wires land under screws.
- Dust caps/covers both sides at teardown; a spare cable in the kit is
  the field fix for anything flaky.

## Port A universal pinout — EVERY box, used or not

| DB9 pin | Carries |
|---|---|
| 1 | 5V (button LEDs / lamps) |
| 2 | GND (switch common, LED −, piezo −) |
| 3–9 | signals 1–7, in room order |

Signal n lands on XIAO **D(n−1)** unless the room table says otherwise.
Buttons are closures to GND (input-pullup); LEDs wire pin 1→LED+,
pin 2→LED− (always lit, no GPIO — per the games plan).

## The DMX jack — every box

**XLR3 female panel jack** (D-size footprint — the enclosure cuts the
Ø24 barrel hole ONLY, confirmed against the received part's Ø23.55
insert 2026-07-23; no pre-cut screw holes. The jack is its own jig:
two short wood screws through its flange holes — jacks ship WITHOUT
screws), wired to the MAX485 at the bench: solder pigtails to the three
cups, heat-shrink, pins 2/3 land under the module's A/B screw terminal —
done once per box.

| XLR pin | Carries |
|---|---|
| 1 | GND |
| 2 | Data− (MAX485 B) |
| 3 | Data+ (MAX485 A) |

Female on the box per the DMX512 transmitter convention, so the room run
is one ordinary **XLR M-F cable used whole** — male end into the box,
female end into the first fixture's DMX IN, 120Ω terminator plug on the
chain's last OUT. Full build + failure table: `dmx-over-wifi.md`.
Bench-soldered polarity beats the old adapter's field screw terminals:
swapped D+/D− was the classic "fixture flickers randomly" failure, and
now it can't happen in the field.

## Per-room map (port A)

| Room | Pin 3 | 4 | 5 | 6 | 7 | 8 | 9 |
|---|---|---|---|---|---|---|---|
| Gate | pad 1 | pad 2 | pad 3 | pad 4 | pad 5 | pad 6 | — |
| Deep Playa Handshake | btn 1 | btn 2 | btn 3 | btn 4 | btn 5 | — | — |
| Bike Lock | Q1-TRUE | Q1-FALSE | Q2-TRUE | Q2-FALSE | — | — | — |
| No Friends Monday | ladder ADC | WS2812 data | — | — | — | — | — |
| Photo Bomb | shutter | — | — | — | — | — | — |
| Monkey | pedestal switch | — | — | — | — | — | — |
| Porto | piezo 1 + | piezo 2 + | piezo 3 + | — | — | — | — |

Gate banks: pads 1–3 = bank A, 4–6 = bank B. NFM's resistor ladder and
lamp chain live at the truck; pins 1/2 power the lamps — **5V addressable
strip only (from Tim's stash), never 12V sign stock**, and the 74AHCT125
data shifter sits in the box so pin 4 carries 5V-level data down the cable
(ladder values + decode: `room-games-plan.md` / `game_lightsout_hw.yaml`).
Porto piezo − legs all common to pin 2.

**Gate's pads land on an MCP23017 (GPA0–5), not XIAO pads** — the DMX plan
found Gate pin-full (6 pads + radar + I2S = 11/11), so it opens the
expander path early: I2C on D4/D5, cable and pin map above unchanged, DMX
TX takes the freed D0. See `dmx-over-wifi.md` and
`sim/esphome/packages/game_gate_hw_mcp.yaml`.

Rooms with no wired inputs (Entrance, Exit, Guy Line, VMM, Cuddle,
Cop Dodge, Sparkle Pony, Temple) leave port A's pre-cut window empty —
blank it against dust (tape/cover plate) — but every room, wired or not,
carries the XLR jack for its DMX out.
Moop pucks are wireless — nothing here.

## BOM (shopping-list.xlsx)

| Item | Qty | Note |
|---|---|---|
| DB9 female screw-terminal breakout | 9 | 7 port-A box ends + 2 spares |
| DB9 male screw-terminal breakout | 9 | 7 pod ends + 2 spares |
| DB9 M-F straight-through extension cables | 9 | port-A lengths per room + 2 spares |
| XLR3 female panel jack, D-size (Devinal 4-pack, amzn B07S6J8WVD, $8.99) | 20 | 5 packs: 15 DMX outs + 5 spares; solder cups, bench-wired |
| Short wood screws (#4-ish, 6–10mm) | ~34 | 2 per jack through its flange holes — **from stash**; jacks ship with no screws |
| XLR3 M-F cables, 6 ft | 17 | box → first fixture, used WHOLE (nothing gets cut up); 2 spares double as fixture hops |
| DMX 120Ω XLR terminator plug | 17 | one per room chain + spares |
| MAX485 TTL→RS485 module (DE/RE broken out) | 17 | the DMX driver — 15 + 2 spares |
| DB9 dust caps (M+F) | ~20 | playa — port A box + pod ends |
| XLR female dust cover | 16 | playa — the jack sits open when the room cable's out |
| MCP23017 breakout | 2 | Gate now + 1 spare (the growth path arrived early) |
