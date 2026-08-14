# Virtual ESP32 sensor nodes (ESPHome host platform)

The planned wireless sensor nodes (`../../hardware-recommendations.md`) as real
ESPHome firmware, compiled to **native Linux binaries** — same engine, scheduler,
debounce filters and `http_request` code that will run on the XIAO ESP32-C3s.
The only differences from hardware: no WiFi (host network stack) and the physical
sensor driver is replaced by a template binary_sensor you trip over the native API.

```bash
./run_node.sh entrance         # build + run one node (first ever build ~2 min)
./run_node.sh photo-bomb -d    # background daemon (log: node-photo-bomb.log)
./validate_all.sh              # esphome config-check all 15 nodes
.venv/bin/python harness.py list
.venv/bin/python harness.py trip entrance    # virtual doorway crossing
.venv/bin/python harness.py trip all         # storm the whole maze
.venv/bin/python harness.py press photo-bomb # push the room's button (photo-bomb, monkey)
```

Verified working 2026-07-16 (tripwires) and 2026-07-17 (buttons): `harness.py trip|press` →
node runs its automation → `POST /api/run_effect` hits the server (UA `ESPHome/2026.7.0`) →
effect runs (and for the Photo Bomb button, the webcam takes the photo). Nothing in the
server can tell it from a real node.

**First real XIAO ESP32-C3 bench-validated 2026-07-17** (`bench-xiao-c3.yaml` — the
button-room stack on real hardware): USB flash → WiFi join → native-API
`press_button` → POST over WiFi → `MonkeyBusiness` ran in Monkey Room,
press-to-effect ≈ 16 ms. Hardware notes: the 3s `http_request` timeout IS
enforced on the C3 — the node logs `HTTP Request failed; Code: -1` at 3s while
the server completes the effect (by design, see caveats below); and the XIAO
has **no onboard antenna** — clip on the U.FL pigtail, or you get near-empty
scans, -80..-96 dBm and endless WPA `Handshake Failed`/`Auth Expired`.

## Layout

- `packages/logic.yaml` — the shared node base (name, api port, 3s http_request),
  **identical for sim and hardware**. Trigger behavior comes from the packages below;
  a node with none of them (exit/temple/vertical-moop-march — their Lightning-on-entry
  placeholders were test wiring, removed 2026-07-17) is an API bench node until its
  bespoke effect is designed.
- `packages/tripwire.yaml` — doorway-crossing trigger: `tripwire` sensor → 30ms
  `delayed_on` debounce → occupancy latch → POST `run_effect` `${effect}`. Once a
  radar room is occupied, additional enter edges are ignored until `room_vacated`
  clears the latch; this prevents LD2410 moving-target re-presses from firing the
  same room repeatedly while someone is still inside. Exposes the `trip` and
  `vacate` actions for the harness.
- `packages/button.yaml` — trigger for rooms with a physical button:
  `push_button` sensor → same debounce/POST contract → `${button_effect}` with an 8s
  cooldown (covers the 6.5s PhotoBomb-Shot sequence). Exposes the `press_button`
  action. Included by `photo-bomb.yaml` (shutter button → `PhotoBomb-Shot`) and
  `monkey.yaml` (puzzle-completion microswitch → `MonkeyBusiness`).
