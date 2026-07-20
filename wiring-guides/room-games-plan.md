# Room games plan (2026-07-20)

The interactive game layer for the 2026 build. One audio language everywhere:
**CorrectAnswer = the maze-wide victory chime, WrongAnswer = the fail sound**
(existing effects + audio, nothing new to record); finishing a room fires that
room's big effect AFTER the chime lands (~2.5s later). Game logic lives in the
room node firmware (`sim/esphome/packages/game_*.yaml`) with a byte-for-byte
behavioral mirror in the sim (`sim/web/app.js` `resolveGame`); the sensor map
is `triggers.json` (entries with a `game` key). The server needs zero changes
— games resolve locally and POST plain `/api/run_effect`.

Buttons throughout are **30mm illuminated arcade buttons** (EG Starts 5-colour
kits, 5V LED + microswitch). Button LEDs wire straight to the node's 5V rail
(always lit — no GPIO spent on lamps, except NFM's WS2812 chain below).

## Gate — two-bank body press ("the pat-down")

- **Hardware:** 6 buttons in two banks of 3. The visitor lines their body up
  and presses a whole bank at once. Wiring: pads on **D0–D5** of the room S3.
  Pin budget: 6 buttons + LD2410C UART (2) + I2S (3) = **11/11 — this is the
  second exactly-full box after Cuddle** (relief valve if a pin is ever
  needed: bank LEDs could move off-rail, or the radar could go — decide then).
- **Logic** (`game_gate.yaml`, **bench-verified 2026-07-20** — 4-path harness
  test `sim/tools/gate_game_test.py`): pads carry a 350ms `delayed_off` hold,
  so "simultaneous" = all 3 of a bank ON together. Bank 1 → CorrectAnswer
  chime and arms a 30s stage window; bank 2 inside the window →
  **GateInspection** (room complete); bank 2 un-armed → WrongAnswer.
- **Placement: PENDING** — the sim shows the 6 pads side by side as a
  placeholder row only. The doorway radar trigger (GateInspection on entry)
  stays as-is alongside the game.
- Sim note: one click = the whole bank (you can't press 3 at once with a
  mouse); the real node genuinely requires all three.

## Deep Playa Handshake — five buttons, one winner

- **Hardware:** 5 buttons on **D0–D4** (+ radar UART + I2S = 10/11).
- **Logic** (`game_dph.yaml`): exactly one button (random) is the winner —
  CorrectAnswer and the winner re-rolls; the other four fire WrongAnswer.
  The winner persists across failed presses, so it's a real hunt.

## Bike Lock Room — two-question true/false quiz

- **Hardware:** 4 buttons on **D0–D3** (9/11): Q1-TRUE, Q1-FALSE, Q2-TRUE,
  Q2-FALSE, under a sign with two true/false questions (sign to be made).
- **Logic** (`game_bike.yaml`): correct button → CorrectAnswer and latches
  that question for 60s; wrong button → WrongAnswer and resets progress;
  both questions correct → chime then **BikeLockRoom**.
- **ANSWER KEY IS A PLACEHOLDER** (Q1=TRUE, Q2=FALSE) until the sign exists —
  edit the one lambda in `game_bike.yaml` (and the `correct` flags in
  `triggers.json`) when the real questions are written.

## Vertical Moop March — four standalone button pucks

- **Hardware:** 4 **wireless pucks**, no wire to the node box: XIAO ESP32-C3
  (from the spare pool — pucks don't need PSRAM) + one 30mm button on D1 +
  an 18650 on the XIAO's battery pads, in a small case. **Always-on**, ~12h
  day shift per charge — they join the fleet's nightly dusk-recharge flip.
  Flash target `hardware_c3.yaml`; nodes `rooms/moop-button-{1..4}.yaml`
  (API 6076–6079, MACs :10–:13).
- **Logic:** game rule **TBD** — for now every press fires the CorrectAnswer
  chime (`button.yaml` reused, 3s cooldown). The room's own node keeps its
  radar + audio unchanged.

## Monkey Room — button now, dance later

- Unchanged today: the silver-monkey pedestal microswitch fires
  **MonkeyBusiness** (its own celebration = the victory).
- **FUTURE (TBD, nothing built):** a night-time "do a dance / movement" win
  condition — candidate: LD2450 track jitter or LD2410C energy variance as a
  motion-intensity signal, gated to night hours; falls back to the button.

## Temple Room — future spec only

- No interaction this year; the node stays an API bench node. Placeholder for
  a future bespoke effect + interaction.

## No Friends Monday — truck Lights-Out

- **Hardware:** 5 lit arcade buttons in a row on the existing wooden truck
  model. **2 pins total**: buttons on ONE resistor-ladder ADC pin, lamps as a
  5-pixel WS2812 chain on one data pin (a spare HiLetgo 74AHCT125 from the
  sign build shifts the data line). + radar UART + I2S = 7/11.
- **Logic** (`game_lightsout.yaml`): classic 1-D Lights Out — pressing button
  n toggles lamps n−1/n/n+1; all five lit → chime then **NoFriendsMonday**,
  then the board re-scrambles (random, never solved). Starts on the fixed
  unsolved pattern 0b01010. Lamp state lives in the firmware bitmask; the
  WS2812 output component gets added on the hardware flash (state + POSTs are
  already in the package).

## BOM additions

| Item | Qty | Note |
|---|---|---|
| 30mm LED arcade buttons (EG Starts 5-colour 5-pk) | 24 → 5 pks | Gate 6, DPH 5, Bike 4, Moop 4, NFM 5 |
| XIAO ESP32-C3 | 4 | Moop pucks — from the existing spare pool ($0 if spares hold) |
| 18650 cells + holders | 4 | pucks; XIAO battery pads do the charging |
| Small puck cases | 4 | 3D-print or off-the-shelf |
| WS2812 pixels (5) + resistor-ladder Rs | 1 set | NFM truck; 74AHCT125 from sign spares |

## Bench & sim

- Sim: all 24 game triggers live in the panel/world now; games play with the
  same logic (Gate's one-click-per-bank simplification aside).
- Harness pokes: `call <host>:<port> press_pad pad=1..6` (gate),
  `press_shake n=1..5`, `press_bike n=1..4`, `press_truck n=1..5`,
  `press <room>` (moop pucks).
- `sim/tools/gate_game_test.py` = the 4-path gate regression (needs
  `run_node.sh gate -d` first).
