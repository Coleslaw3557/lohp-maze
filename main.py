import os
import logging
import json
from flask import Flask, request, jsonify, abort
from dmx_state_manager import DMXStateManager
from dmx_interface import DMXOutputManager
from light_config_manager import LightConfigManager
from effects_manager import EffectsManager
from interrupt_handler import InterruptHandler
from sequence_runner import SequenceRunner

# Configuration
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
SECRET_KEY = os.environ.get('SECRET_KEY', 'your_secret_key_here')
NUM_FIXTURES = 21
CHANNELS_PER_FIXTURE = 8

# Set up logging
logging.basicConfig(level=logging.DEBUG if DEBUG else logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
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
for fixture_id in range(NUM_FIXTURES):
    dmx_state_manager.reset_fixture(fixture_id)

# Start threads
dmx_output_manager.start()

# Ensure no theme is running at startup
effects_manager.stop_current_theme()

def set_verbose_logging(enabled):
    logging.getLogger().setLevel(logging.DEBUG if enabled else logging.INFO)
    logger.log(logging.DEBUG if enabled else logging.INFO, f"Verbose logging {'enabled' if enabled else 'disabled'}")

@app.before_request
def before_request():
    set_verbose_logging(session.get('verbose_logging', False))

@app.route('/api/set_master_brightness', methods=['POST'])
def set_master_brightness():
    brightness = float(request.json.get('brightness', 1.0))
    effects_manager.set_master_brightness(brightness)
    return jsonify({"status": "success", "master_brightness": brightness})

@app.route('/api/set_theme', methods=['POST'])
def set_theme():
    theme_name = request.json.get('theme_name')
    if not theme_name:
        return jsonify({'status': 'error', 'message': 'Theme name is required'}), 400

    if effects_manager.set_current_theme(theme_name):
        return jsonify({'status': 'success', 'message': f'Theme set to {theme_name}'})
    else:
        return jsonify({'status': 'error', 'message': f'Failed to set theme to {theme_name}'}), 400

@app.route('/api/run_effect', methods=['POST'])
def run_effect():
    room = request.json.get('room')
    effect_name = request.json.get('effect_name')
    
    if not room or not effect_name:
        return jsonify({'status': 'error', 'message': 'Room and effect_name are required'}), 400
    
    effect_data = effects_manager.get_effect(effect_name)
    if not effect_data:
        return jsonify({'status': 'error', 'message': f'Effect {effect_name} not found'}), 404
    
    success, log_messages = effects_manager.apply_effect_to_room(room, effect_data)
    
    if success:
        return jsonify({'status': 'success', 'message': f'Effect {effect_name} applied to room {room}', 'log_messages': log_messages})
    else:
        return jsonify({'status': 'error', 'message': f'Failed to apply effect {effect_name} to room {room}', 'log_messages': log_messages}), 500

@app.route('/api/rooms', methods=['GET'])
def get_rooms():
    rooms = light_config.get_room_layout()
    return jsonify(rooms)

@app.route('/api/effects', methods=['GET'])
def get_effects():
    effects = effects_manager.get_all_effects()
    return jsonify(effects)

@app.route('/api/themes', methods=['GET'])
def get_themes():
    themes = effects_manager.get_all_themes()
    return jsonify(themes)

@app.route('/api/run_test', methods=['POST'])
def run_test():
    test_type = request.json['testType']
    rooms = request.json['rooms']
    
    try:
        if test_type == 'channel':
            channel_values = request.json['channelValues']
            return run_channel_test(rooms, channel_values)
        elif test_type == 'effect':
            effect_name = request.json['effectName']
            return run_effect_test(rooms, effect_name)
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

def run_effect_test(rooms, effect_name):
    try:
        effect_data = effects_manager.get_effect(effect_name)
        if not effect_data:
            return jsonify({"error": f"Effect '{effect_name}' not found"}), 404
        
        for room in rooms:
            success, log_messages = effects_manager.apply_effect_to_room(room, effect_data)
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

@app.route('/api/trigger_lightning', methods=['POST'])
def trigger_lightning():
    try:
        room_layout = light_config.get_room_layout()
        for room in room_layout.keys():
            effect_data = effects_manager.get_effect("Lightning")
            if effect_data:
                success, log_messages = effects_manager.apply_effect_to_room(room, effect_data)
                if not success:
                    logger.warning(f"Failed to apply lightning effect to room {room}")
            else:
                logger.error("Lightning effect not found")
                return jsonify({"error": "Lightning effect not found"}), 404
        return jsonify({"message": "Lightning effect triggered"}), 200
    except Exception as e:
        logger.exception("Error triggering lightning effect")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Create the lightning effect
    effects_manager.create_lightning_effect()
    app.run(host='0.0.0.0', port=5000, debug=DEBUG, threaded=True)
