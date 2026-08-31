import os
import sys
import glob
import time
import json
import logging
import asyncio
import subprocess
import traceback
import urllib.error
import urllib.request
import websockets
from quart import Quart, request, jsonify, Response, send_from_directory, send_file
from quart_cors import cors
from dmx_state_manager import DMXStateManager
import dmx_interface
from dmx_interface import DMXOutputManager
from artnet_output_manager import ArtNetOutputManager
from light_config_manager import LightConfigManager
from effects_manager import EffectsManager
from remote_host_manager import RemoteHostManager
from audio_manager import AudioManager, SOUND_MODES
from node_audio_manager import NodeAudioManager
from live_audio import LiveAudioHub
from floor_show_manager import FloorShowManager, read_saved_theme
from room_background_manager import RoomBackgroundManager
from maze_ambient_manager import MazeAmbientManager
from maze_ambience_manager import MazeAmbienceManager
from camera_manager import CameraManager
from telemetry_store import TelemetryStore
from effects.photobomb_shot import SHUTTER_OFFSET
from effects.moop_march import MOOP_WIN_RGB, MOOP_WIN_TOTAL
from photobooth import PhotoBoothSession

# Configuration
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
# ids 0-19: the 20 maze pars/spots (ch 1-160); ids 20-43: the 24 Camp Sign
# letter/logo zones (ch 161-352, ESP32 bridge out front). This one constant
# sizes the DMX state, the FTDI frame, the Art-Net payload the room nodes
# receive (zero-padded to 512 on the wire) and the sim's virtual universe.
NUM_FIXTURES = 44
CHANNELS_PER_FIXTURE = 8
# The camp sign's arcade storm button (wiring-guides/camp-sign-plan.md):
# every accepted press = Lightning + its thunder in every room and on every
# speaker at once. ONE server-side cooldown covers all sources (the sign
# node's POST, the sim's panel button) — presses inside it get 429.
SIGN_STORM_COOLDOWN_S = 30
DOORWAY_ENTRY_SUPPRESS_PAD_S = 5
DOORWAY_ENTRY_ONE_SHOTS = {
    ("Entrance", "Entrance"),
    ("Exit", "Exit"),
}
BACKTRACK_EFFECT_NAME = "Backtrack"
BACKTRACK_TOKEN_TTL_S = 180
BACKTRACK_ROOM_BLOCK_S = 30
BACKTRACK_ENTRANCE_RESET_S = 8
BACKTRACK_FORWARD_MIN_STEPS = 2
BACKTRACK_REVERSE_TRIGGER_STEPS = 1
BACKTRACK_BLIND_REVERSE_ENTRY_ROOMS = {"Entrance"}
PHOTOBOMB_ROOM = "Photo Bomb Room"
PHOTOBOMB_SHOT_EFFECT = "PhotoBomb-Shot"
PHOTOBOMB_ENTRY_EFFECT = "PhotoBomb-BG"
# Victory/failure ride the shared answer cues: the audio layer swaps in the
# room-local PhotoBombRoom-RightAnswer / -WrongAnswer pools once the console
# assigns them files, and falls back to the shared chime/fail sounds until then.
PHOTOBOMB_VICTORY_EFFECT = "PhotoBomb-Landed"   # lights-only: snap is on-node
PHOTOBOMB_FAIL_EFFECT = "WrongAnswer"
# The chime fires a beat after the photo LANDS ON DISK (on_captured): the real
# capture completes ~1.9s in (fswebcam open + warm-up), so +0.8s puts the click
# right at the shot effect's tail. Synthetic captures land much earlier and the
# chime overlaps the flash — cosmetic, sim/bench only.
PHOTOBOMB_VICTORY_DELAY_S = 0.8
# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)
logging.getLogger('pyftdi.ftdi').setLevel(logging.WARNING)
# aioesphomeapi logs its own WARNING for every failed connect attempt. The
# node-audio keepalive already reports connected/lost transitions at INFO, so
# a powered-off room box must not spam the log on each retry (the 2026-08-21
# storm: 5 benched boxes ~ 40 warnings/min, drowning the ring buffer).
logging.getLogger('aioesphomeapi.connection').setLevel(logging.ERROR)

app = Quart(__name__, static_folder='frontend/static')
app = cors(app)
telemetry_store = TelemetryStore(os.environ.get(
    'LOHP_TELEMETRY_DB', os.path.join('data', 'telemetry.sqlite3')))

connected_clients = set()
_doorway_entry_last_fire = {}


def _source_ip():
    forwarded = request.headers.get('X-Forwarded-For', '')
    if forwarded:
        return forwarded.split(',', 1)[0].strip()
    return request.remote_addr


_telemetry_writes = set()  # keep in-flight executor futures referenced


def _record_event(event_type, room=None, effect_name=None, value=None,
                  sensor_type=None, sensor_name=None, node_name=None,
                  node_uptime_ms=None, seq=None):
    """Queue a telemetry INSERT on a worker thread. The SD-card write used
    to run ON the event loop ahead of the response — every trigger paid an
    fsync before its lights moved (live-night lag, 2026-08-31). Request-
    bound fields are snapshotted here; returns True as an opaque handle
    (only the unused /api/telemetry batch route ever echoed the row id)."""
    kwargs = dict(
        event_type=event_type, room=room, node_name=node_name,
        sensor_type=sensor_type, sensor_name=sensor_name,
        effect_name=effect_name, value=value,
        source_ip=_source_ip(),
        user_agent=request.headers.get('User-Agent', ''),
        node_uptime_ms=node_uptime_ms, seq=seq)

    def write():
        try:
            telemetry_store.record_event(**kwargs)
        except Exception as e:
            logger.error(f"Telemetry write failed for {event_type}: {e}",
                         exc_info=True)

    try:
        future = asyncio.get_running_loop().run_in_executor(None, write)
        _telemetry_writes.add(future)
        future.add_done_callback(_telemetry_writes.discard)
    except RuntimeError:
        write()  # no running loop (tests) — inline
    return True


def _doorway_entry_suppressed(room, effect_name, effect_data, now=None):
    """Entrance/Exit ToF sensors can re-post while a visitor is still crossing.
    These effects should pick exactly one random audio file per crossing, so
    repeated posts inside the effect window become harmless no-ops.

    The backtrack warning gets the same treatment in EVERY room: a blocked room
    answers each re-trigger with the warning instead of its own effect, so a
    visitor standing in a blocked room used to collect a fresh 2.4 s red/amber
    strobe on every sensor re-post (28 of them in one walkthrough — the most
    fired effect in the log, and what reads as "rapidly flashing"). One warning
    per pass says the same thing without the strobe.
    """
    key = (room, effect_name)
    if key not in DOORWAY_ENTRY_ONE_SHOTS and effect_name != BACKTRACK_EFFECT_NAME:
        return False, 0, None
    now = now if now is not None else time.monotonic()
    duration = float((effect_data or {}).get('duration') or 0)
    window = max(duration, 0) + DOORWAY_ENTRY_SUPPRESS_PAD_S
    last = _doorway_entry_last_fire.get(key)
    if last is not None and now - last < window:
        return True, window - (now - last), last
    _doorway_entry_last_fire[key] = now
    return False, 0, now


def _clear_doorway_entry_fire(room, effect_name, started_at):
    key = (room, effect_name)
    if _doorway_entry_last_fire.get(key) == started_at:
        _doorway_entry_last_fire.pop(key, None)


def log_and_exit(error_message):
    logger.critical(f"Critical error: {error_message}")
    logger.critical(f"Traceback: {traceback.format_exc()}")
    sys.exit(1)


# --- WebSocket server for the room units ---

async def websocket_handler(websocket, path):
    connected_clients.add(websocket)
    try:
        async for message in websocket:
            data = json.loads(message)
            handlers = {
                'client_connected': handle_client_connected,
                'status_update': handle_status_update,
                'trigger_event': handle_trigger_event,
            }
            handler = handlers.get(data.get('type'))
            if handler:
                await handler(websocket, data)
            else:
                logger.warning(f"Unknown message type received: {data.get('type')}")
                await websocket.send(json.dumps({"status": "error", "message": "Unknown message type"}))
    except websockets.exceptions.ConnectionClosedError as e:
        logger.info(f"WebSocket connection closed: {e}")
    except Exception as e:
        logger.error(f"Error in WebSocket handler: {e}")
    finally:
        connected_clients.discard(websocket)
        remote_host_manager.remove_client_by_websocket(websocket)
        logger.info("WebSocket client disconnected")


async def handle_client_connected(ws, data):
    unit_name = data.get('data', {}).get('unit_name')
    associated_rooms = data.get('data', {}).get('associated_rooms', [])
    client_ip = ws.remote_address[0]
    if unit_name and associated_rooms:
        logger.info(f"Client connected: {unit_name} ({client_ip}) - Associated rooms: {associated_rooms}")
        # Ack first: the client's handshake recv() expects connection_response
        # before any other message (like the audio download list) arrives.
        await ws.send(json.dumps({"type": "connection_response", "status": "success", "message": "Connection acknowledged"}))
        await remote_host_manager.update_client_rooms(unit_name, client_ip, associated_rooms, ws)
    else:
        logger.warning(f"Received incomplete client connection data: {data}")
        await ws.send(json.dumps({"type": "connection_response", "status": "error", "message": "Incomplete connection data"}))


async def handle_status_update(ws, data):
    logger.info(f"Status update received: {data}")
    await ws.send(json.dumps({"type": "status_update_response", "status": "success", "message": "Status update acknowledged"}))


