import os
import sys
import glob
import time
import json
import logging
import asyncio
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
from audio_manager import AudioManager
from node_audio_manager import NodeAudioManager
from floor_show_manager import FloorShowManager, read_saved_theme
from camera_manager import CameraManager
from effects.photobomb_shot import SHUTTER_OFFSET
from room_answer_pools import answer_pool_name

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
BACKTRACK_EFFECT_NAME = "Backtrack"
BACKTRACK_TOKEN_TTL_S = 180
BACKTRACK_ROOM_BLOCK_S = 30
BACKTRACK_ENTRANCE_RESET_S = 8
BACKTRACK_FORWARD_MIN_STEPS = 2
BACKTRACK_REVERSE_TRIGGER_STEPS = 1
BACKTRACK_BLIND_REVERSE_ENTRY_ROOMS = {"Entrance"}
DEEP_PLAYA_ROOM = "Deep Playa Handshake"
DEEP_PLAYA_ENTRY_EFFECT = "DeepPlaya-BG"
DEEP_PLAYA_STALE_ENTRY_EFFECT = "DeepPlaya-Hit"
MOOP_ROOM = "Vertical Moop March"
MOOP_BUTTON_EFFECT = "CorrectAnswer"
MOOP_RIGHT_EFFECT = answer_pool_name(MOOP_ROOM, "CorrectAnswer")
MOOP_WRONG_EFFECT = answer_pool_name(MOOP_ROOM, "WrongAnswer")
MOOP_WINDOW_S = 60
MOOP_BUTTON_COUNT = 4

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)
logging.getLogger('pyftdi.ftdi').setLevel(logging.WARNING)

app = Quart(__name__, static_folder='frontend/static')
app = cors(app)

connected_clients = set()
_moop_lock = asyncio.Lock()
_moop_state = {
    'pressed': set(),
    'started_at': None,
    'timer': None,
}


def _moop_button_id(data):
    for key in ('trigger_name', 'button_name', 'sensor_name'):
        value = data.get(key)
        if value:
            return str(value)
    index = data.get('button_index')
    if index is None:
        index = data.get('game_index')
    if index is not None:
        try:
            return f"Moop Button {int(index) + 1}"
        except (TypeError, ValueError):
            return str(index)
    return None


def _reset_moop_locked():
    timer = _moop_state.get('timer')
    current = asyncio.current_task()
    if timer and timer is not current and not timer.done():
        timer.cancel()
    _moop_state['pressed'] = set()
    _moop_state['started_at'] = None
    _moop_state['timer'] = None


async def _apply_moop_resolution(effect_name):
    effect_data = effects_manager.get_effect(effect_name)
    if not effect_data:
        logger.error(f"Moop march resolution effect {effect_name} not found")
        return
    success, message = await effects_manager.apply_effect_to_room(
        MOOP_ROOM, effect_name, effect_data)
    if not success:
        logger.error(f"Moop march resolution failed: {message}")


async def _moop_timeout(started_at):
    try:
        await asyncio.sleep(MOOP_WINDOW_S)
        async with _moop_lock:
            if _moop_state.get('started_at') != started_at:
                return
            if not _moop_state['pressed'] or len(_moop_state['pressed']) >= MOOP_BUTTON_COUNT:
                return
            pressed = sorted(_moop_state['pressed'])
            logger.info(f"Moop march timed out with {len(pressed)}/{MOOP_BUTTON_COUNT}: {pressed}")
            _reset_moop_locked()
        await _apply_moop_resolution(MOOP_WRONG_EFFECT)
    except asyncio.CancelledError:
        return