- `packages/button_gpio_c3.example.yaml` — real-hardware companion: D1→GND
  momentary button feeding the same `push_button` template sensor
  (`button_pin` defaults to the C3's GPIO3; XIAO S3 rooms set `GPIO2`). Include
  it alongside `button.yaml` when flashing real hardware (host platform has no
  GPIO, so it's not part of `validate_all.sh`).
- `packages/sim_host.yaml` — `host:` platform (sim) + a 100ms keepalive interval
  (see gotchas below).
- `packages/hardware_c3.yaml` — `esp32` XIAO C3 + WiFi + OTA. Superseded as the
  fleet platform by the S3 (audio needs PSRAM); still fine for the C3 bench node.
- `packages/hardware_s3.yaml` — **fleet standard**: XIAO ESP32-S3 + PSRAM + WiFi
  + OTA (per-room audio revisit, `wiring-guides/room-node-audio-plan.md`).
- `packages/audio_s3.yaml` — the speaker chain (I2S → PCM5102A → Pebble):
  mixer + dual media/announcement pipelines. Effect cues play as announcements at
  full node volume; ambience/music streams on the media pipeline at lower per-pool
  volume and ducks under effect cues. Maze-wide ambience starts/resumes from
  server-generated `offset_s` URLs, so real ESP speakers follow the same bed
  clock instead of each restart beginning at zero.
- `make_node_audio.py` — generates the server-side cue streams from
  `node_audio_config.json` + `audio_config.json`: `audio_files/cues/*.wav`
  (22.05kHz mono, per-effect volume baked in). Outputs are gitignored — rerun
  after config/mp3 changes so `/api/audio/cues/<cue_id>.wav` is current.
- `rooms/*.yaml` — one node per room: substitutions only (room, effect, server,
  api port 6061–6075, MAC). Room→effect mapping matches `triggers.json` (repo root, the canonical map).

## Flashing a real node later

1. In the room's yaml: swap `sim_host.yaml` → `hardware_s3.yaml` (fleet standard;
   button rooms also set `button_pin: GPIO2` — S3's D1), set
   `server_host: "192.168.252.231"` (the server Pi's RUT reservation —
   `wiring-guides/maze-network.md`), copy `secrets.example.yaml` → `secrets.yaml`.
2. Add the room's actual sensor (`ld2410.yaml` radar in 13 rooms, `tof.yaml` at
   Entrance/Exit, plus any gpio button per the hardware doc) and
   have it drive the automation — either publish to the `tripwire` template sensor,
   or replace it with the platform sensor keeping `id: tripwire` + the `on_press`.
3. Speaker rooms: add `audio_s3.yaml` + the generated `audio/cues-<node>.yaml` to
   the packages, list the room in `node_audio_config.json`, and run
   `./make_node_audio.py`.
4. `esphome run rooms/<room>.yaml` with the board plugged in. Done — `logic.yaml`
   already carried the tested behavior over.

## Radar Occupancy Behavior

Radar-backed rooms should drive `tripwire` from LD2410 moving-target ON and drive
`room_vacated` from LD2410 has-target OFF after the room's `absence_timeout`. "Empty"
means the radar no longer sees any moving or still target for that timeout. Standing
still should remain occupied as long as the LD2410 still holds its still-target lock;
moving again while occupied is ignored by the shared `room_occupied` latch and does
not retrigger the effect.
Rooms with audible leave/send-off sounds can override the radar timeout shorter
(`ld2410_module_timeout_s: "1"`, `absence_timeout: 0s`) so the send-off plays
close to the actual exit instead of after the standard empty-room grace period.

Standard 7 ft x 5 ft bay rooms default to a contained LD2410 profile because rooms
share scaffold frames and radar can see through ply: moving/entry max gate `2`
(about 1.5 m) and still/occupancy max gate `3` (about 2.25 m). Entry only needs
the near-side moving edge as someone crosses into the room; occupancy gets one
gate more so standing still inside the room does not immediately drop out.
Cuddle Cross and the vertical climb shafts can override these substitutions when
their hardware is flashed.

The only per-room tuning should be the radar front end: physical aim, gate
overrides, sensitivity thresholds, and `absence_timeout`. Do not add a second
cooldown around `run_effect`; the latch is the deployed debounce for radar rooms.

## S3 audio bench (bench-xiao-s3.yaml)

The audio-era hardware stack of a button room, mapped as "Monkey Room" in
`node_audio_config.json` so the dev server's real audio commands land on it.
Bring-up order (full checklist: `wiring-guides/room-node-audio-plan.md`):

1. Prep the PCM5102A (boards ship silent): back jumpers FLT→L DEMP→L **XSMT→H**
   FMT→L, front SCK pads → GND. Wire D8/D9/D10 → BCK/LCK/DIN, 5V pin → VIN,
   line-out jack → Pebble; button between D1 (GPIO2) and GND.
2. `./make_node_audio.py` (server-side prep: generates the streamable
   `audio_files/cues/` WAVs — **NOTHING is stored on the node**, 2026-07-25),
   then flash `bench-xiao-s3.yaml`.
3. Drive it the real way: press the button (fires the room effect; the server
   streams the cue to the node as an announcement URL
   `/api/audio/cues/<cue_id>.wav`), or `POST /api/run_effect`;
   `POST /api/start_maze_ambience` for the streamed bed — the server's
   `node_audio_manager.py` handles both, additively beside the WS/sim path.
   Looping ambience is prepared server-side as a generated crossfaded MP3 for node
   playback, so ESPHome plays one long finite file instead of restarting a short
   loop on the node. Generated files live under `audio_files/generated/` and are
   intentionally not committed. Node ambience URLs may include `offset_s` so a
   cue resume or a late node reconnect rejoins the current maze-bed position.
4. Bench checks that gate the 15× buy: cue latency vs the VLC feel, 10× rapid
   `play_cue` retrigger (ESPHome #15692 regression), 30min ambience+cue soak on
   marginal RF, overnight power-bank hold, radar baseline with audio playing.

## Hardware-day caveats (learned from the sim)

- ESPHome-originated `/api/run_effect` requests return immediately with
  `accepted: true`; the server runs the effect in the background so native-API
  audio commands can reach the same node without waiting behind a long HTTP
  request. `http_request: timeout: 3s` remains as a network-failure guard.
- **First-event trap**: a template binary_sensor without `publish_initial_state: true`
  treats the first-ever trigger after power-up as its *initial* state — `on_press`
  never fires for it. Cost us the first button press after every boot until fixed
  (2026-07-17); the tripwire had the same latent bug (first visitor after power-up
  would walk through unnoticed). Keep that flag on any new sensor.
- `api: reboot_timeout: 0s` is required on sim AND bench nodes — the default reboots
  the node every 15 min when no API client (Home Assistant) is connected.
- `web_server` does not exist on the host platform — that's why the harness uses the
  native API instead.

## Host-platform (sim) quirks — not applicable to real ESP32s

- **ESPHome 2026.7.0 host scheduler starvation**: the host select() loop only wakes
  on socket traffic, so timers scheduled while idle (debounce filters, `delay:`,
  queued scripts) can sit for seconds-to-minutes until the next packet. Automations
  looked dead or minutes-late depending on API chatter. `sim_host.yaml` keeps a
  standing 100ms no-op `interval:` so the wake deadline stays short. Real ESP32
  nodes run a proper RTOS loop and don't need this.
- **Run long-lived sim nodes as daemons** (`./run_node.sh <room> -d`): it compiles,
  then execs the built binary directly. An `esphome run` wrapper left attached
  without a terminal can stall the node's loop for seconds at a time.
- Node stdout is block-buffered when redirected to a file — an empty
  `node-<room>.log` doesn't mean the node is idle. For live logs, subscribe over
  the native API or run in a real terminal.