async def handle_trigger_event(ws, data):
    # Units trigger effects via the REST API; this message is informational only.
    logger.info(f"Trigger event received: {data}")
    await ws.send(json.dumps({"type": "trigger_event_response", "status": "success", "message": "Trigger event processed"}))


# --- Component initialization ---

dmx_state_manager = DMXStateManager(NUM_FIXTURES, CHANNELS_PER_FIXTURE)

# Two DMX sinks, config-gated by dmx_nodes.json (wiring-guides/dmx-over-wifi.md):
# Art-Net unicast to the room nodes (the plan of record — cut over 2026-07-22)
# and the legacy FTDI wired chain (ftdi:true resurrects it; a fixture is only
# ever on one chain, so running both is safe). A missing/broken FTDI degrades
# gracefully when Art-Net nodes are enabled; with NO output at all it still
# raises — a maze with zero DMX outputs should crash-loop visibly, not run
# dark. The sim's virtual sink (VIRTUAL flag) is the sim's frame feed, not
# FTDI hardware, so the ftdi flag never gates it.
artnet_output_manager = ArtNetOutputManager.from_config(dmx_state_manager)
try:
    with open('dmx_nodes.json') as _f:
        _ftdi_wanted = json.load(_f).get('ftdi', True)
except FileNotFoundError:
    _ftdi_wanted = True
dmx_output_manager = None
if _ftdi_wanted or getattr(dmx_interface, 'VIRTUAL', False):
    try:
        dmx_output_manager = DMXOutputManager(dmx_state_manager)
    except Exception as e:
        if artnet_output_manager is None:
            raise
        logger.error(f"FTDI output unavailable ({e}) — continuing on Art-Net nodes only")
elif artnet_output_manager is None:
    log_and_exit("dmx_nodes.json disables FTDI but enables no Art-Net nodes — no DMX output")

light_config = LightConfigManager()
if artnet_output_manager is not None:
    # Per-room dirty tracking (2026-08-31): each Art-Net target only gets
    # frames when its own room's channels move (see set_room_slices).
    artnet_output_manager.set_room_slices({
        room: [(f['start_address'] - 1,
                f['start_address'] - 1 + CHANNELS_PER_FIXTURE)
               for f in fixtures]
        for room, fixtures in light_config.get_room_layout().items()})
audio_manager = AudioManager()
node_audio_manager = NodeAudioManager(audio_manager=audio_manager)
live_audio_hub = LiveAudioHub()


def _resolve_audio_file(requested):
    """Path under audio_files/ for a bed's relative file name (same
    resolution serve_audio applies), or None."""
    audio_root = os.path.abspath(os.path.join(os.path.dirname(__file__), 'audio_files'))
    if (os.path.basename(requested) == requested
            and not os.path.exists(os.path.join(audio_root, requested))):
        matches = glob.glob(os.path.join(audio_root, '**', os.path.basename(requested)),
                            recursive=True)
        if matches:
            requested = os.path.relpath(matches[0], audio_root)
    path = os.path.abspath(os.path.join(audio_root, requested))
    if os.path.commonpath([audio_root, path]) != audio_root or not os.path.exists(path):
        return None
    return path


def _node_live_url(node_file, loop):
    """live_url_provider for node_audio_manager: shared realtime broadcast
    (live_audio.py) so beds play the same edge on every box."""
    path = _resolve_audio_file(node_file)
    if path is None:
        return None
    key = live_audio_hub.ensure(path, loop=loop)
    return (f"http://{node_audio_manager.server_host}:"
            f"{node_audio_manager.server_port}/api/audio/live/{key}.mp3")


node_audio_manager.live_url_provider = _node_live_url
remote_host_manager = RemoteHostManager(audio_manager=audio_manager, node_audio=node_audio_manager)
effects_manager = EffectsManager(light_config, dmx_state_manager, remote_host_manager, audio_manager)
camera_manager = CameraManager()
# Cuddle Cross takes its sound and its colour from whatever the floor projector
# is running (floor_show_manager.py). The renderer reports in on
# /api/floor_event; until it does, the room is lit for the theme the projector
# was last showing.
floor_show_manager = FloorShowManager(effects_manager, remote_host_manager)
floor_show_manager.prime_theme(read_saved_theme(os.path.dirname(os.path.abspath(__file__))))

# Always-on maze-wide ambience bed (audio_config.json `maze_ambience`), followed
# by always-on per-room background sound (audio_config.json `room_backgrounds`,
# room_background_manager.py) — a room keeping its own loop regardless of the
# maze-wide ambience bed, and overriding the maze ambience on its speaker while
# it plays. Cuddle Cross is reserved: its bed follows the projection instead.
maze_ambience_manager = MazeAmbienceManager(audio_manager, remote_host_manager)
room_background_manager = RoomBackgroundManager(
    audio_manager, remote_host_manager, reserved_room=floor_show_manager.room)
# Roaming ambient one-shots (audio_config.json `ambient_oneshots`,
# maze_ambient_manager.py) — random files on random timers: per-room pools
# (the Entrance's hallow murmurs) plus a maze-wide pool that lands one crow/
# owl/wolf in a different random room each firing. Cuddle Cross is reserved
# here too — the floor show owns that room's ambience.
maze_ambient_manager = MazeAmbientManager(
    audio_manager, remote_host_manager, reserved_room=floor_show_manager.room)
# Reconnecting audio clients (a reloaded sim tab, a rebooted unit) ask these
# for the beds their rooms should already be playing.
remote_host_manager.maze_bed_providers.append(maze_ambience_manager.bed)
remote_host_manager.bed_providers += [floor_show_manager.bed_for_room,
                                      room_background_manager.bed_for_room]
remote_host_manager.client_gone_hooks.append(room_background_manager.client_gone)

# Photo Bomb camera: every PhotoBomb-Shot run schedules a webcam capture at the
# flash; a superseded/stopped run (button re-press restarts the countdown)
# cancels it so exactly one photo comes out of the last full countdown.
effects_manager.register_effect_hooks(
    PHOTOBOMB_SHOT_EFFECT,
    on_start=lambda room: camera_manager.schedule_capture(SHUTTER_OFFSET, room),
    on_cancel=lambda room: camera_manager.cancel_pending(),
)

# Vertical Moop March win (Tim 2026-08-17): all four buttons inside the round
# slam the room to SOLID victory green and HOLD it until the radar reports the
# room empty. The hook arms the theme_manager win hold the moment the victory
# effect actually starts; the effect's last frame equals the hold, so the room
# just stays green when it ends. /api/room_vacated -> set_room_occupied(False)
# releases it. No on_cancel: a press superseding the victory bloom must not
# un-win the room.
effects_manager.register_effect_hooks(
    "VerticalMoopMarch-RightAnswer",
    on_start=lambda room: effects_manager.theme_manager.set_room_win_hold(
        room, MOOP_WIN_RGB, MOOP_WIN_TOTAL),
)

# Photo Bomb game state: entry starts the room bed; shots are limited to
# MAX_SHOTS per rolling WINDOW_S seconds (photobooth.py, Tim 2026-08-22) —
# over-window presses fail until the window drains.
photobooth = PhotoBoothSession()
_photobomb_victory_task = None


def _cancel_photobomb_victory():
    global _photobomb_victory_task
    if _photobomb_victory_task and not _photobomb_victory_task.done():
        _photobomb_victory_task.cancel()
    _photobomb_victory_task = None


def _on_photobomb_captured(room, path):
    """A photo actually landed on disk = the room objective. Chime the victory
    cue once the shot effect's outro settles; a new press before it fires
    cancels it (the run_effect intercept), so back-to-back shots chime once."""
    global _photobomb_victory_task
    _cancel_photobomb_victory()

    async def victory():
        await asyncio.sleep(PHOTOBOMB_VICTORY_DELAY_S)
        await effects_manager.apply_effect_to_room(room or PHOTOBOMB_ROOM,
                                                   PHOTOBOMB_VICTORY_EFFECT)
    _photobomb_victory_task = asyncio.create_task(victory())


camera_manager.on_captured = _on_photobomb_captured


def _load_maze_route_tracking():
    """Route order, entry effects (reverse-travel inference), and the rooms
    with the full occupancy pair (leave_action) — the ones that hold their
    occupied colour lock until the radar reports them empty."""
    route = []
    entry_effects = {}
    hold_rooms = set()
    try:
        with open(os.path.join('sim', 'maze_layout.json')) as f:
            route = json.load(f).get('route', [])
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"Maze route tracking disabled; could not read route: {e}")
    try:
        with open('triggers.json') as f:
            for trig in json.load(f).get('triggers', []):
                if trig.get('type') != 'presence':
                    continue
                if trig.get('leave_action'):
                    hold_rooms.add(trig['room'])
                action = trig.get('action') or {}
                effect = (action.get('data') or {}).get('effect_name')
                if (
                    action.get('path') != '/api/run_effect'
                    or not effect
                    or trig.get('room') in entry_effects
                ):
                    continue
                entry_effects[trig['room']] = effect
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"Maze route tracking disabled; could not read entry triggers: {e}")
        entry_effects = {}
        hold_rooms = set()
    entry_route = [room for room in route if room in entry_effects]
    return entry_route, {room: i for i, room in enumerate(entry_route)}, entry_effects, hold_rooms


MAZE_ENTRY_ROUTE, MAZE_ENTRY_INDEX, MAZE_ENTRY_EFFECTS, MAZE_HOLD_ROOMS = _load_maze_route_tracking()
_route_tokens = []
_next_route_token_id = 1
_backtrack_room_until = {}


def _reset_route_tracking():
    _route_tokens.clear()
    _backtrack_room_until.clear()


