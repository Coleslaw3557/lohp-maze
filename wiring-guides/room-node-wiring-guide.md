# Room node box — pin-to-pin wiring reference (2026-07-24)

Every connection inside the universal node enclosure (`../enclosure/README.md`),
one table per component. Pinouts verified against each part's spec sheet —
sources listed at the bottom. The why/how-to-mount lives in the companion docs
(`dmx-over-wifi.md`, `db9-field-wiring.md`, `room-node-audio-plan.md`,
`room-games-plan.md`); this is only what-pin-goes-where.

Board is the **XIAO ESP32-S3** (fleet standard; GPIO numbers below are S3).
Common rails: **5V** = the XIAO's 5V pin (fed by its USB-C, the box supply).
**3V3** = the XIAO's 3.3V pin. **GND** = common ground, every module.

## Wire color code (in-box, set 2026-07-24 — six stocked colors)

| Color | Carries |
|---|---|
| Red | 5V rail: every VCC/VIN, DB9 pin 1, the DE+RE tie to VCC |
| Black | GND: every module GND, XLR pin 1, DB9 pin 2 |
| White | 3V3: MCP23017 VCC + RESET (Gate), NFM ladder 10k feed |
| Green | data OUT of the XIAO: UART Tx (D6, D2), MAX485 DI, I2S DIN, AHCT 1A in / 1Y out |
| Yellow | data INTO the XIAO: radar Tx lines (→ D7 / D3), every DB9 signal jumper (buttons, piezos, ladder) |
| Blue | clock/bus pairs: I2C SDA + SCL, I2S BCK + LCK — pair identity comes from the labeled module pins |

Exception — the XLR cup pigtails, so the polarity-critical pair can never
be confused: **Data+ (pin 3 → A screw) = green, Data− (pin 2 → B screw) =
yellow**, pin 1 = black.

## XIAO ESP32-S3 pad map (Seeed wiki)

| Pad | GPIO | Used for |
|---|---|---|
| D0 | 1 | per-room: buttons / NFM ladder ADC / Porto piezo 1 / **Gate: DMX TX** |
| D1 | 2 | button contract (Photo Bomb, Monkey) / NFM lamp data / DPH+Bike button 2 / Porto piezo 2 |
| D2 | 3 | Cuddle: LD2450 (node Tx) / DPH+Bike button 3 / Porto piezo 3 |
| D3 | 4 | Cuddle: LD2450 (node Rx) / DPH+Bike button 4 |
| D4 | 5 | I2C SDA — TOF200C (Entrance/Exit), MCP23017 (Gate) / DPH button 5 |
| D5 | 6 | **DMX TX (default)** / I2C SCL in Entrance/Exit + Gate |
| D6 | 43 | LD2410C Rx (node Tx) — the 12 LD2410C rooms; unused in Cuddle |
| D7 | 44 | LD2410C Tx (node Rx) / **DMX TX in Entrance + Exit** |
| D8 | 7 | I2S BCLK → DAC BCK |
| D9 | 8 | I2S LRCLK → DAC LCK |
| D10 | 9 | I2S DOUT → DAC DIN |
| 5V | — | rail: MAX485 VCC, DAC VIN, radar VCC, DB9 pin 1 |
| 3V3 | — | Gate: MCP23017 VCC+RESET; NFM: ladder 10k top resistor |
| GND | — | common: every module GND, XLR pin 1, DB9 pin 2 |

DMX TX per room: **D5** in the 13 radar rooms, **D7** in Entrance + Exit
(their I2C ToF owns D4/D5, and with no radar D6/D7 is free), **D0** at Gate
(pads moved to the MCP23017) — `dmx-over-wifi.md`.

## MAX485 → XLR jack (every box — the DMX out)

Received screw-terminal variant, orientation photo-fixed 07-24: header at the
screw-terminal end = **VCC / B / A / GND**; far-end header = **RO / RE / DE / DI**.

| MAX485 pin | Wire to |
|---|---|
| VCC | 5V rail |
| DE + RE | tied together → VCC (always transmitting) |
| GND | GND + XLR pin 1 pigtail |
| DI | XIAO DMX TX pad (D5 / D7 / D0 per room) |
| RO | not connected (5V logic — never to the XIAO) |
| A screw | XLR pin 3 pigtail (Data+) |
| B screw | XLR pin 2 pigtail (Data−) |

XLR3 female jack (DMX512 convention): **1 = GND, 2 = Data−, 3 = Data+**.
Cups are bench-soldered pigtails; heat-shrink each.

## PCM5102A DAC (audio rooms)

Purple GY board. Prep first (5 solder bridges, board is silent without them):
back pads **FLT→L, DEMP→L, XSMT→H, FMT→L**; front pads **SCK→GND**.

| DAC pin | Wire to |
|---|---|
| VIN | 5V rail |
| GND | GND |
| BCK | XIAO D8 (GPIO7) |
| LCK | XIAO D9 (GPIO8) |
| DIN | XIAO D10 (GPIO9) |
| SCK | no wire (bridged to GND on-board) |
| 3.5mm jack | line out → Pebble speaker through the AUX hole |

