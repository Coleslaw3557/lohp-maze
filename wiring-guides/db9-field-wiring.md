# DB9 field wiring standard (2026-07-21)

The traveling-maze field IO: every node box carries **two DB9 positions on
the left wall** (`enclosure/node-enclosure.scad`). Port A is etched, opened
in the 7 wired rooms. Port B is **cut in every box — it's the room's DMX
out** (`dmx-over-wifi.md`): the node's MAX485 drives the room's fixtures
through it via a DB9→XLR adapter. A future MCP23017 expansion shares port
B's shell on its reserved pins (Gate does this already — see below).
Rapid setup = one premade cable per wired room + one DMX adapter, done.

**No crimping or soldering anywhere in the system:**

- **Box end:** DB9 screw-terminal breakout (female), bolted through the
  wall at the etched cutout with its jackscrews. Node wires land under
  screws inside.
- **Cable:** premade **straight-through M-F DB9 serial extension** —
  ⚠ NOT a null-modem cable (those swap pins internally and scramble the
  map). Any length, ~$5.
- **Pod end:** DB9 screw-terminal breakout (male) inside the button
  cluster. Button/piezo wires land under screws.
- Dust caps both sides at teardown; a spare cable in the kit is the
  field fix for anything flaky.

## Universal pinout — EVERY box, used or not

**Port A** (field IO):

| DB9 pin | Carries |
|---|---|
| 1 | 5V (button LEDs / lamps) |
| 2 | GND (switch common, LED −, piezo −) |
| 3–9 | signals 1–7, in room order |

Signal n lands on XIAO **D(n−1)** unless the room table says otherwise.
Buttons are closures to GND (input-pullup); LEDs wire pin 1→LED+,
pin 2→LED− (always lit, no GPIO — per the games plan).

**Port B** (DMX out, every box — `dmx-over-wifi.md` has the full build):

| DB9 pin | Carries |
|---|---|
| 1 | 5V (universal convention — wire it, the DMX adapter ignores it) |
| 2 | GND → XLR 1 |
| 3 | Data+ (MAX485 A) → XLR 3 |
| 4 | Data− (MAX485 B) → XLR 2 |
| 5–9 | reserved — an MCP23017's extra signals may share this shell |

Get D+/D− right at the adapter's screw terminals and label the adapter —
swapped polarity is the classic "fixture flickers randomly" field failure.

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
lamp chain live at the truck; pins 1/2 power the WS2812s. Porto piezo −
legs all common to pin 2.

**Gate's pads land on an MCP23017 (GPA0–5), not XIAO pads** — the DMX plan
found Gate pin-full (6 pads + radar + I2S = 11/11), so it opens the
expander path early: I2C on D4/D5, cable and pin map above unchanged, DMX
TX takes the freed D0. See `dmx-over-wifi.md` and
`sim/esphome/packages/game_gate_hw_mcp.yaml`.

Rooms with no wired inputs (Entrance, Exit, Guy Line, VMM, Cuddle,
Cop Dodge, Sparkle Pony, Temple) keep port A as an unopened etch — but
every room, wired or not, bolts a breakout into port B for its DMX out.
Moop pucks are wireless — nothing here.

## BOM (shopping-list.xlsx)

| Item | Qty | Note |
|---|---|---|
| DB9 female screw-terminal breakout | 25 | 7 port-A box ends + 15 port-B (DMX) + 3 spares |
| DB9 male screw-terminal breakout | 25 | 7 pod ends + 15 DMX→XLR adapters + 3 spares |
| DB9 M-F straight-through extension cables | 9 | port-A lengths per room + 2 spares |
| XLR3 M-F cables, 6 ft | 17 | 15 cut → adapter tails; 2 whole = fixture hops (`dmx-over-wifi.md`) |
| DMX 120Ω XLR terminator plug | 17 | one per room chain + spares |
| MAX485 TTL→RS485 module (DE/RE broken out) | 17 | the port-B driver — 15 + 2 spares |
| DB9 dust caps (M+F) | ~36 | playa — both ports now |
| MCP23017 breakout | 2 | Gate now + 1 spare (the growth path arrived early) |
