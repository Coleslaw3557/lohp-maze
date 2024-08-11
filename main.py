import os
import logging
import asyncio
import json
import websockets
from quart import Quart, request, jsonify, Response
from quart_cors import cors
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
logging.basicConfig(level=logging.DEBUG if DEBUG else logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Quart(__name__)
app = cors(app)
app.secret_key = SECRET_KEY

connected_clients = set()

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
        'client_connected': handle_client_connected
    }
    
    handler = handlers.get(message_type)
    if handler:
        await handler(ws, data)
    else:
        logger.warning(f"Unknown message type received: {message_type}")
        await ws.send(json.dumps({"status": "error", "message": "Unknown message type"}))

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
remote_host_manager = RemoteHostManager()
audio_manager = AudioManager()
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
    if not theme_name:
        return jsonify({'status': 'error', 'message': 'Theme name is required'}), 400

    try:
        logger.info(f"Setting theme to: {theme_name}")
        success = await asyncio.wait_for(effects_manager.set_current_theme_async(theme_name), timeout=10.0)
        if success:
            logger.info(f"Theme set successfully to: {theme_name}")
            return jsonify({'status': 'success', 'message': f'Theme set to {theme_name}'})
        else:
            logger.error(f"Failed to set theme to: {theme_name}")
            return jsonify({'status': 'error', 'message': f'Failed to set theme to {theme_name}'}), 400
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
    audio_params = data.get('audio', {})
    
    if not room or not effect_name:
        return jsonify({'status': 'error', 'message': 'Room and effect_name are required'}), 400
    
    logger.info(f"Preparing effect: {effect_name} for room: {room}")
    effect_data = effects_manager.get_effect(effect_name)
    if not effect_data:
        logger.error(f"Effect not found: {effect_name}")
        return jsonify({'status': 'error', 'message': f'Effect {effect_name} not found'}), 404
    
    # Add audio parameters to effect data
    effect_data['audio'] = audio_params
    
    try:
        effect_id = await effects_manager.buffer_effect(room, effect_name, effect_data)
        await effects_manager.prepare_effect(effect_id)
        
        # Synchronize execution time
        execution_time = time.time() + 1  # Schedule execution 1 second in the future
        
        # Notify all clients to prepare for synchronized execution
        await remote_host_manager.notify_clients_of_execution(execution_time)
        
        # Schedule the effect execution
        asyncio.create_task(schedule_effect_execution(effect_id, execution_time))
        
        return jsonify({'status': 'success', 'message': f'Effect {effect_name} scheduled for room {room}', 'effect_id': effect_id})
    except Exception as e:
        error_message = f"Error scheduling effect {effect_name} for room {room}: {str(e)}"
        logger.error(error_message, exc_info=True)
        return jsonify({'status': 'error', 'message': error_message}), 500

async def schedule_effect_execution(effect_id, execution_time):
    await asyncio.sleep(execution_time - time.time())
    success = await effects_manager.execute_effect(effect_id)
    if success:
        logger.info(f"Effect {effect_id} executed successfully")
    else:
        logger.error(f"Failed to execute effect {effect_id}")

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
    if not effect_name:
        return jsonify({'status': 'error', 'message': 'Effect name is required'}), 400

    try:
        success, message = await effects_manager.apply_effect_to_all_rooms(effect_name)
        if success:
            return jsonify({"message": f"{effect_name} effect triggered in all rooms"}), 200
        else:
            return jsonify({"error": message}), 400
    except Exception as e:
        logger.exception(f"Error triggering {effect_name} effect in all rooms")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    import asyncio
    from hypercorn.config import Config
    from hypercorn.asyncio import serve

    config = Config()
    config.bind = ["0.0.0.0:5000"]
    config.use_reloader = DEBUG
    config.accesslog = "-"  # Log to stdout
    config.errorlog = "-"  # Log to stderr
    config.loglevel = "INFO"

    async def run_server():
        await initialize_remote_hosts()
        websocket_server = await websockets.serve(websocket_handler, "0.0.0.0", 8765)
        quart_server = serve(app, config)
        await asyncio.gather(websocket_server.wait_closed(), quart_server)

    print("Starting server on http://0.0.0.0:5000")
    asyncio.run(run_server())
