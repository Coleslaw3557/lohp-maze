import logging
import time
import threading
import asyncio
from effect_utils import generate_theme_values

logger = logging.getLogger(__name__)

class ThemeManager:
    def __init__(self, dmx_state_manager, light_config_manager, interrupt_handler):
        self.dmx_state_manager = dmx_state_manager
        self.light_config_manager = light_config_manager
        self.interrupt_handler = interrupt_handler
        self.themes = {}
        self.current_theme = None
        self.theme_thread = None
        self.stop_theme = threading.Event()
        self.theme_lock = threading.Lock()
        self.master_brightness = 1.0
        self.frequency = 10  # Reduce update rate to 10 Hz
        self.paused_rooms = set()
        self.theme_list = []
        self.current_theme_index = -1
        self.previous_values = {}  # Store previous values for smoothing
        self.smoothing_factor = 0.2  # Adjust this value to control smoothing (0.0 to 1.0)
        self.load_themes()  # Load themes when initializing

    def load_themes(self):
        # Load themes with more dynamic and vibrant settings
        self.themes = {
            "NeonNightlife": {
                "duration": 3600,  # 1 hour
                "transition_speed": 0.1,
                "color_variation": 1.0,
                "intensity_fluctuation": 0.8,
                "overall_brightness": 0.9,
                "room_transition_speed": 0.05,
                "color_wheel_speed": 0.2,
                "neon_pulse": 0.9,
                "strobe_frequency": 0.3,
                "color_shift": 0.7,
                "base_hue": 0.8,  # Purple
                "hue_range": 1.0,  # Full spectrum
                "saturation_min": 0.7,
                "saturation_max": 1.0,
                "value_min": 0.6,
                "value_max": 1.0
            },
            "TropicalParadise": {
                "duration": 3600,  # 1 hour
                "transition_speed": 0.08,
                "color_variation": 0.9,
                "intensity_fluctuation": 0.6,
                "overall_brightness": 0.85,
                "room_transition_speed": 0.04,
                "color_wheel_speed": 0.15,
                "wave_effect": 0.7,
                "sunset_glow": 0.8,
                "palm_shadow": 0.5,
                "base_hue": 0.1,  # Orange
                "hue_range": 0.3,  # Orange to Green
                "saturation_min": 0.6,
                "saturation_max": 1.0,
                "value_min": 0.7,
                "value_max": 0.95
            },
            "CyberPunk": {
                "duration": 3600,  # 1 hour
                "transition_speed": 0.12,
                "color_variation": 1.0,
                "intensity_fluctuation": 0.9,
                "overall_brightness": 0.95,
                "room_transition_speed": 0.06,
                "color_wheel_speed": 0.25,
                "neon_flicker": 0.8,
                "data_stream": 0.7,
                "hologram_effect": 0.6,
                "base_hue": 0.6,  # Blue
                "hue_range": 0.8,  # Blue to Pink
                "saturation_min": 0.8,
                "saturation_max": 1.0,
                "value_min": 0.7,
                "value_max": 1.0
            },
            "EnchantedForest": {
                "duration": 3600,  # 1 hour
                "transition_speed": 0.06,
                "color_variation": 0.8,
                "intensity_fluctuation": 0.7,
                "overall_brightness": 0.8,
                "room_transition_speed": 0.03,
                "color_wheel_speed": 0.1,
                "fairy_lights": 0.6,
                "moonbeam": 0.5,
                "firefly_effect": 0.7,
                "base_hue": 0.3,  # Green
                "hue_range": 0.4,  # Green to Purple
                "saturation_min": 0.5,
                "saturation_max": 0.9,
                "value_min": 0.6,
                "value_max": 0.9
            },
            "CosmicVoyage": {
                "duration": 3600,  # 1 hour
                "transition_speed": 0.15,
                "color_variation": 1.0,
                "intensity_fluctuation": 0.9,
                "overall_brightness": 0.9,
                "room_transition_speed": 0.07,
                "color_wheel_speed": 0.3,
                "starfield_twinkle": 0.8,
                "nebula_swirl": 0.7,
                "wormhole_effect": 0.6,
                "base_hue": 0.7,  # Indigo
                "hue_range": 1.0,  # Full spectrum
                "saturation_min": 0.7,
                "saturation_max": 1.0,
                "value_min": 0.5,
                "value_max": 1.0
            }
        }
        self.theme_list = list(self.themes.keys())

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

    async def set_current_theme_async(self, theme_name):
        logger.info(f"Setting theme to: {theme_name}")
        if theme_name in self.themes:
            with self.theme_lock:
                old_theme = self.current_theme
                await self.stop_current_theme_async()
                self.current_theme = theme_name
                self.stop_theme.clear()
                self.theme_thread = threading.Thread(target=self._run_theme, args=(theme_name,))
                self.theme_thread.start()
            logger.info(f"Theme changed from {old_theme} to: {theme_name}")
            return True
        else:
            logger.warning(f"Theme not found: {theme_name}")
            return False

    async def stop_current_theme_async(self):
        async with asyncio.Lock():
            if self.current_theme:
                logger.info(f"Stopping current theme: {self.current_theme}")
                self.stop_theme.set()
                if self.theme_thread and self.theme_thread.is_alive():
                    try:
                        await asyncio.wait_for(asyncio.to_thread(self.theme_thread.join), timeout=5.0)
                    except asyncio.TimeoutError:
                        logger.warning("Theme thread join timed out after 5 seconds")
                        self.theme_thread = None
                self.current_theme = None
                self.current_theme_index = -1
                await asyncio.to_thread(self._reset_all_lights)
                logger.info("Theme stopped and lights reset")

    async def set_next_theme_async(self):
        logger.info("Setting next theme")
        if not self.theme_list:
            logger.warning("No themes available")
            return None

        current_index = self.theme_list.index(self.current_theme) if self.current_theme in self.theme_list else -1
        for i in range(len(self.theme_list)):
            next_index = (current_index + i + 1) % len(self.theme_list)
            next_theme = self.theme_list[next_index]
            if next_theme != self.current_theme:
                success = await self.set_current_theme_async(next_theme)
                if success:
                    logger.info(f"Successfully set next theme to: {next_theme}")
                    return next_theme
        
        logger.error("Failed to set any theme after trying all available themes")
        return None

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
        last_update_time = 0
        try:
            while not self.stop_theme.is_set():
                current_time = time.time() - start_time
                if current_time - last_update_time >= 1 / self.frequency:
                    self._generate_and_apply_theme_step(theme_data, current_time)
                    last_update_time = current_time
                time.sleep(0.001)  # Small sleep to prevent CPU hogging
        except Exception as e:
            logger.error(f"Error in theme {theme_name}: {str(e)}", exc_info=True)
        finally:
            logger.info(f"Theme {theme_name} stopped")

    def _generate_and_apply_theme_step(self, theme_data, current_time):
        room_layout = self.light_config_manager.get_room_layout()
        total_rooms = len(room_layout)
        all_room_channels = {}
        for room_index, (room, lights) in enumerate(room_layout.items()):
            if room not in self.paused_rooms:
                room_channels = generate_theme_values(theme_data, current_time, self.master_brightness, room_index, total_rooms)
                smoothed_channels = self._smooth_channels(room, room_channels)
                all_room_channels[room] = smoothed_channels
                logger.debug(f"Generated channels for room {room}: {smoothed_channels}")
                self._apply_room_channels(room, lights, smoothed_channels)
            else:
                logger.debug(f"Room {room} is paused, skipping theme application")
        
        if not all_room_channels:
            logger.warning("No room channels were generated. Check if all rooms are paused or if there's an issue with room layout.")
        
        return all_room_channels

    def _smooth_channels(self, room, new_channels):
        if room not in self.previous_values:
            self.previous_values[room] = new_channels
            return new_channels

        smoothed_channels = {}
        for channel, value in new_channels.items():
            prev_value = self.previous_values[room].get(channel, value)
            smoothed_value = prev_value + (value - prev_value) * self.smoothing_factor
            smoothed_channels[channel] = int(smoothed_value)

        self.previous_values[room] = smoothed_channels
        return smoothed_channels

    def pause_theme_for_room(self, room):
        self.paused_rooms.add(room)
        logger.info(f"Theme paused for room: {room}")

    def resume_theme_for_room(self, room):
        self.paused_rooms.discard(room)
        logger.info(f"Theme resumed for room: {room}")

    def _apply_room_channels(self, room, lights, room_channels):
        current_time = time.time()
        for light in lights:
            start_address = light['start_address']
            light_model = self.light_config_manager.get_light_config(light['model'])
            fixture_id = (start_address - 1) // 8
            if fixture_id not in self.interrupt_handler.interrupted_fixtures or \
               (fixture_id in self.interrupt_handler.interrupt_end_times and current_time >= self.interrupt_handler.interrupt_end_times[fixture_id]):
                fixture_values = [0] * 8
                for channel, value in room_channels.items():
                    if channel in light_model['channels']:
                        channel_offset = light_model['channels'][channel]
                        fixture_values[channel_offset] = value
                current_values = self.dmx_state_manager.get_fixture_state(fixture_id)
                logger.debug(f"Updating fixture {fixture_id} in room {room}: Current values: {current_values}, New values: {fixture_values}")
                self.dmx_state_manager.update_fixture(fixture_id, fixture_values)
            else:
                logger.debug(f"Fixture {fixture_id} in room {room} is interrupted, skipping update")

    def set_master_brightness(self, brightness):
        self.master_brightness = max(0.0, min(1.0, brightness))
        logger.info(f"Master brightness set to {self.master_brightness}")

    def get_all_themes(self):
        return self.themes

    def get_theme(self, theme_name):
        return self.themes.get(theme_name)

    async def apply_theme_to_room(self, room):
        if self.current_theme:
            theme_data = self.themes[self.current_theme]
            room_layout = self.light_config_manager.get_room_layout()
            lights = room_layout.get(room, [])
            current_time = time.time()
            room_channels = generate_theme_values(theme_data, current_time, self.master_brightness)
            self._apply_room_channels(room, lights, room_channels)
        else:
            logger.warning(f"No current theme to apply to room {room}")

    async def update_theme_value(self, control_id, value):
        if self.current_theme:
            theme_data = self.themes[self.current_theme]
            if control_id in theme_data:
                theme_data[control_id] = value
                logger.info(f"Updated {control_id} to {value} for current theme")
                return True
            else:
                logger.warning(f"Control {control_id} not found in current theme")
                return False
        else:
            logger.warning("No current theme to update")
            return False
