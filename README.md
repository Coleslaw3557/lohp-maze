# LoHP-MazeManager Control System

Lighting and audio control for the LoHP maze — one central server (the system's only Pi) drives
DMX fixtures and coordinates wireless ESP32-S3 room nodes that fire sensor triggers and play
per-room audio.

The maze in the simulator (`sim/` — the 3D representation is the layout reference):

| Street view — day | Street view — night |
|---|---|
| ![Street view, day](sim/img/street-day.png) | ![Street view, night](sim/img/street-night.png) |

## How it works

- **Server** (this directory): Quart REST API on port 5000, WebSocket server on port 8765,
  DMX output at 44Hz — Art-Net unicast over WiFi to the room nodes' RS-485 ports
  (`dmx_nodes.json`, `wiring-guides/dmx-over-wifi.md`) and/or the legacy FTDI USB-DMX wired
  chain during the transition. Runs themes (ambient, whole-maze lighting) and effects (short
  per-room sequences that interrupt the theme).
- **Room nodes** (`sim/esphome/`): battery/AC-powered XIAO ESP32-S3 node boxes, one per room,
  on the maze WiFi. Sensors (mmWave radar, ToF, buttons, piezos) fire effects by POSTing to the
  server's REST API; each node's speaker plays effect cues and streamed music, commanded by the
  server over the ESPHome native API (`node_audio_manager.py` + `node_audio_config.json`).
- **Floor projection** (`projection_engine.py` + `projection_renderer.py`): the Cuddle Cross
  floor show, three themes on one engine — **lava** (a Mayan stepping-stone crossing with
  sink/rise mischief and the surfacing Kukulkan), **jungle** (snakes on a leaf-litter
  floor that flee your feet, fireflies) and **temple** (torch-lit flagstones, scarab
  swarms, a skittish resident spider) — rendered by the same server Pi straight to
  its HDMI framebuffer and thrown onto the upper deck by a face-down short-throw projector.
  Its own systemd service outside the container; walker input is the room's LD2450 radar
  (demo phantom walkers until it's wired). Plans: `wiring-guides/cuddle-lava-plan.md`,
  `wiring-guides/cuddle-jungle-plan.md`, `wiring-guides/cuddle-temple-plan.md`.
- **Fallback audio client** (`client/`): the retired Pi-unit stack (units A/B/C are
  decommissioned), kept working as a fallback — one Linux host with a USB sound card per zone
  (`client/config-single-pi.json`) speaking the same WebSocket protocol.
- **Frontend**: a small control panel served at `http://<server>:5000/` (brightness, live theme
  tuning, next-theme).

Effects are defined in code in `effects/` and registered in `effects_manager.py`.
Audio for each effect is mapped in `audio_config.json`; fixtures and rooms in
`light_config.json`; the sensor→effect trigger map in `triggers.json`.

## Running the server

```
docker compose up -d
```

or natively:

```
pip install -r requirements.txt
python main.py
```

No DMX hardware needed on the server since the 2026-07-22 cutover — `dmx_nodes.json` ships
with every room node enabled and `ftdi:false` (set `ftdi:true` with the dongle attached to
resurrect the legacy wired chain). See
[hardware-recommendations.md](hardware-recommendations.md) for the wireless sensor-node
architecture, `wiring-guides/` for the node-box, audio, and sign build plans (the unit-a/b/c
guides are historical), and `client/README.md` for the fallback audio client.

### Deploying to the server Pi

The production box is a DietPi Raspberry Pi 3B+ flashed from a preconfigured SD image —
first boot joins the WiFi, installs Docker and authorizes the bench box's SSH key
unattended ([pi-notes.md](pi-notes.md)). Then:

```bash
tools/deploy-rpi.sh                  # target lohp-server.local (mDNS), or pass an IP
```

rsyncs the repo to `/home/dietpi/lohp-server`, installs the `lohp-server` systemd unit,
builds the compose image, and waits for `http://<pi>:5000/api/health`. The floor projection
installs once per card with `tools/rpi-projection-setup.sh` (configures the legacy display
stack with a grid-sized framebuffer the GPU scales — one reboot — then the
`lohp-projection` service paints the framebuffer directly).
The sim's header **RPI** dot watches the box: green = server answering, amber = booted but
not deployed, red = unreachable.

## Basic operations

```bash
# Set a theme
curl -X POST http://localhost:5000/api/set_theme -H "Content-Type: application/json" -d '{"theme_name": "NeonNightlife"}'

# Run an effect in a room
curl -X POST http://localhost:5000/api/run_effect -H "Content-Type: application/json" -d '{"room": "Entrance", "effect_name": "Lightning"}'

# Adjust master brightness
curl -X POST http://localhost:5000/api/set_master_brightness -H "Content-Type: application/json" -d '{"brightness": 0.8}'
```

Full API reference: [api-docs.md](api-docs.md). Adding effects: [adding_new_effects.md](adding_new_effects.md).

## Photo booth & the silver monkey

Two rooms have button-driven set pieces (buttons wired to the room's ESP32 node,
`sim/esphome/rooms/{photo-bomb,monkey}.yaml`):

- **Photo Bomb Room** — a USB webcam on the server Pi plus a shutter button. A press fires
  the `PhotoBomb-Shot` effect: camera power-up jingle, 3-2-1 countdown beeps (3 seconds to
  strike a pose), then a full-white FLASH synced with the shutter sound while
  `camera_manager.py` grabs a frame. Photos land on the Pi's SD card in `photos/` as
  `photobomb_YYYY-MM-DD_HH-MM-SS.jpg`; browse them at `GET /api/photobomb/photos`.
  Re-pressing mid-countdown restarts the countdown (never double-shoots); the timeline is
  defined once in `effects/photobomb_shot.py` and shared by the lights, the soundtrack
  (`tools/make_photobomb_audio.py`) and the capture scheduler. Optional `camera_config.json`
  overrides device/resolution/photos dir.
- **Monkey Room** — the silver monkey puzzle (a nod to Legends of the Hidden Temple) closes a
  microswitch when the assembly seats home, firing `MonkeyBusiness`: the actual Shrine of the
  Silver Monkey assembly cue sampled from the show (`tools/fetch_monkey_sound.sh`) with gold
  flashes synced to the fanfare, a white-gold mega flash on the final stinger, and emerald
  twinkles fading out.

## The Cuddle Cross floor show (lava / jungle / temple)

The upper-deck crossing is a projection-mapped floor show with two selectable themes.

**Lava**: molten lava with a chain of five carved grey
stepping stones — Mayan numerals in walking order, one dot at the east door through one bar
(five) at the west; the goal is to walk across the stones. Walk toward a stone and it may
sink after its glyph flashes hot (a carved warning) while another rises off your line;
lava bubbles pop, canopy shadows press in at the deck rim, embers drift, and every minute
or two **Kukulkan** — the feathered serpent — surfaces, scans the room with pulsing amber
eyes, and slips back under.

**Jungle**: the temple floor reclaimed — a leaf-litter carpet under moving sun-dapple
where a tzabcan rattlesnake (with a working rattle), a gold eyelash viper, and a coral
snake slither across the deck and dart away from your feet, fallen glyph stones go mossy
and glint as you approach, fireflies blink, and a sun-pool follows each walker.

**Temple**: the floor itself, swept and torch-lit — dark mossy flagstones under breathing
torchlight, carved glyphs that fill with gold as you approach, scarab swarms (The Mummy)
that pour from pits in the floor and circle your feet, and a big slow spider that
scurries when you get close. The calm one.

Both are presence-cued: the show starts when the radar sees someone and
fades out 60 s after the deck empties.

One numpy engine (`projection_engine.py`, `FloorShow` base + `THEMES` registry) drives both
displays: the projector (`projection_renderer.py`, live-switchable via `POST :5002/theme/<name>` → `/dev/fb0`) and the
sim preview (state + field streamed over `WS /sim/projection`; the page renders the
engine's own precomputed artwork, and the header **Floor** button switches the shared
theme for every tab). Content specs and tuning knobs:
[wiring-guides/cuddle-lava-plan.md](wiring-guides/cuddle-lava-plan.md) and
[wiring-guides/cuddle-jungle-plan.md](wiring-guides/cuddle-jungle-plan.md).
The **Cuddle orb** — a round-display watching eye mounted under the rear sensor box,
sharing the same radar — is specced in
[wiring-guides/cuddle-orb-plan.md](wiring-guides/cuddle-orb-plan.md).

## Architecture

- `main.py` — REST API, WebSocket server, component wiring
- `effects_manager.py` — effect registry and per-room effect execution
- `theme_manager.py` — ambient theme loop (its own thread, paused per-room during effects)
- `interrupt_handler.py` — takes fixtures over from the theme while an effect runs
- `dmx_state_manager.py` / `dmx_interface.py` — DMX channel state and the 44Hz FTDI output thread
- `artnet_output_manager.py` / `artnet.py` / `dmx_nodes.json` — Art-Net unicast to the room
  nodes' DMX ports (`wiring-guides/dmx-over-wifi.md`); node firmware in
  `sim/esphome/components/artnet_dmx/`
- `remote_host_manager.py` — audio command fan-out: WebSocket to every claiming client, mirrored
  to ESP32 nodes via `node_audio_manager.py` (ESPHome native API: firmware cues + streamed music)
- `audio_manager.py` — audio catalog from `audio_config.json`, served to clients over HTTP
- `camera_manager.py` — Photo Bomb webcam capture scheduling (synthetic backend without hardware)
- `projection_engine.py` — the Cuddle lava floor show: stones, mischief, Kukulkan (shared by
  sim and projector; pure numpy)
- `projection_renderer.py` — fullscreen framebuffer output on the server Pi
  (systemd `lohp-projection`, outside the container)
- `effects/` — one file per effect; `effect_utils.py` — shared step interpolation and theme math
