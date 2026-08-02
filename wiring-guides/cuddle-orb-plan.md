# Cuddle orb — Guition JC3636W518C round display

A watching eye at the rear of Cuddle Cross, under the sensor box, plus a
gesture control surface.
Standalone Wi-Fi device; talks to the server over the existing REST API. Sim
preview lives behind the **Eye** button; layout `eye` key in
`sim/maze_layout.json`.

## Hardware (identified for real 2026-07-23 — it is NOT a Waveshare)

- **Board:** Guition **JC3636W518C** (Shenzhen Jingcai "JCZN"; SKU sticker
  1012003, batch 2520) — round **1.8" 360×360 IPS**, **ST77916** panel over
  **QSPI**, **CST816D** capacitive touch (chip id 0xB6), **QI wireless power
  receiver** (feeds the 5 V rail; USB wins over QI when both present), 3.5 mm
  line-out via PCM5100A I2S DAC, I2S mic, TF slot, one button (K1 = GPIO0
  boot strap).
- **No battery and no IMU.** Official spec sheet + a community teardown agree;
  the QI receiver's status pins are unconnected, there is no charger IC and no
  battery ADC. Consequences: shake and dock/undock gestures have no onboard
  sensor (see trigger table), unplugging = fully off (which makes recovery
  easy), and the mounted orb needs a continuously powered QI pad or USB feed.
- **MCU:** ESP32-S3R8 (QFN56 rev v0.2) — 16 MB quad flash (eFuse-set QIO),
  8 MB octal PSRAM, native USB-Serial-JTAG `303a:1001` → `/dev/ttyACM0`.
  Unit #2 (working, flashed): MAC `fc:01:2c:d2:5d:d4`. Unit #1 (bench brick,
  recoverable): MAC `fc:01:2c:d1:e2:3c` — see Flash safety + recovery.
- **Wiring generation:** the W518 family shipped two PCB wirings plus a
  knob-shaped sibling (JC3636K518, source of the bogus "CS=14" pin lists).
  This unit is the **original 2024 wiring**, proven electrically with
  `firmware/orb-diag/` (CST816 ACKs on SDA=7/SCL=8 right after a GPIO40 reset
  pulse; the mid-2025 wiring's PCA9554 expander is absent). Full pin map and
  the family story live in `firmware/orb/board.h`. Key pins: QSPI CS=10 SCK=9
  D0–D3=11/12/13/14, LCD_RST=47, backlight=15 (MOSFET, PWM-able), touch SDA=7
  SCL=8 RST=40 INT=41, audio unmute XSMT=48.

Input channels that physically exist: touch, the K1 button, Wi-Fi.

## Flash safety + recovery

- **Never assign GPIO19/20** (native USB D−/D+). Unit #1 "bricked" exactly
  this way: the 07-22 I2C pin-sweep sketch ran `Wire.begin` on GPIO20 every
  3 s, killing USB seconds after each boot. It is not dead: **hold K1 while
  plugging USB** → ROM download mode → `esptool erase-flash` → reflash. After
  manual download mode esptool can't auto-reset; power-cycle when done.
- Full 16 MB factory image of unit #2:
  `~/lohp/orb-backups/jc3636w518c_fc-01-2c-d2-5d-d4_factory.bin`
  (sha256 `ec0e7804…`). Restore with `esptool write-flash 0x0 <file>`.
  Vendor firmware is also mirrored publicly (td0034/JC3636W518 on GitHub,
  `9-Burn` folder).
- esptool **stub** reads stall on this unit at one content-poisoned 4 KB page
  (0xC0000): use `--no-stub` for flash reads.
- Use USB-A→C cables; C-to-C often fails to power the board (no CC resistors
  per the V1 schematic).

## Placement

Mounted at the **rear of the room, directly under the back-corner sensor/node
box** (Tim's placement 2026-07-23; supersedes both the center-mast idea — the
display would sit inside the 3.5 in pole — and a high-on-the-canvas spot) —
facing the street/entry (`yaw_deg 0`), watching the deck from behind, on the
same plumb line as the LD2450 it reads. Under-box mounting keeps the orb off
the printed canvas and puts it beside existing power/wiring. Fix it
permanently over its **QI coil** — with no battery on board the coil is the
orb's continuous power feed, not a charger, so a pocketed puck dies within
arm's reach of the mount (better anti-theft than a leash). The alternative is a deliberately leashed handheld talisman; pick one
early, it changes the enclosure. Real panel is 32.5 mm; the sim draws it larger
so the eye reads across the deck.

## Gaze — it actually watches

The eye tracks whoever the room's **LD2450** (24 GHz millimeter-wave position
radar) reports — the **same node-box radar the floor projection already reads**
(`projection` key; node box at `(10.044, -0.15)`), so **no new sensor**. The
pupil follows the nearest target's bearing with a first-order lag (~150 ms sensor
+ render), dilates/constricts as they get close, glows "awake" while a target is
fresh, drifts and blinks when the deck is empty.

