import json
import logging
import time
import threading
import random

logger = logging.getLogger(__name__)

class EffectsManager:
    def __init__(self, config_file='effects_config.json', light_config_manager=None):
        self.config_file = config_file
        self.effects = self.load_config()
        self.room_effects = {}
        self.themes = {}
        self.current_theme = None
        self.theme_thread = None
        self.stop_theme = threading.Event()
        self.light_config_manager = light_config_manager
        self.frequency = 24  # Default frequency

    def update_frequency(self, new_frequency):
        self.frequency = new_frequency
        if self.current_theme:
            self.stop_current_theme()
            self.set_current_theme(self.current_theme)  # Restart the current theme with new frequency

    def load_config(self):
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            logger.info(f"Effects configuration loaded from {self.config_file}")
            return config
        except FileNotFoundError:
            logger.error(f"Configuration file {self.config_file} not found.")
            return {}
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from {self.config_file}.")
            return {}

    def save_config(self):
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.effects, f, indent=4)
            logger.info(f"Effects configuration saved to {self.config_file}")
        except IOError:
            logger.error(f"Error writing to {self.config_file}")

    def get_effect(self, room):
        return self.effects.get(room, None)

    def add_effect(self, effect_name, effect_data):
        self.effects[effect_name] = effect_data
        self.save_config()
        logger.info(f"Effect added: {effect_name}")

    def update_effect(self, effect_name, effect_data):
        if effect_name in self.effects:
            self.effects[effect_name] = effect_data
            self.save_config()
            logger.info(f"Effect updated: {effect_name}")
        else:
            logger.warning(f"No effect found: {effect_name}")

    def remove_effect(self, effect_name):
        if effect_name in self.effects:
            del self.effects[effect_name]
            self.save_config()
            logger.info(f"Effect removed: {effect_name}")
        else:
            logger.warning(f"No effect found: {effect_name}")

    def assign_effect_to_room(self, room, effect_name):
        if effect_name in self.effects:
            self.room_effects[room] = effect_name
            logger.info(f"Effect {effect_name} assigned to room: {room}")
        else:
            logger.warning(f"No effect found: {effect_name}")

    def remove_effect_from_room(self, room):
        if room in self.room_effects:
            del self.room_effects[room]
            logger.info(f"Effect removed from room: {room}")
        else:
            logger.warning(f"No effect assigned to room: {room}")

    def get_room_effect(self, room):
        effect_name = self.room_effects.get(room)
        if effect_name:
            return self.effects.get(effect_name)
        return None

    def get_all_effects(self):
        return self.effects

    def add_theme(self, theme_name, theme_data):
        theme_data['frequency'] = 40  # Fixed at 40 Hz
        self.themes[theme_name] = theme_data
        self.save_config()
        logger.info(f"Theme added: {theme_name}")

    def update_theme(self, theme_name, theme_data):
        if theme_name in self.themes:
            theme_data['frequency'] = 40  # Fixed at 40 Hz
            self.themes[theme_name] = theme_data
            self.save_config()
            logger.info(f"Theme updated: {theme_name}")
            if self.current_theme == theme_name:
                self.stop_theme.set()
                if self.theme_thread:
                    self.theme_thread.join()
                self.stop_theme.clear()
                self.theme_thread = threading.Thread(target=self._run_theme, args=(theme_name,))
                self.theme_thread.start()
        else:
            logger.warning(f"No theme found: {theme_name}")

    def set_theme_brightness(self, theme_name, brightness):
        if theme_name in self.themes:
            self.themes[theme_name]['overall_brightness'] = brightness
            self.save_config()
            logger.info(f"Theme brightness updated: {theme_name}, brightness: {brightness}")
            if self.current_theme == theme_name:
                # Restart the theme to apply the new brightness
                self.set_current_theme(theme_name)
        else:
            logger.warning(f"No theme found: {theme_name}")

    def remove_theme(self, theme_name):
        if theme_name in self.themes:
            del self.themes[theme_name]
            self.save_config()
            logger.info(f"Theme removed: {theme_name}")
        else:
            logger.warning(f"No theme found: {theme_name}")

    def get_all_themes(self):
        return self.themes

    def get_theme(self, theme_name):
        return self.themes.get(theme_name)

    def set_current_theme(self, theme_name):
        if theme_name in self.themes:
            self.current_theme = theme_name
            self.stop_theme.set()
            if self.theme_thread:
                self.theme_thread.join()
            self.stop_theme.clear()
            self.theme_thread = threading.Thread(target=self._run_theme, args=(theme_name,))
            self.theme_thread.start()
            logger.info(f"Current theme set to: {theme_name}")
        else:
            logger.warning(f"Theme not found: {theme_name}")

    def _run_theme(self, theme_name):
        theme_data = self.themes[theme_name]
        self.light_config_manager.dmx_interface.set_frequency(40)  # Fixed at 40 Hz
        while not self.stop_theme.is_set():
            start_time = time.time()
            self._generate_and_apply_theme_steps(theme_data)
            if time.time() - start_time < theme_data['duration']:
                time.sleep(theme_data['duration'] - (time.time() - start_time))

    def _generate_and_apply_theme_steps(self, theme_data):
        room_layout = self.light_config_manager.get_room_layout()
        speed = theme_data.get('speed', 1.0)  # Default to 1.0 if 'speed' is not present
        step_duration = 1.0 / speed
        for _ in range(int(theme_data['duration'] * speed)):
            if self.stop_theme.is_set():
                break
            step = self._generate_theme_step(theme_data, room_layout)
            self._apply_theme_step(step)
            time.sleep(step_duration)

    def _generate_theme_step(self, theme_data, room_layout):
        step = {'rooms': {}}
        for room in room_layout.keys():
            if room not in self.room_effects:
                step['rooms'][room] = self._generate_room_channels(theme_data)
        return step

    def _generate_room_channels(self, theme_data):
        channels = {}
        overall_brightness = theme_data.get('overall_brightness', 0.5)
        green_blue_balance = theme_data.get('green_blue_balance', 0.5)
        color_variation = theme_data.get('color_variation', 0.5)
        intensity_fluctuation = theme_data.get('intensity_fluctuation', 0.5)

        # Adjust base colors based on green-blue balance
        base_green = int(180 * (1 + (green_blue_balance - 0.5) * 0.4))  # 20% variation
        base_blue = int(20 * (1 + (0.5 - green_blue_balance) * 0.4))  # 20% variation
        base_red = 30  # Keep red constant for jungle theme

        # Apply color variation and intensity fluctuation
        red = max(0, min(255, base_red + int(random.uniform(-20, 20) * color_variation)))
        green = max(0, min(255, base_green + int(random.uniform(-40, 40) * color_variation)))
        blue = max(0, min(255, base_blue + int(random.uniform(-20, 20) * color_variation)))

        # Apply overall brightness and intensity fluctuation
        total_dimming = int(overall_brightness * 255 * (1 + random.uniform(-0.2, 0.2) * intensity_fluctuation))
        total_dimming = max(0, min(255, total_dimming))

        channels['total_dimming'] = total_dimming
        channels['r_dimming'] = red
        channels['g_dimming'] = green
        channels['b_dimming'] = blue

        return channels

    def _hue_to_rgb(self, hue):
        r = self._hue_to_rgb_helper(hue + 1/3)
        g = self._hue_to_rgb_helper(hue)
        b = self._hue_to_rgb_helper(hue - 1/3)
        return {'r_dimming': r, 'g_dimming': g, 'b_dimming': b}

    def _hue_to_rgb_helper(self, hue):
        hue = hue % 1
        if hue < 0:
            hue += 1
        if hue * 6 < 1:
            return hue * 6
        if hue * 2 < 1:
            return 1
        if hue * 3 < 2:
            return (2/3 - hue) * 6
        return 0

    def _apply_theme_step(self, step):
        room_layout = self.light_config_manager.get_room_layout()
        for room, lights in room_layout.items():
            if room not in self.room_effects:
                room_channels = step['rooms'].get(room, {})
                for light in lights:
                    start_address = light['start_address']
                    light_model = self.light_config_manager.get_light_config(light['model'])
                    for channel, value in room_channels.items():
                        if channel in light_model['channels']:
                            channel_offset = light_model['channels'][channel]
                            self.light_config_manager.dmx_interface.set_channel(start_address + channel_offset, value)
        self.light_config_manager.dmx_interface.send_dmx()

    def stop_current_theme(self):
        self.stop_theme.set()
        if self.theme_thread:
            self.theme_thread.join()
        self.current_theme = None
        self._reset_all_lights()
        logger.info("Current theme stopped and all lights reset")

    def _reset_all_lights(self):
        room_layout = self.light_config_manager.get_room_layout()
        for room, lights in room_layout.items():
            for light in lights:
                start_address = light['start_address']
                light_model = self.light_config_manager.get_light_config(light['model'])
                for channel in light_model['channels'].values():
                    self.light_config_manager.dmx_interface.set_channel(start_address + channel, 0)
        self.light_config_manager.dmx_interface.send_dmx()

    def create_cop_dodge_effect(self):
        cop_dodge_effect = {
            "duration": 15.0,
            "steps": [
                # Slower alternating sequence
                {"time": 0.0, "channels": {"total_dimming": 255, "r_dimming": 255, "b_dimming": 0}},
                {"time": 0.5, "channels": {"total_dimming": 255, "r_dimming": 0, "b_dimming": 255}},
                {"time": 1.0, "channels": {"total_dimming": 255, "r_dimming": 255, "b_dimming": 0}},
                {"time": 1.5, "channels": {"total_dimming": 255, "r_dimming": 0, "b_dimming": 255}},
                {"time": 2.0, "channels": {"total_dimming": 255, "r_dimming": 255, "b_dimming": 0}},
                {"time": 2.5, "channels": {"total_dimming": 255, "r_dimming": 0, "b_dimming": 255}},
                # Repeat the sequence
                {"time": 3.0, "channels": {"total_dimming": 255, "r_dimming": 255, "b_dimming": 0}},
                {"time": 3.5, "channels": {"total_dimming": 255, "r_dimming": 0, "b_dimming": 255}},
                {"time": 4.0, "channels": {"total_dimming": 255, "r_dimming": 255, "b_dimming": 0}},
                {"time": 4.5, "channels": {"total_dimming": 255, "r_dimming": 0, "b_dimming": 255}},
                {"time": 5.0, "channels": {"total_dimming": 255, "r_dimming": 255, "b_dimming": 0}},
                {"time": 5.5, "channels": {"total_dimming": 255, "r_dimming": 0, "b_dimming": 255}},
                # Final off state
                {"time": 15.0, "channels": {"total_dimming": 0, "r_dimming": 0, "b_dimming": 0}}
            ]
        }
        self.add_effect("Cop Dodge", cop_dodge_effect)
