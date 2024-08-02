import os
import time
import logging
import json
from flask import Flask, request, render_template, redirect, url_for, session, jsonify, abort, flash
from dmx_interface import DMXInterface
from light_config_manager import LightConfigManager
from effects_manager import EffectsManager
import threading

# Configuration
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
SECRET_KEY = os.environ.get('SECRET_KEY', 'your_secret_key_here')
DMX_UPDATE_RATE = 40  # Hz (fixed at 40Hz)
DMX_STATUS_CHECK_INTERVAL = 60  # seconds

# Set up logging
logging.basicConfig(level=logging.DEBUG if DEBUG else logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = SECRET_KEY

# Initialize components
dmx = DMXInterface()
light_config = LightConfigManager(dmx_interface=dmx)
effects_manager = EffectsManager(light_config_manager=light_config)
effects_manager.create_cop_dodge_effect()

# Global Hz setting
global_hz = 24

import random

def create_jungle_theme():
    duration = 600.0  # 10 minutes
    steps = []
    rooms = ["Entrance", "Cop Dodge", "Gate", "Guy Line Climb", "Sparkle Pony Room", "Porto Room", 
             "Cuddle Cross", "Exit", "Photo Bomb Room", "Deep Playa Handshake", "No Friends Monday", 
             "Template Room", "Monkey Room", "Bike Lock Room", "Vertical Moop March"]
    
    base_green = 180
    base_red = 30
    base_blue = 20
    base_total_dim = 230

    for t in range(0, int(duration) + 1):
        step = {"time": float(t), "rooms": {}}
        time_factor = t / duration  # Factor to increase variation over time
        for room in rooms:
            # Increase variation over time
            green = base_green + int(random.randint(-40, 40) * time_factor)
            red = base_red + int(random.randint(-20, 20) * time_factor)
            blue = base_blue + int(random.randint(-20, 20) * time_factor)
            total_dim = base_total_dim + int(random.randint(-100, 0) * time_factor)  # Allow dimming down to 25%
            
            # Ensure values are within valid range
            green = max(0, min(255, green))
            red = max(0, min(255, red))
            blue = max(0, min(255, blue))
            total_dim = max(64, min(255, total_dim))  # 64 is 25% of 255
            
            step["rooms"][room] = {
                "total_dimming": total_dim,
                "r_dimming": red,
                "g_dimming": green,
                "b_dimming": blue
            }
        steps.append(step)
    
    # Smooth out transitions
    smoothed_steps = []
    for i in range(len(steps)):
        current_step = steps[i]
        next_step = steps[min(i+1, len(steps)-1)]
        interpolated_step = {"time": current_step["time"], "rooms": {}}
        for room in rooms:
            interpolated_step["rooms"][room] = {
                "total_dimming": int(current_step["rooms"][room]["total_dimming"] * 0.75 + next_step["rooms"][room]["total_dimming"] * 0.25),
                "r_dimming": int(current_step["rooms"][room]["r_dimming"] * 0.75 + next_step["rooms"][room]["r_dimming"] * 0.25),
                "g_dimming": int(current_step["rooms"][room]["g_dimming"] * 0.75 + next_step["rooms"][room]["g_dimming"] * 0.25),
                "b_dimming": int(current_step["rooms"][room]["b_dimming"] * 0.75 + next_step["rooms"][room]["b_dimming"] * 0.25)
            }
        smoothed_steps.append(interpolated_step)
    
    return {
        "duration": duration,
        "steps": smoothed_steps,
        "transition_speed": 0.5,
        "color_variation": 0.5,
        "intensity_fluctuation": 0.5,
        "overall_brightness": 0.5,
        "green_blue_balance": 0.5
    }

# Create and add the jungle theme
jungle_theme = create_jungle_theme()
effects_manager.add_theme("Jungle", jungle_theme)

def dmx_update_loop():
    last_status_check = time.time()
    while True:
        dmx.send_dmx_with_timing()
        
        current_time = time.time()
        if current_time - last_status_check >= DMX_STATUS_CHECK_INTERVAL:
            if not dmx.check_status():
                logger.error("DMX Interface is not ready. Attempting to reinitialize.")
                try:
                    dmx.close()
                    dmx.__init__()
                    logger.info("DMX Interface reinitialized successfully.")
                except Exception as e:
                    logger.error(f"Failed to reinitialize DMX Interface: {str(e)}")
            last_status_check = current_time

dmx_thread = threading.Thread(target=dmx_update_loop, daemon=True)
dmx_thread.start()

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
                           current_theme=effects_manager.current_theme,
                           global_hz=global_hz)

