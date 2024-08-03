import os
import logging
from flask import Flask, request, render_template, redirect, url_for, session, jsonify, abort, flash
from dmx_state_manager import DMXStateManager
from dmx_interface import DMXOutputManager
from light_config_manager import LightConfigManager
from effects_manager import EffectsManager
from sequence_runner import SequenceRunner
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

app = Flask(__name__)
app.secret_key = SECRET_KEY

# Initialize components
dmx_state_manager = DMXStateManager(NUM_FIXTURES, CHANNELS_PER_FIXTURE)
dmx_output_manager = DMXOutputManager(dmx_state_manager, frequency=44)
light_config = LightConfigManager()
effects_manager = EffectsManager(light_config_manager=light_config, dmx_state_manager=dmx_state_manager)
sequence_runner = SequenceRunner(dmx_state_manager)
interrupt_handler = InterruptHandler(dmx_state_manager)

# Start threads
dmx_output_manager.start()
sequence_runner.start()

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
                           themes=effects_manager.get_all_themes(),
                           current_theme=effects_manager.current_theme)

@app.route('/toggle_verbose_logging', methods=['POST'])
def toggle_verbose_logging():
    new_state = request.form.get('verbose_logging') == 'true'
    session['verbose_logging'] = new_state
    set_verbose_logging(new_state)
    return jsonify({"status": "success", "verbose_logging": new_state})

@app.route('/set_theme', methods=['POST'])
def set_theme():
    theme_name = request.form.get('theme_name')
    if theme_name:
        effects_manager.set_current_theme(theme_name)
    else:
        effects_manager.stop_current_theme()
    return redirect(url_for('index'))

@app.route('/stop_theme', methods=['POST'])
def stop_theme():
    effects_manager.stop_current_theme()
    return jsonify({"status": "success", "message": "Theme stopped successfully"})

@app.route('/themes')
def themes():
    return render_template('themes.html', themes=effects_manager.get_all_themes(), current_theme=effects_manager.current_theme)

@app.route('/effects')
def effects():
    return render_template('effects.html', effects=effects_manager.get_all_effects())

@app.route('/rooms')
def rooms():
    return render_template('room_manager.html', room_layout=light_config.get_room_layout(), effects_manager=effects_manager)

@app.route('/light_models')
def light_models():
    return render_template('light_models.html', light_models=light_config.get_light_models())

@app.route('/add_theme', methods=['GET', 'POST'])
def add_theme():
    if request.method == 'POST':
        theme_name = request.form['theme_name']
        theme_data = {
            'duration': float(request.form['duration']),
            'transition_speed': float(request.form['transition_speed']),
            'color_variation': float(request.form['color_variation']),
            'intensity_fluctuation': float(request.form['intensity_fluctuation']),
            'overall_brightness': float(request.form['overall_brightness']),
            'green_blue_balance': float(request.form['green_blue_balance'])
        }
        effects_manager.add_theme(theme_name, theme_data)
        return redirect(url_for('themes'))
    return render_template('add_theme.html')

@app.route('/edit_theme/<theme_name>', methods=['GET', 'POST'])
def edit_theme(theme_name):
    if request.method == 'POST':
        theme_data = {
            'duration': float(request.form['duration']),
            'transition_speed': float(request.form['transition_speed']),
            'color_variation': float(request.form['color_variation']),
            'intensity_fluctuation': float(request.form['intensity_fluctuation']),
            'overall_brightness': float(request.form['overall_brightness']),
            'green_blue_balance': float(request.form['green_blue_balance'])
        }
        try:
            effects_manager.update_theme(theme_name, theme_data)
            flash('Theme updated successfully', 'success')
        except Exception as e:
            flash(f'Error updating theme: {str(e)}', 'error')
        return jsonify({'status': 'success', 'message': 'Theme updated successfully'})
    theme = effects_manager.get_theme(theme_name)
    return render_template('edit_theme.html', theme_name=theme_name, theme=theme)

@app.route('/remove_theme/<theme_name>', methods=['POST'])
def remove_theme(theme_name):
    effects_manager.remove_theme(theme_name)
    return redirect(url_for('themes'))

@app.route('/set_theme_brightness', methods=['POST'])
def set_theme_brightness():
    theme_name = request.form.get('theme_name')
    brightness = float(request.form.get('brightness'))
    if theme_name and brightness is not None:
        try:
            effects_manager.set_theme_brightness(theme_name, brightness)
            return jsonify({'status': 'success'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)})
    return jsonify({'status': 'error', 'message': 'Invalid input'})

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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=DEBUG, threaded=True)
