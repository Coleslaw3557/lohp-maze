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
Physically each button's 4-wire JST lead lands in the room's **button pod**
(`../enclosure/button-pod/`, 2026-08-15) at the far end of the DB9-A cable —
pinouts and the pod recipe: `arcade-button-db9-prewire-guide.md`.

## Gate — two-bank body press ("the pat-down")

- **Hardware:** 6 buttons in two banks of 3. The visitor lines their body up
  and presses a whole bank at once. Wiring: pads on **D0–D5** of the room S3.
  Pin budget: 6 buttons + LD2410C UART (2) + I2S (3) = **11/11 — this is the
  second exactly-full box after Cuddle** (relief valve if a pin is ever
  needed: bank LEDs could move off-rail, or the radar could go — decide then).
- **Logic** (`game_gate.yaml`, **bench-verified 2026-07-20** — 4-path harness
  test `sim/tools/gate_game_test.py`): pads carry a 350ms `delayed_off` hold,
  so "simultaneous" = all 3 of a bank ON together. Bank 1 → CorrectAnswer
  chime and arms a 30s stage window; bank 2 inside the window → CorrectAnswer
  chime; bank 2 un-armed → WrongAnswer. Room entry/exit stays on the Gate
  radar occupancy trigger.
- **Placement: PENDING** — the sim shows the 6 pads side by side as a
  placeholder row only. The doorway radar trigger (GateInspection on entry)
  stays as-is alongside the game.
- Sim note: individual pad clicks are silent unless all three pads in the bank
  are clicked inside the same 350ms hold window, matching the real node.

## Deep Playa Handshake — five buttons, one winner

- **Hardware:** 5 buttons on **D0–D4** (+ radar UART + I2S = 10/11).
- **Logic** (`game_dph.yaml`): the doorway occupancy enter randomizes exactly
  one winning button. It fires CorrectAnswer; the other four fire WrongAnswer.
  The winner persists across failed presses, so it's a real hunt.

## Porto Room — three knock pads, one pass per entry

- **Hardware:** 3 piezo knock pads on **D0-D2** (+ radar UART + I2S + DMX = 9/11).
- **Logic** (`game_porto.yaml`): the doorway occupancy enter randomizes one
  winning pad. Attempt 1 always fires `PortoHit`; attempts 2-3 pass only on
  the winning pad; attempt 4 passes regardless so the visitor cannot get
  stuck. Vacate clears the seed and attempt count so the next entry re-rolls.
- **Hardware front-end** (`game_porto_hw.yaml`): each piezo ADC channel thresholds
  into the same `porto_press` script used by the sim/harness action.

## Bike Lock Room — two-question true/false quiz

- **Hardware:** 4 buttons on **D0–D3** (9/11): Q1-TRUE, Q1-FALSE, Q2-TRUE,
  Q2-FALSE, under a sign with two true/false questions (sign to be made).
- **Logic** (`game_bike.yaml`): correct button → CorrectAnswer and latches
  that question for 60s; wrong button → WrongAnswer and resets progress;
  both questions correct → chime then **BikeLockRoom**.
- **Answer key:** static for the room, not randomized. The `correct` flags in
  `triggers.json` drive the sim, and the audio console mirrors them into
  `sim/esphome/rooms/bike-lock.yaml` for the node firmware.

## Vertical Moop March — four buttons, one 60s round

- **Hardware:** 4 buttons on **D0–D3** (+ radar UART + I2S + DMX D5 =
  10/11), wired like every other game room: JST pigtails into the room's
  button pod, DB9-A pins 3–6 back to the node box.
  > Rev 2026-08-16: this replaces the wireless XIAO-C3 + 18650 **puck**
  > design (four battery boxes, their cases, and a nightly charging chore
  > to avoid one cable run in a room that already has a node box, a pod
  > standard, and a 12V bus drop — wrong trade; Tim killed it). The
  > `moop-button-{1..4}.yaml` nodes (API 6076–6079, MACs :10–:13) are
  > deleted and those ports/MACs are free again.
- **Logic** (`game_moop.yaml`): the first press opens a 60s round; every
  press fires the shared CorrectAnswer chime; all four unique buttons
  inside the round fire chime → 2.5s → `VerticalMoopMarch-RightAnswer`;
  the round timing out on a partial set fires
  `VerticalMoopMarch-WrongAnswer` and resets. Resolves **on the node**
  like the other games — the server's puck-era 60s aggregation in
  `main.py` is gone.

## Monkey Room — button now, dance later

- Unchanged today: the silver-monkey pedestal microswitch fires
  **MonkeyBusiness** (its own celebration = the victory). LIVE on the real
  node box 2026-08-16 — physical press → effect + par + Pebble validated.