## The face — Olmec talking head (2026-07-23; the archaeological-basalt
version and the HAL/Mayan skins are both retired)

One full-screen face: a **Legends of the Hidden Temple-style Olmec homage** —
warm terracotta stone, stepped headdress with muted turquoise inlays and
carved bosses, ear spools, one heavy straight brow, broad flat nose, and the
signature **sliding lower-jaw slab in its carved slot**. The authoritative
renderer is the per-pixel shader in `firmware/orb/face_olmec.h` (height
field → normals → two-light terracotta shading), shared verbatim with
`firmware/orb/tools/preview_face.cpp` so the identical image renders on the
host for art iteration before flashing.

Movement: big white eyes that **light up** (warm glow + halo) while the radar
holds a target, pupils tracking with saccades and a first-order lag, nostrils
breathing on a 5.2 s cycle — and the **jaw talks**: idle chatter episodes
every 20–35 s, a short "notices you" drop when someone appears, syllable-like
open/close motion from layered sines, and a warm light inside the mouth void
while speaking. No eyelids, no blinks — the TV prop has none; presence comes
from the glow and the jaw. During each gesture POST the jaw holds open
(mid-sentence) instead of the face freezing. The board's 3.5 mm line-out is
the obvious future hook for actual voice lines synced to the jaw.

## Trigger API wiring (the "wiring")

The orb is a **standalone Wi-Fi HTTP client** that POSTs to endpoints in
`main.py`. It is **not** a room-node sensor, so it stays out of `triggers.json`
(that file drives the ESPHome room-node codegen). It takes its Wi-Fi
credentials the same way the nodes do.

**The orb is the whole Cuddle control surface** (decided 2026-07-23): no
arcade/wall buttons in this room — every guest control is a touch gesture on
the face.

**Touch menu (2026-07-23, supersedes the blind-gesture vocabulary):** any
touch on the idle face opens a carved stone wedge menu (`menu_olmec.h`, same
height-field + `shadePixel` idiom as the face, prerendered to PSRAM at boot,
~full-screen blit to open). Five wedges with gold-inlaid glyphs, clockwise
from the top; a stepped-pyramid hub medallion or 8 s idle closes it. Presses
select on release (slide off to cancel); the storm wedge instead charges on a
1 s hold with an ember sweep, so a stray poke can't fire it. The jaw drops
and "speaks" through each POST, like every orb action.

| Wedge (glyph)          | HTTP call                                                      | Effect            |
|------------------------|---------------------------------------------------------------|-------------------|
| **LIGHTS** (sun, top)  | `POST /api/set_theme` `{"next_theme":true}`                    | Next lighting theme |
| **AMBIENCE** (pan pipes) | `POST /api/toggle_maze_ambience` `{}` | Maze ambience on / off |
| **STORM** (bolt) — hold 1 s to charge | `POST /api/run_effect_all_rooms` `{"effect_name":"LightningStorm"}` | Storm all rooms |
| **FLOOR** (serpent coil) | `POST /api/next_floor_theme` `{}` (or `{"theme":"<name>"}`) — main.py relays to the floor renderer's `:5002` theme control (`POST /theme/next`; the sim serves the identical protocol on the bench, `sim_ui._start_floor_ctl`) | Floor projector theme (lava/jungle/temple) |
| **CALM** (closed eye)  | `POST /api/stop_effect` `{}` — the menu finally gave calm a home (no dock/charge signal exists on this hardware for the original dock-to-calm idea) | Stop effects everywhere |

Preview the menu art without flashing: `tools/preview_face --menu out.rgb
[wedge amt]` (same host-preview flow as the face). A per-theme radial picker
(wedge per named theme) remains a possible future layer on the same menu
machinery.

