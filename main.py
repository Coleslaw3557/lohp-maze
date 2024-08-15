import os
import logging
import asyncio
import json
import websockets
import sys
import traceback
import random
from quart import Quart, request, jsonify, Response, send_from_directory, send_file
from quart_cors import cors
import os
from werkzeug.urls import uri_to_iri, iri_to_uri
from dmx_state_manager import DMXStateManager
from dmx_interface import DMXOutputManager
from light_config_manager import LightConfigManager
from effects_manager import EffectsManager
from interrupt_handler import InterruptHandler
from remote_host_manager import RemoteHostManager
from audio_manager import AudioManager

# Configuration
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
SECRET_KEY = os.environ.get('SECRET_KEY', 'your_secret_key_here')
NUM_FIXTURES = 21
CHANNELS_PER_FIXTURE = 8

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler(sys.stdout)])  # Log to stdout
logger = logging.getLogger(__name__)

# Set specific loggers to desired levels
logging.getLogger('pyftdi.ftdi').setLevel(logging.WARNING)
logging.getLogger('pydub.converter').setLevel(logging.ERROR)

# Set the root logger to INFO
logging.getLogger().setLevel(logging.INFO)

app = Quart(__name__, static_folder='frontend/static')
app = cors(app)
app.secret_key = SECRET_KEY

@app.route('/')
async def index():
    return await send_file('frontend/index.html')

connected_clients = set()

def log_and_exit(error_message):
    logger.critical(f"Critical error: {error_message}")
    logger.critical(f"Traceback: {traceback.format_exc()}")
    sys.exit(1)

async def websocket_handler(websocket, path):
    connected_clients.add(websocket)
    try:
        async for message in websocket:
            data = json.loads(message)
            message_type = data.get('type')
            if message_type == 'client_connected':
                await handle_client_connected(websocket, data)
            else:
                await handle_websocket_message(websocket, data)
    except websockets.exceptions.ConnectionClosedError as e:
        logger.info(f"WebSocket connection closed: {e}")
    except Exception as e:
        logger.error(f"Error in WebSocket handler: {e}")
    finally:
        connected_clients.remove(websocket)
        logger.info("WebSocket client disconnected")

async def handle_client_connected(websocket, data):
    logger.info(f"handle_client_connected called with websocket: {websocket}, data: {data}")
    unit_name = data.get('data', {}).get('unit_name')
    associated_rooms = data.get('data', {}).get('associated_rooms', [])
    if unit_name and associated_rooms:
        remote_host_manager.update_client_rooms(unit_name, websocket.remote_address[0], associated_rooms, websocket)
        logger.info(f"Client connected: {unit_name} ({websocket.remote_address[0]}) - Associated rooms: {associated_rooms}")
        response = {"type": "connection_response", "status": "success", "message": "Connection acknowledged"}
        await websocket.send(json.dumps(response))
        logger.info(f"Sent connection response: {response}")
    else:
        logger.warning(f"Received incomplete client connection data: {data}")
        response = {"type": "connection_response", "status": "error", "message": "Incomplete connection data"}
        await websocket.send(json.dumps(response))
        logger.info(f"Sent error response: {response}")

async def handle_status_update(websocket, data):
    logger.info(f"Status update received: {data}")
    await websocket.send(json.dumps({"type": "status_update_response", "status": "success", "message": "Status update acknowledged"}))

async def handle_websocket_message(ws, data):
    """
    Handle incoming WebSocket messages.
    """
    message_type = data.get('type')
    handlers = {
        'status_update': handle_status_update,
        'trigger_event': handle_trigger_event,
        'client_connected': handle_client_connected,
        'client_ready': handle_client_ready
    }
    
    handler = handlers.get(message_type)
    if handler:
        await handler(ws, data)
    else:
        logger.warning(f"Unknown message type received: {message_type}")
        await ws.send(json.dumps({"status": "error", "message": "Unknown message type"}))

async def handle_client_ready(ws, data):
    """
    Handle client ready messages.
    """
    effect_id = data.get('effect_id')
    client_ip = ws.remote_address[0]
    remote_host_manager.set_client_ready(effect_id, client_ip)
    logger.info(f"Client {client_ip} ready for effect {effect_id}")

