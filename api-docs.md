# LoHP-MazeManager API Documentation

This document outlines the available API endpoints for the LoHP-MazeManager Control System.

## Base URL

All API requests should be made to:

```
http://<server-ip>:5000/api
```

Replace `<server-ip>` with the IP address or hostname of your LoHP-MazeManager server.

## Endpoints

### 1. Set Theme

Sets the current lighting theme for all rooms.

- **URL:** `/set_theme`
- **Method:** `POST`
- **Data Params:**
  ```json
  {
    "theme_name": "[string]"
  }
  ```
- **Optional Params:**
  ```json
  {
    "next_theme": true
  }
  ```

#### Example
```bash
curl -X POST http://localhost:5000/api/set_theme \
     -H "Content-Type: application/json" \
     -d '{"theme_name": "DeepCanopy"}'
```

To set the next theme:
```bash
curl -X POST http://localhost:5000/api/set_theme \
     -H "Content-Type: application/json" \
     -d '{"next_theme": true}'
```

To turn off the theme:
```bash
curl -X POST http://localhost:5000/api/set_theme \
     -H "Content-Type: application/json" \
     -d '{"theme_name": "NoTheme"}'
```

### 2. Run Effect

Runs a specific effect in a given room.

- **URL:** `/run_effect`
- **Method:** `POST`
- **Data Params:**
  ```json
  {
    "room": "[string]",
    "effect_name": "[string]"
  }
  ```

#### Example
```bash
curl -X POST http://localhost:5000/api/run_effect \
     -H "Content-Type: application/json" \
     -d '{"room": "Entrance", "effect_name": "Lightning"}'
```

### 3. Set Master Brightness

Adjusts the master brightness for all lights.

- **URL:** `/set_master_brightness`
- **Method:** `POST`
- **Data Params:**
  ```json
  {
    "brightness": [float]
  }
  ```

#### Example
```bash
curl -X POST http://localhost:5000/api/set_master_brightness \
     -H "Content-Type: application/json" \
     -d '{"brightness": 0.8}'
```

### 4. Get Rooms

Retrieves the list of configured rooms.

- **URL:** `/rooms`
- **Method:** `GET`

#### Example
```bash
curl http://localhost:5000/api/rooms
```

### 5. Get Effects List

Retrieves the list of available effects.

- **URL:** `/effects_list`
- **Method:** `GET`

#### Example
```bash
curl http://localhost:5000/api/effects_list
```

### 6. Get Themes

Retrieves the list of available themes.

- **URL:** `/themes`
- **Method:** `GET`

#### Example
```bash
curl http://localhost:5000/api/themes
```

### 7. Start Maze Ambience

Starts the configured maze-wide ambience bed on all connected clients. The
standing configuration is global: Cuddle Cross is the normal exception because
the floor show owns its local bed. Long bed files play once; short loop assets
repeat for a bounded window before the server rotates to a fresh anti-repeat
pick. ESP32 room nodes receive a server-clocked start timestamp; when a node
starts, resumes after a cue, or reconnects later, the server gives it an
`/api/audio/<file>?offset_s=...` URL so real room speakers rejoin the same
position instead of restarting the ambience from zero.

- **URL:** `/start_maze_ambience`
- **Method:** `POST`

#### Example
```bash
curl -X POST http://localhost:5000/api/start_maze_ambience
```

### 8. Stop Maze Ambience

Stops the currently playing maze-wide ambience bed on all connected clients.
Cuddle's floor-show bed is separate and keeps playing while the show is active.

- **URL:** `/stop_maze_ambience`
- **Method:** `POST`

#### Example
```bash
curl -X POST http://localhost:5000/api/stop_maze_ambience
```

### 8b. Room Backgrounds (manual per-room background sound)

The normal maze ambience is global, so `audio_config.json` leaves
`room_backgrounds` empty. This endpoint still exists for runtime auditions: a
room opted in here plays one random bed pick on that room's ambience channel,
overriding the maze-wide ambience on that speaker while it plays. The POST is
not persisted. Cuddle Cross is refused because its background follows the floor
projection.

- **URL:** `/room_backgrounds`
- **Method:** `GET` (state: `configured` + `playing`) / `POST`
- **Data Params (POST):**
  ```json
  {
    "room": "No Friends Monday",
    "effect": "NoFriendsMonday-Background"
  }
  ```
  `"effect": null` opts the room back out and stops its bed.

#### Example
```bash
curl -X POST http://localhost:5000/api/room_backgrounds \
  -H 'Content-Type: application/json' \
  -d '{"room": "No Friends Monday", "effect": "NoFriendsMonday-Background"}'
```

### 9. Run Test

Runs a test sequence for lighting or effects.