## LD2410C radar (12 rooms — all but Entrance/Exit and Cuddle, which runs the LD2450)

Hi-Link manual Table 1 pin order **Tx, Rx, OUT, GND, VCC** — wire by the board
silk. UART 256000 baud 8N1, 3.3V logic, 5V supply (~79 mA).

| LD2410C pin | Wire to |
|---|---|
| VCC | 5V rail |
| GND | GND |
| Tx | XIAO D7 (GPIO44) |
| Rx | XIAO D6 (GPIO43) |
| OUT | not connected (UART carries everything) |

## TOF200C time-of-flight (Entrance + Exit only)

| TOF200C pin | Wire to |
|---|---|
| VIN | 5V rail (board regulates; I2C pull-ups sit at 3.3V on-board) |
| GND | GND |
| SDA | XIAO D4 (GPIO5) |
| SCL | XIAO D5 (GPIO6) |
| XSHUT, GPIO1 | not connected |

These 2 rooms have no radar, so their DMX TX is **D7**. They are also the only
two boxes with an opening in the window panel — 940 nm passes neither wood nor
plain acrylic, so they keep the 16×16 aperture (see `enclosure/README.md`).

**Radar is not an option here** and this was settled 2026-07-30: it only works
with a foil layer behind the shared Exit|Entrance divider (bare ply passes
24 GHz and the two halves detect each other), and Tim ruled the foil out. Do not
re-propose it. Firmware: `packages/tof.yaml`. **Part: TOF200C** (VL53L0X inside —
ESPHome native, no external component). Gate stays 2.1 m; the module's own 2 m
ceiling is what actually excludes the street, since past ~2 m it returns nothing
and that reads as empty. Confirm the board is in I2C mode at 0x29 before
flashing — some batches ship UART. The TOF050C (0.5 m) is too short to use here.

## Guy Line Climb + Vertical Moop March (radar, top of the room pointed down)

Full-height shafts with ropes going in all directions, which can't be arranged
predictably. The radar mounts at the **top of the room pointed straight down**
(Guy Line 3.70 m; VMM 1.80 m above the level-1 deck) so its cone covers the whole
floor and it sees someone at the bottom **however they got there** — in through
the doorway, or down the ropes or the scaffolding. Wiring is the standard radar
recipe above: D6/D7, DMX TX on D5. VMM additionally carries the 4 march-game
buttons on D0–D3 through port A pins 3–6 (2026-08-16 — the wireless puck
design is dead; `game_moop.yaml`, pod recipe in `db9-field-wiring.md`).

**Guy Line AS BUILT 2026-08-20: the box carries a XIAO ESP32-C6, not the
fleet's S3.** Wiring positions are unchanged (radar D6/D7, DMX TX D5) but the
GPIO numbers differ — firmware follows the hardware via
`packages/hardware_c6.yaml` (full C6 pin map in its header; radar =
GPIO16/17, DMX TX = GPIO23 on uart1). The C6 has no PSRAM, so **this box has
no speaker** until the board is swapped for an S3 (swap = reflash on
hardware_s3.yaml + new MAC -> re-do the RUT reservation). Guy Line's radar
gates are widened for the 3.70 m top-down mount: move 5 / still 6 (defaults
would miss a walker at the floor).

## LD2450 tracking radar (Cuddle only — the room's ONE radar since 2026-08-20)

Cuddle consolidated to the LD2450 alone (Tim, 2026-08-20): it does presence
(same two-edge contract as the LD2410C rooms, `packages/ld2450.yaml`) AND the
floor-projection / orb-gaze target tracks. Still-target dropout (a tracker
losing a statue-still person) is bridged by the module presence timeout + the
room's 60 s `absence_timeout`, not by a second radar.

**AS BUILT 2026-08-20: the box keeps the ORIGINAL D2/D3 assignment** (Tim had
already wired it when the consolidation briefly moved the plan to D6/D7;
firmware follows the hardware — bench-validated same day). D6/D7 sit unused
in this box.

Hi-Link manual pins **5V, GND, Tx, Rx**. UART 256000 baud, 3.3V logic.

| LD2450 pin | Wire to |
|---|---|
| 5V | 5V rail |
| GND | GND |
| Tx | XIAO D3 (GPIO4) |
| Rx | XIAO D2 (GPIO3) |

## DB9 port A (7 wired rooms; window blanked elsewhere)

Universal: **pin 1 = 5V rail, pin 2 = GND, pins 3–9 = signals** (button LEDs
across 1/2, always lit; buttons close their signal to GND, internal pull-ups).

| Room | DB9 3 | DB9 4 | DB9 5 | DB9 6 | DB9 7 | DB9 8 |
|---|---|---|---|---|---|---|
| Gate | MCP GPA0 | GPA1 | GPA2 | GPA3 | GPA4 | GPA5 |
| Deep Playa Handshake | D0 | D1 | D2 | D3 | D4 | — |
| Bike Lock | D0 | D1 | D2 | D3 | — | — |
| No Friends Monday | D0 (ladder) | ← AHCT 1Y via 33–100Ω | — | — | — | — |
| Photo Bomb | **D1** | — | — | — | — | — |
| Monkey | **D1** | — | — | — | — | — |
| Porto | D0 | D1 | D2 | — | — | — |