async def handle_client_connected(ws, data):
    """
    Handle client connection messages.
    """
    unit_name = data.get('data', {}).get('unit_name')
    associated_rooms = data.get('data', {}).get('associated_rooms', [])
    client_ip = ws.remote_address[0]  # Get the actual client IP
    if unit_name and associated_rooms:
        remote_host_manager.update_client_rooms(unit_name, client_ip, associated_rooms, ws)
        logger.info(f"Client connected: {unit_name} ({client_ip}) - Associated rooms: {associated_rooms}")
        await ws.send(json.dumps({"type": "connection_response", "status": "success", "message": "Connection acknowledged"}))
    else:
        logger.warning(f"Received incomplete client connection data: {data}")
        await ws.send(json.dumps({"type": "connection_response", "status": "error", "message": "Incomplete connection data"}))

async def handle_status_update(ws, data):
    """
    Handle status update messages from clients.
    """
    logger.info(f"Status update received: {data}")
    await ws.send(json.dumps({"status": "success", "message": "Status update acknowledged"}))

async def handle_trigger_event(ws, data):
    """
    Handle trigger event messages from clients.
    """
    logger.info(f"Trigger event received: {data}")
    # TODO: Process the trigger event
    await ws.send(json.dumps({"status": "success", "message": "Trigger event processed"}))

async def broadcast_message(message):
    """
    Broadcast a message to all connected clients.
    """
    if connected_clients:
        await asyncio.wait([client.send(json.dumps(message)) for client in connected_clients])

# Initialize components
dmx_state_manager = DMXStateManager(NUM_FIXTURES, CHANNELS_PER_FIXTURE)
dmx_output_manager = DMXOutputManager(dmx_state_manager)
light_config = LightConfigManager(dmx_state_manager=dmx_state_manager)
audio_manager = AudioManager()
remote_host_manager = RemoteHostManager(audio_manager=audio_manager)
effects_manager = EffectsManager(config_file='effects_config.json', light_config_manager=light_config, dmx_state_manager=dmx_state_manager, remote_host_manager=remote_host_manager, audio_manager=audio_manager)
interrupt_handler = InterruptHandler(dmx_state_manager, effects_manager.theme_manager)
effects_manager.interrupt_handler = interrupt_handler
logger.info("InterruptHandler initialized and passed to EffectsManager")

# Reset all lights to off
dmx_state_manager.reset_all_fixtures()

# Start threads
dmx_output_manager.start()

# Ensure no theme is running at startup
effects_manager.stop_current_theme()

async def initialize_remote_hosts():
    # Initialize WebSocket connections to remote hosts
    await remote_host_manager.initialize_websocket_connections()

@app.route('/api/set_master_brightness', methods=['POST'])
async def set_master_brightness():
    data = await request.json
    brightness = float(data.get('brightness', 1.0))
    effects_manager.set_master_brightness(brightness)
    return jsonify({"status": "success", "master_brightness": brightness})

from quart import request

@app.route('/api/set_theme', methods=['POST'])
async def set_theme():
    data = await request.json
    theme_name = data.get('theme_name')
    next_theme = data.get('next_theme', False)

    if not theme_name and not next_theme:
        return jsonify({'status': 'error', 'message': 'Theme name or next_theme flag is required'}), 400

    try:
        if theme_name.lower() == 'notheme':
            logger.info("Turning off theme")
            await effects_manager.stop_current_theme_async()
            return jsonify({'status': 'success', 'message': 'Theme turned off'})
        
        if theme_name:
            logger.info(f"Setting theme to: {theme_name}")
            success = await asyncio.wait_for(effects_manager.set_current_theme_async(theme_name), timeout=10.0)
            if success:
                logger.info(f"Theme set successfully to: {theme_name}")
                return jsonify({'status': 'success', 'message': f'Theme set to {theme_name}'})
            else:
                logger.error(f"Failed to set theme to: {theme_name}")
                return jsonify({'status': 'error', 'message': f'Failed to set theme to {theme_name}'}), 400
        else:
            logger.error("No valid theme name provided")
            return jsonify({'status': 'error', 'message': 'No valid theme name provided'}), 400
    except asyncio.TimeoutError:
        logger.error(f"Timeout while setting theme to: {theme_name}")
        return jsonify({'status': 'error', 'message': f'Timeout while setting theme to {theme_name}'}), 504
    except Exception as e:
        logger.error(f"Error setting theme: {str(e)}")
        return jsonify({'status': 'error', 'message': f'An error occurred while setting the theme: {str(e)}'}), 500