- **URL:** `/run_test`
- **Method:** `POST`
- **Data Params:**
  ```json
  {
    "testType": "[string]",
    "rooms": ["[string]"],
    "channelValues": {
      "[channel]": [int]
    }
  }
  ```
  or
  ```json
  {
    "testType": "[string]",
    "rooms": ["[string]"],
    "effectName": "[string]"
  }
  ```

#### Example (Channel Test)
```bash
curl -X POST http://localhost:5000/api/run_test \
     -H "Content-Type: application/json" \
     -d '{
       "testType": "channel",
       "rooms": ["Entrance"],
       "channelValues": {
         "total_dimming": 255,
         "r_dimming": 255,
         "g_dimming": 0,
         "b_dimming": 0
       }
     }'
```

#### Example (Effect Test)
```bash
curl -X POST http://localhost:5000/api/run_test \
     -H "Content-Type: application/json" \
     -d '{
       "testType": "effect",
       "rooms": ["Entrance"],
       "effectName": "Lightning"
     }'
```

### 10. Stop Test

Stops any ongoing test and resets the lights.

- **URL:** `/stop_test`
- **Method:** `POST`

#### Example
```bash
curl -X POST http://localhost:5000/api/stop_test
```

### 11. Run Effect in All Rooms

Runs a specific effect in all rooms simultaneously.

- **URL:** `/run_effect_all_rooms`
- **Method:** `POST`
- **Data Params:**
  ```json
  {
    "effect_name": "[string]",
    "audio": {
      "volume": [float],
      "loop": [boolean]
    }
  }
  ```

#### Example
```bash
curl -X POST http://localhost:5000/api/run_effect_all_rooms \
     -H "Content-Type: application/json" \
     -d '{
       "effect_name": "Lightning",
       "audio": {
         "volume": 0.8,
         "loop": false
       }
     }'
```

### 11b. Sign Storm

The camp-sign arcade button: fires **Lightning in every room and on the sign
at once, with thunder on every speaker** (the same all-rooms broadcast as
`/run_effect_all_rooms` with Lightning). The sign bridge firmware
(`firmware/sign/`) POSTs this on a button press; anything else may call it too.

**The server owns the cooldown** (`SIGN_STORM_COOLDOWN_S = 30` in `main.py`,
one shared timer for every source). Presses inside it get **429** with
`retry_after_s`; a failed strike does not burn the cooldown. The 200 returns
only after the ~3.5 s strike completes, so short-timeout fire-and-forget
callers (the node) may drop the response — the strike still runs.

- **URL:** `/sign_storm`
- **Method:** `POST`
- **Data Params:** none (empty JSON body)

#### Example
```bash
curl -X POST http://localhost:5000/api/sign_storm \
     -H "Content-Type: application/json" \
     -d '{}'
```

### 12. Stop Effect

Stops the currently running effect in a specific room or all rooms.

- **URL:** `/stop_effect`
- **Method:** `POST`
- **Data Params:**
  ```json
  {
    "room": "[string]"
  }
  ```
  Note: If "room" is not provided, it will stop effects in all rooms.

#### Example (Stop effect in a specific room)
```bash
curl -X POST http://localhost:5000/api/stop_effect \
     -H "Content-Type: application/json" \
     -d '{"room": "Entrance"}'
```

#### Example (Stop effects in all rooms)
```bash
curl -X POST http://localhost:5000/api/stop_effect
```

### 12b. Room Vacated

The leave half of a radar room's occupancy pair, and the `leave_action` on
radar-backed `presence` triggers in `triggers.json`. A room node POSTs it when
its radar stops seeing anyone for the room's absence timeout (5 s standard,
60 s on dwell rooms), meaning no target at all, moving or still. Entrance and
Exit use narrow ToF beams and intentionally do not POST this on beam clear;
once a ToF room triggers, its routine finishes normally.

The server cancels anything still running in the room, silences lingering effect
audio, and hands the room's fixtures back to the current theme. The resume is
unconditional, so a room vacated long after its entry effect already finished
still ends up on ambient. Maze ambience is deliberately untouched; if a room
bed was active, stopping it hands that speaker back to the maze ambience bed.

Functionally the same work as a per-room `/stop_effect`; it exists as its own
route because the room is reporting a fact rather than an operator issuing a
stop, and it reads as one in the log.

- **URL:** `/room_vacated`
- **Method:** `POST`
- **Data Params:**
  ```json
  {
    "room": "[string]"
  }
  ```
  `room` is required (400 without it). Repeated calls are harmless.

#### Example
```bash
curl -X POST http://localhost:5000/api/room_vacated \
     -H "Content-Type: application/json" \
     -d '{"room": "Entrance"}'
```