@app.route('/update_hz', methods=['POST'])
def update_hz():
    global global_hz
    try:
        new_hz = int(request.form['hz'])
        if new_hz <= 0 or new_hz > 100:
            raise ValueError("Hz value must be between 1 and 100")
        global_hz = new_hz
        dmx.set_frequency(new_hz)
        logger.info(f"Global Hz updated to {new_hz}")
        flash('Global Hz updated successfully', 'success')
        return jsonify({'status': 'success', 'message': f'Global Hz updated successfully to {new_hz}'})
    except ValueError as e:
        logger.error(f"Invalid Hz value: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating Hz: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': 'An error occurred while updating Hz'}), 500

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
                start_address = int(light['start_address'])
                light_model = light_config.get_light_config(light['model'])
                for channel, value in channel_values.items():
                    if channel in light_model['channels']:
                        channel_offset = light_model['channels'][channel]
                        dmx.set_channel(start_address + channel_offset, int(value))
        dmx.send_dmx()
        return jsonify({"message": f"Channel test applied to rooms: {', '.join(rooms)}"}), 200
    except Exception as e:
        logger.exception(f"Error in channel test for rooms: {', '.join(rooms)}")
        return jsonify({"error": str(e)}), 500

@app.route('/stop_test', methods=['POST'])
def stop_test():
    try:
        dmx.reset_all_channels()
        dmx.send_dmx()
        logger.info("Test stopped and all channels reset")
        return jsonify({"message": "Test stopped and lights reset"}), 200
    except Exception as e:
        logger.exception("Error stopping test")
        return jsonify({"error": str(e)}), 500

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

@app.route('/remove_theme/<theme_name>', methods=['POST'])
def remove_theme(theme_name):
    effects_manager.remove_theme(theme_name)
    return redirect(url_for('themes'))

@app.route('/add_theme', methods=['GET', 'POST'])
def add_theme():
    if request.method == 'POST':
        theme_name = request.form['theme_name']
        theme_data = {
            'duration': float(request.form['duration']),
            'speed': float(request.form['speed']),
            'flow': float(request.form['flow']),
            'randomness': float(request.form['randomness']),
            'brightness': float(request.form['brightness']),
            'color_shift': float(request.form['color_shift'])
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
            'green_blue_balance': float(request.form['green_blue_balance']),
            'frequency': int(request.form['frequency'])
        }
        try:
            effects_manager.update_theme(theme_name, theme_data)
            flash('Theme updated successfully', 'success')
        except Exception as e:
            flash(f'Error updating theme: {str(e)}', 'error')
        return redirect(url_for('themes'))
    theme = effects_manager.get_theme(theme_name)
    return render_template('edit_theme.html', theme_name=theme_name, theme=theme)

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

@app.route('/rooms')
def rooms():
    room_layout = light_config.get_room_layout()
    return render_template('room_manager.html', room_layout=room_layout, effects_manager=effects_manager)

@app.route('/add_room', methods=['GET', 'POST'])
def add_room():
    if request.method == 'POST':
        room_name = request.form['room_name']
        lights = []
        for i in range(int(request.form['light_count'])):
            model = request.form[f'model_{i}']
            start_address = int(request.form[f'start_address_{i}'])
            lights.append({'model': model, 'start_address': start_address})
        light_config.add_room(room_name, lights)
        return redirect(url_for('rooms'))
    return render_template('add_room.html', light_models=light_config.get_light_models())

@app.route('/edit_room/<room>', methods=['GET', 'POST'])
def edit_room(room):
    if request.method == 'POST':
        lights = []
        for i in range(int(request.form['light_count'])):
            model = request.form[f'model_{i}']
            start_address = int(request.form[f'start_address_{i}'])
            lights.append({'model': model, 'start_address': start_address})
        light_config.update_room(room, lights)
        return redirect(url_for('rooms'))
    room_layout = light_config.get_room_layout()
    return render_template('edit_room.html', room=room, lights=room_layout[room], light_models=light_config.get_light_models())

@app.route('/delete_room/<room>', methods=['POST'])
def delete_room(room):
    light_config.remove_room(room)
    return redirect(url_for('rooms'))

@app.route('/light_models')
def light_models():
    return render_template('light_models.html', light_models=light_config.get_light_models())

@app.route('/add_light_model', methods=['GET', 'POST'])
def add_light_model():
    if request.method == 'POST':
        model = request.form['model']
        channels = {}
        for key, value in request.form.items():
            if key.startswith('channel_'):
                channel_name = key.split('_')[1]
                channels[channel_name] = int(value)
        config = {'channels': channels}
        light_config.add_light_model(model, config)
        return redirect(url_for('light_models'))
    return render_template('add_light_model.html')

@app.route('/edit_light_model/<model>', methods=['GET', 'POST'])
def edit_light_model(model):
    if request.method == 'POST':
        channels = {}
        for key, value in request.form.items():
            if key.startswith('channel_'):
                channel_name = key.split('_')[1]
                channels[channel_name] = int(value)
        config = {'channels': channels}
        light_config.update_light_model(model, config)
        return redirect(url_for('light_models'))
    light_model = light_config.get_light_config(model)
    return render_template('edit_light_model.html', model=model, light_model=light_model)

@app.route('/remove_light_model/<model>', methods=['POST'])
def remove_light_model(model):
    light_config.remove_light_model(model)
    return redirect(url_for('light_models'))

@app.route('/effects')
def effects():
    return render_template('effects.html', effects=effects_manager.get_all_effects())

@app.route('/add_effect', methods=['GET', 'POST'])
def add_effect():
    if request.method == 'POST':
        room = request.form['room']
        effect_data = {
            'duration': float(request.form['duration']),
            'steps': json.loads(request.form['steps'])
        }
        effects_manager.add_effect(room, effect_data)
        return redirect(url_for('effects'))
    rooms = light_config.get_room_layout().keys()
    return render_template('add_effect.html', rooms=rooms)

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
    if effect is None:
        abort(404)  # Return a 404 error if the effect is not found
    return render_template('edit_effect.html', effect_name=effect_name, effect=effect)

@app.route('/remove_effect/<effect_name>', methods=['POST'])
def remove_effect(effect_name):
    effects_manager.remove_effect(effect_name)
    return redirect(url_for('effects'))

@app.route('/assign_effect', methods=['POST'])
def assign_effect():
    room = request.form['room']
    effect_name = request.form['effect_name']
    effects_manager.assign_effect_to_room(room, effect_name)
    return redirect(url_for('rooms'))

@app.route('/remove_room_effect/<room>', methods=['POST'])
def remove_room_effect(room):
    effects_manager.remove_effect_from_room(room)
    return redirect(url_for('rooms'))

@app.route('/test_effect/<room>', methods=['POST'])
def test_effect(room):
    effect = effects_manager.get_room_effect(room)
    if effect:
        success, log_messages = light_config.test_effect(room, effect)
        if success:
            return jsonify({
                "message": f"Effect for room {room} tested successfully",
                "log_messages": log_messages
            }), 200
        else:
            return jsonify({
                "error": f"Failed to test effect for room {room}",
                "log_messages": log_messages
            }), 500
    else:
        return jsonify({"error": f"No effect found for room {room}"}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=DEBUG, threaded=True)