import time

@app.route('/api/run_effect', methods=['POST'])
async def run_effect():
    data = await request.json
    room = data.get('room')
    effect_name = data.get('effect_name')
    
    if not room or not effect_name:
        return jsonify({'status': 'error', 'message': 'Room and effect_name are required'}), 400
    
    logger.info(f"Preparing effect: {effect_name} for room: {room}")
    effect_data = effects_manager.get_effect(effect_name)
    if not effect_data:
        logger.error(f"Effect not found: {effect_name}")
        return jsonify({'status': 'error', 'message': f'Effect {effect_name} not found'}), 404
    
    try:
        # Get audio configuration for the effect
        audio_config = audio_manager.get_audio_config(effect_name)
        if audio_config and audio_config.get('audio_files'):
            audio_file = random.choice(audio_config['audio_files'])
            volume = audio_config.get('volume', audio_manager.audio_config['default_volume'])
        else:
            audio_file = None
            volume = None
    
        # Add audio parameters to effect data only if audio_file exists
        if audio_file:
            effect_data['audio'] = {
                'file': audio_file,
                'volume': volume
            }
        
        # Execute the effect immediately
        success, message = await effects_manager.apply_effect_to_room(room, effect_name, effect_data)
        
        if success:
            return jsonify({'status': 'success', 'message': f'Effect {effect_name} executed in room {room}'})
        else:
            logger.error(f"Failed to execute effect {effect_name} in room {room}: {message}")
            return jsonify({'status': 'error', 'message': message}), 500
    except Exception as e:
        error_message = f"Error executing effect {effect_name} for room {room}: {str(e)}"
        logger.error(error_message, exc_info=True)
        return jsonify({'status': 'error', 'message': error_message}), 500

@app.route('/api/audio_files_to_download', methods=['GET'])
def get_audio_files_to_download():
    audio_files = audio_manager.get_audio_files_to_download()
    return jsonify(audio_files)

# This function has been removed as it's no longer needed

@app.route('/api/stop_effect', methods=['POST'])
async def stop_effect():
    data = await request.json
    room = data.get('room')
    
    try:
        await effects_manager.stop_current_effect(room)
        message = f"Effect stopped in room: {room}" if room else "Effects stopped in all rooms"
        return jsonify({'status': 'success', 'message': message})
    except Exception as e:
        error_message = f"Error stopping effect: {str(e)}"
        logger.error(error_message, exc_info=True)
        return jsonify({'status': 'error', 'message': error_message}), 500

@app.route('/api/rooms', methods=['GET'])
def get_rooms():
    rooms = light_config.get_room_layout()
    return jsonify(rooms)

@app.route('/api/effects_details', methods=['GET'])
def get_effects_details():
    effects = effects_manager.get_all_effects()
    return jsonify(effects)

@app.route('/api/effects_list', methods=['GET'])
def get_effects_list():
    effects_list = effects_manager.get_effects_list()
    return jsonify(effects_list)

@app.route('/api/themes', methods=['GET'])
def get_themes():
    themes = effects_manager.get_all_themes()
    return jsonify(themes)

@app.route('/api/light_models', methods=['GET'])
def get_light_models():
    light_models = light_config.get_light_models()
    return jsonify(light_models)

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
    clients = remote_host_manager.get_connected_clients_info()
    return jsonify(clients)

