import os
import sys
import time
import json
import logging
import asyncio
import traceback
import websockets
from quart import Quart, request, jsonify, Response, send_from_directory, send_file
from quart_cors import cors
from dmx_state_manager import DMXStateManager
from dmx_interface import DMXOutputManager
from light_config_manager import LightConfigManager
from effects_manager import EffectsManager
from remote_host_manager import RemoteHostManager
from audio_manager import AudioManager
from node_audio_manager import NodeAudioManager
from camera_manager import CameraManager
from effects.photobomb_shot import SHUTTER_OFFSET

# Configuration
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
NUM_FIXTURES = 21
CHANNELS_PER_FIXTURE = 8

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)
logging.getLogger('pyftdi.ftdi').setLevel(logging.WARNING)

app = Quart(__name__, static_folder='frontend/static')
app = cors(app)

connected_clients = set()


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
    await ws.send(json.dumps({"status": "success", "message": "Trigger event processed"}))


# --- Component initialization ---

dmx_state_manager = DMXStateManager(NUM_FIXTURES, CHANNELS_PER_FIXTURE)
dmx_output_manager = DMXOutputManager(dmx_state_manager)
light_config = LightConfigManager()
audio_manager = AudioManager()
node_audio_manager = NodeAudioManager(audio_manager=audio_manager)
remote_host_manager = RemoteHostManager(audio_manager=audio_manager, node_audio=node_audio_manager)
effects_manager = EffectsManager(light_config, dmx_state_manager, remote_host_manager, audio_manager)
camera_manager = CameraManager()

# Photo Bomb camera: every PhotoBomb-Shot run schedules a webcam capture at the
# flash; a superseded/stopped run (button re-press restarts the countdown)
# cancels it so exactly one photo comes out of the last full countdown.
effects_manager.register_effect_hooks(
    'PhotoBomb-Shot',
    on_start=lambda room: camera_manager.schedule_capture(SHUTTER_OFFSET),
    on_cancel=lambda room: camera_manager.cancel_pending(),
)

dmx_state_manager.reset_all_fixtures()
dmx_output_manager.start()
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

    if not effects_manager.get_effect(effect_name):
        return jsonify({'status': 'error', 'message': f'Effect {effect_name} not found'}), 404

    try:
        success, message = await effects_manager.apply_effect_to_room(room, effect_name)
        if success:
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


@app.route('/api/stop_effect', methods=['POST'])
async def stop_effect():
    data = await request.json
    room = data.get('room')
    try:
        await effects_manager.stop_current_effect(room)
        message = f"Effect stopped in room: {room}" if room else "Effects stopped in all rooms"
        return jsonify({'status': 'success', 'message': message})
    except Exception as e:
        logger.error(f"Error stopping effect: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/audio_files_to_download', methods=['GET'])
def get_audio_files_to_download():
    return jsonify(audio_manager.get_audio_files_to_download())


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


@app.route('/api/audio/<path:filename>')
async def serve_audio(filename):
    base_dir = os.path.dirname(__file__)
    music_path = os.path.join(base_dir, 'music', os.path.basename(filename))
    audio_dir = os.path.join(base_dir, 'music' if os.path.exists(music_path) else 'audio_files')
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
