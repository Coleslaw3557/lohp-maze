# Room node audio — per-room speakers on the ESP32 nodes (plan)

Decided direction 2026-07-18 (parts + ESPHome facts verified that day; prices
move). Companion to `room-node-enclosure-plan.md` — this doc adds audio to the
node boxes; it does not change any sensing geometry there.

## Why move audio off the Pis

Today audio is per-**zone**, not per-room: units A/B/C each drive one output
shared by 5 rooms (`client/config-unit-*.json`), so most visitors hear a
speaker several rooms away. Putting a speaker at every node box:

- puts sound ≤2.6 m from the visitor in every room (beats today's arrangement
  by proximity, not wattage);
- makes reality match the sim, which already spatializes audio per room;
- retires units A/B/C completely — after the sensor migration they were
  audio-only, the Photo Bomb camera lives on the server Pi, and Cuddle
  projection renders from the server Pi too. One Pi total; A/B/C leave the
  fleet, no spares kept.

## Node chip: XIAO ESP32-S3 for audio rooms

The legacy Arduino `i2s_audio` media player is **removed** from ESPHome
(2026.4); the only path is the modern `speaker` media player on ESP-IDF (which
`hardware_c3.yaml` already targets). Verified capability split:

| | XIAO ESP32-C3 (no PSRAM) | XIAO ESP32-S3 ($7.49, 8MB PSRAM + 8MB flash) |
|---|---|---|
| Embedded one-shot cues | ✔ (~300–600 KB flash budget) | ✔ (roomy) |
| Looping ambient from flash | ✔ (`speaker_source` + `repeat_one`) | ✔ |
| Stream music from `/api/audio/` | shaky (tiny buffers; `buffer_size` ≤ ~20 KB) | ✔ (buffered) |
| Music bed + stinger **mixed** | ✘ single pipeline — stinger interrupts music | ✔ dual media+announcement pipeline w/ ducking |
| Sample rates | 16–22.05 kHz mono WAV/FLAC | 44.1 kHz fine |

Today's behavior is music + effects mixing simultaneously, so **audio rooms
get the S3**. Same XIAO footprint → enclosure, cleats, and Dx-position wiring
unchanged; add a `hardware_s3.yaml` platform package (GPIO numbers differ per
Dx, see pin map). **Fleet-revisit recommendation: standardize ALL 15 nodes on
the S3** — one platform package, one pin map, one spares pool, and CPU/RAM
headroom for the heavy boxes (Cuddle runs two radars + four buttons + audio
on one chip). Existing C3s become bench units/spares. C3 fallback if one is
pressed into audio duty: stingers + a looped room-tone, no simultaneous
music.

## Speaker: line-level out, powered speaker — skip the amp board

The PCM5102A DAC board has a pre-soldered 3.5 mm stereo line-out jack, and the
**Creative Pebble 2.0 is 5 V-USB powered with a plain analog 3.5 mm input**
(verified: it is NOT a USB-audio device). So the already-owned Pebbles plug
straight into the DAC — no amplifier board, no speaker soldering, and the
volume knob comes built into the right satellite.

**Path A (default): XIAO S3 → PCM5102A → 3.5 mm cable → Creative Pebble 2.0.**
2 × 2.2 W RMS into 2-inch drivers + passive radiators, 100 Hz–17 kHz. Realistic
program peaks mid-80s dB @1 m → high-70s/low-80s at visitor distance: per-room
parity with today's zone speaker, at close range, in every room. Already
playa-proven in this maze.

Considered and passed on (2026-07-19): **Dell AC511/AC511M USB soundbar** —
it *would* drop in (Dell's manual confirms a 3.5 mm analog aux-in alongside
USB audio, plus USB power; renewed ~$20, eBay lots ~$10), but it's 2.5 W
total vs the Pebble's 4.4 W RMS and Amazon pricing ties a Pebble *pair* —
Tim's call: stick with Pebbles.

**Path B (compact/sealed alternative, only where dust-sealed matters):
PCM5102A → PAM8403-with-pot ($5.19, single board) → sealed 4 Ω speaker.**
The pot is confirmed panel-mountable (threaded bushing + nut included) and has
a built-in on/off switch. **Do not buy the CQRobot 4Ω3W pair for this** —
verified sensitivity is ~76–77 dB @1W/1m (≈81 dB @1 m flat out, mid-70s at
2.6 m): too quiet outdoors, and stock was 2 units. If Path B happens, pick a
speaker with ≥85 dB/W sensitivity. PAM8403 rules if used: absolute max 5.5 V,
no reverse protection, one full channel per speaker (L+/L−), never bridge L/R
together, never ground a speaker − terminal, 470–1000 µF across 5 V near the
amp.

