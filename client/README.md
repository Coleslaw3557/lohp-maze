# LoHP-MazeManager Remote Unit Client

Runs on a Raspberry Pi. Plays effect audio and background music on command from the central
server (WebSocket), and fires sensor triggers at the server's REST API (laser tripwires,
ADS1115 buttons, piezo knock sensors — until the ESP32 nodes replace them, see
[../hardware-recommendations.md](../hardware-recommendations.md)).

## Components

- `main.py` — wires everything up, connects to the server, exits on connection loss
  (docker's `restart: always` is the reconnect strategy)
- `websocket_client.py` — handles server messages: `play_effect_audio`, `audio_stop`,
  `start/stop_background_music`, `audio_files_to_download`, `shutdown`
- `audio_manager.py` — downloads/caches audio from the server, plays it with VLC on one or
  more output zones
- `trigger_manager.py` — polls sensors (lasers 10ms, ADC 50ms) and POSTs each trigger's
  configured action to the server's REST API (`run_effect`, `set_theme`, music controls, …).
  Only loaded when the config defines triggers, so audio-only units run without the Pi GPIO stack
- `config_manager.py` — loads the unit's JSON config

## Configuration

One JSON file per deployment, selected with the `UNIT_CONFIG` environment variable:

- `config-unit-a.json` / `config-unit-b.json` / `config-unit-c.json` — the original three-Pi
  layout: each Pi covers ~5 rooms with one audio output and its local sensor triggers.
- `config-single-pi.json` — consolidated mode: one Pi covers all rooms, with a `zones` map
  routing each room's audio to its own USB sound card. No triggers (the ESP32 nodes own those).

### Multi-zone audio (`zones`)

```json
"zones": {
  "zone-a": {
    "alsa_device": "plughw:CARD=zonea",
    "rooms": ["Entrance", "Cuddle Cross", "..."]
  }
}
```

Each zone is one ALSA output device and the rooms it covers. The server already sends the room
name with every audio command, so the client routes each sound to the right card; whole-maze
audio (background music, all-rooms effects) plays on every zone. Configs without `zones` behave
exactly as before: one default output for all associated rooms.

### USB sound cards

Identical USB dongles can swap ALSA card numbers between boots. Pin each card's name to its
physical USB port with the included udev rule:

1. Edit `99-lohp-audio.rules` — instructions for finding your port paths are in the file.
2. `sudo cp 99-lohp-audio.rules /etc/udev/rules.d/ && sudo udevadm control --reload && sudo reboot`
3. `aplay -l` should now show cards `zonea`, `zoneb`, `zonec`, matching
   `plughw:CARD=...` in `config-single-pi.json`.

## Running

```bash
UNIT_CONFIG=config-single-pi.json docker compose up -d --build
```

`UNIT_CONFIG` defaults to `config-unit-a.json`. For boot-time startup via systemd see
[pi-notes.md](pi-notes.md). Audio files are downloaded from the server on startup and cached
in `cache/`, so first boot needs the server reachable.

## Troubleshooting

- `docker logs lohp-client` — startup logs list the configured zones, each trigger, and
  initial ADC voltages.
- No audio on one zone: check `aplay -l` card names against the config, and that `/dev/snd`
  is passed through (it is, in the provided compose file).
- Triggers firing but no effect: the client logs the server's HTTP response per trigger —
  a 404 means the effect name in this config doesn't exist server-side.
- The client exits on WebSocket loss by design; docker restarts it. If it's boot-looping,
  the server address in the config is wrong or the server is down.
