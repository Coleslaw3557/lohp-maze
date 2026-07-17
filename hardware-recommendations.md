# Going Wireless: Sensor-Node Recommendations

The wiring pain and the flaky lasers share one fix: put a ~$5 WiFi microcontroller in each room
with a one-sided sensor, and have it fire the **exact same HTTP POST the Pis fire today**
(`POST /api/run_effect {"room": ..., "effect_name": ...}`). Zero server changes. The Pis stay
for what they're good at — audio playback — with their sensor harnesses, level shifters,
ADS1115s, and bridge panels simply unplugged.

## Why the cheap lasers failed (so we don't repeat it)

- A collimated laser dot must stay on a few-mm² receiver across the doorway; temporary structures
  flex with temperature and wind, so alignment drifts daily.
- The 5V receiver modules are bare photoresistors with a threshold — no modulation, no ambient-light
  rejection. Sunlight, art cars, or your own DMX wash holds them on or off.
- Dust films both lenses and scatters the beam; day-1 calibration is wrong by day 3.
- Visible lasers at eye height in a dark maze are an eye-safety liability.

Everything below is either one-sided (nothing to align across the gap) or modulated/radar-based.

## Recommended architecture

**Node:** Seeed XIAO ESP32-C3 (~$5) — external antenna (real RF through maze walls) and LiPo
charging built in. Budget alternative: ESP32-C3 SuperMini (~$2.50–4), but range-test the antenna
and buy 20% spares.

**Firmware: ESPHome.** Per-node YAML, no code, OTA updates, a debug web UI on every node, and
native drivers for every sensor below. One shared package + a 6-line file per room, all kept in
this repo. Pre-compile at home (the toolchain needs internet); on-site re-flashes are OTA from a
laptop. A whole trigger node is roughly:

```yaml
# rooms/entrance.yaml
substitutions:
  room: "Entrance"
  effect: "Entrance"
packages:
  common: !include common.yaml   # wifi (static IP, power_save_mode: none), OTA, api
binary_sensor:
  - platform: gpio               # break-beam / button; ld2410 & vl53l0x are also native
    pin: { number: GPIO3, mode: INPUT_PULLUP, inverted: true }
    filters: [delayed_on: 30ms]
    on_press:
      - http_request.post:
          url: http://192.168.1.238:5000/api/run_effect
          request_headers: { Content-Type: application/json }
          json: { room: "${room}", effect_name: "${effect}" }
```

**Network:** a dedicated 2.4GHz travel router inside the maze (GL.iNet Mango ~$29 or Opal ~$40 —
USB-powered, runs off a power bank), wired to the server's Ethernet port. Survey channels at night
with a phone WiFi analyzer, pin the emptiest of 1/6/11, WPA2, static IPs. Fifteen nodes sending
one tiny POST per event is a trivial WiFi load even in congested camp spectrum — congestion kills
throughput, and you need none. Keep ESP-NOW (native in ESPHome) as the break-glass re-flash if
assembled-maze testing shows real drops; don't start there, it needs a serial gateway and server
changes. Off-the-shelf Zigbee (Sonoff PIR + Zigbee2MQTT) is workable but adds MQTT plumbing and
only gives you sluggish PIR blobs — skip it.

## Sensor picks (all 3.3V-friendly, no level shifters)

| Use case | Primary | Fallback |
|---|---|---|
| Doorway crossing | **VL53L1X ToF (~$5–8)**: one-sided "virtual tripwire" on the jamb — beam across at hip height, trigger when range < doorway width. Invisible, eye-safe, nothing to align, I2C straight into the node. Recess it behind a small aperture and threshold generously (e.g. <60cm across a 90cm doorway) so dust-shortened readings don't false-trigger. | IR break-beam pair — Adafruit #2168-style ($6) for narrow dark doorways; industrial M18 through-beam pair (E3F-5DN1, ~$15 with brackets, needs a $1.50 5V→12V boost) where you want modulated, never-think-about-it-again certainty over longer spans. LED cone beam = far more alignment-tolerant than a laser. |
| Room presence | **HLK-LD2410C mmWave radar (~$4)**: sees moving *and stationary* people through plastic, so it lives **fully sealed inside the dust-proof box**. Dark-immune, zero alignment. Native ESPHome support. Tune max-gate distance so it doesn't see through thin walls into the next room. | AM312 PIR (~$1.50) where "someone moved, roughly" is enough — degraded on hot afternoons and slow to re-trigger, fine on cool nights. |
| Buttons / knock stations | Arcade buttons straight to node GPIOs (internal pull-ups + ESPHome debounce). **Implemented**: `sim/esphome/packages/button.yaml` + `button_gpio_c3.example.yaml` (GPIO3→GND) drive the Photo Bomb shutter button and the Monkey puzzle completion switch. Piezo discs to a node ADC pin with a 1MΩ bleed resistor, or a $1 LM393 knock module to a GPIO. | — |

The Monkey puzzle switch is just a button in disguise: a lever microswitch under the
silver monkey's top piece, closed when the assembly seats home, wired to the room
node like any arcade button (NO + COM → GPIO3/GND).

