import logging
import time
import threading
from effect_utils import generate_theme_values

logger = logging.getLogger(__name__)

class ThemeManager:
    def __init__(self, dmx_state_manager, light_config_manager):
        self.dmx_state_manager = dmx_state_manager
        self.light_config_manager = light_config_manager
        self.themes = {}
        self.current_theme = None
        self.theme_thread = None
        self.stop_theme = threading.Event()
        self.theme_lock = threading.Lock()
        self.master_brightness = 1.0
        self.frequency = 44  # 44 Hz update rate

    def load_themes(self):
        # Load themes from a JSON file or database
        self.themes = {
            "Ocean": {
                "duration": 120,
                "transition_speed": 0.2,
                "color_variation": 0.5,
                "intensity_fluctuation": 0.4,
                "overall_brightness": 0.7,
                "blue_green_balance": 0.9
            },
            "Jungle": {
                "duration": 60,
                "transition_speed": 0.4,
                "color_variation": 0.5,
                "intensity_fluctuation": 0.3,
                "overall_brightness": 0.6,
                "green_blue_balance": 0.3
            }
        }

    def set_current_theme(self, theme_name):
        if theme_name in self.themes:
            with self.theme_lock:
                old_theme = self.current_theme
                self.stop_current_theme()
                self.current_theme = theme_name
                self.stop_theme.clear()
                self.theme_thread = threading.Thread(target=self._run_theme, args=(theme_name,))
                self.theme_thread.start()
            logger.info(f"Theme changing from {old_theme} to: {theme_name}")
            return True
        else:
            logger.warning(f"Theme not found: {theme_name}")
            return False

    def stop_current_theme(self):
        with self.theme_lock:
            if self.current_theme:
                self.stop_theme.set()
                if self.theme_thread and self.theme_thread.is_alive():
                    self.theme_thread.join(timeout=5)
                self.current_theme = None
                self._reset_all_lights()
                logger.info("Current theme stopped and all lights reset")

    def _reset_all_lights(self):
        for fixture_id in range(self.dmx_state_manager.num_fixtures):
            self.dmx_state_manager.reset_fixture(fixture_id)

    def _run_theme(self, theme_name):
        theme_data = self.themes[theme_name]
        logger.info(f"Starting theme: {theme_name}")
        start_time = time.time()
        while not self.stop_theme.is_set():
            current_time = time.time() - start_time
            self._generate_and_apply_theme_step(theme_data, current_time)
            time.sleep(1 / self.frequency)
        logger.info(f"Theme {theme_name} stopped")

    def _generate_and_apply_theme_step(self, theme_data, current_time):
        room_layout = self.light_config_manager.get_room_layout()
        for room, lights in room_layout.items():
            room_channels = generate_theme_values(theme_data, current_time, self.master_brightness)
            self._apply_room_channels(room, lights, room_channels)

    def _apply_room_channels(self, room, lights, room_channels):
        for light in lights:
            start_address = light['start_address']
            light_model = self.light_config_manager.get_light_config(light['model'])
            fixture_id = (start_address - 1) // 8
            fixture_values = [0] * 8
            for channel, value in room_channels.items():
                if channel in light_model['channels']:
                    channel_offset = light_model['channels'][channel]
                    fixture_values[channel_offset] = value
            self.dmx_state_manager.update_fixture(fixture_id, fixture_values)

    def set_master_brightness(self, brightness):
        self.master_brightness = max(0.0, min(1.0, brightness))
        logger.info(f"Master brightness set to {self.master_brightness}")

    def get_all_themes(self):
        return self.themes

    def get_theme(self, theme_name):
        return self.themes.get(theme_name)