def _prune_route_tokens(now):
    _route_tokens[:] = [
        token for token in _route_tokens
        if now - token['updated_at'] <= BACKTRACK_TOKEN_TTL_S
    ]
    for room, until in list(_backtrack_room_until.items()):
        if now >= until:
            _backtrack_room_until.pop(room, None)


def _route_tracking_idle(now, idle_s):
    activity_times = [token['updated_at'] for token in _route_tokens]
    activity_times.extend(
        until - BACKTRACK_ROOM_BLOCK_S
        for until in _backtrack_room_until.values()
        if now < until
    )
    if not activity_times:
        return True
    return now - max(activity_times) >= idle_s


def _maybe_reset_route_start(room, effect_name):
    if (
        MAZE_ENTRY_ROUTE
        and room == MAZE_ENTRY_ROUTE[0]
        and MAZE_ENTRY_EFFECTS.get(room) == effect_name
    ):
        now = time.monotonic()
        _prune_route_tokens(now)
        if _route_tracking_idle(now, BACKTRACK_ENTRANCE_RESET_S):
            logger.info("Resetting route backtrack state for new Entrance start")
            _reset_route_tracking()


def _route_token_at(index):
    candidates = [t for t in _route_tokens if t['index'] == index]
    if not candidates:
        return None
    return max(candidates, key=lambda t: t['updated_at'])


def _nearest_route_token_before(index):
    candidates = [t for t in _route_tokens if t['index'] < index]
    if not candidates:
        return None
    return max(candidates, key=lambda t: (t['index'], t['updated_at']))


def _nearest_route_token_after(index):
    candidates = [t for t in _route_tokens if t['index'] > index]
    if not candidates:
        return None
    return min(candidates, key=lambda t: (t['index'], -t['updated_at']))


def _move_route_token(token, index, room, now):
    old_index = token['index']
    if index > token['index']:
        token['forward_steps'] += index - token['index']
        token['reverse_steps'] = 0
        direction = 'forward'
    elif index < token['index']:
        token['reverse_steps'] += token['index'] - index
        direction = 'reverse'
    else:
        direction = 'same'
    token['last_index'] = old_index
    token['last_move_direction'] = direction
    token['last_moved_at'] = now
    token['index'] = index
    token['room'] = room
    token['updated_at'] = now
    token['occupied'] = True
    return direction


def _new_route_token(index, room, now):
    global _next_route_token_id
    token = {
        'id': _next_route_token_id,
        'index': index,
        'room': room,
        'updated_at': now,
        'occupied': True,
        'forward_steps': 0,
        'reverse_steps': 0,
        'last_index': None,
        'last_move_direction': None,
        'last_moved_at': now,
    }
    _next_route_token_id += 1
    _route_tokens.append(token)
    return token


def _route_entry_action(room, effect_name):
    """Infer reverse travel from triggerable route-room transitions.

    There is no visitor id in node POSTs, so tokens are the best server-side
    approximation: forward entries consume a token from the previous triggerable
    room, while reverse entries consume a token from the next triggerable room.
    A token must move forward a couple of rooms before reverse entries flip
    rooms into Backtrack. Stale tokens expire so abandoned runs stop suppressing
    normal room entries.
    """
    index = MAZE_ENTRY_INDEX.get(room)
    if index is None or MAZE_ENTRY_EFFECTS.get(room) != effect_name:
        return None

    now = time.monotonic()
    _prune_route_tokens(now)

    same_token = _route_token_at(index)
    if same_token:
        _move_route_token(same_token, index, room, now)
        if same_token.get('reverse_steps', 0) >= BACKTRACK_REVERSE_TRIGGER_STEPS:
            return 'backtrack'
        return 'same'

    next_token = _nearest_route_token_after(index)
    prev_token = _nearest_route_token_before(index)
    reverse_candidate = (
        next_token
        and next_token.get('forward_steps', 0) >= BACKTRACK_FORWARD_MIN_STEPS
    )
    if reverse_candidate:
        _move_route_token(next_token, index, room, now)
        is_backtrack = next_token['reverse_steps'] >= BACKTRACK_REVERSE_TRIGGER_STEPS
        logger.info(f"Reverse route step into {room} from route token "
                    f"{next_token['id']} ({next_token['reverse_steps']}/"
                    f"{BACKTRACK_REVERSE_TRIGGER_STEPS})")
        return 'backtrack' if is_backtrack else 'reverse'

    if prev_token:
        _move_route_token(prev_token, index, room, now)
        return 'forward'

    _new_route_token(index, room, now)
    return 'new'


def _set_room_backtrack_block(room):
    _backtrack_room_until[room] = time.monotonic() + BACKTRACK_ROOM_BLOCK_S


def _clear_room_backtrack_block(room):
    _backtrack_room_until.pop(room, None)


def _room_backtrack_blocked(room):
    until = _backtrack_room_until.get(room)
    if until is None:
        return False
    if time.monotonic() >= until:
        _backtrack_room_until.pop(room, None)
        return False
    return True


def _route_room_vacated(room):
    index = MAZE_ENTRY_INDEX.get(room)
    if index is None:
        return None
    now = time.monotonic()
    _prune_route_tokens(now)
    token = _route_token_at(index)
    if not token:
        token = _nearest_route_token_after(index)
        if not token:
            return None
        just_moved_forward_from_room = (
            token.get('last_index') == index
            and token.get('last_move_direction') == 'forward'
            and now - token.get('last_moved_at', 0) < 8
        )
        if just_moved_forward_from_room:
            return None
        if token.get('forward_steps', 0) < BACKTRACK_FORWARD_MIN_STEPS:
            return None
        _move_route_token(token, index, room, now)
    if token:
        target_index = index - 1
        target_room = MAZE_ENTRY_ROUTE[target_index] if target_index >= 0 else None
        reverse_departure = token.get('last_move_direction') == 'reverse'
        blind_reverse_ready = (
            reverse_departure
            and target_room in BACKTRACK_BLIND_REVERSE_ENTRY_ROOMS
            and token.get('reverse_steps', 0) >= BACKTRACK_REVERSE_TRIGGER_STEPS
        )
        if blind_reverse_ready:
            _move_route_token(token, target_index, target_room, now)
            token['occupied'] = False
            logger.info(f"Reverse route step toward blind entry {target_room}; "
                        f"firing {BACKTRACK_EFFECT_NAME} from {room}")
            return target_room
        token['occupied'] = False
        token['updated_at'] = now
    return None

dmx_state_manager.reset_all_fixtures()
if dmx_output_manager:
    dmx_output_manager.start()
if artnet_output_manager:
    artnet_output_manager.start()
effects_manager.stop_current_theme()


# --- REST API ---

@app.route('/')
async def index():
    return await send_file('frontend/index.html')


@app.route('/api/set_master_brightness', methods=['POST'])
async def set_master_brightness():
    data = await request.json
    brightness = float(data.get('brightness', 1.0))
    effects_manager.set_master_brightness(brightness)
    return jsonify({"status": "success", "master_brightness": brightness})


@app.route('/api/attract', methods=['GET'])
async def get_attract():
    """The maze's self-running look rotation: enabled, dwell, theme list,
    seconds to the next change."""
    return jsonify(effects_manager.theme_manager.attract_state())


@app.route('/api/attract', methods=['POST'])
async def post_attract():
    """{"on": bool, "dwell_s": secs?, "themes": [...]?} — attract mode keeps
    rotating after manual /api/set_theme calls (they just restart the dwell);
    "on": false hands the stage back to whoever is driving."""
    data = await request.json or {}
    await effects_manager.theme_manager.set_attract(
        data.get('on', True), data.get('dwell_s'), data.get('themes'))
    return jsonify({'status': 'success', **effects_manager.theme_manager.attract_state()})


@app.route('/api/set_theme', methods=['POST'])
async def set_theme():
    data = await request.json
    theme_name = data.get('theme_name')
    next_theme = data.get('next_theme', False)

    try:
        if next_theme:
            next_theme_name = await effects_manager.set_next_theme_async()
            if next_theme_name:
                return jsonify({'status': 'success', 'message': f'Theme set to next theme: {next_theme_name}'})
            return jsonify({'status': 'error', 'message': 'Failed to set next theme'}), 400

        if theme_name:
            if theme_name.lower() == 'notheme':
                await effects_manager.stop_current_theme_async()
                return jsonify({'status': 'success', 'message': 'Theme turned off'})

            try:
                success = await asyncio.wait_for(effects_manager.set_current_theme_async(theme_name), timeout=2.0)
                if success:
                    return jsonify({'status': 'success', 'message': f'Theme set to {theme_name}'})
                return jsonify({'status': 'error', 'message': f'Failed to set theme to {theme_name}'}), 400
            except asyncio.TimeoutError:
                logger.error(f"Timeout while setting theme to: {theme_name}")
                return jsonify({'status': 'error', 'message': f'Timeout while setting theme to {theme_name}'}), 504

        return jsonify({'status': 'error', 'message': 'Theme name or next_theme flag is required'}), 400
    except Exception as e:
        logger.error(f"Error setting theme: {e}")
        return jsonify({'status': 'error', 'message': f'An error occurred while setting the theme: {e}'}), 500


