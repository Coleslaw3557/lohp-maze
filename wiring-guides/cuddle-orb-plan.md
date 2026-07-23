# Cuddle orb — Waveshare ESP32-S3 round display

A watching eye at the rear of Cuddle Cross, under the sensor box, plus a
gesture control surface.
Standalone Wi-Fi device; talks to the server over the existing REST API. Sim
preview lives behind the **Eye** button; layout `eye` key in
`sim/maze_layout.json`.

## Hardware (verified 2026-07-22 via esptool over /dev/ttyACM0)

- **Chip:** ESP32-S3 (QFN56, rev v0.2) — dual-core + LP core, 240 MHz, Wi-Fi + BT 5 LE
- **Memory:** 8 MB embedded PSRAM (the S3R8 variant), 16 MB flash (Puya, quad, 3.3 V)
- **USB:** native USB-Serial-JTAG (`303a:1001`), enumerates as `/dev/ttyACM0`
- **Base MAC / USB serial:** `fc:01:2c:d1:e2:3c`
- **Board:** Waveshare **ESP32-S3-Touch-LCD-1.28** (round puck, wireless-charge
  plate + case). Per Waveshare's spec — confirm the exact SKU before ordering
  parts: round **1.28" 240×240 GC9A01 LCD**, **CST816** capacitive touch,
  **QMI8658** 6-axis IMU (inertial measurement unit: accel + gyro), Li-battery
  with onboard charging.

Four independent input channels — touch, tilt, shake, dock/undock — plus Wi-Fi.

## Placement

Mounted at the **rear of the room, directly under the back-corner sensor/node
box** (Tim's placement 2026-07-23; supersedes both the center-mast idea — the
display would sit inside the 3.5 in pole — and a high-on-the-canvas spot) —
facing the street/entry (`yaw_deg 0`), watching the deck from behind, on the
same plumb line as the LD2450 it reads. Under-box mounting keeps the orb off
the printed canvas and puts it beside existing power/wiring. Fix it
permanently over its **wireless-charge coil** so the battery stays topped (and
acts as a brownout UPS) and the puck **can't be pocketed** — a loose battery
puck in a maze becomes MOOP or walks off. The alternative is a deliberately leashed handheld talisman; pick one
early, it changes the enclosure. Real panel is 32.5 mm; the sim draws it larger
so the eye reads across the deck.

## Gaze — it actually watches

The eye tracks whoever the room's **LD2450** (24 GHz millimeter-wave position
radar) reports — the **same node-box radar the floor projection already reads**
(`projection` key; node box at `(10.044, -0.15)`), so **no new sensor**. The
pupil follows the nearest target's bearing with a first-order lag (~150 ms sensor
+ render), dilates/constricts as they get close, glows "awake" while a target is
fresh, drifts and blinks when the deck is empty.

## Two eyes (skins)

The environment is jungle / Mayan-themed, so the **Mayan** eye is the native
skin; **HAL** is a sci-fi easter egg.

- **`mayan`** — jade-and-gold jaguar/serpent deity eye: gold sun-stone rim with
  glyph ticks, carved jade sclera, amber iris with striations, an **obsidian
  vertical slit** that narrows when someone's close, jade eyelids that blink.
- **`hal`** — the 2001 red camera lens: brass bezel, gold ring, deep red lens,
  a hot white-yellow pupil that tracks and pulses, flicker "blink".

The sim's `drawMayanEye` / `drawHalEye` canvas code (`sim/web/app.js`) is the
**reference renderer** — the same shapes translate directly to LovyanGFX/TFT_eSPI
calls on the device. Other eye directions considered: Quetzalcoatl feathered-
serpent, full jade mosaic death-mask eye, cenote/water ripple. The jaguar/serpent
slit won for menace + animation.

## Trigger API wiring (the "wiring")

The orb is a **standalone Wi-Fi HTTP client** that POSTs to endpoints that
**already exist** in `main.py`. It is **not** a room-node sensor, so it stays out
of `triggers.json` (that file drives the ESPHome room-node codegen). It takes its
Wi-Fi credentials the same way the nodes do.

| Gesture (channel)            | HTTP call                                                      | Effect            |
|------------------------------|---------------------------------------------------------------|-------------------|
| **Shake** (IMU)              | `POST /api/run_effect_all_rooms` `{"effect_name":"LightningStorm"}` | Storm all rooms   |
| **Touch wheel / swipe** (CST816) | `POST /api/set_theme` `{"next_theme":true}` (or `{"theme_name":"<name>"}`) | Advance / pick theme |
| **Dock** on charger          | `POST /api/stop_effect` `{}`                                   | Calm / disarm all |
| **Undock**                   | (local) arm gesture mode                                      | —                 |

A circular screen is ideal for a **radial theme picker** drawn on the touch
panel; the wheel can call `/api/set_theme` with a specific `theme_name` per
wedge instead of just next.

## Firmware approach

Custom **Arduino / ESP-IDF** (LovyanGFX or TFT_eSPI for the eye + a small Wi-Fi
HTTP client), **not ESPHome** — rich per-frame animation is painful in
LVGL-under-ESPHome, and the orb isn't a DMX/sensor node. 8 MB PSRAM / 16 MB flash
is ample for a full-frame graphics buffer and a generous partition layout.

## Sim preview

- **Eye** button (top row) cycles **off / HAL / Mayan** (persisted in
  localStorage, like the Steel button). Default `hal` (`skin` in the layout).
- Climb to the **Cuddle Cross** upper deck and look to the rear — it hangs
  just under the back-corner node box; walk around inside that box's radar
  wedge and the pupil tracks you.
- Delete the `eye` key from `sim/maze_layout.json` to drop the orb entirely.

## Open TBDs

- Confirm the exact Waveshare SKU (touch/IMU part numbers, wireless-charge kit).
- Gaze sign: flip `gx` in `updateEye` if the pupil reads reversed on the real
  panel (the disc mirrors left/right; commented at the flip point).
- Theme-wheel UX: radial per-theme picker vs. simple next-advance.
- Confirm dock = stop-all is the wanted "calm" behavior.
- Mount-permanently-over-charger vs. leashed-handheld decision.