@app.route('/api/terminate_client', methods=['POST'])
async def terminate_client():
    data = await request.json
    client_ip = data.get('ip')
    if not client_ip:
        return jsonify({'status': 'error', 'message': 'Client IP is required'}), 400
    
    success = await remote_host_manager.terminate_client(client_ip)
    if success:
        return jsonify({'status': 'success', 'message': f'Client {client_ip} terminated successfully'})
    else:
        return jsonify({'status': 'error', 'message': f'Failed to terminate client {client_ip}'}), 500

@app.route('/api/room_layout', methods=['GET'])
def get_room_layout():
    room_layout = light_config.get_room_layout()
    return jsonify(room_layout)

@app.route('/api/rooms_units_fixtures', methods=['GET'])
def get_rooms_units_fixtures():
    room_layout = light_config.get_room_layout()
    connected_clients = remote_host_manager.get_connected_clients_info()
    
    result = {}
    for room, fixtures in room_layout.items():
        result[room] = {
            'fixtures': [{'model': f['model'], 'start_address': f['start_address']} for f in fixtures],
            'units': [client['name'] for client in connected_clients if room in client['rooms']]
        }
    
    return jsonify(result)

@app.route('/api/update_theme_value', methods=['POST'])
async def update_theme_value():
    data = await request.json
    control_id = data.get('control_id')
    value = data.get('value')
    
    if control_id is None or value is None:
        return jsonify({'status': 'error', 'message': 'Missing control_id or value'}), 400
    
    success = await effects_manager.update_theme_value(control_id, value)
    if success:
        return jsonify({'status': 'success', 'message': f'Updated {control_id} to {value}'})
    else:
        return jsonify({'status': 'error', 'message': 'Failed to update theme value'}), 500

@app.route('/api/start_music', methods=['POST'])
async def start_music():
    try:
        logger.info("Received request to start music")
        
        # First, stop any currently playing music
        await effects_manager.stop_music()
        logger.info("Stopped any currently playing music")
        
        # Now start the new music
        success = await effects_manager.start_music()
        if success:
            logger.info("Successfully started background music")
            return jsonify({"status": "success", "message": "Background music started"}), 200
        else:
            logger.error("Failed to start background music")
            return jsonify({"status": "error", "message": "Failed to start background music"}), 500
    except Exception as e:
        logger.error(f"Error starting background music: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": f"Internal server error: {str(e)}"}), 500