async def _record_moop_press(data):
    button_id = _moop_button_id(data)
    if not button_id:
        logger.warning("Moop march CorrectAnswer did not include trigger_name; "
                       "playing button sound without changing round state")
        return False

    async with _moop_lock:
        now = time.monotonic()
        if (
            _moop_state['started_at'] is None
            or now - _moop_state['started_at'] > MOOP_WINDOW_S
        ):
            _reset_moop_locked()
            _moop_state['started_at'] = now
            _moop_state['timer'] = asyncio.create_task(_moop_timeout(now))

        _moop_state['pressed'].add(button_id)
        count = len(_moop_state['pressed'])
        logger.info(f"Moop march button latched: {button_id} ({count}/{MOOP_BUTTON_COUNT})")
        if count < MOOP_BUTTON_COUNT:
            return False

        logger.info("Moop march complete; scheduling room-local right-answer pool")
        _reset_moop_locked()
        return True


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
audio_manager = AudioManager()
node_audio_manager = NodeAudioManager(audio_manager=audio_manager)
remote_host_manager = RemoteHostManager(audio_manager=audio_manager, node_audio=node_audio_manager)
effects_manager = EffectsManager(light_config, dmx_state_manager, remote_host_manager, audio_manager)
camera_manager = CameraManager()
# Cuddle Cross takes its sound and its colour from whatever the floor projector
# is running (floor_show_manager.py). The renderer reports in on
# /api/floor_event; until it does, the room is lit for the theme the projector
# was last showing.
floor_show_manager = FloorShowManager(effects_manager, remote_host_manager)
floor_show_manager.prime_theme(read_saved_theme(os.path.dirname(os.path.abspath(__file__))))

# Photo Bomb camera: every PhotoBomb-Shot run schedules a webcam capture at the
# flash; a superseded/stopped run (button re-press restarts the countdown)
# cancels it so exactly one photo comes out of the last full countdown.
effects_manager.register_effect_hooks(
    'PhotoBomb-Shot',
    on_start=lambda room: camera_manager.schedule_capture(SHUTTER_OFFSET),
    on_cancel=lambda room: camera_manager.cancel_pending(),
)


def _load_maze_route_tracking():
    """Route order and entry effects used to infer reverse travel from entries."""
    route = []
    entry_effects = {}
    try:
        with open(os.path.join('sim', 'maze_layout.json')) as f:
            route = json.load(f).get('route', [])
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"Maze route tracking disabled; could not read route: {e}")
    try:
        with open('triggers.json') as f:
            for trig in json.load(f).get('triggers', []):
                action = trig.get('action') or {}
                effect = (action.get('data') or {}).get('effect_name')
                if (
                    action.get('path') != '/api/run_effect'
                    or not effect
                    or trig.get('room') in entry_effects
                    or trig.get('type') not in {'laser', 'presence'}
                ):
                    continue
                entry_effects[trig['room']] = effect
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"Maze route tracking disabled; could not read entry triggers: {e}")
        entry_effects = {}
    entry_route = [room for room in route if room in entry_effects]
    return entry_route, {room: i for i, room in enumerate(entry_route)}, entry_effects


MAZE_ENTRY_ROUTE, MAZE_ENTRY_INDEX, MAZE_ENTRY_EFFECTS = _load_maze_route_tracking()
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

    if not room or not effect_name:
        return jsonify({'status': 'error', 'message': 'Room and effect_name are required'}), 400

    if room == DEEP_PLAYA_ROOM and effect_name == DEEP_PLAYA_STALE_ENTRY_EFFECT:
        logger.warning(f"Rewriting stale {room} entry effect "
                       f"{DEEP_PLAYA_STALE_ENTRY_EFFECT} -> {DEEP_PLAYA_ENTRY_EFFECT}")
        effect_name = DEEP_PLAYA_ENTRY_EFFECT

    if not effects_manager.get_effect(effect_name):
        return jsonify({'status': 'error', 'message': f'Effect {effect_name} not found'}), 404

    try:
        moop_complete = False
        if room == MOOP_ROOM and effect_name == MOOP_BUTTON_EFFECT:
            moop_complete = await _record_moop_press(data)

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

        effect_data = effects_manager.get_effect(effect_name)
        if not effect_data:
            return jsonify({'status': 'error', 'message': f'Effect {effect_name} not found'}), 404

        success, message = await effects_manager.apply_effect_to_room(room, effect_name, effect_data)
        if success:
            if moop_complete:
                asyncio.create_task(_apply_moop_resolution(MOOP_RIGHT_EFFECT))
            return jsonify({'status': 'success', 'message': f'Effect {effect_name} executed in room {room}'})
        logger.error(f"Failed to execute effect {effect_name} in room {room}: {message}")
        return jsonify({'status': 'error', 'message': message}), 500
    except Exception as e:
        error_message = f"Error executing effect {effect_name} for room {room}: {e}"
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