### Photo Bomb camera (implemented)

The camera does **not** go on a sensor node — a USB webcam (any UVC one, e.g. Logitech
C270) plugs into the server Pi next to the USB-DMX interface. The room's ESP32 button
fires `PhotoBomb-Shot` over the normal trigger contract; the server runs the
countdown/flash and `camera_manager.py` grabs the frame at the shutter moment
(fswebcam, in the Docker image). Photos land on the Pi's SD card in `photos/` with
date/timestamp filenames; browse via `GET /api/photobomb/photos`. The privileged
container already sees `/dev/video0`; `camera_config.json` (optional) overrides
device/resolution/paths.

Skip HC-SR04 ultrasonic entirely (sloppy cone, absorbs into costumes, units interfere, dust).

## Power (12-hour night runs; a node draws ~0.5W)

1. **Rooms with lighting power** (most of them): a $5 USB wall cube off the same feed as the DMX
   fixture. "Power-only wiring" — no data runs.
2. **Rooms without**: 20,000mAh USB power bank (~$22) runs the whole event. The classic trap is
   bank auto-shutoff at low draw — `power_save_mode: none` keeps the node above most cutoff
   thresholds, but **test one unit of the exact bank model before buying five**. Guaranteed
   option: Voltaic V25 "Always On" ($45). 18650 shields are cheaper but bare-cell logistics on
   playa aren't worth it; PoE splitters reintroduce the cable pulls this project is escaping.

## Budget (15 rooms, mid-2026 street prices)

| Item | Qty | Ext |
|---|---|---|
| XIAO ESP32-C3 (12 rooms + 3 flashed spares + 3 button stations) | 18 | $90 |
| LD2410C mmWave (presence rooms) | 10 | $45 |
| VL53L1X ToF (doorway tripwires) | 6 | $39 |
| M18 through-beam pairs (problem doorways) | 2 | $31 |
| AM312 PIR (spares/backup) | 5 | $7 |
| IP65 enclosures with cable glands | 15 | $75 |
| USB wall cubes | 10 | $50 |
| 20Ah power banks (pre-tested model) | 5 | $110 |
| GL.iNet travel router | 1 | $29 |
| Boost modules, JST leads, velcro, misc | — | $30 |
| **Total** | | **≈ $506** |

That's roughly what the old multi-conductor cabling alone cost, and per-room install drops from
"pull and terminate a home run to the Pi" to "screw one box to the wall and plug it in."
AliExpress prices swing 2–3× with sales; Amazon multi-packs are the stable reference.

## Audio: consolidate the three Pis to one (implemented)

Once the ESP32 nodes own all sensing, the Pis' only job is zone audio — and one Pi 4 with a
cheap USB sound dongle per zone (~$10 each, and they sound better than the Pi's headphone jack)
does the work of all three. The client now supports this directly: `client/config-single-pi.json`
maps each room to a zone and each zone to an ALSA device, and the server needs no changes
(it already names the room in every audio command). Pin the dongles' ALSA names to their USB
ports with `client/99-lohp-audio.rules` so identical dongles can't swap zones between boots.

The one physical constraint is audio cable geography: the three distributed Pis kept analog
line-level runs short. A central Pi wants either the zone amps consolidated next to it (then run
speaker-level wire out to the rooms — robust over these distances, unlike long unbalanced 3.5mm
runs on generator power), or it isn't worth doing. If the amps can't move, keep the three Pis on
their existing per-unit configs — both modes run the same code. The freed-up Pis become spares,
and the consolidated config can even run on the server box itself (USB dongles in the server,
`client/` container alongside it) for a one-box-plus-ESP32s system — with `triggers: []` the
client skips the Pi GPIO stack entirely; just remove the `/dev/gpiomem` and `/dev/i2c-1` device
lines from `client/docker-compose.yml` on a non-Pi host.

One caution for the transition: don't leave the consolidated client and the old units connected
at once. The server routes each room's audio to the first client that claimed it, so a parallel
run means per-room audio lands on whichever connected first and whole-maze audio plays on both
systems simultaneously. Test nights should run one audio client at a time.

Adds to the BOM: 3 × USB sound dongles (~$30), replaces two Pi power feeds.

## Migration plan

1. Bench-build one node + VL53L1X and one node + LD2410C; point them at the dev server and watch
   `/api/run_effect` fire. The server can't tell an ESP32 trigger from a Pi trigger.
2. Build the fleet: `common.yaml` + one substitution file per room, checked in here. Label each
   enclosure with node name = room = static IP suffix. Flash 3 spares.
3. At the maze: unplug the sensor harnesses/level shifters/ADS1115s from the Pis and delete the
   `triggers` arrays from `client/config-unit-*.json`. Pis keep doing audio unchanged.
4. Run both systems in parallel for a test night before ripping out the old wiring for good.
5. Optionally consolidate audio to one Pi (`config-single-pi.json`, section above) once the
   amp placement question is settled.