@app.route('/api/run_effect', methods=['POST'])
async def run_effect():
    data = await request.json
    room = data.get('room')
    effect_name = data.get('effect_name')
    requested_effect_name = effect_name
    # The firing sensor's name ("Moop Button 2") — nodes and the sim both send
    # it; per-button light overrides key on it (effects_manager).
    trigger_name = data.get('trigger_name')

    if not room or not effect_name:
        return jsonify({'status': 'error', 'message': 'Room and effect_name are required'}), 400

    if not effects_manager.get_effect(effect_name):
        return jsonify({'status': 'error', 'message': f'Effect {effect_name} not found'}), 404

    try:
        trigger_effect_name = effect_name
        trigger_event_type = (
            'room_entry' if MAZE_ENTRY_EFFECTS.get(room) == trigger_effect_name
            else 'effect_trigger'
        )
        # Entry in a full-occupancy-pair room pins the room to its own colour
        # (theme_manager OCCUPIED_MIX) until /api/room_vacated releases it —
        # the entry effect plays over it, then the room settles into the held
        # look instead of the plain theme blend.
        if trigger_event_type == 'room_entry' and room in MAZE_HOLD_ROOMS:
            effects_manager.set_room_occupied(room, True)
        _maybe_reset_route_start(room, effect_name)
        route_action = _route_entry_action(room, effect_name)
        if route_action == 'forward':
            _clear_room_backtrack_block(room)
        elif route_action == 'backtrack':
            _set_room_backtrack_block(room)
            effect_name = BACKTRACK_EFFECT_NAME
        elif _room_backtrack_blocked(room):
            effect_name = BACKTRACK_EFFECT_NAME
        elif route_action in ('same', 'new'):
            _clear_room_backtrack_block(room)

        # Photo Bomb booth: entries reset the shot budget; presses past it get
        # the failure cue instead of a countdown. Runs after the backtrack
        # rewrites so reverse travel neither counts shots nor resets sessions.
        if room == PHOTOBOMB_ROOM:
            if effect_name == PHOTOBOMB_ENTRY_EFFECT:
                photobooth.entered()
            elif effect_name == PHOTOBOMB_SHOT_EFFECT:
                _cancel_photobomb_victory()
                if not photobooth.press():
                    logger.info(
                        f"Photo Bomb window full ({photobooth.max_shots} shots "
                        f"in {photobooth.window_s:.0f}s); firing failure cue")
                    effect_name = PHOTOBOMB_FAIL_EFFECT

        effect_data = effects_manager.get_effect(effect_name)
        if not effect_data:
            return jsonify({'status': 'error', 'message': f'Effect {effect_name} not found'}), 404

        suppressed, remaining, started_at = _doorway_entry_suppressed(
            room, effect_name, effect_data)
        if suppressed:
            logger.info(f"Suppressing duplicate {room} {effect_name} entry trigger "
                        f"({remaining:.1f}s left in one-shot window)")
            _record_event(
                f"{trigger_event_type}_suppressed",
                room=room,
                effect_name=effect_name,
                value={
                    'requested_effect_name': requested_effect_name,
                    'trigger_effect_name': trigger_effect_name,
                    'route_action': route_action,
                    'retry_after_s': round(remaining, 1),
                    'payload': data,
                },
            )
            return jsonify({
                'status': 'success',
                'message': f'Effect {effect_name} already running/recent in room {room}',
                'suppressed': True,
                'retry_after_s': round(remaining, 1),
            })

        _record_event(
            trigger_event_type,
            room=room,
            effect_name=effect_name,
            value={
                'requested_effect_name': requested_effect_name,
                'trigger_effect_name': trigger_effect_name,
                'route_action': route_action,
                'payload': data,
            },
        )

        async def execute_effect():
            success, message = await effects_manager.apply_effect_to_room(
                room, effect_name, effect_data, trigger_name=trigger_name)
            if success:
                return True, message
            _clear_doorway_entry_fire(room, effect_name, started_at)
            logger.error(f"Failed to execute effect {effect_name} in room {room}: {message}")
            return False, message

        user_agent = request.headers.get('User-Agent', '')
        if user_agent.startswith('ESPHome/'):
            async def background_execute_effect():
                try:
                    await execute_effect()
                except Exception as e:
                    _clear_doorway_entry_fire(room, effect_name, started_at)
                    logger.error(f"Async ESPHome effect {effect_name} for room {room} failed: {e}",
                                 exc_info=True)

            asyncio.create_task(background_execute_effect())
            return jsonify({
                'status': 'success',
                'message': f'Effect {effect_name} accepted for room {room}',
                'accepted': True,
            })

        success, message = await execute_effect()
        if success:
            return jsonify({'status': 'success', 'message': f'Effect {effect_name} executed in room {room}'})
        _record_event(
            'effect_failed',
            room=room,
            effect_name=effect_name,
            value={'requested_effect_name': requested_effect_name, 'message': message},
        )
        return jsonify({'status': 'error', 'message': message}), 500
    except Exception as e:
        error_message = f"Error executing effect {effect_name} for room {room}: {e}"
        _record_event(
            'effect_error',
            room=room,
            effect_name=effect_name,
            value={'requested_effect_name': requested_effect_name, 'error': str(e)},
        )
        logger.error(error_message, exc_info=True)
        return jsonify({'status': 'error', 'message': error_message}), 500


@app.route('/api/run_effect_all_rooms', methods=['POST'])
async def run_effect_all_rooms():
    data = await request.json
    effect_name = data.get('effect_name')

    if not effect_name:
        return jsonify({'status': 'error', 'message': 'Effect name is required'}), 400

    if not effects_manager.get_effect(effect_name):
        return jsonify({'status': 'error', 'message': f'Effect {effect_name} not found'}), 404

    try:
        success, message = await effects_manager.apply_effect_to_all_rooms(effect_name, data.get('audio'))
        if success:
            return jsonify({'status': 'success', 'message': f'Effect {effect_name} executed in all rooms'})
        logger.error(message)
        return jsonify({'status': 'error', 'message': message}), 500
    except Exception as e:
        error_message = f"Error executing effect {effect_name} for all rooms: {e}"
        logger.error(error_message, exc_info=True)
        return jsonify({'status': 'error', 'message': error_message}), 500


_sign_storm_last_fire = None  # time.monotonic() of the last accepted press


@app.route('/api/sign_storm', methods=['POST'])
async def sign_storm():
    """The camp-sign arcade button: maze-wide Lightning + thunder on every
    speaker simultaneously, behind one shared cooldown."""
    global _sign_storm_last_fire
    now = time.monotonic()
    if _sign_storm_last_fire is not None:
        remaining = SIGN_STORM_COOLDOWN_S - (now - _sign_storm_last_fire)
        if remaining > 0:
            return jsonify({'status': 'cooldown',
                            'retry_after_s': round(remaining, 1),
                            'message': f'storm cooling down — {remaining:.0f}s left'}), 429
    # Check-and-stamp with no await between them = atomic on the event loop;
    # stamping before the run keeps presses during the strike in the cooldown.
    _sign_storm_last_fire = now
    try:
        success, message = await effects_manager.apply_effect_to_all_rooms('Lightning')
        if success:
            return jsonify({'status': 'success', 'message': 'Storm fired maze-wide'})
        _sign_storm_last_fire = None  # a failed strike shouldn't burn the cooldown
        logger.error(f"Sign storm failed: {message}")
        return jsonify({'status': 'error', 'message': message}), 500
    except Exception as e:
        _sign_storm_last_fire = None
        error_message = f"Error firing the sign storm: {e}"
        logger.error(error_message, exc_info=True)
        return jsonify({'status': 'error', 'message': error_message}), 500