### 12c. Floor Event

The Cuddle floor projection reporting what it is doing, so the room can follow
it (`floor_show_manager.py`). Posted by whichever renderer is driving the
projector — `projection_renderer.py` on the Pi, the sim's engine on the bench —
every couple of seconds while a show is up, immediately whenever the engine's
own events happen, and once when the deck empties (an empty deck then stays
quiet: there is no bed left to watch over).

The server turns a report into three things: the room's light palette (the
entry swell's colours and the ceiling/tint the maze theme's wash is squeezed
into for the projection room), a looping ambience **bed** for as long as
`active` is true, and the occasional **accent** — a capped ember flare on the
pars plus one file from the theme's accent pool.

`active` is the authority for the bed. A renderer that dies simply stops
reporting, and the bed stops on its own 20 s later; there is no way for the
room to be left rumbling to an empty deck. Only LAVA has sounds today; the
other four themes light correctly and stay silent.

- **URL:** `/floor_event`
- **Method:** `POST`
- **Data Params:**
  ```json
  {
    "theme": "lava",
    "active": true,
    "events": [{"e": "sink", "id": 3, "x": 128.0, "y": 96.0}]
  }
  ```
  All three are optional: `theme` and `active` are remembered when omitted, and
  a report with no `events` is a plain heartbeat. Event names are the floor
  engine's own (`projection_engine.py`): `sink`, `rise`, `pop`, `monster_swim`,
  `monster_breach`, `show_on`, `show_off`.
- **Response:** the floor state, plus `accent` — the effect this batch fired,
  or `null` (most batches: accents are gated by probability and cooldown, and
  at most one fires per report).

#### Example
```bash
curl -X POST http://localhost:5000/api/floor_event \
     -H "Content-Type: application/json" \
     -d '{"theme": "lava", "active": true, "events": [{"e": "monster_breach"}]}'
```

### 13. Get Effects Details

Retrieves detailed information about all available effects.

- **URL:** `/effects_details`
- **Method:** `GET`

#### Example
```bash
curl http://localhost:5000/api/effects_details
```

### 14. Get Light Models

Retrieves information about all configured light models.

- **URL:** `/light_models`
- **Method:** `GET`

#### Example
```bash
curl http://localhost:5000/api/light_models
```

### 15. Sensor Telemetry + Analytics

The server records room events in `data/telemetry.sqlite3` using server UTC as
the clock of record. `/api/run_effect` automatically records canonical room
entries and other effect triggers; `/api/room_vacated` records room exits.
Nodes can also POST richer diagnostics here without changing effect behavior.

#### Ingest One Event
```bash
curl -X POST http://localhost:5000/api/telemetry \
     -H "Content-Type: application/json" \
     -d '{"room": "Cop Dodge", "event_type": "heartbeat", "sensor_type": "wifi", "sensor_name": "rssi", "value": {"rssi_dbm": -61}, "node_uptime_ms": 123456, "seq": 42}'
```

#### Ingest Batch
```bash
curl -X POST http://localhost:5000/api/telemetry \
     -H "Content-Type: application/json" \
     -d '{"room": "Cop Dodge", "node_name": "lohp-node-cop-dodge", "events": [{"event_type": "radar_presence", "value": true}, {"event_type": "heartbeat", "value": {"rssi_dbm": -61}}]}'
```

#### Review Events
```bash
curl 'http://localhost:5000/api/sensor_events?room=Cop%20Dodge&limit=100'
curl 'http://localhost:5000/api/sensor_events.csv?since_s=3600'
```

Useful analytics endpoints:

- `GET /api/analytics/room_dwell?since_s=3600&include_visits=1`
- `GET /api/analytics/maze_runs?timeout_s=900`
- `GET /api/analytics/abandonment?timeout_s=900`
- `GET /api/analytics/room_heatmap`

