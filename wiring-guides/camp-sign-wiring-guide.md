# LoHP Maze Wiring Guide
# CAMP SIGN (DMX 161–352)

> Plan/rationale: `camp-sign-plan.md`. Parts: `../shopping-list.xlsx` (Camp Sign tab).
> This is the build-time reference: every item and where it goes.

## Placement

| Item | Location |
|---|---|
| ABI 12V 500W PSU | LEFT pillar, mounted vertically, fan clear, AC terminals covered |
| 35A MAXI main fuse | LEFT pillar, ≤18 in of 8 AWG from PSU V+ |
| LEFT fuse block (+ neg bus) | LEFT pillar, beside PSU |
| RIGHT fuse block (+ neg bus) | RIGHT pillar, fed by the cross-arch trunk |
| Sign node box (cut `../enclosure/node-enclosure-sign.svg`): XIAO S3, 74AHCT125, buck, MAX485 | Behind the removable logo disc (band center), floor screwed to the cavity wood, lid up. Ports: 12V in + DMX XLR (left wall), D1–D3 data out (back), USB + BTN (right) — see the plan's Enclosure section |
| Dfi RX (fallback only) | OUTSIDE the box, its male XLR plugged into the box's DMX jack, antenna clear of steel |
| Storm arcade button (lit) | On the sign scaffolding at reachable height; its 3-wire run (switch + always-lit lamp, 2026-07-31) plugs into the box's BTN pigtail (right wall, "STORM" etch) |
| Dfi TX | Plugged into the LAST maze fixture's DMX OUT (female); wall-wart on that fixture's AC run |
| Strip groups (pixel 0 always at band center; regrouped 2026-07-29) | 1 "Legends of the" (lands at 'e') · 2 logo disc · 3 "Hidden Playa" (lands at 'H') |

## AC in (inverter generator — no GFCI)

| From | To |
|---|---|
| Generator cord (3-conductor) | Cord grip at LEFT pillar base |
| Hot / Neutral | PSU L / N (covered) |
| Ground | PSU ground terminal AND chassis lug |
| DC V− | NOT bonded to AC ground — DC floats |

## 12V spine

One run per chain (2026-07-29), power landing ONLY at a word's front or
back — never mid-word. Spare positions on both blocks for soak-test
additions (word boundaries only).

| Circuit | Fuse | Wire | Runs to |
|---|---|---|---|
| PSU V+ → MAIN | 35A MAXI | 8 AWG, short | LEFT block stud |
| LEFT C1 | 10A | 14 AWG stub | "Legends of the" power in at 'L' (front of Legends — lands at LEFT pillar) |
| LEFT C2 | 5A | 18 AWG up-arch | Logo-field power (cavity, beside the box) |
| LEFT C3 | 2A | 18 AWG up-arch | Box 12V pigtail (2-pin, left wall) → buck IN+ (and Dfi RX if it's a 12V unit) |
| LEFT C4 → trunk | 20A | 10 AWG pair across band back | RIGHT block stud |
| RIGHT C1 | 10A | 14 AWG stub | "Hidden Playa" power in at 'a' (back of Playa — lands at RIGHT pillar) |

Negatives: PSU V− → LEFT neg bus; trunk black → RIGHT neg bus; every strip
white and the cavity GND land on the nearest bus. Every + connection above
lands through a 2-pin waterproof pigtail so chains disconnect. Data enters
each letter chain at the CENTER end ('e' / 'H'), power at the outboard end
('L' / 'a') — all word boundaries. Final fuse sizes after measuring:
installed meters × 1.2A, next size up (est. loads: LEFT C1 ≈ 7.7A ·
logo ≈ 3.6A · RIGHT C1 ≈ 9.2A).

## Controller cavity — XIAO ESP32-S3

| S3 pin | GPIO | Connection |
|---|---|---|
| 5V | — | Buck OUT+ (5V); the storm-button lamp taps this rail at the BTN pigtail. Unplug before flashing over USB |
| GND | — | Common (buck OUT−, AHCT pin 7, MAX485 GND, XLR pin 1) |
| 3V3 | — | MAX485 VCC (3.3V feed = 3.3V RO output, S3-safe) |
| D0 | GPIO1 | AHCT pin 2 (1A) → D1 "Legends of the" data |
| D1 | GPIO2 | AHCT pin 5 (2A) → D2 logo-field data |
| D2 | GPIO3 | AHCT pin 9 (3A) → D3 "Hidden Playa" data |
| D3 | GPIO4 | Storm button via the BTN pigtail (3-wire): microswitch NO shorts it to GND, INPUT_PULLUP, ~50 ms debounce → POST /api/sign_storm (server owns the 30 s cooldown); the lamp rides the same pigtail (its own section below) |
| D4 | GPIO5 | MAX485 RO (UART1 RX, DMX in) |
| D5–D10, TX/RX | — | Not used |

Buck: IN+ ← LEFT C3 (12V) · IN− ← common · OUT+ 5V → S3 5V pin + the BTN
pigtail's red lamp lead (+ Dfi RX if it's a 5V unit — check its adapter
before wiring). Orientation at the etched
BUCK zone: **12V-IN terminal end toward the left wall** (straight shot from
the 12V hole), 5V-OUT end toward the XIAO; the terminal blocks overhang the
etched body outline at both ends, wire entries low.

## 74AHCT125 (DIP-14, socketed)

