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

## Layout

- `packages/logic.yaml` — the shared node base (name, api port, 3s http_request),
  **identical for sim and hardware**. Trigger behavior comes from the packages below;
  a node with none of them (exit/temple/vertical-moop-march — their Lightning-on-entry
  placeholders were test wiring, removed 2026-07-17) is an API bench node until its
  bespoke effect is designed.
- `packages/tripwire.yaml` — doorway-crossing trigger: `tripwire` sensor → 30ms
  `delayed_on` debounce → POST `run_effect` `${effect}` → 5s cooldown (`script` with
  `mode: single`). Exposes the `trip` action for the harness.
- `packages/button.yaml` — trigger for rooms with a physical button:
  `push_button` sensor → same debounce/POST contract → `${button_effect}` with an 8s
  cooldown (covers the 6.5s PhotoBomb-Shot sequence). Exposes the `press_button`
  action. Included by `photo-bomb.yaml` (shutter button → `PhotoBomb-Shot`) and
  `monkey.yaml` (puzzle-completion microswitch → `MonkeyBusiness`).
- `packages/button_gpio_c3.example.yaml` — real-hardware companion: GPIO3→GND
  momentary button feeding the same `push_button` template sensor. Include it
  alongside `button.yaml` when flashing a XIAO C3 (host platform has no GPIO, so
  it's not part of `validate_all.sh`).
- `packages/sim_host.yaml` — `host:` platform (sim) + a 100ms keepalive interval
  (see gotchas below).
- `packages/hardware_c3.yaml` — `esp32` XIAO C3 + WiFi + OTA (real nodes).
- `rooms/*.yaml` — one node per room: substitutions only (room, effect, server,
  api port 6061–6075, MAC). Room→effect mapping matches `client/config-unit-*.json`.

## Flashing a real node later

1. In the room's yaml: swap `sim_host.yaml` → `hardware_c3.yaml`, set
   `server_host: "192.168.1.238"`, copy `secrets.example.yaml` → `secrets.yaml`.
2. Add the room's actual sensor (VL53L1X / LD2410 / gpio per the hardware doc) and
   have it drive the automation — either publish to the `tripwire` template sensor,
   or replace it with the platform sensor keeping `id: tripwire` + the `on_press`.
3. `esphome run rooms/<room>.yaml` with the board plugged in. Done — `logic.yaml`
   already carried the tested behavior over.

## Hardware-day caveats (learned from the sim)

- **The server holds `/api/run_effect` until the effect finishes** (up to ~15s) and
  ESPHome's `http_request` blocks the node's loop while waiting — a button press
  during a tripwire's hold would queue behind it. `http_request: timeout: 3s` keeps
  the node responsive: hanging up early does **not** cancel the in-flight effect
  (verified against the server 2026-07-17 — a client that disconnected after 1s
  still got its full effect + photo capture). Note the host platform doesn't enforce
  this timeout exactly; real ESP32s do.
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