### Verified parts (2026-07-18)

| Part | Price | Notes |
|---|---|---|
| PCM5102A DAC, purple GY board, 2-pack (amzn B0DNW32Y46) | $8.88/2 | Headers unsoldered; 3.5 mm line-out jack fitted; **all config jumpers ship unbridged — must solder** (below) |
| Creative Pebble 2.0 | $20.99/pair | 5 V USB-A power (≤1 A) + 3.5 mm analog in; knob on right satellite |
| XIAO ESP32-S3 (Seeed 113991114) | $7.49 | 8 MB PSRAM + 8 MB flash |
| PAM8403 w/ switch-pot (amzn B01DKAI51M) — Path B only | $5.19 | 30×22 mm, 3–5.5 V |
| 1N5817 Schottky | pennies | Only if feeding the XIAO's 5 V pin instead of its USB-C |

### PCM5102A board prep (5 solder bridges per board)

Back-side H/L jumpers ship open — bridge: **FLT→L, DEMP→L, XSMT→H (unmutes!),
FMT→L (I2S)**. Front: **bridge SCK to GND** (pads beside the SCK pin) so the
internal PLL derives the master clock from BCK — no MCLK pin from the ESP.
An unprepped board is silent; this is the #1 bring-up trap.

## Standard pin map (by XIAO Dx position — same physical wiring on C3 and S3)

| Dx | C3 GPIO | S3 GPIO | Reserved for |
|---|---|---|---|
| D0, D2, D3 | 2, 4, 5 | 1, 3, 4 | ADC / aux (Porto piezos; Cuddle LD2450 UART1 on D2/D3) |
| D1 | 3 | 2 | Button contract (`button_gpio_c3.example.yaml`) |
| D4 / D5 | 6 / 7 | 5 / 6 | I2C — VL53L1X (ToF rooms) |
| D6 / D7 | 21 / 20 | 43 / 44 | UART — LD2410C (radar rooms) |
| **D8** | **8** | **7** | **I2S BCLK → PCM5102A BCK** |
| **D9** | **9** | **8** | **I2S LRCLK → PCM5102A LCK** |
| **D10** | **10** | **9** | **I2S DOUT → PCM5102A DIN** |

D8–D10 (the unused SPI trio) is conflict-free in every room type — including
worst-case Cuddle (2 radar UARTs + 4 hex buttons + I2S = exactly 11/11 pins).
C3 note: GPIO8/9 are strapping pins but the DAC's inputs are Hi-Z, so boot is
unaffected. C3 Porto note: GPIO5/D3 is ADC2 (unusable with WiFi) — the three
piezos sit on D0/D1/D2.

## Power

- Box draw with audio idle: ESP ~80–100 mA + LD2410C ~79 mA + PCM5102A ~25 mA
  ≈ **200 mA @5 V** — above bank auto-off thresholds (and `power_save_mode:
  none` already enforces this). Pebble adds its own draw from a second bank
  port; music at party volume averages roughly +0.5–1 W.
