# Going Wireless: Sensor-Node Recommendations

The wiring pain and the flaky lasers share one fix: put a ~$5 WiFi microcontroller in each room
with a one-sided sensor, and have it fire the **exact same HTTP POST the unit Pis used to fire**
(`POST /api/run_effect {"room": ..., "effect_name": ...}`). Zero server changes. The unit Pis
A/B/C are gone entirely — sensing lives on the nodes, per-room audio moved to the same node
boxes (`wiring-guides/room-node-audio-plan.md`), and the ONE remaining Pi is the server.

## Why the cheap lasers failed (so we don't repeat it)

- A collimated laser dot must stay on a few-mm² receiver across the doorway; temporary structures
  flex with temperature and wind, so alignment drifts daily.
- The 5V receiver modules are bare photoresistors with a threshold — no modulation, no ambient-light
  rejection. Sunlight, art cars, or your own DMX wash holds them on or off.
- Dust films both lenses and scatters the beam; day-1 calibration is wrong by day 3.
- Visible lasers at eye height in a dark maze are an eye-safety liability.

Everything below is either one-sided (nothing to align across the gap) or modulated/radar-based.

## Recommended architecture

**Node:** Seeed XIAO ESP32-S3 ($7.49) — the fleet standard since the 2026-07-18 audio revisit
(`wiring-guides/room-node-audio-plan.md`): same footprint and external antenna as the C3, plus
8MB PSRAM + 8MB flash, which the per-room speaker chain requires (dual media+announcement audio
pipeline — music bed and effect cues mixed on-device). C3s already on hand stay as bench units
and spares; a C3 pressed into audio duty can only do effect cues OR music, never both at once.
Pin note: wiring is keyed to XIAO Dx positions; GPIO numbers differ per board (D1 button = GPIO2
on S3 vs GPIO3 on C3; I2S D8/D9/D10 = GPIO7/8/9 on S3).

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
  logic: !include packages/logic.yaml   # wifi (static IP, power_save_mode: none), OTA, api, http_request — see sim/esphome/packages/
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

## Power (generator covers evening/night; banks cover only the ~12h day shift)