@app.route('/api/stop_music', methods=['POST'])
async def stop_music():
    try:
        success = await effects_manager.stop_music()
        if success:
            return jsonify({"status": "success", "message": "Background music stopped"}), 200
        else:
            return jsonify({"status": "error", "message": "Failed to stop background music"}), 500
    except Exception as e:
        logger.error(f"Error stopping background music: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/kill_process', methods=['POST'])
async def kill_process():
    logger.info("Kill process request received")
    response = {"status": "success", "message": "Process termination initiated"}
    await asyncio.sleep(0.1)  # Small delay to allow response to be sent
    os._exit(0)  # This will immediately terminate the Python process
    return jsonify(response)  # This line won't be reached, but it's here for completeness

# This route has been removed as it was a duplicate

@app.route('/api/run_test', methods=['POST'])
async def run_test():
    test_type = request.json['testType']
    rooms = request.json['rooms']
    
    try:
        if test_type == 'channel':
            channel_values = request.json['channelValues']
            return await run_channel_test(rooms, channel_values)
        elif test_type == 'effect':
            effect_name = request.json['effectName']
            return await run_effect_test(rooms, effect_name)
        else:
            return jsonify({"error": "Invalid test type"}), 400
    except Exception as e:
        logger.exception(f"Error running {test_type} test")
        return jsonify({"error": str(e)}), 500

def run_channel_test(rooms, channel_values):
    try:
        for room in rooms:
            lights = light_config.get_room_layout().get(room, [])
            for light in lights:
                start_address = light['start_address']
                light_model = light_config.get_light_config(light['model'])
                fixture_values = [0] * CHANNELS_PER_FIXTURE
                for channel, value in channel_values.items():
                    if channel in light_model['channels']:
                        channel_offset = light_model['channels'][channel]
                        fixture_values[channel_offset] = int(value)
                dmx_state_manager.update_fixture((start_address - 1) // CHANNELS_PER_FIXTURE, fixture_values)
        return jsonify({"message": f"Channel test applied to rooms: {', '.join(rooms)}"}), 200
    except Exception as e:
        logger.exception(f"Error in channel test for rooms: {', '.join(rooms)}")
        return jsonify({"error": str(e)}), 500

async def run_effect_test(rooms, effect_name):
    try:
        effect_data = effects_manager.get_effect(effect_name)
        if not effect_data:
            return jsonify({"error": f"Effect '{effect_name}' not found"}), 404
        
        for room in rooms:
            success = await effects_manager.apply_effect_to_room(room, effect_data)
            if not success:
                return jsonify({"error": f"Failed to apply effect to room {room}"}), 500
        
        return jsonify({"message": f"Effect '{effect_name}' applied to rooms: {', '.join(rooms)}"}), 200
    except Exception as e:
        logger.exception(f"Error in effect test for rooms: {', '.join(rooms)}")
        return jsonify({"error": str(e)}), 500

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

@app.route('/api/run_effect_all_rooms', methods=['POST'])
async def run_effect_all_rooms():
    data = await request.json
    effect_name = data.get('effect_name')
    audio_params = data.get('audio', {})
        
    if not effect_name:
        return jsonify({'status': 'error', 'message': 'Effect name is required'}), 400
        
    logger.info(f"Preparing effect: {effect_name} for all rooms")
    effect_data = effects_manager.get_effect(effect_name)
    if not effect_data:
        logger.error(f"Effect not found: {effect_name}")
        return jsonify({'status': 'error', 'message': f'Effect {effect_name} not found'}), 404
        
    # Select a random audio file for the effect
    audio_file = audio_manager.get_random_audio_file(effect_name)
    if not audio_file:
        logger.warning(f"No audio file found for effect: {effect_name}")
        
    # Add audio parameters to effect data
    effect_data['audio'] = {**audio_params, 'file': audio_file}
        
    try:
        # Play the audio file for all connected clients
        audio_success = await remote_host_manager.play_audio_for_all_clients(effect_name, effect_data['audio'])
            
        # Execute the effect immediately for all rooms
        success, message = await effects_manager.apply_effect_to_all_rooms(effect_name, effect_data)
            
        if success:
            return jsonify({'status': 'success', 'message': f'Effect {effect_name} executed for all remote units simultaneously'})
        else:
            error_message = f"Failed to execute effect {effect_name} for all remote units. Message: {message}"
            logger.error(error_message)
            return jsonify({'status': 'error', 'message': error_message}), 500
    except Exception as e:
        error_message = f"Error executing effect {effect_name} for all remote units: {str(e)}"
        logger.error(error_message, exc_info=True)
        return jsonify({'status': 'error', 'message': error_message}), 500

@app.route('/api/audio/<path:filename>')
async def serve_audio(filename):
    if filename.startswith('The 7th Continent Soundscape'):
        audio_dir = os.path.join(os.path.dirname(__file__), 'music')
    else:
        audio_dir = os.path.join(os.path.dirname(__file__), 'audio_files')
    return await send_from_directory(audio_dir, filename)

if __name__ == '__main__':
    import asyncio
    from hypercorn.config import Config
    from hypercorn.asyncio import serve

    config = Config()
    config.bind = ["0.0.0.0:5000"]
    config.use_reloader = DEBUG
    config.accesslog = "-"  # Log to stdout
    config.errorlog = "-"  # Log to stderr
    config.loglevel = "DEBUG"

    async def run_server():
        try:
            await initialize_remote_hosts()
            websocket_server = await websockets.serve(websocket_handler, "0.0.0.0", 8765)
            quart_server = serve(app, config)
            await asyncio.gather(websocket_server.wait_closed(), quart_server)
        except Exception as e:
            log_and_exit(f"Server crashed: {str(e)}")

    print("Starting server on http://0.0.0.0:5000")
    try:
        asyncio.run(run_server())
    except Exception as e:
        log_and_exit(f"Failed to start server: {str(e)}")