- **Topology (2026-07-19 v5, Tim's calls): the generator IS the night power
  — it runs all evening/night (the same backstage AC that feeds the DMX
  fixtures). On-hand USB banks ($0, "assume I have them") bridge ONLY the
  ~12h day shift, recharging overnight at their own boxes.** NIGHT: box gear
  runs off a small AC→USB wall cube on the fixture runs, the room's bank
  charging on the same cube (~3 A-ports ≈ 15W per room; drawer cubes first,
  a 6-port PowerPort-6-class shared between two adjacent rooms fills gaps).
  DAY: the bank carries the box — ~15–25Wh per shift (~1W node steady +
  lighter daytime Pebble duty), so **any ≥10000mAh bank covers a full day**
  (~24Wh usable); big banks go to loud rooms and the server Pi (biggest day
  load, 50–70Wh; the mast router ~25Wh charges in place overnight via a 10ft
  A-extension — charge current tolerates the droop — or swaps daily). Daily
  flip = two 10-second plug moves per room (dawn: gear cube→bank; dusk:
  gear→cube, bank→charge port); **banks that pass through skip the flips**
  — leave them inline 24/7 and feed the input from the cube at night (the
  plug-in blip = one harmless node reboot at dusk; banks that won't output
  while charging use flips). Per-bank requirements: ≥2 outputs with at least
  one USB-A (the Pebble's captive plug is A-male; the node takes A or C),
  holds the ~200 mA load without auto-off (10-min node test, cull flunkers —
  the draw sits 3–4× over typical cutoffs), pass-through check sorts the
  fleet into inline-24/7 vs flip piles. Room plug set: Pebble captive A-male
  into an A port, node USB-C via a 1ft A-to-C; bank velcro'd OUTSIDE the box
  (flips without opening it, no battery heat inside, shaded). v3 (3× SOLIX
  C300 cluster stations, ~$840) superseded: the night problem is the
  generator's, and the day problem is bank-drawer sized. Unchanged physics:
  5V won't survive 30–50ft runs — banks and cubes sit AT the boxes. Top-up
  reference if the fleet runs short: Miady 2-pack 20000mAh $28.99
  (B0GQM3SB65) / INIU single $29.99 (B0DFLSQBHT). Bench gate before install
  week: one representative bank + node + Pebble through a full day-shift
  discharge with audio duty-cycling (ESPHome uptime sensor = the witness).
- **Wiring collapses without the amp board:** port 1 → XIAO USB-C; the
  radar's VCC and the DAC's VIN tap the XIAO's **5 V pin** (~105 mA combined,
  well within the pin's budget); port 2 → Pebble USB. No USB breakout board,
  no bulk capacitor, no Schottky — all three existed only to feed the amp
  (the 1N5817 is needed only when pushing power *into* the 5 V pin, not
  drawing from it).

## Enclosure + radar coexistence

- **DAC (and Path B amp) go inside the box; the speaker never does.** Two
  reasons from the enclosure plan: no metal (magnet!) within ~5 cm of the
  radar aperture, and a speaker vibrating the box injects micro-doppler into
  a radar listening for still-presence.
- Mount the Pebble satellites off-box: shelf bracket or zip-tie cradle on the
  scaffold leg **below** the box (street side stays clear), ≥5 cm from the
  radar window, cables through the existing gland alongside power.
- Interior cost is trivial: the DAC is 30×20 mm; the 15.8×20.8×8.8 cm interior
  absorbs it even in the Porto worst case. Path B pot mounts through a **side**
  wall (never the radar window panel).
- **Mock-bay protocol addition:** capture the empty-room radar baseline with
  the room's own audio playing at show volume (same reasoning as the box-fan
  wind rehearsal) so speaker vibration is inside the thresholds before they're
  locked.

## ESPHome sketch (S3, dual pipeline — simplified; the shipped firmware is `sim/esphome/packages/audio_s3.yaml`)

```yaml
i2s_audio:
  i2s_bclk_pin: GPIO7    # D8
  i2s_lrclk_pin: GPIO8   # D9
  # no i2s_mclk_pin — PCM5102A SCK pad bridged to GND

speaker:
  - platform: i2s_audio
    id: dac_out
    dac_type: external
    i2s_dout_pin: GPIO9  # D10
    sample_rate: 44100
    channel: mono
    buffer_duration: 100ms

media_player:
  - platform: speaker
    name: Room Audio
    id: room_audio
    media_pipeline:           # streamed music bed from /api/audio/<file>
      speaker: dac_out
      format: MP3
      sample_rate: 44100
      num_channels: 1
    announcement_pipeline:    # embedded effect cues, mixed/ducked over music
      speaker: dac_out
      format: WAV
      sample_rate: 22050
      num_channels: 1
    files:
      - id: cue_room_effect
        file: audio/<room-effect>.wav   # this room's stinger(s), 22.05k mono

api:
  actions:
    - action: play_cue        # server → node, ~100–300 ms to first sound
      then:
        - media_player.speaker.play_on_device_media_file:
            media_file: cue_room_effect
            announcement: true
```

The shipped package (`audio_s3.yaml`) additionally routes both pipelines
through a `mixer` speaker with per-pipeline resamplers and the 12 dB ducking
automations — this sketch omits them for brevity, but they're required:
without the mixer a cue would seize the speaker instead of ducking the music.

## Server changes — IMPLEMENTED 2026-07-18

1. `node_audio_manager.py` + `node_audio_config.json`: aioesphomeapi downlink
   mirroring every WS audio command onto mapped rooms — `play_effect_audio` →
   the node's `play_cue` action (embedded cue), `start_background_music` →
   `media_player.play_media` on the existing `/api/audio/<file>` URL,
   `audio_stop` → announcement-only stop (music survives, matching VLC).
2. Additive beside WS: `remote_host_manager.send_audio_command` dispatches to
   nodes and still emits every WS message — the sim's browser client keeps
   working; rooms migrate one at a time via the config.
3. Fire-and-forget behind a per-node FIFO lock (ordering preserved, a dead
   node never delays lights), connect-backoff + stale-command drop so an
   unreachable node can't queue late cues. Tests:
   `sim/tools/node_audio_test.py` (unit) + `sim/tools/concurrency_test.py`
   (regression, both green 2026-07-18). Firmware side:
   `sim/esphome/packages/audio_s3.yaml` + `make_node_audio.py` (cue assets +
   dispatch, per-effect volume baked in) + `bench-xiao-s3.yaml` — the bench
   config validates against ESPHome 2026.7.0.

Latency/sync: embedded-cue start (~100–300 ms) is in the same band as the VLC
start-check the effect timelines were hand-tuned against; music start over
HTTP (0.5–3 s) only affects the 300 s rotation, which is unsynced anyway.

## Bench checklist before buying 15 of anything

1. One S3 + prepped PCM5102A + Pebble on the bench node config; verify
   `play_cue` latency feels like the VLC path (Photo Bomb's 4.0 s shutter
   offset is the sensitive one).
2. **Rapid retrigger:** fire `play_cue` 10× fast — ESPHome issue #15692
   (2026-04) reported announcement replays going silent; confirm the current
   release is clean (Porto's piezo spam is exactly this pattern).
3. Music stream + stinger mix for 30 min on marginal RF (the -76..-85 dBm
   desk) — listen for stutter and for supply whine on quiet passages.
4. Bank-hold test: node + radar + Pebble idle overnight on the actual bank
   model — confirm no auto-off.
5. Radar false-still check with audio playing (pre-run of the mock-bay
   addition).

## Fleet revisit — sensor-by-sensor pass (2026-07-18)

Consolidations checked against every sensor in the maze; what stays and why:

- **Cuddle keeps BOTH radars.** Tempting to let the LD2450 (projection
  tracking) also do presence and drop the LD2410C — but the LD2450 is a
  motion tracker that loses perfectly still targets, and Cuddle's entire
  effect hook is *sustained still presence* via the LD2410C's still-energy
  gates. Not consolidatable.
- **Hex 4-button station → optional 1-pin resistor ladder.** Cuddle's box is
  the only exactly-full one (11/11 pins). If it ever needs a pin back, the
  four buttons collapse onto one ADC pin with a resistor ladder (frees 3
  GPIOs); costs a tiny resistor board + threshold logic, slightly less robust
  with dusty contacts. Keep 4 digital pins for now; this is the relief valve.
- **Porto keeps 3 separate piezo ADC pins** — pad identity is free there (no
  button, no I2C) and helps debugging.
- **Photo Bomb camera stays on the server Pi.** The XIAO S3-Sense camera is a
  2 MP OV2640 — wrong tool for keepsake photos, and the USB-webcam pipeline
  already works.
- **Cuddle projection renders on the server Pi** (2026-07-20: fleet is
  exactly one Pi, no spares) — nothing ESP-class drives an HDMI projector,
  so the server Pi's HDMI out does it; the rack→hex cable run is unchanged
  from the old spare-3B-at-the-rack plan. Bench-verify the render coexists
  with Quart + DMX + camera on the one board.
- **Config guardrail: no BLE components in audio nodes** (documented
  crash combination with ESPHome audio).
- **RF: mount the show AP high on the 20 ft center mast** — 15 nodes
  streaming music on 2.4 GHz want line-of-sight; desk-bench RF was already
  marginal at -76..-85 dBm.

## Open items

- How many Pebble pairs are on hand vs the ~15 rooms (new pairs $20.99).
- Which rooms actually get speakers (all 15, or skip the climb shafts?).
- Confirm whether the 14 remaining nodes were already purchased as C3s —
  decides whether S3s are an add or a swap.
- Which rooms are the ~5 no-mains (bank) rooms — those get the recharge
  rotation.
