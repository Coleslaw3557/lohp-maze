# LoHP-MazeManager Control System

Lighting and audio control for the LoHP maze — a central server drives DMX fixtures and coordinates
Raspberry Pi room units that play audio and report sensor triggers.

The maze in the simulator (`sim/` — the 3D representation is the layout reference):

| Street view — day | Street view — night |
|---|---|
| ![Street view, day](sim/img/street-day.png) | ![Street view, night](sim/img/street-night.png) |

## How it works

- **Server** (this directory): Quart REST API on port 5000, WebSocket server on port 8765,
  DMX output at 44Hz over an FTDI USB-DMX interface. Runs themes (ambient, whole-maze lighting)
  and effects (short per-room sequences that interrupt the theme).
- **Clients** (`client/`): Raspberry Pi units that play effect audio and background music on
  command from the server via WebSocket, and (until the planned ESP32 sensor nodes take over)
  watch sensors over GPIO/ADC and fire effects by POSTing to the server's REST API. Runs either
  as the original three units (A/B/C, ~5 rooms each) or as a single Pi driving one USB sound
  card per zone (`client/config-single-pi.json`).
- **Frontend**: a small control panel served at `http://<server>:5000/` (brightness, live theme
  tuning, next-theme).

Effects are defined in code in `effects/` and registered in `effects_manager.py`.
Audio for each effect is mapped in `audio_config.json`; fixtures and rooms in `light_config.json`.

## Running the server

```
docker compose up -d
```

or natively:

```
pip install -r requirements.txt
python main.py
```

Requires the FTDI USB-DMX interface to be attached. See `client/README.md` for the room units,
`wiring-guides/` for unit wiring, and [hardware-recommendations.md](hardware-recommendations.md)
for the planned wireless sensor-node replacement.

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

## Architecture

- `main.py` — REST API, WebSocket server, component wiring
- `effects_manager.py` — effect registry and per-room effect execution
- `theme_manager.py` — ambient theme loop (its own thread, paused per-room during effects)
- `interrupt_handler.py` — takes fixtures over from the theme while an effect runs
- `dmx_state_manager.py` / `dmx_interface.py` — DMX channel state and the 44Hz FTDI output thread
- `remote_host_manager.py` — WebSocket commands to the room units (effect audio, background music)
- `audio_manager.py` — audio catalog from `audio_config.json`, served to clients over HTTP
- `effects/` — one file per effect; `effect_utils.py` — shared step interpolation and theme math