- **FUTURE (TBD, nothing built):** a night-time "do a dance / movement" win
  condition — candidate: LD2450 track jitter or LD2410C energy variance as a
  motion-intensity signal, gated to night hours; falls back to the button.

## Temple Room — future spec only

- No interaction this year; the node stays an API bench node. Placeholder for
  a future bespoke effect + interaction.

## No Friends Monday — truck Lights-Out

- **Hardware:** 5 lit arcade buttons in a row on the existing wooden truck
  model (confirmed real, 2026-07-22). **2 pins total**: buttons on ONE
  resistor-ladder ADC pin (D0), lamps as a 5-pixel addressable chain on one
  data pin (D1; a spare HiLetgo 74AHCT125 from the sign build shifts the
  data line — shifter lives IN THE BOX fed 5V, so DB9-A pin 4 carries
  5V-level data down the cable). + radar UART + I2S + DMX = 9/11.
- **Shifter chip received 2026-07-23** — the SN74AHCT125N 10-pack is the
  bare PDIP-14 (~21 × 10 mm over the legs), no breakout board. Mount =
  **dead-bug**: glue the chip on its back, legs up, at the **etched AHCT
  zone** (back-center of the universal floor since the 07-24 layout pass;
  the other 14 rooms leave it empty) — VHB or CA/epoxy, not hot glue,
  boxes bake on playa. Legs-up MIRRORS the pinout: with the notch pointing away, pin 1
  becomes the far-RIGHT leg — paint-mark pin 1 BEFORE gluing. Wire gate 1
  only: pin 14 = 5V, pin 7 = GND, pin 1 (1OE̅) = GND, pin 2 (1A) ← XIAO
  D1 (GPIO2), pin 3 (1Y) → 33–100Ω right at the leg → the DB9 breakout's
  pin-4 screw. Ground every unused input and enable (pins 4, 5, 9, 10,
  12, 13 — one bus wire back to pin 7); outputs 6/8/11 stay unconnected.
  0.1µF ceramic across pins 14–7 at the legs; zip-tie the loom to the
  floor — dead-bug joints fail by wire-tug, not by glue. (The sign's own
  chip stays socketed per `camp-sign-wiring-guide.md`.)
- **Lamps come from Tim's strip stash — any 5V addressable (WS2812B/SK6812
  class), NOT 12V WS2811 sign stock** (DB9-A pins 1/2 supply 5V). Set
  `truck_chipset`/`truck_rgb_order` in the flash substitutions to match the
  strip grabbed; nothing is purchased for this.
- **Ladder values** (10k top resistor 3V3→ADC node; each button grounds the
  node through its own R): btn1 = wire (0.00V), btn2 = 2.2k (0.60V),
  btn3 = 4.7k (1.06V), btn4 = 10k (1.65V), btn5 = 22k (2.27V), open = 3.3V.
  Decode windows at the midpoints, 2-sample confirmation — implemented in
  `game_lightsout_hw.yaml`.
- **Logic** (`game_lightsout.yaml`): classic 1-D Lights Out — pressing button
  n toggles lamps n−1/n/n+1; all five lit → chime then **NoFriendsMonday**,
  then the board re-scrambles (random, never solved). Starts on the fixed
  unsolved pattern 0b01010. Lamp state lives in the firmware bitmask;
  `game_lightsout_hw.yaml` is the hardware-flash companion that renders the
  bitmask to the chain (50ms addressable lambda) and decodes the ladder
  (state + POSTs are already in the base package).

## BOM additions

All rolled into **`../shopping-list.xlsx`** — the one shopping list (Totals
tab + a tab per room). Summary:

| Item | Qty | Note |
|---|---|---|
| 30mm LED arcade buttons (EG Starts 5-colour 5-pk) | 24 → 5 pks | Gate 6, DPH 5, Bike 4, Moop 4, NFM 5 |
| WS2812 pixels (5) + resistor-ladder Rs | 1 set | NFM truck; 74AHCT125 from sign spares (10-pack received 07-23) |

## Bench & sim

- Sim: all 24 game triggers live in the panel/world now; games play with the
  same logic (Gate's one-click-per-bank simplification aside).
- Harness pokes: `call <host>:<port> press_pad pad=1..6` (gate),
  `press_shake n=1..5`, `press_bike n=1..4`, `press_truck n=1..5`,
  `press_moop n=1..4`, `press <room>` (single-button rooms).
- `sim/tools/gate_game_test.py` = the 4-path gate regression (needs
  `run_node.sh gate -d` first).