## Additional Endpoints

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/` | Web control panel (serves `frontend/index.html`) |
| GET | `/api/health` | Liveness probe: `{"status": "ok", "service": "lohp-server"}` — polled by `tools/deploy-rpi.sh` and the sim's RPI status dot |
| GET | `/api/room_layout` | Alias of `/api/rooms` |
| GET | `/api/rooms_units_fixtures` | Rooms with their fixtures and the client units covering them |
| GET | `/api/connected_clients` | Connected room units (name, IP, rooms) |
| POST | `/api/terminate_client` | Close a unit's WebSocket. Body: `{"ip": "<client-ip>"}` |
| POST | `/api/update_theme_value` | Live-tune the running theme. Body: `{"control_id": "color-variation", "value": 0.5}`. Control IDs read by themes: `transition-speed`, `color-variation`, `intensity-fluctuation`, `color-wheel-speed`, `wave-effect` (unknown IDs are accepted and stored but never read) |
| GET | `/api/light_fixtures` | Plain-text fixture listing (ROBCO terminal style) |
| GET | `/api/audio_files_to_download` | Lists configured effect/ambience audio files clients should cache |
| GET | `/api/audio/<filename>` | Serves an audio file. ESP node ambience may include `?offset_s=<seconds>`; the server streams from that position so nodes can rejoin a shared maze-bed clock. |
| POST | `/api/reload_audio_config` | Re-reads `audio_config.json` without a restart, so pool edits from the audio console (`tools/audio_console.py`) go live. Returns `{"pools": {"<effect>": <file count>}}` |
| GET | `/api/attract` | The maze's self-running look rotation: `enabled`, `dwell_s`, the dark `themes` cycle, `current_theme`, `next_change_in_s` |
| POST | `/api/attract` | `{"on": bool, "dwell_s"?, "themes"?}` — attract survives manual `/api/set_theme` calls (they restart the dwell); after a theme stop the maze relights itself in ~3 min |
| GET | `/api/sound_mode` | The global sound mode: `{"mode": "unattended"\|"attended", "modes": [...]}`. Attended = staff-run fast pass: sound pools resolve through the `audio_config.json` `effects_attended` overrides (shared-until-edited, curated in the audio console's Attended view); lights/DMX and the floor projector are identical in both modes. Never persisted — every boot is `unattended` |
| POST | `/api/sound_mode` | `{"mode": "attended"\|"unattended"}` — flips which sound selections play. Live beds (maze ambience, room backgrounds, Cuddle floor bed) whose pools differ between modes restart with a fresh pick (listed as `restarted` in the response); one-shots and cues pick the new mode up on their next draw. The sim's Sound Mode button flips it today; the entrance node's physical switch will POST the same body |
| GET | `/api/floor_state` | What the server believes the Cuddle floor show is doing: `theme`, `active`, the `bed` pool playing, the `ambient` one-shot pool armed, `has_sounds`, and `age_s` since the renderer last reported (`null` = never) |
| POST | `/api/next_floor_theme` | Switches the projector's floor theme through the renderer's control port (`FLOOR_CTL_URL`, default `:5002`) and recolours the room to match. Body `{"theme": "lava"}` picks one; an empty body cycles |
| POST | `/api/telemetry` | Records arbitrary node/sensor telemetry. Accepts one event object or `{"events": [...]}` batch; server UTC receive time is authoritative |
| GET | `/api/sensor_events` | Queries stored events. Filters: `room`, `event_type`, `since`, `since_s`, `until`, `limit`, `order=asc` |
| GET | `/api/sensor_events.csv` | CSV export of the same event query |
| GET | `/api/analytics/room_dwell` | Derives room visits and dwell summaries from `room_entry` + `room_vacated`; add `include_visits=1` for raw visit pairs |
| GET | `/api/analytics/maze_runs` | Infers maze runs, duration and completion from route-ordered room entries. `timeout_s` controls abandonment cutoff |
| GET | `/api/analytics/abandonment` | Counts inferred incomplete runs by last room seen |
| GET | `/api/analytics/room_heatmap` | Coarse room-level heatmap weights from visits and dwell |
| GET | `/api/photobomb/photos` | Photo booth captures, newest first (`photos_dir`, capture `backend`, and per-photo filename/size/timestamp) |
| GET | `/api/photobomb/photos/<filename>` | Serves one captured photo (JPEG) |
| POST | `/api/shutdown` | Powers off the server host and all connected units after 3 seconds |
| POST | `/api/kill_process` | Immediately terminates the server process (docker restarts it) |

## Error Handling

All API endpoints will return appropriate HTTP status codes:

- 200: Success
- 400: Bad Request
- 404: Not Found
- 500: Internal Server Error

Most error responses include a JSON body of the form:

```json
{
  "status": "error",
  "message": "Error description"
}
```

Exception: `/api/run_test` and `/api/stop_test` return `{"message": ...}` on success and `{"error": ...}` on failure.

## WebSocket API

In addition to the RESTful API, the system communicates with the room units via WebSockets on:

```
ws://<server-ip>:8765
```

Clients send `client_connected` (with `unit_name` and `associated_rooms`) and `status_update`. (`trigger_event` is accepted but legacy/unused — nothing sends it; all triggering is the REST API.) The server sends `connection_response`, `status_update_response`, `audio_files_to_download`, `play_effect_audio`, `audio_stop`, `start_maze_ambience`, `stop_maze_ambience`, room ambience commands, and `shutdown`. See `client/websocket_client.py` for the message shapes.