@app.route('/api/stop_effect', methods=['POST'])
async def stop_effect():
    data = await request.json
    room = data.get('room')
    try:
        await effects_manager.stop_current_effect(room)
        if room is None:
            # Stop-all must mean silence, and the floor bed rides its own
            # channel. A running projection show starts it again on its next
            # report — the projector owns whether the deck has a show on it.
            await floor_show_manager.stop()
        message = f"Effect stopped in room: {room}" if room else "Effects stopped in all rooms"
        return jsonify({'status': 'success', 'message': message})
    except Exception as e:
        logger.error(f"Error stopping effect: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500


def _room_leave_effect(room):
    """The opt-in leave-sound pool for a room (audio_config
    `room_leave_sounds`), or None. Case-insensitive on the room name and read
    per call, so /api/reload_audio_config picks up edits."""
    sounds = audio_manager.audio_config.get('room_leave_sounds') or {}
    for name, effect in sounds.items():
        if not name.startswith('_') and name.lower() == room.lower():
            return effect
    return None


@app.route('/api/room_vacated', methods=['POST'])
async def room_vacated():
    """A room node reporting that its radar lost the last visitor — the
    `leave_action` half of the occupancy contract in triggers.json.

    Same work as a per-room /api/stop_effect (cancel anything still running,
    silence lingering effect audio, hand the room back to the theme), but it is
    the room reporting a fact rather than an operator issuing a stop, and it
    reads as one in the log when something misbehaves at the maze. Maze
    ambience is deliberately untouched: it never stopped, and effect audio
    mixes over it rather than replacing it."""
    data = await request.json
    room = data.get('room')
    if not room:
        return jsonify({'status': 'error', 'message': 'Room is required'}), 400
    try:
        _record_event('room_vacated', room=room, value={'payload': data})
        logger.info(f"Room vacated: {room}")
        # Release the occupied colour lock first: the theme repaint inside
        # stop_effect_in_room's resume must render the plain room blend.
        effects_manager.set_room_occupied(room, False)
        if room == PHOTOBOMB_ROOM:
            photobooth.vacated()
            _cancel_photobomb_victory()
        blind_backtrack_room = _route_room_vacated(room)
    except Exception as e:
        logger.error(f"Error handling vacate for room {room}: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500

    async def finish_vacate():
        if blind_backtrack_room:
            _set_room_backtrack_block(room)
            _set_room_backtrack_block(blind_backtrack_room)
            success, message = await effects_manager.apply_effect_to_room(room, BACKTRACK_EFFECT_NAME)
            if not success:
                raise RuntimeError(message)
            return f'Room {room} vacated; {BACKTRACK_EFFECT_NAME} fired'
        interrupted_effect = await effects_manager.stop_effect_in_room(room)
        # Opt-in send-off: a room can name a one-shot pool to fire as its last
        # visitor leaves (audio_config `room_leave_sounds` — Cop Dodge and
        # Sparkle Pony, Tim 2026-08-01). Only fire it after the entry effect has
        # completed; if vacate had to interrupt the active effect, the visitor
        # ran through before the current sound/show finished and a send-off
        # would pile on late.
        leave_effect = _room_leave_effect(room)
        if leave_effect and interrupted_effect:
            logger.info(f"Leave sound {leave_effect} skipped in {room}: "
                        "vacate interrupted the active effect")
        elif leave_effect:
            await remote_host_manager.play_effect_audio(leave_effect, rooms=[room])
            logger.info(f"Leave sound {leave_effect} fired in {room}")
        return f'Room {room} vacated'

    # Fast-return for node posts, mirroring run_effect: the slow half
    # (stop-effect round trips, blind-backtrack's 2.4 s effect, leave
    # sounds) used to blow the node's 3 s HTTP timeout, and its mode:single
    # script had already cleared occupancy — the vacate was silently LOST
    # and the room stayed colour-locked (live-night lag, 2026-08-31).
    if request.headers.get('User-Agent', '').startswith('ESPHome/'):
        async def background_finish():
            try:
                await finish_vacate()
            except Exception as e:
                logger.error(f"Async vacate for room {room} failed: {e}",
                             exc_info=True)
        asyncio.create_task(background_finish())
        return jsonify({'status': 'success',
                        'message': f'Vacate accepted for room {room}',
                        'accepted': True})
    try:
        message = await finish_vacate()
        return jsonify({'status': 'success', 'message': message})
    except Exception as e:
        logger.error(f"Error handling vacate for room {room}: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/audio_files_to_download', methods=['GET'])
def get_audio_files_to_download():
    return jsonify(audio_manager.get_audio_files_to_download())


@app.route('/api/reload_audio_config', methods=['POST'])
def reload_audio_config():
    """Re-read audio_config.json without a restart, after the audio pool console
    (tools/audio_console.py) edits it. AudioManager is the only holder of the
    parsed config; its anti-repeat history re-sizes itself to the new pools."""
    audio_manager.audio_config = audio_manager.load_config()
    pools = {name: len(cfg.get('audio_files', []))
             for name, cfg in audio_manager.audio_config.get('effects', {}).items()}
    logger.info(f"Audio config reloaded: {len(pools)} pools, "
                f"{sum(pools.values())} files")
    return jsonify({'status': 'success', 'pools': pools,
                    'message': f'{len(pools)} pools, {sum(pools.values())} files'})


@app.route('/api/rooms', methods=['GET'])
@app.route('/api/room_layout', methods=['GET'])
def get_rooms():
    return jsonify(light_config.get_room_layout())


@app.route('/api/effects_details', methods=['GET'])
def get_effects_details():
    return jsonify(effects_manager.get_all_effects())


@app.route('/api/effects_list', methods=['GET'])
def get_effects_list():
    return jsonify(effects_manager.get_effects_list())


@app.route('/api/themes', methods=['GET'])
def get_themes():
    return jsonify(effects_manager.get_all_themes())


@app.route('/api/light_models', methods=['GET'])
def get_light_models():
    return jsonify(light_config.get_light_models())


@app.route('/api/light_fixtures', methods=['GET'])
def get_light_fixtures():
    room_layout = light_config.get_room_layout()
    output = "ROBCO INDUSTRIES UNIFIED OPERATING SYSTEM\n"
    output += "COPYRIGHT 2075-2077 ROBCO INDUSTRIES\n"
    output += "----- LIGHT FIXTURES DATABASE -----\n\n"
    for room, lights in room_layout.items():
        output += f"ROOM: {room}\n"
        for light in lights:
            output += f"  MODEL: {light['model']}\n"
            output += f"  START ADDRESS: {light['start_address']}\n"
        output += "\n"
    return Response(output, mimetype='text/plain')


@app.route('/api/connected_clients', methods=['GET'])
def get_connected_clients():
    return jsonify(remote_host_manager.get_connected_clients_info())


@app.route('/api/terminate_client', methods=['POST'])
async def terminate_client():
    data = await request.json
    client_ip = data.get('ip')
    if not client_ip:
        return jsonify({'status': 'error', 'message': 'Client IP is required'}), 400
    if await remote_host_manager.terminate_client(client_ip):
        return jsonify({'status': 'success', 'message': f'Client {client_ip} terminated successfully'})
    return jsonify({'status': 'error', 'message': f'Failed to terminate client {client_ip}'}), 500


@app.route('/api/rooms_units_fixtures', methods=['GET'])
def get_rooms_units_fixtures():
    room_layout = light_config.get_room_layout()
    clients = remote_host_manager.get_connected_clients_info()
    return jsonify({
        room: {
            'fixtures': [{'model': f['model'], 'start_address': f['start_address']} for f in fixtures],
            'units': [client['name'] for client in clients if room in client['rooms']]
        }
        for room, fixtures in room_layout.items()
    })


@app.route('/api/update_theme_value', methods=['POST'])
async def update_theme_value():
    data = await request.json
    control_id = data.get('control_id')
    value = data.get('value')
    if control_id is None or value is None:
        return jsonify({'status': 'error', 'message': 'Missing control_id or value'}), 400
    if await effects_manager.update_theme_value(control_id, value):
        return jsonify({'status': 'success', 'message': f'Updated {control_id} to {value}'})
    return jsonify({'status': 'error', 'message': 'Failed to update theme value'}), 500


# --- Sound mode: unattended (default walk-through) vs attended (staff-run
# fast pass, short pointed sounds). The mode swaps sound POOL CONTENTS only
# (audio_manager.py `effects_attended` overlay); lights/DMX and the floor
# projector are identical in both. Never persisted: every boot is unattended.
# The sim's panel button flips it today; the entrance node's physical switch
# (DB9 Port A, packages/button.yaml pattern) will POST the same body later.

def sound_mode_state():
    return {'mode': audio_manager.sound_mode, 'modes': list(SOUND_MODES)}


async def _reapply_beds_for_mode():
    """After a mode flip, re-pick live continuous audio whose pool resolves
    differently in the new mode; one-shots and cues pick it up on their next
    draw. A pool emptied in the new mode must STOP (clients loop their bed
    until replaced or stopped), not keep looping the old mode's file."""
    restarted = []
    effect = maze_ambience_manager.effect
    if effect and maze_ambience_manager.playing and audio_manager.attended_differs(effect):
        if audio_manager.get_audio_config(effect).get('audio_files'):
            await maze_ambience_manager.apply_now(force=True)
            restarted.append('maze_ambience')
        else:
            # keep `effect` configured so flipping back revives the bed
            maze_ambience_manager._clear_playing()
            await remote_host_manager.stop_maze_ambience()
            restarted.append('maze_ambience (stopped: pool empty in this mode)')
    rooms = await room_background_manager.restart_differing(audio_manager.attended_differs)
    restarted.extend(f'room_background:{room}' for room in rooms)
    if floor_show_manager.bed and audio_manager.attended_differs(floor_show_manager.bed):
        if await floor_show_manager.restart_bed():
            restarted.append('floor_bed')
    return restarted


async def _reapply_beds_for_levels():
    """Restart every live bed so a level change is audible immediately
    (nodes get a freshly gain-baked stream; clients get the new payload
    volume). Cues pick the new effect_level up on their next draw."""
    restarted = []
    if maze_ambience_manager.effect and maze_ambience_manager.playing:
        await maze_ambience_manager.apply_now(force=True)
        restarted.append('maze_ambience')
    rooms = await room_background_manager.restart_differing(lambda e: True)
    restarted.extend(f'room_background:{room}' for room in rooms)
    if floor_show_manager.bed:
        if await floor_show_manager.restart_bed():
            restarted.append('floor_bed')
    return restarted


@app.route('/api/audio_levels', methods=['GET'])
async def get_audio_levels():
    """The global flat-mix knobs (2026-08-22): beds at ambience_level,
    every effect/cue at effect_level, no ducking anywhere."""
    return jsonify({'ambience_level': audio_manager.level('ambience_level'),
                    'effect_level': audio_manager.level('effect_level')})


@app.route('/api/audio_levels', methods=['POST'])
async def post_audio_levels():
    """{"ambience_level": 0.65} and/or {"effect_level": 0.98} — persisted in
    data/audio_levels.json (survives deploys), applied everywhere from the Pi:
    live beds restart at the new level now; cues use effect_level on their
    next play. CAVEAT: node cue WAVs are BAKED at effect_level — after
    changing effect_level, rerun sim/esphome/make_node_audio.py (works inside
    the container) so streamed cues actually change; Photo Bomb's in-flash
    snap only follows with a reflash."""
    data = await request.get_json() or {}
    try:
        levels = audio_manager.set_levels(
            ambience_level=data.get('ambience_level'),
            effect_level=data.get('effect_level'))
    except (TypeError, ValueError):
        return jsonify({'status': 'error',
                        'message': 'levels must be numbers 0..1'}), 400
    restarted = await _reapply_beds_for_levels()
    resp = {'status': 'success', **levels, 'beds_restarted': restarted}
    if data.get('effect_level') is not None:
        resp['note'] = ('cue WAVs bake effect_level: rerun '
                        'sim/esphome/make_node_audio.py to apply it to cues')
    return jsonify(resp)


@app.route('/api/sound_mode', methods=['GET'])
async def get_sound_mode():
    """unattended (power-up default) vs attended (staff-run fast pass)."""
    return jsonify(sound_mode_state())


@app.route('/api/sound_mode', methods=['POST'])
async def post_sound_mode():
    """{"mode": "attended"|"unattended"} or {"toggle": true} — flip which
    sound selections play (audio only). Live beds whose pools differ restart
    with a fresh pick."""
    data = await request.get_json() or {}
    if data.get('toggle') is True:
        mode = 'attended' if audio_manager.sound_mode == 'unattended' else 'unattended'
    else:
        mode = data.get('mode')
    if mode not in SOUND_MODES:
        return jsonify({'status': 'error',
                        'message': (
                            f'mode must be one of {list(SOUND_MODES)}, '
                            'or send {"toggle": true}'
                        )}), 400
    changed = audio_manager.set_sound_mode(mode)
    restarted = await _reapply_beds_for_mode() if changed else []
    return jsonify({'status': 'success', 'changed': changed,
                    'restarted': restarted, **sound_mode_state()})


def _down_room_names():
    enabled = set(node_audio_manager.enabled_rooms())
    connected = set(node_audio_manager.connected_rooms())
    return sorted(enabled - connected)


def _short_room_name(room):
    aliases = {
        'Bike Lock Room': 'BIKE',
        'Cop Dodge': 'COP',
        'Cuddle Cross': 'CUDDLE',
        'Deep Playa Handshake': 'DPH',
        'Gate': 'GATE',
        'Guy Line Climb': 'GUY',
        'Monkey Room': 'MONKEY',
        'Photo Bomb Room': 'PHOTO',
        'Porto Room': 'PORTO',
        'Sparkle Pony Room': 'SPARKLE',
        'Vertical Moop March': 'VMM',
    }
    return aliases.get(room, room.upper()[:8])


def _packed_room_lines(rooms, width=19):
    lines = []
    current = ''
    for room in rooms:
        name = _short_room_name(room)
        candidate = name if not current else f'{current} {name}'
        if len(candidate) > width and current:
            lines.append(current)
            current = name
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _plain_lines(lines):
    return Response('\n'.join(str(x) for x in lines) + '\n', mimetype='text/plain')


@app.route('/api/orb/page/<page>', methods=['GET'])
async def orb_page(page):
    """Plain-text operator pages for the tiny orb UI."""
    page = page.lower()
    if page == 'mode':
        return _plain_lines([
            'OPERATOR MODE',
            f'CURRENT: {audio_manager.sound_mode.upper()}',
            '',
            'TAP TOGGLE',
        ])
    if page == 'health':
        down = _down_room_names()
        if not down:
            return _plain_lines(['HEALTH CHECK', 'DOWN: 0', 'NONE'])
        return _plain_lines(['HEALTH CHECK', f'DOWN: {len(down)}'] + _packed_room_lines(down))
    if page == 'maintenance':
        return _plain_lines([
            'MAINTENANCE',
            'TOP RESTART SERVER',
            'BOTTOM RESTART PROJECTION',
        ])
    if page == 'projector':
        lines = ['PROJECTOR']
        lines.extend(await asyncio.to_thread(_projector_power_status))
        lines.extend(await asyncio.to_thread(_projection_status_lines))
        lines.extend(['', 'TOP POWER ON', 'BOTTOM POWER OFF'])
        return _plain_lines(lines)
    return _plain_lines(['UNKNOWN PAGE'])


@app.route('/api/orb/action', methods=['POST'])
async def orb_action():
    """Operator actions from the orb. Most commands return before work starts."""
    data = await request.get_json(silent=True) or {}
    action = data.get('action')
    if action == 'toggle_mode':
        mode = 'attended' if audio_manager.sound_mode == 'unattended' else 'unattended'
        changed = audio_manager.set_sound_mode(mode)
        restarted = await _reapply_beds_for_mode() if changed else []
        return jsonify({'status': 'success', 'changed': changed,
                        'restarted': restarted, **sound_mode_state()})
    if action == 'restart_server':
        _host_fire_and_forget('sleep 1; systemctl restart lohp-server.service')
        return jsonify({'status': 'success', 'message': 'server restart queued'})
    if action == 'restart_projection':
        _host_fire_and_forget('systemctl restart lohp-projection.service')
        return jsonify({'status': 'success', 'message': 'projection restart queued'})
    if action == 'projector_on':
        _host_fire_and_forget(
            'cd /home/dietpi/lohp-server && touch .projector-manual && '
            'python3 projector_power.py --on'
        )
        return jsonify({'status': 'success', 'message': 'projector power-on queued'})
    if action == 'projector_off':
        _host_fire_and_forget(
            'cd /home/dietpi/lohp-server && touch .projector-manual && '
            'python3 projector_power.py --off'
        )
        return jsonify({'status': 'success', 'message': 'projector power-off queued'})
    return jsonify({'status': 'error', 'message': f'unknown action {action!r}'}), 400


@app.route('/api/maze_ambience', methods=['GET'])
async def get_maze_ambience():
    """The configured always-on maze-wide ambience bed."""
    return jsonify(maze_ambience_manager.state())


@app.route('/api/maze_ambience', methods=['POST'])
async def set_maze_ambience():
    """Runtime opt-in/out for auditioning: {"effect": ...|null}.
    Not persisted — a keeper goes in audio_config.json `maze_ambience`."""
    data = await request.get_json() or {}
    ok, message = maze_ambience_manager.set_effect(data.get('effect'))
    if not ok:
        return jsonify({'status': 'error', 'message': message}), 400
    await maze_ambience_manager.apply_now()
    return jsonify({'status': 'success', 'message': message,
                    **maze_ambience_manager.state()})


@app.route('/api/start_maze_ambience', methods=['POST'])
async def start_maze_ambience():
    try:
        if not maze_ambience_manager.effect:
            ok, message = maze_ambience_manager.set_effect(
                maze_ambience_manager.default_effect)
            if not ok:
                return jsonify({"status": "error", "message": message}), 500
        await maze_ambience_manager.apply_now(force=True)
        if maze_ambience_manager.playing:
            return jsonify({"status": "success", "message": "Maze ambience started",
                            **maze_ambience_manager.state()})
        return jsonify({"status": "error", "message": "Failed to start maze ambience"}), 500
    except Exception as e:
        logger.error(f"Error starting maze ambience: {e}", exc_info=True)
        return jsonify({"status": "error", "message": f"Internal server error: {e}"}), 500


@app.route('/api/stop_maze_ambience', methods=['POST'])
async def stop_maze_ambience():
    try:
        maze_ambience_manager.set_effect(None)
        maze_ambience_manager._clear_playing()
        await remote_host_manager.stop_maze_ambience()
        return jsonify({"status": "success", "message": "Maze ambience stopped"})
    except Exception as e:
        logger.error(f"Error stopping maze ambience: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500




# Cuddle floor-projection theme control (projection_renderer.py ThemeControl):
# same-host on playa (the one Pi renders the projection); the sim serves the
# identical protocol on the bench.
FLOOR_CTL_URL = os.environ.get('FLOOR_CTL_URL', 'http://127.0.0.1:5002')
HOST_NSENTER = ['nsenter', '--target', '1', '--mount', '--uts', '--ipc', '--net', '--pid', '--']


def _host_run(args, timeout=4):
    """Run a short command on the Pi host from inside the privileged container."""
    cmd = HOST_NSENTER + list(args)
    return subprocess.run(cmd, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, timeout=timeout)


def _host_fire_and_forget(shell_cmd):
    subprocess.Popen(
        HOST_NSENTER + ['sh', '-lc', shell_cmd],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


async def _host_run_async(args, timeout=4):
    return await asyncio.to_thread(_host_run, args, timeout)


def _projector_power_status():
    out = []
    try:
        res = _host_run(['sh', '-lc', 'cd /home/dietpi/lohp-server && python3 projector_power.py --status'], timeout=5)
        text = (res.stdout or '').strip()
        out.append(text if text else f'status rc={res.returncode}')
    except Exception as e:
        out.append(f'status unavailable: {type(e).__name__}')
    try:
        res = _host_run(['systemctl', 'is-active', 'lohp-projector-power.service'], timeout=2)
        out.append(f'power svc: {(res.stdout or "").strip() or "unknown"}')
    except Exception:
        out.append('power svc: unknown')
    manual = os.path.exists('.projector-manual')
    out.append(f'manual: {"yes" if manual else "no"}')
    return out


def _projection_status_lines():
    lines = []
    try:
        res = _host_run(['systemctl', 'is-active', 'lohp-projection.service'], timeout=2)
        lines.append(f'renderer: {(res.stdout or "").strip() or "unknown"}')
    except Exception:
        lines.append('renderer: unknown')
    try:
        with urllib.request.urlopen(f'{FLOOR_CTL_URL}/theme', timeout=1.5) as r:
            body = json.loads(r.read())
        lines.append(f'floor theme: {body.get("theme", "?")}')
    except Exception:
        lines.append('floor ctl: down')
    return lines


@app.route('/api/next_floor_theme', methods=['POST'])
async def next_floor_theme():
    """Relay to the floor projector's theme control (the orb's very-long-press).
    Body {"theme": "lava"} picks a specific theme; empty body cycles to next."""
    try:
        data = await request.get_json(silent=True) or {}
        pick = data.get('theme') or 'next'

        def _post():
            req = urllib.request.Request(f'{FLOOR_CTL_URL}/theme/{pick}',
                                         data=b'', method='POST')
            with urllib.request.urlopen(req, timeout=2) as r:
                return r.status, json.loads(r.read())

        status, body = await asyncio.to_thread(_post)
        # Recolour the room (and swap its bed) now rather than waiting for the
        # renderer's next report — the switch is already committed.
        await floor_show_manager.set_theme(body.get('theme'))
        return jsonify({"status": "success", "theme": body.get('theme'),
                        "message": f"Floor theme -> {body.get('theme')}"})
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors='replace')
        logger.error(f"Floor theme control refused {pick!r}: {e.code} {detail}")
        return jsonify({"status": "error", "message": f"Floor control refused: {detail}"}), 502
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        logger.error(f"Floor theme control unreachable at {FLOOR_CTL_URL}: {e}")
        return jsonify({"status": "error",
                        "message": "Floor projection renderer unreachable"}), 502
    except Exception as e:
        logger.error(f"Error switching floor theme: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/floor_event', methods=['POST'])
async def floor_event():
    """The floor projection reporting in (projection_renderer.py on the Pi,
    sim_ui's engine on the bench). Fire-and-forget from the renderer's side:

        {"theme": "lava", "active": true, "events": [{"e": "sink", ...}, ...]}

    `active` is the authority for the room's ambience bed; `events` are the
    engine's own moments, which occasionally earn an accent (sound + a capped
    light flare). While a show is UP the renderer reports every couple of
    seconds even if nothing happens, so silence means it is gone and the bed
    stops; an empty deck reports once and then keeps quiet."""
    data = await request.get_json(silent=True) or {}
    try:
        accent = await floor_show_manager.handle_report(
            theme=data.get('theme'),
            active=data.get('active'),
            events=data.get('events') or [])
        return jsonify({'status': 'success', 'accent': accent,
                        **floor_show_manager.state()})
    except Exception as e:
        logger.error(f"Error handling floor event: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/floor_state', methods=['GET'])
async def floor_state():
    """What the server thinks the floor show is doing (theme, bed, liveness)."""
    return jsonify(floor_show_manager.state())


@app.route('/api/room_backgrounds', methods=['GET'])
async def get_room_backgrounds():
    """Which rooms keep their own always-on background, and what's playing."""
    return jsonify(room_background_manager.state())


@app.route('/api/room_backgrounds', methods=['POST'])
async def set_room_background():
    """Runtime opt-in/out for auditioning: {"room": ..., "effect": ...|null}.
    Not persisted — a keeper goes in audio_config.json `room_backgrounds`."""
    data = await request.json
    room = data.get('room')
    if not room:
        return jsonify({'status': 'error', 'message': 'Room is required'}), 400
    ok, message = room_background_manager.set_room(room, data.get('effect'))
    if not ok:
        return jsonify({'status': 'error', 'message': message}), 400
    await room_background_manager.apply_now()
    return jsonify({'status': 'success', 'message': message,
                    **room_background_manager.state()})


@app.route('/api/ambient', methods=['GET'])
async def get_ambient():
    """The armed ambient one-shot timers (audio_config `ambient_oneshots`)."""
    return jsonify(maze_ambient_manager.state())


@app.route('/api/ambient', methods=['POST'])
async def fire_ambient():
    """Fire one ambient one-shot NOW, skipping the random interval —
    auditioning. {"maze": true} lands a maze-pool file in a random room;
    {"room": <name>} fires that room's own pool."""
    data = await request.get_json() or {}
    ok, message = await maze_ambient_manager.fire_now(
        room=data.get('room'), maze=bool(data.get('maze')))
    return (jsonify({'status': 'success' if ok else 'error',
                     'message': message}), 200 if ok else 400)


def _telemetry_window_args():
    since = request.args.get('since')
    since_s = request.args.get('since_s')
    until = request.args.get('until')
    if since_s and not since:
        try:
            since = time.time() - float(since_s)
        except (TypeError, ValueError):
            since = None
    return since, until


def _event_limit(default=250):
    try:
        return int(request.args.get('limit', default))
    except (TypeError, ValueError):
        return default


@app.route('/api/telemetry', methods=['POST'])
async def post_telemetry():
    """Flexible ingest path for ESP/node diagnostics and future sensor details.

    Accepts either one event object or {"events": [...]} for batching. Server UTC
    receive time is authoritative; node uptime/sequence can be included for gap
    analysis, but not as the clock of record.
    """
    data = await request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({'status': 'error', 'message': 'JSON object required'}), 400
    events = data.get('events')
    if events is None:
        events = [data]
    elif not isinstance(events, list):
        return jsonify({'status': 'error', 'message': 'events must be a list'}), 400

    ids = []
    for event in events:
        if not isinstance(event, dict):
            return jsonify({'status': 'error', 'message': 'each event must be an object'}), 400
        merged = {
            'room': data.get('room'),
            'node_name': data.get('node_name'),
            'sensor_type': data.get('sensor_type'),
            'sensor_name': data.get('sensor_name'),
            **event,
        }
        event_type = merged.get('event_type') or merged.get('type') or 'telemetry'
        event_id = _record_event(
            event_type=event_type,
            room=merged.get('room'),
            node_name=merged.get('node_name'),
            sensor_type=merged.get('sensor_type'),
            sensor_name=merged.get('sensor_name'),
            effect_name=merged.get('effect_name'),
            node_uptime_ms=merged.get('node_uptime_ms'),
            seq=merged.get('seq'),
            value=merged.get('value') if 'value' in merged else merged,
        )
        ids.append(event_id)
    return jsonify({'status': 'success', 'count': len(ids), 'ids': ids})


@app.route('/api/sensor_events', methods=['GET'])
def get_sensor_events():
    since, until = _telemetry_window_args()
    events = telemetry_store.query_events(
        room=request.args.get('room') or None,
        event_type=request.args.get('event_type') or None,
        since=since,
        until=until,
        limit=_event_limit(),
        newest_first=request.args.get('order') != 'asc',
    )
    return jsonify({'events': events, 'count': len(events)})


@app.route('/api/sensor_events.csv', methods=['GET'])
def get_sensor_events_csv():
    since, until = _telemetry_window_args()
    events = telemetry_store.query_events(
        room=request.args.get('room') or None,
        event_type=request.args.get('event_type') or None,
        since=since,
        until=until,
        limit=_event_limit(5000),
        newest_first=False,
    )
    csv_text = telemetry_store.events_csv(events)
    return Response(
        csv_text,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=lohp-sensor-events.csv'},
    )


@app.route('/api/analytics/room_dwell', methods=['GET'])
def analytics_room_dwell():
    since, until = _telemetry_window_args()
    visits = telemetry_store.room_visits(since=since, until=until)
    body = {
        'rooms': telemetry_store.room_dwell_summary(since=since, until=until),
        'visit_count': len(visits),
    }
    if request.args.get('include_visits') in {'1', 'true', 'yes'}:
        body['visits'] = visits
    return jsonify(body)


@app.route('/api/analytics/maze_runs', methods=['GET'])
def analytics_maze_runs():
    since, until = _telemetry_window_args()
    try:
        timeout_s = float(request.args.get('timeout_s', 900))
    except (TypeError, ValueError):
        timeout_s = 900
    runs = telemetry_store.maze_runs(
        MAZE_ENTRY_ROUTE, since=since, until=until, timeout_s=timeout_s)
    completed = [r for r in runs if r['completed']]
    durations = [r['duration_s'] for r in completed]
    return jsonify({
        'route': MAZE_ENTRY_ROUTE,
        'runs': runs,
        'run_count': len(runs),
        'completed_count': len(completed),
        'abandoned_count': len(runs) - len(completed),
        'completion_rate': round(len(completed) / len(runs), 3) if runs else None,
        'avg_completed_duration_s': (
            round(sum(durations) / len(durations), 3) if durations else None
        ),
    })


@app.route('/api/analytics/abandonment', methods=['GET'])
def analytics_abandonment():
    since, until = _telemetry_window_args()
    try:
        timeout_s = float(request.args.get('timeout_s', 900))
    except (TypeError, ValueError):
        timeout_s = 900
    runs = telemetry_store.maze_runs(
        MAZE_ENTRY_ROUTE, since=since, until=until, timeout_s=timeout_s)
    counts = {}
    for run in runs:
        if not run['completed']:
            room = run['last_room']
            counts[room] = counts.get(room, 0) + 1
    rooms = [{'room': room, 'abandoned_count': count}
             for room, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))]
    return jsonify({'rooms': rooms, 'abandoned_count': sum(counts.values())})


@app.route('/api/analytics/room_heatmap', methods=['GET'])
def analytics_room_heatmap():
    """Coarse heatmap input: one cell per room, weighted by visits and dwell."""
    since, until = _telemetry_window_args()
    rooms = telemetry_store.room_dwell_summary(since=since, until=until)
    max_dwell = max((room['total_duration_s'] for room in rooms), default=0.0)
    max_visits = max((room['visits'] for room in rooms), default=0)
    for room in rooms:
        room['dwell_weight'] = (
            round(room['total_duration_s'] / max_dwell, 3) if max_dwell else 0.0
        )
        room['visit_weight'] = (
            round(room['visits'] / max_visits, 3) if max_visits else 0.0
        )
    return jsonify({'rooms': rooms})


@app.route('/api/toggle_maze_ambience', methods=['POST'])
async def toggle_maze_ambience():
    try:
        if maze_ambience_manager.playing:
            maze_ambience_manager.set_effect(None)
            maze_ambience_manager._clear_playing()
            await remote_host_manager.stop_maze_ambience()
            success = True
            playing = False
        else:
            if not maze_ambience_manager.effect:
                ok, message = maze_ambience_manager.set_effect(
                    maze_ambience_manager.default_effect)
                if not ok:
                    return jsonify({"status": "error", "message": message}), 500
            await maze_ambience_manager.apply_now(force=True)
            success = bool(maze_ambience_manager.playing)
            playing = success
        if success:
            return jsonify({"status": "success",
                            "message": f"Maze ambience {'started' if playing else 'stopped'}",
                            **maze_ambience_manager.state()})
        return jsonify({"status": "error", "message": "Failed to toggle maze ambience"}), 500
    except Exception as e:
        logger.error(f"Error toggling maze ambience: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500




@app.route('/api/shutdown', methods=['POST'])
async def shutdown():
    logger.info("Shutdown request received")
    shutdown_time = time.time() + 3
    shutdown_message = json.dumps({"type": "shutdown", "shutdown_time": shutdown_time})
    await asyncio.gather(*[client.send(shutdown_message) for client in connected_clients])
    # Power off the host from inside the privileged container
    asyncio.get_event_loop().call_later(3, lambda: os.system('echo o > /proc/sysrq-trigger'))
    return jsonify({"status": "success", "message": "Shutdown initiated"})


@app.route('/api/kill_process', methods=['POST'])
async def kill_process():
    logger.info("Kill process request received")
    await asyncio.sleep(0.1)  # Allow the response to be sent first
    os._exit(0)


@app.route('/api/run_test', methods=['POST'])
async def run_test():
    data = await request.json
    test_type = data['testType']
    rooms = data['rooms']
    try:
        if test_type == 'channel':
            return await run_channel_test(rooms, data['channelValues'])
        elif test_type == 'effect':
            return await run_effect_test(rooms, data['effectName'])
        return jsonify({"error": "Invalid test type"}), 400
    except Exception as e:
        logger.exception(f"Error running {test_type} test")
        return jsonify({"error": str(e)}), 500


async def run_channel_test(rooms, channel_values):
    for room in rooms:
        for light in light_config.get_room_layout().get(room, []):
            light_model = light_config.get_light_config(light['model'])
            fixture_values = [0] * CHANNELS_PER_FIXTURE
            for channel, value in channel_values.items():
                if channel in light_model['channels']:
                    fixture_values[light_model['channels'][channel]] = int(value)
            dmx_state_manager.update_fixture((light['start_address'] - 1) // CHANNELS_PER_FIXTURE, fixture_values)
    return jsonify({"message": f"Channel test applied to rooms: {', '.join(rooms)}"}), 200


async def run_effect_test(rooms, effect_name):
    if not effects_manager.get_effect(effect_name):
        return jsonify({"error": f"Effect '{effect_name}' not found"}), 404
    for room in rooms:
        success, message = await effects_manager.apply_effect_to_room(room, effect_name)
        if not success:
            return jsonify({"error": f"Failed to apply effect to room {room}: {message}"}), 500
    return jsonify({"message": f"Effect '{effect_name}' applied to rooms: {', '.join(rooms)}"}), 200


@app.route('/api/stop_test', methods=['POST'])
def stop_test():
    try:
        for fixture_id in range(NUM_FIXTURES):
            dmx_state_manager.reset_fixture(fixture_id)
        logger.info("Test stopped and all channels reset")
        return jsonify({"message": "Test stopped and lights reset"}), 200
    except Exception as e:
        logger.exception("Error stopping test")
        return jsonify({"error": str(e)}), 500


@app.route('/api/photobomb/photos', methods=['GET'])
def list_photobomb_photos():
    return jsonify({
        'photos_dir': camera_manager.photos_dir,
        'backend': camera_manager.backend,
        'photos': camera_manager.list_photos(),
    })


@app.route('/api/photobomb/photos/<path:filename>')
async def serve_photobomb_photo(filename):
    return await send_from_directory(camera_manager.photos_dir, filename)


@app.route('/api/health')
async def health():
    """Liveness for deploy scripts and the sim's RPI status dot."""
    return jsonify({"status": "ok", "service": "lohp-server"})


@app.route('/api/audio/live/<key>')
async def serve_live_audio(key):
    """One shared realtime MP3 per bed (live_audio.py): every node on this
    URL hears the same live edge — the sync mechanism for looping beds."""
    opened = live_audio_hub.open(key.removesuffix('.mp3'))
    if opened is None:
        return jsonify({"status": "error", "message": "no such live bed"}), 404
    queue, close = opened

    async def chunks():
        try:
            while True:
                chunk = await queue.get()
                if chunk is None:
                    break
                yield chunk
        finally:
            close()

    return Response(chunks(), mimetype='audio/mpeg')


@app.route('/api/audio/<path:filename>')
async def serve_audio(filename):
    def resolve_audio_path(requested):
        # Older clients can still ask by bare basename, even though new play
        # commands preserve the selected pool member's relative path.
        if (os.path.basename(requested) == requested
                and not os.path.exists(os.path.join(audio_dir, requested))):
            matches = glob.glob(os.path.join(audio_dir, '**', os.path.basename(requested)),
                                recursive=True)
            if matches:
                requested = os.path.relpath(matches[0], audio_dir)
        path = os.path.abspath(os.path.join(audio_dir, requested))
        if os.path.commonpath([audio_dir, path]) != audio_dir:
            return None
        return path if os.path.exists(path) else None

    base_dir = os.path.dirname(__file__)
    audio_dir = os.path.abspath(os.path.join(base_dir, 'audio_files'))
    offset_raw = request.args.get('offset_s')
    if offset_raw is not None:
        try:
            offset_s = max(0.0, float(offset_raw))
        except (TypeError, ValueError):
            return jsonify({"status": "error", "message": "bad offset_s"}), 400
        path = resolve_audio_path(filename)
        if path is None:
            return jsonify({"status": "error", "message": "audio not found"}), 404
        return await stream_audio_from_offset(path, offset_s)
    if (os.path.basename(filename) == filename
            and not os.path.exists(os.path.join(audio_dir, filename))):
        matches = glob.glob(os.path.join(audio_dir, '**', os.path.basename(filename)),
                            recursive=True)
        if matches:
            filename = os.path.relpath(matches[0], audio_dir)
    return await send_from_directory(audio_dir, filename)


async def stream_audio_from_offset(path, offset_s):
    ext = os.path.splitext(path)[1].lower()
    codec = ["-codec:a", "copy"] if ext == ".mp3" else ["-codec:a", "libmp3lame", "-q:a", "4"]
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-ss", f"{offset_s:.3f}",
        "-i", path,
        "-vn",
        *codec,
        "-f", "mp3",
        "pipe:1",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    async def chunks():
        try:
            while True:
                chunk = await proc.stdout.read(32768)
                if not chunk:
                    break
                yield chunk
            stderr = await proc.stderr.read()
            await proc.wait()
            if proc.returncode not in (0, None):
                logger.warning(f"Offset audio stream failed for {os.path.basename(path)} "
                               f"@ {offset_s:.3f}s: {stderr.decode(errors='replace')[:300]}")
        finally:
            if proc.returncode is None:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), 2)
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()

    return Response(chunks(), mimetype='audio/mpeg')


if __name__ == '__main__':
    from hypercorn.config import Config
    from hypercorn.asyncio import serve

    _bed_cache_warmup_task = None  # keep the boot warmup task referenced
    config = Config()
    config.bind = ["0.0.0.0:5000"]
    config.use_reloader = False
    config.accesslog = "-"
    config.errorlog = "-"
    config.loglevel = "DEBUG" if DEBUG else "INFO"

    async def _warm_node_bed_cache():
        """Pre-transcode the maze bed pool's gain-baked node streams in the
        background so rotations are cache-hit. A cache-miss transcode is
        30-60s of ffmpeg per 15-minute track; the payload build runs in a
        worker thread now, but a cold rotation would still start its bed a
        transcode late — this keeps that a boot-time background cost."""
        effect = maze_ambience_manager.effect
        if not effect:
            return
        try:
            prepared = await asyncio.to_thread(audio_manager.warm_node_streams, [effect])
            logger.info(f"Node bed cache warm ({effect}: {prepared} stream(s) ready)")
        except Exception as e:
            logger.error(f"Node bed cache warmup failed: {e}", exc_info=True)

    async def run_server():
        try:
            websocket_server = await websockets.serve(websocket_handler, "0.0.0.0", 8765)
            # Node connections are kept warm from boot: liveness (audio_rooms)
            # is real and the first bed start never races a cold connect.
            node_audio_manager.ensure_running()
            camera_manager.ensure_warm_grabber()  # frame-at-the-snap (2026-08-22)
            maze_ambience_manager.ensure_running()
            room_background_manager.ensure_running()
            global _bed_cache_warmup_task
            _bed_cache_warmup_task = asyncio.create_task(_warm_node_bed_cache())
            # the maze lights itself: attract rotation from boot (Tim 2026-08-01)
            await effects_manager.theme_manager.set_attract(True)
            maze_ambient_manager.ensure_running()
            await asyncio.gather(websocket_server.wait_closed(), serve(app, config))
        except Exception as e:
            log_and_exit(f"Server crashed: {e}")

    print("Starting server on http://0.0.0.0:5000")
    try:
        asyncio.run(run_server())
    except Exception as e:
        log_and_exit(f"Failed to start server: {e}")
