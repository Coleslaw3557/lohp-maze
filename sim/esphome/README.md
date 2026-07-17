# Virtual ESP32 sensor nodes (ESPHome host platform)

The planned wireless sensor nodes (`../../hardware-recommendations.md`) as real
ESPHome firmware, compiled to **native Linux binaries** — same engine, scheduler,
debounce filters and `http_request` code that will run on the XIAO ESP32-C3s.
The only differences from hardware: no WiFi (host network stack) and the physical
sensor driver is replaced by a template binary_sensor you trip over the native API.

```bash
./run_node.sh entrance         # build + run one node (first ever build ~2 min)
./validate_all.sh              # esphome config-check all 15 nodes
.venv/bin/python harness.py list
.venv/bin/python harness.py trip entrance    # virtual doorway crossing
.venv/bin/python harness.py trip all         # storm the whole maze
```

Verified working 2026-07-16: `harness.py trip entrance` → node runs its automation →
`POST /api/run_effect {"room":"Entrance","effect_name":"Entrance"}` hits the server
(UA `ESPHome/2026.7.0`) → effect runs. Nothing in the server can tell it from a real node.

## Layout

- `packages/logic.yaml` — the shared contract, **identical for sim and hardware**:
  `tripwire` sensor → 30ms `delayed_on` debounce → POST `run_effect` → 5s cooldown
  (`script` with `mode: single`). Also exposes the `trip` action for the harness.
- `packages/sim_host.yaml` — `host:` platform (sim).
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

- **The server holds `/api/run_effect` until the effect finishes** (up to ~15s).
  ESPHome's `http_request` blocks the node's loop while waiting, so during a long
  effect the node won't service other events (fine for one sensor per node, and the
  5s cooldown makes it moot — but don't hang a second time-critical sensor off the
  same node). On real ESP32s keep an eye on watchdog warnings from long holds; if
  they appear, drop `http_request: timeout:` to ~3s — but first verify on the bench
  that an early client disconnect doesn't cancel the server's in-flight effect.
- `api: reboot_timeout: 0s` is required on sim AND bench nodes — the default reboots
  the node every 15 min when no API client (Home Assistant) is connected.
- `web_server` does not exist on the host platform — that's why the harness uses the
  native API instead.