@app.route('/api/room_vacated', methods=['POST'])
async def room_vacated():
    """A room node reporting that its radar lost the last visitor — the
    `leave_action` half of the occupancy contract in triggers.json.

    Same work as a per-room /api/stop_effect (cancel anything still running,
    silence lingering effect audio, hand the room back to the theme), but it is
    the room reporting a fact rather than an operator issuing a stop, and it
    reads as one in the log when something misbehaves at the maze. Background
    music is deliberately untouched: it never stopped, and effect audio mixes
    over it rather than replacing it."""
    data = await request.json
    room = data.get('room')
    if not room:
        return jsonify({'status': 'error', 'message': 'Room is required'}), 400
    try:
        logger.info(f"Room vacated: {room}")
        blind_backtrack_room = _route_room_vacated(room)
        if blind_backtrack_room:
            _set_room_backtrack_block(room)
            _set_room_backtrack_block(blind_backtrack_room)
            success, message = await effects_manager.apply_effect_to_room(room, BACKTRACK_EFFECT_NAME)
            if not success:
                return jsonify({'status': 'error', 'message': message}), 500
            return jsonify({'status': 'success',
                            'message': f'Room {room} vacated; {BACKTRACK_EFFECT_NAME} fired'})
        await effects_manager.stop_effect_in_room(room)
        return jsonify({'status': 'success', 'message': f'Room {room} vacated'})
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


@app.route('/api/start_music', methods=['POST'])
async def start_music():
    try:
        if await effects_manager.start_music():
            return jsonify({"status": "success", "message": "Background music started"})
        return jsonify({"status": "error", "message": "Failed to start background music"}), 500
    except Exception as e:
        logger.error(f"Error starting background music: {e}", exc_info=True)
        return jsonify({"status": "error", "message": f"Internal server error: {e}"}), 500


@app.route('/api/stop_music', methods=['POST'])
async def stop_music():
    try:
        if await effects_manager.stop_music():
            return jsonify({"status": "success", "message": "Background music stopped"})
        return jsonify({"status": "error", "message": "Failed to stop background music"}), 500
    except Exception as e:
        logger.error(f"Error stopping background music: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# Cuddle floor-projection theme control (projection_renderer.py ThemeControl):
# same-host on playa (the one Pi renders the projection); the sim serves the
# identical protocol on the bench.
FLOOR_CTL_URL = os.environ.get('FLOOR_CTL_URL', 'http://127.0.0.1:5002')


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


@app.route('/api/toggle_music', methods=['POST'])
async def toggle_music():
    try:
        success, playing = await effects_manager.toggle_music()
        if success:
            return jsonify({"status": "success",
                            "message": f"Background music {'started' if playing else 'stopped'}"})
        return jsonify({"status": "error", "message": "Failed to toggle background music"}), 500
    except Exception as e:
        logger.error(f"Error toggling background music: {e}", exc_info=True)
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


@app.route('/api/audio/<path:filename>')
async def serve_audio(filename):
    base_dir = os.path.dirname(__file__)
    is_bare_name = os.path.basename(filename) == filename
    music_path = os.path.join(base_dir, 'music', filename) if is_bare_name else None
    audio_dir = os.path.join(
        base_dir,
        'music' if music_path and os.path.exists(music_path) else 'audio_files')
    # Older clients can still ask by bare basename, even though new play
    # commands preserve the selected pool member's relative path.
    if audio_dir.endswith('audio_files') and not os.path.exists(os.path.join(audio_dir, filename)):
        matches = glob.glob(os.path.join(audio_dir, '**', os.path.basename(filename)),
                            recursive=True)
        if matches:
            filename = os.path.relpath(matches[0], audio_dir)
    return await send_from_directory(audio_dir, filename)


if __name__ == '__main__':
    from hypercorn.config import Config
    from hypercorn.asyncio import serve

    config = Config()
    config.bind = ["0.0.0.0:5000"]
    config.use_reloader = False
    config.accesslog = "-"
    config.errorlog = "-"
    config.loglevel = "DEBUG" if DEBUG else "INFO"

    async def run_server():
        try:
            websocket_server = await websockets.serve(websocket_handler, "0.0.0.0", 8765)
            await asyncio.gather(websocket_server.wait_closed(), serve(app, config))
        except Exception as e:
            log_and_exit(f"Server crashed: {e}")

    print("Starting server on http://0.0.0.0:5000")
    try:
        asyncio.run(run_server())
    except Exception as e:
        log_and_exit(f"Failed to start server: {e}")
