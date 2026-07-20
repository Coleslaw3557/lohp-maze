# LoHP Maze Wiring Guide
# CAMP SIGN (DMX 161–352)

> Plan/rationale: `camp-sign-plan.md`. Parts: `../sign-shopping-list.xlsx`.
> This is the build-time reference: every item and where it goes.

## Placement

| Item | Location |
|---|---|
| ABI 12V 500W PSU | LEFT pillar, mounted vertically, fan clear, AC terminals covered |
| 35A MAXI main fuse | LEFT pillar, ≤18 in of 8 AWG from PSU V+ |
| LEFT fuse block (+ neg bus) | LEFT pillar, beside PSU |
| RIGHT fuse block (+ neg bus) | RIGHT pillar, fed by the cross-arch trunk |
| Controller cavity: XIAO S3, 74AHCT125, buck, HiLetgo RS485, Dfi RX | Behind the removable logo disc (band center) |
| Dfi TX | Plugged into the LAST maze fixture's DMX OUT (female); wall-wart on that fixture's AC run |
| Strip groups (pixel 0 always at band center) | 1 Legends · 2 "of the"+logo · 3 Hidden · 4 Playa |

## AC in (inverter generator — no GFCI)

| From | To |
|---|---|
| Generator cord (3-conductor) | Cord grip at LEFT pillar base |
| Hot / Neutral | PSU L / N (covered) |
| Ground | PSU ground terminal AND chassis lug |
| DC V− | NOT bonded to AC ground — DC floats |

## 12V spine

| Circuit | Fuse | Wire | Runs to |
|---|---|---|---|
| PSU V+ → MAIN | 35A MAXI | 8 AWG, short | LEFT block stud |
| LEFT C1 | 10A | 14 AWG up-arch | Group 1 feed at 's' (Legends start, center) |
| LEFT C2 | 7.5A | 14 AWG up-arch | Group 2 feed in the cavity (logo + "of the") |
| LEFT C3 | 2A | 18 AWG up-arch | Cavity: buck IN+ (and Dfi RX if it's a 12V unit) |
| LEFT C4 | 5A | 18 AWG stub | Injection: 'L' far end (lands at LEFT pillar) |
| LEFT C5 | 5A | 18 AWG up-arch | Injection: Legends midpoint (≈ 'n'/'d') |
| LEFT C6 → trunk | 20A | 10 AWG pair across band back | RIGHT block stud |
| RIGHT C1 | 7.5A | 14 AWG up-arch | Group 3 feed at 'H' (Hidden start) |
| RIGHT C2 | 7.5A | 14 AWG | Group 4 feed at 'P' (Playa start) |
| RIGHT C3 | 5A | 18 AWG stub | Injection: Playa 'a' far end (lands at RIGHT pillar) |
| RIGHT C4 | 5A | 18 AWG | Injection: Hidden 'n' far end (mid-right arch) |

Negatives: PSU V− → LEFT neg bus; trunk black → RIGHT neg bus; every strip
white and the cavity GND land on the nearest bus. Every + connection above
lands through a 2-pin waterproof pigtail so letters/groups disconnect.
Final fuse sizes after measuring: installed meters × 1.2A, next size up.

## Controller cavity — XIAO ESP32-S3

| S3 pin | GPIO | Connection |
|---|---|---|
| 5V | — | Buck OUT+ (5V). Unplug before flashing over USB |
| GND | — | Common (buck OUT−, AHCT pin 7, HiLetgo GND, XLR pin 1) |
| 3V3 | — | HiLetgo VCC (3.3V feed = 3.3V output, S3-safe) |
| D0 | GPIO1 | AHCT pin 2 (1A) → group 1 data |
| D1 | GPIO2 | AHCT pin 5 (2A) → group 2 data |
| D2 | GPIO3 | AHCT pin 9 (3A) → group 3 data |
| D3 | GPIO4 | AHCT pin 12 (4A) → group 4 data |
| D4 | GPIO5 | HiLetgo RXD (UART1 RX, DMX in) |
| D5–D10, TX/RX | — | Not used |

Buck: IN+ ← LEFT C3 (12V) · IN− ← common · OUT+ 5V → S3 5V pin (+ Dfi RX if
it's a 5V unit — check its adapter before wiring).

## 74AHCT125 (DIP-14, socketed)

| Pin | Connection |
|---|---|
| 14 VCC | 5V (buck OUT+) |
| 7 GND | Common |
| 1, 4, 10, 13 (OE̅) | GND — all four buffers enabled |
| 2 ← S3 D0 | 3 → 33–100Ω → group 1 data lead |
| 5 ← S3 D1 | 6 → 33–100Ω → group 2 data lead |
| 9 ← S3 D2 | 8 → 33–100Ω → group 3 data lead |
| 12 ← S3 D3 | 11 → 33–100Ω → group 4 data lead |

Series resistors at the chip end. Data leads run along the band to each
group's pixel 0 (longest: ~4 ft to 'P'). On-hand TXS0108E is NOT a sub here.

## DMX link (Dfi 2.4G)

| Item | Connection |
|---|---|
| Dfi TX (male XLR) | Into last maze fixture's DMX OUT. Wired chain keeps its own 120Ω at that fixture |
| Dfi TX power | Its wall-wart, on that fixture's AC run |
| ID group | Same setting on TX and RX; pick a non-default group in case neighbors run Dfi |
| Dfi RX | In the cavity, antenna clear of steel; powered per its spec (5V from buck or 12V from LEFT C3) |
| RX XLR male out | MAYWILLA female pigtail |
| Pigtail pin 3 (Data+) | HiLetgo screw terminal A |
| Pigtail pin 2 (Data−) | HiLetgo screw terminal B |
| Pigtail pin 1 | Common GND |
| 120Ω (on-hand) | Across A–B screw terminals |

HiLetgo TTL header: VCC → S3 3V3 · GND → common · **RXD → S3 D4** · TXD
floating (RX-only). Batch silk varies — if the bench shows no frames, swap
RXD/TXD once.

## Strip groups (BTF 3-pin: red +12V · green DATA · white GND — verify vs reel arrow)

Pixel 0 of every group is at band center; 3-pin waterproof pigtail pair at
each group start + one at the logo disc (removable). Letter-to-letter jumps:
soldered 3-wire + adhesive shrink, riding the gap behind the letters.

| Output | Physical pixel order (center → out) | Zones in that order | DMX @ |
|---|---|---|---|
| 1 | s d n e g e L (Legends reversed) | 6,5,4,3,2,1,0 | 209→161 |
| 2 | logo field · e h t · f o ("the"/"of" reversed) | 12,11,10,9,8,7 | 257→217 |
| 3 | H i d d e n | 13…18 | 265→305 |
| 4 | P l a y a | 19…23 | 313→345 |

Count pixels per letter as installed → firmware table (letter = zone =
contiguous pixel range). Strip serpentines on each letter's BACK, LEDs facing
the band, screw clips; logo = serpentine field behind the disc + diffuser.

## Bring-up checklist

1. Flash S3 on the bench BEFORE connecting the buck (USB and 5V-pin feed not together).
2. Set Dfi TX+RX to the same ID group; verify frames at @161 with a bench par chain.
3. Polarity-check every 2-pin injection drop before inserting its fuse.
4. Red-only test per output, then full white: 12V ≥ 11.5V at every group's far pixel — add a stub from the nearest block if low.
5. Re-check fuse sizes against measured strip meters (×1.2A rule).