**Topology (2026-07-19 v5, Tim's calls): the generator IS the night power — it runs all
evening/night, the same AC that feeds the DMX fixtures along the back scaffolding. USB
battery banks (the EXISTING on-hand fleet, $0, buy none) only bridge the daytime, and they
recharge overnight at their own boxes while the generator is up.** No power stations, no
long 5V runs, no charge-rack rotation. Per room the load is ~0.2A of node plus a Pebble.

- **Night (generator up):** each box's gear runs off a small AC→USB wall cube plugged into
  the backstage runs the fixtures already use, and the room's bank recharges on the same
  cube. Raid the wall-cube drawer first — a room needs ~3 A-ports at night (node + Pebble +
  bank input, ~15W); one 6-port PowerPort-6-class charger shared between two adjacent rooms
  (7ft apart, 10ft leads) also works if buying gap-fill.
- **Day (generator off):** the bank carries the box. A ~12h day shift runs ~15-25Wh (~1W
  node steady + lighter daytime Pebble duty) — **a 10000mAh bank (~24Wh usable) covers a
  full day; 20000mAh does it with a skipped-morning of margin.** Any on-hand bank
  ≥10000mAh qualifies; put the big ones in loud rooms and on the server.
- **The daily flip (10 seconds per room):** dawn — node + Pebble plugs move cube → bank;
  dusk — plugs move back to the cube, bank lead onto the cube's third port. **Banks that
  pass through cleanly skip the flips entirely**: leave the bank inline 24/7 and just feed
  its input from the cube at night (a brief output blip when the input plugs in = one node
  reboot at dusk, harmless — but a bank that won't output while charging must use flips).
- **Banks: existing on-hand units, buy none.** Per-bank requirements: **≥2 outputs with at
  least one USB-A** (the Pebble's captive plug is A-male; the node takes A or C) and it
  must **hold the box's ~0.2A load without auto-off** — 10 minutes under a node, cull
  flunkers to phone duty. Mixed brands/sizes fine; sharpie a number on each. Need = 16
  (15 rooms + mast router) + spares. Top-up reference if short (listings checked
  2026-07-19): Miady 2-pack 20000mAh $28.99/pair (B0GQM3SB65) or INIU single $29.99
  (B0DFLSQBHT).
- **Auto-off is a non-issue at this load:** the box draws ~0.2A *continuously* (S3 WiFi +
  radar/ToF + DAC), 3-4× above the ~50-60mA "phone finished charging" cutoff cheap banks
  use, and the Pebble idles on top. The v3 lesson stands — every brand hides low-current
  timers somewhere — so the safety case is load math plus the per-bank test, not brand
  trust.
- **In-box wiring unchanged:** radar VCC + DAC VIN tap the XIAO's 5V pin (~105mA); no other
  power electronics in the box. **Velcro the bank OUTSIDE the box** (lid or the scaffold
  tube beside it): flips without opening the box, no battery heat inside, and shade it.
- **The two non-room day loads:** the server RPi (~4-6W → 50-70Wh/day, the biggest single
  draw — earmark the largest on-hand bank or a pair for it) and the mast router (~2W →
  ~25Wh/day; charge its bank in place overnight via a 10ft A-extension from the nearest
  backstage cube — charge current tolerates the droop — or swap it daily).
- **Why not stations / one central battery (v3, superseded):** 3× SOLIX C300 + mandatory
  chargers ≈ $840 of UPS behavior for a system whose night power is the generator anyway.
  The 5V physics is unchanged — 30-50ft at these currents drops half a volt — which is
  exactly why banks and cubes sit AT the boxes.
- **Bench gate (per-bank, before install week):** 10 minutes under a node (auto-off cull),
  plus the pass-through check — does the output stay live while the input charges? Sort
  the fleet into "inline 24/7" and "flip" piles. Overnight-test one representative bank +
  node + Pebble with audio duty-cycling (ESPHome uptime sensor = the witness).

## Per-box kit (what one room's enclosure gets)

**Identical in all 15 rooms** — the audio/brain core: XIAO ESP32-S3 ($7.49) +
PCM5102A DAC ($4.44) + 3.5mm cable + Creative Pebble 2.0 pair ($20.99, mounted
off-box) + an on-hand USB bank velcro'd at the box for the day shift and a
wall cube on the night generator AC (see Power).
One firmware family; a room's YAML just picks its sensor package.

**Differs per room** — the sensor pack:

| Rooms | Sensor pack |
|---|---|
| 10 wing bays (Monkey, Temple, NFM, Cop Dodge, Gate, Bike Lock, Deep Playa, Photo Bomb, Porto, Sparkle) | LD2410C radar |
| Cuddle Cross | LD2410C + hex 4-button termination (+ LD2450 later, projection subsystem) |
| Entrance / Exit | VL53L1X ToF (through the START/FINISH arch) |
| Guy Line Climb / Vertical Moop March | VL53L1X ToF (across the shaft arch) |
| Monkey (add-on) | puzzle microswitch, 2-wire to the box |
| Photo Bomb (add-on) | shutter arcade button, 2-wire to the box |
| Porto (add-on) | 3 piezo discs + ADC front-ends |

## Budget (15 rooms, mid-2026 street prices)

| Item | Qty | Ext |
|---|---|---|
| XIAO ESP32-S3 (15 rooms + 3 flashed spares) | 18 | $135 |
| LD2410C mmWave (presence rooms) | 10 | $45 |
| VL53L1X ToF (doorway tripwires) | 6 | $39 |
| M18 through-beam pairs (problem doorways) | 2 | $31 |
| AM312 PIR (spares/backup) | 5 | $7 |
| PCM5102A I2S DAC 2-packs (amzn B0DNW32Y46; 15 rooms + 1 spare) | 8 | $71 |
| Creative Pebble 2.0 pairs ($20.99 ea, **minus pairs on hand**) | ≤15 | ≤$315 |
| 3.5mm M-M cables + second wall-cube ports for the Pebbles | — | $40 |
| Wooden node enclosures (shop-built — see room-node-enclosure-plan.md) | 15 | — |
| USB battery banks — EXISTING on-hand fleet, day shift only (16 + spares; Miady 2-pk $29 = top-up ref) | — | $0 |
| Night AC→USB wall cubes (~3 A-ports/room off the fixture runs — raid the drawer; PowerPort-6-class 1-per-2-rooms fills gaps) | ≤8 | $0–50 |
| USB runs: 16× A-to-C 1ft (bank/cube→node) + 4× USB-A 10ft extensions (far Pebble mounts + router charge lead) | ~20 | ~$50 |
| GL.iNet travel router (mount it high on the 20ft center mast) | 1 | $29 |
| Boost modules, JST leads, velcro, misc | — | $30 |
| **Total** | | **≈ $790–840 minus owned Pebbles** (power share ≈ $50 of cables + cube gap-fill — v3's station scheme was ≈ $940) |

Audio rows land the whole per-room chain at ~$12 of electronics + a Pebble per room; the
node's speaker replaces the three Pi units A/B/C outright (camera already lives on the server
Pi, and Cuddle projection renders from the server Pi's HDMI). The whole system runs on exactly
ONE Pi; A/B/C leave the fleet — no spares.

That's roughly what the old multi-conductor cabling alone cost, and per-room install drops from
"pull and terminate a home run to the Pi" to "screw one box to the wall and plug it in."
AliExpress prices swing 2–3× with sales; Amazon multi-packs are the stable reference.

## Audio: consolidate the three Pis to one (SUPERSEDED 2026-07-18)

> Superseded by **per-room audio on the nodes**: XIAO S3 → PCM5102A line-out →
> Creative Pebble at every box, effect cues compiled into node firmware, music
> streamed from the server's `/api/audio/` — plan in
> `wiring-guides/room-node-audio-plan.md`, server downlink in
> `node_audio_manager.py` + `node_audio_config.json`, firmware in
> `sim/esphome/packages/audio_s3.yaml` (+ generated cues), bench node
> `sim/esphome/bench-xiao-s3.yaml`. The single-Pi mode below still works and
> remains the fallback if the S3 bench disappoints — both paths run the same
> server code, and the WS client protocol stays live for the sim regardless.

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
their existing per-unit configs — both modes run the same code. The consolidated config can
even run on the server box itself (USB dongles in the server,
`client/` container alongside it) for a one-box-plus-ESP32s system — with `triggers: []` the
client skips the Pi GPIO stack entirely; just remove the `/dev/gpiomem` and `/dev/i2c-1` device
lines from `client/docker-compose.yml` on a non-Pi host.

One caution for the transition: don't leave the consolidated client and the old units connected
at once. The server sends each room's audio to EVERY client that claimed it, so a parallel
run means per-room and whole-maze audio play on both systems simultaneously. Test nights
should run one audio client at a time.

Adds to the BOM: 3 × USB sound dongles (~$30), replaces two Pi power feeds.

## Migration plan

1. Bench-build one node + VL53L1X and one node + LD2410C; point them at the dev server and watch
   `/api/run_effect` fire. The server can't tell an ESP32 trigger from a Pi trigger.
2. Build the fleet: the shared packages (`sim/esphome/packages/`) + one substitution file per room, checked in here. Label each
   enclosure with node name = room = static IP suffix. Flash 3 spares.
3. At the maze: mount each labeled box at its clamp point (`wiring-guides/room-node-enclosure-plan.md`)
   and power it. (The old Pi harnesses are already history — units A/B/C were decommissioned
   2026-07; `triggers.json` at the repo root is the canonical sensor→effect map.)
4. Audio: bench the S3 speaker chain (`sim/esphome/bench-xiao-s3.yaml` + the checklist in
   `wiring-guides/room-node-audio-plan.md`), then migrate rooms into `node_audio_config.json`
   one at a time — the node path is additive beside the WS fallback client, so a room can run
   both for a test night.