⚠ Photo Bomb + Monkey land on **D1**, not D0 — D1 is the fleet button
contract (`button_gpio_c3.example.yaml`, `button_pin: GPIO2` on S3).
Porto: piezo + on the signal pins, all piezo − to pin 2; **1MΩ bleed
resistor from each of D0/D1/D2 to GND at the XIAO** (bench-soldered).
NFM: **10k from 3V3 → D0** in the box (ladder top resistor); the ladder
resistors + lamp chain live at the truck.

## MCP23017 (Gate only — Waveshare board)

Address 0x27 = A0/A1/A2 left open (they float high; shorting = low).
I2C at 100 kHz. Buttons close GPA pins to GND, internal pull-ups on.

| MCP23017 pin | Wire to |
|---|---|
| VCC | 3V3 |
| GND | GND |
| SDA | XIAO D4 (GPIO5) |
| SCL | XIAO D5 (GPIO6) |
| RESET | 3V3 |
| GPA0–GPA5 | DB9 pins 3–8 |
| INTA, INTB, GPA6–7, GPB0–7 | not connected |

Gate's DMX TX is **D0** (pads moved here freed it).

## 74AHCT125 level shifter (No Friends Monday only — dead-bug at the AHCT zone)

Bare SN74AHCT125N, glued legs-up. ⚠ Legs-up MIRRORS the pinout — with the
notch pointing away, pin 1 is the far-RIGHT leg; paint-mark pin 1 before gluing.

| AHCT pin | Wire to |
|---|---|
| 14 (VCC) | 5V rail — 0.1µF ceramic across 14/7 at the legs |
| 7 (GND) | GND |
| 1 (1OE̅) | GND |
| 2 (1A) | XIAO D1 (GPIO2) |
| 3 (1Y) | 33–100Ω right at the leg → DB9 pin 4 screw |
| 4, 5, 9, 10, 12, 13 | GND (one bus wire to pin 7) |
| 6, 8, 11 | not connected |

## Per-room summary

| Room | Sensor(s) | DMX TX | Port A |
|---|---|---|---|
| Entrance / Exit | TOF200C (D4/D5) | D7 | blank |
| Guy Line Climb | LD2410C, top of room pointed down | D5 | blank |
| Vertical Moop March | LD2410C top-down + 4 buttons D0–D3 | D5 | pins 3–6 |
| Gate | LD2410C + 6 pads via MCP23017 | D0 | pins 3–8 |
| Deep Playa Handshake | LD2410C + 5 buttons D0–D4 | D5 | pins 3–7 |
| Bike Lock | LD2410C + 4 buttons D0–D3 | D5 | pins 3–6 |
| No Friends Monday | LD2410C + ladder D0 + lamp data D1 | D5 | pins 3–4 |
| Photo Bomb / Monkey | LD2410C + button D1 | D5 | pin 3 |
| Porto | LD2410C + 3 piezos D0–D2 | D5 | pins 3–5 |
| Cop Dodge / Sparkle Pony / Temple | LD2410C | D5 | blank |
| Cuddle Cross | LD2450 on D2/D3 (sole radar 2026-08-20, as built) — own window etch | D5 | blank |

Every room: MAX485+XLR (DMX out) and, if it's an audio room, the DAC on
D8–D10. WiFi antenna stays inside. (2026-08-16: the wireless Moop pucks are
dead — VMM's 4 game buttons wire to its box like every other button room.)
Draw on the 5V pin: radar + DAC + MAX485 ≈ 135 mA — within the pin budget.

## Spec-sheet sources

- XIAO ESP32-S3 pad→GPIO map: Seeed Studio wiki (Getting Started, pin list).
- LD2410C: Hi-Link HLK-LD2410C User Manual V1.00, Table 1 (pins Tx/Rx/OUT/GND/VCC,
  5V supply >200 mA, 3.3V IO, UART 256000 8N1).
- LD2450: Hi-Link HLK-LD2450 Instruction Manual (pins 5V/GND/Tx/Rx, 3.3V IO,
  UART 256000 8N1).
- PCM5102A GY board: board schematic (macsbug 2021-02-19) — header
  SCK/BCK/DIN/LCK/GND/VIN, inputs 5V-tolerant, VIN through on-board 3.3V
  regulator, FLT/DEMP/XSMT/FMT tri-pads + SCK-to-GND bridge.
- TOF200C breakout (VL53L0X): VIN/GND/SDA/SCL/XSHUT/GPIO1 (interrupt) — generic board,
  confirm silk on the received units.
- SN74AHCT125: TI datasheet (quad 3-state buffer; 1OE̅/1A/1Y = pins 1/2/3,
  GND = 7, VCC = 14).
- MCP23017 board: Waveshare wiki — A0/A1/A2 open = high = address 0x27.
- MAX485 module pin order: photo-verified against the received batch 07-24
  (`dmx-over-wifi.md`), which beats any generic module drawing.
- XLR DMX pinout: DMX512 (ANSI E1.11) transmitter convention, per
  `db9-field-wiring.md`.