**CST816 quirk (2026-07-23):** the touch chip's reports go quiet in spurts
while a finger rests dead still — a raw "no finger" mid-hold is a report gap,
not a lift. The firmware latches "down" through gaps and only treats 220 ms of
true silence as a release; hold-to-fire wedges additionally require a raw
report at the firing moment, so an early lift can never phantom-fire the
storm. (Before the fix, the storm charge canceled and restarted on every gap —
visible as a sweep that never completes.)

## Firmware (LANDED 2026-07-23 — `firmware/orb/`)

Custom **Arduino** sketch (Arduino_GFX 1.6.7 — its bundled `JC3636W518`
profile is this exact wiring — on esp32 core 3.3.11), **not ESPHome** — rich
per-frame animation is painful in LVGL-under-ESPHome, and the orb isn't a
DMX/sensor node. `./build.sh flash` compiles + USB-flashes; `./build.sh
monitor` for serial; `gen_secrets.sh` pulls Wi-Fi credentials from
`sim/esphome/secrets.yaml` (same network as the nodes). **ArduinoOTA** is in
(hostname `lohp-orb`, two 3 MB OTA slots) so the mounted orb reflashes over
Wi-Fi.

Render architecture: the terracotta head shades **once at boot** (~4.4 s
carve, two-pass: height/recess field → neighbor-difference normals) into a
PSRAM base layer, full-screen flushed once; the jaw slab prerenders once into
a small tile. Per frame only the two eye rects repaint (glow pulses, pupils
move); the jaw region repaints only while the slab moves or the void glow
changes (composite: restore the slot from base → light the void → drop the
tile in at the current jaw position), the nostril rect only on breath steps.
**Measured ~48 fps**, frame 9 ms idle (eyes 6.3 ms, jaw ~0 between chatter).
Build is `-O2` (`-Os` default was 3× slower on the shader). Boot: RGB sweep
(panel proof) → ~4 s carve → face.

Managing the device:

- `./build.sh flash` — USB flash (writes app0)
- `./build.sh ota [host]` — Wi-Fi reflash via espota port 3232 (default
  `lohp-orb.local`; use the IP if mDNS is slow). Password = `OTA_PASSWORD` in
  `secrets.h` (gen_secrets sets it to the Wi-Fi password). OTA writes the
  inactive app slot; the boot banner prints `running from app0|app1` — that
  label is the ground truth for whether an OTA landed.
- `./build.sh monitor` — serial console at 115200
- Unbrick / factory restore: see Flash safety + recovery above.

## Sim preview

- **Eye** button (top row) toggles **off / Olmec** (persisted in
  localStorage, like the Steel button). Default `olmec` (`skin` in the
  layout); the sim's `drawOlmecFace` is a canvas stand-in — the device shader
  is authoritative.
- Climb to the **Cuddle Cross** upper deck and look to the rear — it hangs
  just under the back-corner node box; walk around inside that box's radar
  wedge and the pupil tracks you.
- Delete the `eye` key from `sim/maze_layout.json` to drop the orb entirely.

## Open TBDs

- **LD2450 gaze relay**: server-side endpoint (or UDP push) feeding the orb the
  same radar targets the floor projection reads; firmware hook is the synthetic
  attention block in `orb.ino`.
- ~~Calm gesture design~~ RESOLVED 2026-07-23: the touch menu's CALM wedge
  (`/api/stop_effect`). K1 remains the one free physical input for future use.
- Theme-wheel UX: radial per-theme picker vs. simple next-advance.
- Gaze sign: set `GAZE_FLIP_X 1` in `board.h` if the pupil reads reversed on
  the real panel.
- Rescue unit #1 (hold K1 while plugging USB, erase, reflash) — and confirm the
  cased C_I_Y exposes K1 without opening the puck.
- Battery contradiction: listings claim one, docs + teardown say none. If a
  unit keeps running off-pad with USB out, revisit (would also revive dock
  detect via a VBAT ADC like the knob sibling's GPIO1).
- Eyeball the panel: colors (invert), orientation, `GAZE_FLIP_X` in `board.h`
  if the gaze reads mirrored.
- Optional: cache the carved base image to the FAT partition to skip the ~4 s
  boot carve.
