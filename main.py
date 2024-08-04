import os
import logging
import json
from flask import Flask, request, render_template, redirect, url_for, session, jsonify, abort, flash
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

@app.route('/')
def index():
    return render_template('index.html', 
                           verbose_logging=session.get('verbose_logging', False),
                           current_theme=effects_manager.current_theme,
                           master_brightness=effects_manager.master_brightness)

@app.route('/set_master_brightness', methods=['POST'])
def set_master_brightness():
    brightness = float(request.form.get('brightness', 1.0))
    effects_manager.set_master_brightness(brightness)
    return jsonify({"status": "success", "master_brightness": brightness})

@app.route('/set_theme', methods=['POST'])
def set_theme():
    if request.is_json:
        theme_name = request.json.get('theme_name')
        if effects_manager.set_current_theme(theme_name):
            return jsonify({'status': 'success', 'message': f'Theme set to {theme_name}'})
        else:
            return jsonify({'status': 'error', 'message': f'Failed to set theme to {theme_name}'}), 400
    else:
        return jsonify({'status': 'error', 'message': 'Invalid content type, expected JSON'}), 415

@app.route('/run_effect', methods=['POST'])
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

@app.route('/toggle_verbose_logging', methods=['POST'])
def toggle_verbose_logging():
    new_state = request.form.get('verbose_logging') == 'true'
    session['verbose_logging'] = new_state
    set_verbose_logging(new_state)
    return jsonify({"status": "success", "verbose_logging": new_state})

@app.route('/effects')
def effects():
    return render_template('effects.html', effects=effects_manager.get_all_effects())

@app.route('/rooms')
def rooms():
    return render_template('room_manager.html', room_layout=light_config.get_room_layout(), effects_manager=effects_manager)

@app.route('/light_models')
def light_models():
    return render_template('light_models.html', light_models=light_config.get_light_models())

@app.route('/edit_room/<room>', methods=['GET', 'POST'])
def edit_room(room):
    if request.method == 'POST':
        lights = []
        for i in range(int(request.form['light_count'])):
            lights.append({
                'model': request.form[f'model_{i}'],
                'start_address': int(request.form[f'start_address_{i}'])
            })
        light_config.update_room(room, lights)
        return redirect(url_for('rooms'))
    room_layout = light_config.get_room_layout()
    if room not in room_layout:
        abort(404)
    return render_template('edit_room.html', room=room, lights=room_layout[room], light_models=light_config.get_light_models())

@app.route('/delete_room/<room>', methods=['POST'])
def delete_room(room):
    light_config.remove_room(room)
    return redirect(url_for('rooms'))

@app.route('/add_room', methods=['GET', 'POST'])
def add_room():
    if request.method == 'POST':
        room_name = request.form['room_name']
        lights = []
        for i in range(int(request.form['light_count'])):
            lights.append({
                'model': request.form[f'model_{i}'],
                'start_address': int(request.form[f'start_address_{i}'])
            })
        light_config.add_room(room_name, lights)
        return redirect(url_for('rooms'))
    return render_template('add_room.html', light_models=light_config.get_light_models())

@app.route('/add_light_model', methods=['GET', 'POST'])
def add_light_model():
    if request.method == 'POST':
        model = request.form['model']
        channels = {}
        for key, value in request.form.items():
            if key.startswith('channel_'):
                channels[request.form[f'channel_name_{key[8:]}']] = int(value)
        light_config.add_light_model(model, {"channels": channels})
        return redirect(url_for('light_models'))
    return render_template('add_light_model.html')

@app.route('/assign_effect', methods=['POST'])
def assign_effect():
    room = request.form.get('room')
    effect_name = request.form.get('effect_name')
    effects_manager.assign_effect_to_room(room, effect_name)
    return redirect(url_for('rooms'))

@app.route('/remove_room_effect/<room>', methods=['POST'])
def remove_room_effect(room):
    effects_manager.remove_effect_from_room(room)
    return redirect(url_for('rooms'))

@app.route('/test_effect/<room>', methods=['POST'])
def test_effect(room):
    effect_name = effects_manager.room_effects.get(room)
    if effect_name:
        effect_data = effects_manager.effects.get(effect_name)
        if effect_data:
            success, log_messages = effects_manager.apply_effect_to_room(room, effect_data)
            return jsonify({"success": success, "log_messages": log_messages})
        else:
            return jsonify({"error": f"Effect '{effect_name}' not found"}), 400
    return jsonify({"error": "No effect assigned to this room"}), 400

@app.route('/edit_light_model/<model>', methods=['GET', 'POST'])
def edit_light_model(model):
    if request.method == 'POST':
        channels = {}
        for key, value in request.form.items():
            if key.startswith('channel_'):
                channels[key[8:]] = int(value)
        light_config.update_light_model(model, {"channels": channels})
        return redirect(url_for('light_models'))
    light_model = light_config.get_light_config(model)
    return render_template('edit_light_model.html', model=model, light_model=light_model)

@app.route('/remove_light_model/<model>', methods=['POST'])
def remove_light_model(model):
    light_config.remove_light_model(model)
    return redirect(url_for('light_models'))

@app.route('/add_effect', methods=['GET', 'POST'])
def add_effect():
    if request.method == 'POST':
        effect_name = request.form['effect_name']
        effect_data = {
            'duration': float(request.form['duration']),
            'steps': json.loads(request.form['steps'])
        }
        effects_manager.add_effect(effect_name, effect_data)
        return redirect(url_for('effects'))
    return render_template('add_effect.html', rooms=light_config.get_room_layout().keys())

@app.route('/edit_effect/<effect_name>', methods=['GET', 'POST'])
def edit_effect(effect_name):
    if request.method == 'POST':
        effect_data = {
            'duration': float(request.form['duration']),
            'steps': json.loads(request.form['steps'])
        }
        effects_manager.update_effect(effect_name, effect_data)
        return redirect(url_for('effects'))
    effect = effects_manager.get_effect(effect_name)
    return render_template('edit_effect.html', effect_name=effect_name, effect=effect)

@app.route('/remove_effect/<effect_name>', methods=['POST'])
def remove_effect(effect_name):
    effects_manager.remove_effect(effect_name)
    return redirect(url_for('effects'))

@app.route('/test_mode')
def test_mode():
    rooms = light_config.get_room_layout().keys()
    return render_template('test_mode.html', rooms=rooms)

@app.route('/run_test', methods=['POST'])
def run_test():
    test_type = request.json['testType']
    rooms = request.json['rooms']
    
    try:
        if test_type == 'channel':
            channel_values = request.json['channelValues']
            return run_channel_test(rooms, channel_values)
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

@app.route('/stop_test', methods=['POST'])
def stop_test():
    try:
        for fixture_id in range(NUM_FIXTURES):
            dmx_state_manager.reset_fixture(fixture_id)
        logger.info("Test stopped and all channels reset")
        return jsonify({"message": "Test stopped and lights reset"}), 200
    except Exception as e:
        logger.exception("Error stopping test")
        return jsonify({"error": str(e)}), 500

@app.route('/trigger_lightning', methods=['POST'])
def trigger_lightning():
    try:
        # Assuming the lightning effect should be applied to all rooms
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
