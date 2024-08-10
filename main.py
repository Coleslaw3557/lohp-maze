import os
import logging
import asyncio
from flask import Flask, request, jsonify
from quart import Quart
from flask_cors import CORS
from werkzeug.urls import uri_to_iri, iri_to_uri
from dmx_state_manager import DMXStateManager
from dmx_interface import DMXOutputManager
from light_config_manager import LightConfigManager
from effects_manager import EffectsManager
from interrupt_handler import InterruptHandler

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
CORS(app)
app.secret_key = SECRET_KEY

# Initialize components
dmx_state_manager = DMXStateManager(NUM_FIXTURES, CHANNELS_PER_FIXTURE)
dmx_output_manager = DMXOutputManager(dmx_state_manager)
light_config = LightConfigManager(dmx_state_manager=dmx_state_manager)
effects_manager = EffectsManager(config_file='effects_config.json', light_config_manager=light_config, dmx_state_manager=dmx_state_manager)
interrupt_handler = InterruptHandler(dmx_state_manager)
effects_manager.interrupt_handler = interrupt_handler
logger.info("InterruptHandler initialized and passed to EffectsManager")

# Reset all lights to off
dmx_state_manager.reset_all_fixtures()

# Start threads
dmx_output_manager.start()

# Ensure no theme is running at startup
effects_manager.stop_current_theme()

@app.route('/api/set_master_brightness', methods=['POST'])
def set_master_brightness():
    brightness = float(request.json.get('brightness', 1.0))
    effects_manager.set_master_brightness(brightness)
    return jsonify({"status": "success", "master_brightness": brightness})

@app.route('/api/set_theme', methods=['POST'])
async def set_theme():
    theme_name = request.json.get('theme_name')
    if not theme_name:
        return jsonify({'status': 'error', 'message': 'Theme name is required'}), 400

    if await effects_manager.theme_manager.set_current_theme_async(theme_name):
        return jsonify({'status': 'success', 'message': f'Theme set to {theme_name}'})
    else:
        return jsonify({'status': 'error', 'message': f'Failed to set theme to {theme_name}'}), 400

@app.route('/api/run_effect', methods=['POST'])
async def run_effect():
    room = request.json.get('room')
    effect_name = request.json.get('effect_name')
    
    if not room or not effect_name:
        return jsonify({'status': 'error', 'message': 'Room and effect_name are required'}), 400
    
    effect_data = effects_manager.get_effect(effect_name)
    if not effect_data:
        return jsonify({'status': 'error', 'message': f'Effect {effect_name} not found'}), 404
    
    success = await effects_manager.apply_effect_to_room(room, effect_data)
    
    if success:
        return jsonify({'status': 'success', 'message': f'Effect {effect_name} applied to room {room}'})
    else:
        return jsonify({'status': 'error', 'message': f'Failed to apply effect {effect_name} to room {room}'}), 500

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
    effect_name = request.json.get('effect_name')
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
    asyncio.run(serve(app, config))