| Pin | Connection |
|---|---|
| 14 VCC | 5V (buck OUT+) |
| 7 GND | Common |
| 1, 4, 10, 13 (OE̅) | GND — all four buffers enabled |
| 2 ← S3 D0 | 3 → 33–100Ω → D1 pigtail → "Legends of the" data, lands at 'e' |
| 5 ← S3 D1 | 6 → 33–100Ω → D2 pigtail → logo-field data (center) |
| 9 ← S3 D2 | 8 → 33–100Ω → D3 pigtail → "Hidden Playa" data, lands at 'H' |
| 12 ← GND (unused input — never float a CMOS input) | 11 n.c. |

Series resistors at the chip end; the chip dead-bugs at the floor's etched
AHCT zone, its outputs going straight out the D1–D3 back-wall holes on
3-pin pigtails. **As-built 2026-08-01: the RED lead carries DATA on D1–D3**
(printed cable labels match) — data + GND only either way; chain +12V never
passes through this box, group power is fuse-block business. Data leads run along the band
to each group's pixel 0 (longest: ~4 ft to 'P'). On-hand TXS0108E is NOT a
sub here.

## Storm button (BTN pigtail, right wall — 3-wire since 2026-07-31)

EG Starts 30 mm illuminated button (5V kit LED, resistor built in — see
room-games-plan.md), the 25th button of the games order. Bench-make the
button tail so the scaffold end just plugs in; the lamp is always lit — no
GPIO spent, the game rooms' rule:

| Lead (as-built 2026-08-01) | Button end | Box end (inside the wall) |
|---|---|---|
| yellow (signal/data) | Microswitch NO | S3 D3 (GPIO4, INPUT_PULLUP) |
| red (+5V power) | Lamp + | Buck OUT+ |
| black (GND) | Microswitch COM + lamp − spliced | Common GND |

Red on THIS pigtail carries live 5V for the lamp — unlike the D1–D3 data
pigtails, whose red +12V lead stays cut.

## DMX link (Dfi 2.4G)

| Item | Connection |
|---|---|
| Dfi TX (male XLR) | Into last maze fixture's DMX OUT. Wired chain keeps its own 120Ω at that fixture |
| Dfi TX power | Its wall-wart, on that fixture's AC run |
| ID group | Same setting on TX and RX; pick a non-default group in case neighbors run Dfi |
| Dfi RX | OUTSIDE the box, male XLR into the box's DMX jack; antenna clear of steel; powered per its spec (5V from buck or 12V from LEFT C3 — its power lead can share the 12V hole) |
| Box DMX jack (Devinal XLR3-F, bench-soldered cups) | pin 3 → MAX485 screw terminal A · pin 2 → terminal B · pin 1 → common GND |
| 120Ω (on-hand) | Across A–B screw terminals (the RX stub is its own bus) |

MAX485 header (the received screw-terminal batch, same module as the room
boxes): VCC → S3 3V3 · GND → common · **RO → S3 D4** · **RE + DE → GND**
(receive enabled) · DI n.c. If the bench shows no frames, check the RE/DE
tie sits at GND. (The MAYWILLA female pigtail the BOM bought for this link
is spare since the panel jack — pack it.)

## Strip groups (BTF 3-pin: red +12V · green DATA · white GND — verify vs reel arrow)

Pixel 0 of every group is at band center; 3-pin waterproof pigtail pair at
each group start (the logo disc IS group 2's start — its pigtail doubles as
the disc's removable disconnect; regrouped 2026-07-29). Letter-to-letter and
word-to-word jumps: soldered 3-wire + adhesive shrink, riding the gap behind
the letters (group 1 jumps the·of→Legends gaps, group 3 the Hidden→Playa
gap, the same way).

| Output | Physical pixel order (center → out) | Zones in that order | DMX @ |
|---|---|---|---|
| 1 | e h t · f o · s d n e g e L (the/of/Legends all reversed) | 11,10,9,…,1,0 | 249→161 |
| 2 | logo field (disc) | 12 | 257 |
| 3 | H i d d e n · P l a y a | 13…23 | 265→345 |

Count pixels per letter as installed → firmware table (letter = zone =
contiguous pixel range). Strip serpentines on each letter's BACK, LEDs facing
the band, screw clips; logo = serpentine field behind the disc + diffuser.

## Bring-up checklist

1. Flash S3 on the bench BEFORE connecting the buck (USB and 5V-pin feed not
   together). *Done 2026-08-01 over USB (`firmware/sign/build.sh flash`);
   reflash from here on = `build.sh ota` (lohp-sign-bridge.local).*
2. Set Dfi TX+RX to the same ID group; verify frames at @161 with a bench par chain.
3. Polarity-check every 2-pin power drop before inserting its fuse.
4. Red-only test per output, then full white: 12V ≥ 11.5V at every group's far
   pixel — if low, add a second entry from the nearest block AT A WORD BOUNDARY.
   (Serial console drives this without the Pi: `1`/`2`/`3` = red on that chain
   alone, `w` = full white, `0` = back to DMX. First red test also confirms the
   reel's color order — if red shows another color, flip `SIGN_COLOR_ORDER` in
   `firmware/sign/sign_config.h`.)
5. Press the storm button (its lamp should already be lit — it rides the buck rail): the whole maze AND the sign flash Lightning with thunder on every speaker at once; a second press inside 30 s must come back 429 (the server cooldown — nothing to configure on the node). *The POST loop is already proven from this box (2026-08-01, serial `s`): 200 "Storm fired maze-wide", re-press 429 — the scaffold button only adds the physical switch on D3.*
6. Re-check fuse sizes against measured strip meters (×1.2A rule).
