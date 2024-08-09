import json
import logging
import time
import threading
import random
import asyncio
import math
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

class EffectsManager:
    def __init__(self, config_file='effects_config.json', light_config_manager=None, dmx_state_manager=None, interrupt_handler=None):
        self.config_file = config_file
        self.effects = self.load_config()
        self.room_effects = {}
        self.themes = {}
        self.current_theme = None
        self.theme_thread = None
        self.stop_theme = threading.Event()
        self.light_config_manager = light_config_manager
        self.dmx_state_manager = dmx_state_manager
        self.interrupt_handler = interrupt_handler
        self.frequency = 44  # 44 Hz update rate
        self.theme_lock = threading.Lock()
        self.master_brightness = 1.0  # Initialize master brightness to 100%
        self.load_themes()
        self._last_values = {}
        self._step_count = 0
        
        if self.interrupt_handler is None:
            logger.warning("InterruptHandler not provided. Some features may not work correctly.")
        else:
            logger.info(f"InterruptHandler successfully initialized: {self.interrupt_handler}")
        
        # Initialize all effects
        self.create_lightning_effect()
        self.create_police_lights_effect()
        self.create_gate_inspection_effect()
        self.create_porto_standby_effect()
        self.create_porto_hit_effect()

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
            logger.info(f"Effect '{effect_name}' assigned to room '{room}'")
        else:
            logger.warning(f"No effect found: {effect_name}")

    def _apply_effect_directly(self, room, effect_data, fixture_ids):
        if not self.dmx_state_manager:
            logger.error("DMX State Manager not available. Cannot apply effect directly.")
            return

        logger.info(f"Applying effect directly to room '{room}' on fixtures: {fixture_ids}")
        start_time = time.time()
        for step in effect_data['steps']:
            current_time = time.time() - start_time
            if current_time >= step['time']:
                for fixture_id in fixture_ids:
                    try:
                        self.dmx_state_manager.update_fixture(fixture_id, list(step['channels'].values()))
                        logger.debug(f"Applied step to fixture {fixture_id}: {step['channels']}")
                    except Exception as e:
                        logger.error(f"Error applying step to fixture {fixture_id}: {str(e)}")
            time.sleep(0.05)  # Small delay to prevent excessive CPU usage
        logger.info(f"Effect application completed for room '{room}'")

    async def apply_effect_to_room(self, room, effect_data):
        room_layout = self.light_config_manager.get_room_layout()
        lights = room_layout.get(room, [])
        fixture_ids = [(light['start_address'] - 1) // 8 for light in lights]
        
        logger.info(f"Applying effect to room '{room}'")
        logger.debug(f"Effect data: {effect_data}")
        logger.debug(f"Fixture IDs for room: {fixture_ids}")
        
        log_messages = []
        
        # Mark this room as having an active effect
        self.room_effects[room] = True
        
        # Apply the effect to all fixtures in the room concurrently
        tasks = [self._apply_effect_to_fixture(fixture_id, effect_data) for fixture_id in fixture_ids]
        await asyncio.gather(*tasks)
        
        log_messages.append(f"Effect applied to all fixtures in room '{room}'")
        logger.info(f"Effect application completed in room '{room}'")
        
        # Remove the active effect flag for this room
        self.room_effects.pop(room, None)
        
        return True, log_messages

    def _continue_theme_for_other_rooms(self):
        while True:
            for room, lights in self.light_config_manager.get_room_layout().items():
                if room not in self.room_effects:
                    fixture_ids = [(light['start_address'] - 1) // 8 for light in lights]
                    theme_values = self._generate_theme_values(room)
                    for fixture_id in fixture_ids:
                        self.dmx_state_manager.update_fixture(fixture_id, theme_values)
            time.sleep(1 / self.frequency)

    async def _fade_to_black(self, room, fixture_ids, duration):
        start_time = time.time()
        while time.time() - start_time < duration:
            progress = (time.time() - start_time) / duration
            tasks = []
            for fixture_id in fixture_ids:
                current_values = self.dmx_state_manager.get_fixture_state(fixture_id)
                faded_values = [int(value * (1 - progress)) for value in current_values]
                tasks.append(self._update_fixture(fixture_id, faded_values))
            await asyncio.gather(*tasks)
            await asyncio.sleep(1 / self.frequency)

    async def _fade_to_theme(self, room, fixture_ids, duration):
        start_time = time.time()
        while time.time() - start_time < duration:
            progress = (time.time() - start_time) / duration
            tasks = []
            for fixture_id in fixture_ids:
                current_values = self.dmx_state_manager.get_fixture_state(fixture_id)
                theme_values = self._generate_theme_values(room)
                interpolated_values = [int(current + (theme - current) * progress)
                                       for current, theme in zip(current_values, theme_values)]
                tasks.append(self._update_fixture(fixture_id, interpolated_values))
            await asyncio.gather(*tasks)
            await asyncio.sleep(1 / self.frequency)

    async def _update_fixture(self, fixture_id, values):
        self.dmx_state_manager.update_fixture(fixture_id, values)
        await asyncio.sleep(0)  # Yield control to allow other coroutines to run

    async def _apply_effect_to_fixture(self, fixture_id, effect_data):
        try:
            await self.interrupt_handler.interrupt_fixture(
                fixture_id,
                effect_data['duration'],
                self._get_effect_step_values(effect_data)
            )
            logger.debug(f"Effect applied to fixture {fixture_id}")
        except Exception as e:
            error_msg = f"Error applying effect to fixture {fixture_id}: {str(e)}"
            logger.error(error_msg)

    def _reset_room_lights(self, room):
        room_layout = self.light_config_manager.get_room_layout()
        lights = room_layout.get(room, [])
        for light in lights:
            fixture_id = (light['start_address'] - 1) // 8
            self.dmx_state_manager.reset_fixture(fixture_id)
        logger.debug(f"Reset lights for room {room}")

    def _fade_to_theme(self, room, fixture_ids, duration):
        start_time = time.time()
        while time.time() - start_time < duration:
            progress = (time.time() - start_time) / duration
            for fixture_id in fixture_ids:
                current_values = self.dmx_state_manager.get_fixture_state(fixture_id)
                theme_values = self._generate_theme_values(room)
                interpolated_values = [int(current + (theme - current) * progress)
                                       for current, theme in zip(current_values, theme_values)]
                self.dmx_state_manager.update_fixture(fixture_id, interpolated_values)
            time.sleep(1 / 44)  # 44Hz update rate

    def _generate_theme_values(self, room):
        if not self.current_theme or self.current_theme not in self.themes:
            return [0] * 8  # Return all zeros if no theme is set

        theme_data = self.themes[self.current_theme]
        current_time = time.time()
        
        # Use theme parameters to generate values
        hue = (math.sin(current_time * theme_data['transition_speed']) + 1) / 2
        saturation = theme_data['color_variation']
        value = theme_data['overall_brightness']
        
        # Convert HSV to RGB
        r, g, b = self._hsv_to_rgb(hue, saturation, value)
        
        # Apply green-blue balance
        if 'green_blue_balance' in theme_data:
            g = g * theme_data['green_blue_balance']
            b = b * (1 - theme_data['green_blue_balance'])
        
        # Apply intensity fluctuation
        intensity = 1 + (math.sin(current_time * 2) * theme_data['intensity_fluctuation'])
        
        return [
            int(255 * intensity),  # total_dimming
            int(r * 255),  # r_dimming
            int(g * 255),  # g_dimming
            int(b * 255),  # b_dimming
            0,  # w_dimming (not used in this example)
            0,  # total_strobe (not used in this example)
            0,  # function_selection (not used in this example)
            0   # function_speed (not used in this example)
        ]

    def _hsv_to_rgb(self, h, s, v):
        if s == 0.0:
            return (v, v, v)
        i = int(h * 6.)
        f = (h * 6.) - i
        p, q, t = v * (1. - s), v * (1. - s * f), v * (1. - s * (1. - f))
        i %= 6
        if i == 0:
            return (v, t, p)
        if i == 1:
            return (q, v, p)
        if i == 2:
            return (p, v, t)
        if i == 3:
            return (p, q, v)
        if i == 4:
            return (t, p, v)
        if i == 5:
            return (v, p, q)

    def _get_effect_step_values(self, effect_data):
        def get_values(elapsed_time):
            for i, step in enumerate(effect_data['steps']):
                if elapsed_time <= step['time']:
                    if i == 0:
                        return [step['channels'].get(channel, 0) for channel in ['total_dimming', 'r_dimming', 'g_dimming', 'b_dimming', 'w_dimming', 'total_strobe', 'function_selection', 'function_speed']]
                    else:
                        prev_step = effect_data['steps'][i-1]
                        t = (elapsed_time - prev_step['time']) / (step['time'] - prev_step['time'])
                        return [
                            int(prev_step['channels'].get(channel, 0) + t * (step['channels'].get(channel, 0) - prev_step['channels'].get(channel, 0)))
                            for channel in ['total_dimming', 'r_dimming', 'g_dimming', 'b_dimming', 'w_dimming', 'total_strobe', 'function_selection', 'function_speed']
                        ]
            return [0] * 8  # Return all zeros if elapsed_time is beyond the last step
        return get_values

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
        all_effects = self.effects.copy()
        for effect_name in ["Lightning", "Police Lights", "GateInspection", "GateGreeters", "WrongAnswer"]:
            if effect_name not in all_effects or all_effects[effect_name] is None:
                effect = self.get_effect(effect_name)
                if effect:
                    all_effects[effect_name] = effect
                else:
                    logger.warning(f"Effect '{effect_name}' is not properly initialized.")
        return all_effects

    def get_effects_list(self):
        effects_list = {}
        for effect_name, effect_data in self.get_all_effects().items():
            description = effect_data.get('description', 'No description available')
            effects_list[effect_name] = description
        return effects_list

    def add_theme(self, theme_name, theme_data):
        theme_data['frequency'] = 40  # Fixed at 40 Hz
        theme_data.setdefault('strobe_speed', 0)  # Add strobe_speed with default 0 (off)
        self.themes[theme_name] = theme_data
        self.save_config()
        logger.info(f"Theme added: {theme_name}")
        logger.debug(f"Theme data: {theme_data}")

    def update_theme(self, theme_name, theme_data):
        if theme_name in self.themes:
            theme_data['frequency'] = 40  # Fixed at 40 Hz
            theme_data.setdefault('strobe_speed', 0)  # Add strobe_speed with default 0 (off)
            self.themes[theme_name] = theme_data
            self.save_config()
            logger.info(f"Theme updated: {theme_name}")
            logger.debug(f"Updated theme data: {theme_data}")
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
        self.default_theme = "Ocean"
        self.set_current_theme(self.default_theme)


    def set_current_theme(self, theme_name):
        if theme_name in self.themes:
            with self.theme_lock:
                old_theme = self.current_theme
                self.stop_current_theme()
                self.current_theme = theme_name
                self.stop_theme.clear()
                if old_theme is None:
                    self.theme_thread = threading.Thread(target=self._run_theme, args=(theme_name,))
                else:
                    self.theme_thread = threading.Thread(target=self._run_theme_with_transition, args=(old_theme, theme_name))
                self.theme_thread.start()
            logger.info(f"Theme changing from {old_theme} to: {theme_name}")
            return True
        else:
            logger.warning(f"Theme not found: {theme_name}")
            return False

    def get_effect(self, effect_name):
        return self.effects.get(effect_name)

    async def apply_effect_to_room(self, room, effect_data):
        room_layout = self.light_config_manager.get_room_layout()
        lights = room_layout.get(room, [])
        fixture_ids = [(light['start_address'] - 1) // 8 for light in lights]
        
        logger.info(f"Applying effect to room '{room}'")
        logger.debug(f"Effect data: {effect_data}")
        logger.debug(f"Fixture IDs for room: {fixture_ids}")
        
        log_messages = []
        
        # Mark this room as having an active effect
        self.room_effects[room] = True
        
        # Apply the effect to all fixtures in the room concurrently
        tasks = [self._apply_effect_to_fixture(fixture_id, effect_data) for fixture_id in fixture_ids]
        await asyncio.gather(*tasks)
        
        log_messages.append(f"Effect applied to all fixtures in room '{room}'")
        logger.info(f"Effect application completed in room '{room}'")
        
        # Remove the active effect flag for this room
        self.room_effects.pop(room, None)
        
        return True, log_messages

    def _apply_effect_to_fixture_sync(self, fixture_id, effect_data):
        try:
            self.interrupt_handler.interrupt_fixture_sync(
                fixture_id,
                effect_data['duration'],
                self._get_effect_step_values(effect_data)
            )
            logger.debug(f"Effect applied to fixture {fixture_id}")
        except Exception as e:
            error_msg = f"Error applying effect to fixture {fixture_id}: {str(e)}"
            logger.error(error_msg)

    def _run_theme_with_transition(self, old_theme, new_theme):
        transition_duration = 2.0  # 2 seconds transition
        start_time = time.time()
        old_theme_data = self.themes.get(old_theme, {})
        new_theme_data = self.themes.get(new_theme, {})
        
        if not old_theme_data:
            logger.warning(f"Old theme '{old_theme}' not found. Starting new theme without transition.")
            self._run_theme(new_theme)
            return
        
        while time.time() - start_time < transition_duration:
            progress = (time.time() - start_time) / transition_duration
            self._generate_and_apply_transition_step(old_theme_data, new_theme_data, progress)
            time.sleep(1 / self.frequency)
        self._run_theme(new_theme)

    def _generate_and_apply_transition_step(self, old_theme_data, new_theme_data, progress):
        room_layout = self.light_config_manager.get_room_layout()
        current_time = time.time()
        for room, lights in room_layout.items():
            if room not in self.room_effects:
                old_channels = self._generate_room_channels(old_theme_data, current_time)
                new_channels = self._generate_room_channels(new_theme_data, current_time)
                transition_channels = self._interpolate_channels(old_channels, new_channels, progress)
                self._apply_room_channels(room, lights, transition_channels)

    def _interpolate_channels(self, old_channels, new_channels, progress):
        return {
            channel: int(old_value + (new_channels[channel] - old_value) * progress)
            for channel, old_value in old_channels.items()
        }

    def stop_current_theme(self):
        with self.theme_lock:
            if self.current_theme:
                self.stop_theme.set()
                if self.theme_thread and self.theme_thread.is_alive():
                    self.theme_thread.join(timeout=5)  # Wait up to 5 seconds for the thread to finish
                self.current_theme = None
                self._reset_all_lights()
                logger.info("Current theme stopped and all lights reset")

    def _run_theme(self, theme_name):
        theme_data = self.themes[theme_name]
        logger.info(f"Starting theme: {theme_name}")
        start_time = time.time()
        while not self.stop_theme.is_set():
            current_time = time.time() - start_time
            self._generate_and_apply_theme_step(theme_data, current_time)
            time.sleep(1 / self.frequency)
        logger.info(f"Theme {theme_name} stopped")

    def stop_current_theme(self):
        if self.current_theme:
            self.stop_theme.set()
            if self.theme_thread and self.theme_thread.is_alive():
                self.theme_thread.join(timeout=5)  # Wait up to 5 seconds for the thread to finish
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
            if current_time >= theme_data['duration']:
                start_time = time.time()  # Reset start time for looping
            self._generate_and_apply_theme_steps(theme_data)
            elapsed_time = time.time() - (start_time + current_time)
            sleep_time = max(0, 1 / self.frequency - elapsed_time)
            if self.stop_theme.wait(timeout=sleep_time):
                break
        logger.info(f"Theme {theme_name} stopped")

    def _generate_and_apply_theme_step(self, theme_data, current_time):
        room_layout = self.light_config_manager.get_room_layout()
        for room, lights in room_layout.items():
            if room not in self.room_effects:
                room_channels = self._generate_room_channels(theme_data, current_time)
                self._apply_room_channels(room, lights, room_channels)

    def _generate_and_apply_theme_steps(self, theme_data):
        room_layout = self.light_config_manager.get_room_layout()
        current_time = time.time()
        for room, lights in room_layout.items():
            if room not in self.room_effects:
                room_channels = self._generate_room_channels(theme_data, current_time)
                for light in lights:
                    fixture_id = (light['start_address'] - 1) // 8
                    light_model = self.light_config_manager.get_light_config(light['model'])
                    fixture_values = [0] * 8
                    for channel, value in room_channels.items():
                        if channel in light_model['channels']:
                            channel_offset = light_model['channels'][channel]
                            fixture_values[channel_offset] = value
                    self.dmx_state_manager.update_fixture(fixture_id, fixture_values)

    def _generate_and_apply_theme_steps(self, theme_data):
        room_layout = self.light_config_manager.get_room_layout()
        speed = theme_data.get('speed', 1.0)
        step_duration = 1.0 / speed
        for _ in range(int(theme_data['duration'] * speed)):
            if self.stop_theme.is_set():
                break
            step = self._generate_theme_step(theme_data, room_layout)
            self._apply_theme_step(step)
            time.sleep(step_duration)

    def _generate_theme_step(self, theme_data, room_layout, current_time):
        step = {'rooms': {}}
        for room in room_layout.keys():
            if room not in self.room_effects:
                step['rooms'][room] = self._generate_room_channels(theme_data, current_time)
        return step

    def _apply_theme_step(self, step):
        room_layout = self.light_config_manager.get_room_layout()
        for room, lights in room_layout.items():
            if room not in self.room_effects:
                room_channels = step['rooms'].get(room, {})
                for light in lights:
                    fixture_id = (light['start_address'] - 1) // 8
                    light_model = self.light_config_manager.get_light_config(light['model'])
                    fixture_values = [0] * 8
                    for channel, value in room_channels.items():
                        if channel in light_model['channels']:
                            channel_offset = light_model['channels'][channel]
                            fixture_values[channel_offset] = value
                    self.dmx_state_manager.update_fixture(fixture_id, fixture_values)

    def _generate_and_apply_theme_steps(self, theme_data):
        room_layout = self.light_config_manager.get_room_layout()
        start_time = time.time()
        while time.time() - start_time < theme_data['duration']:
            if self.stop_theme.is_set():
                break
            current_time = time.time() - start_time
            step = self._generate_theme_step(theme_data, room_layout)
            self._apply_theme_step(step)
            time.sleep(1 / self.frequency)  # Use the instance attribute 'frequency'

    def _generate_theme_step(self, theme_data, room_layout):
        step = {'rooms': {}}
        current_time = time.time()
        for room in room_layout.keys():
            if room not in self.room_effects:
                step['rooms'][room] = self._generate_room_channels(theme_data, current_time)
        return step

    def _apply_theme_step(self, step):
        room_layout = self.light_config_manager.get_room_layout()
        changes = []
        for room, lights in room_layout.items():
            if room not in self.room_effects:
                room_channels = step['rooms'].get(room, {})
                for light in lights:
                    fixture_id = (light['start_address'] - 1) // 8
                    light_model = self.light_config_manager.get_light_config(light['model'])
                    fixture_values = [0] * 8
                    for channel, value in room_channels.items():
                        if channel in light_model['channels']:
                            channel_offset = light_model['channels'][channel]
                            fixture_values[channel_offset] = value
                    self.dmx_state_manager.update_fixture(fixture_id, fixture_values)
                    changes.append((room, fixture_id, fixture_values))
            else:
                changes.append((room, None, "Skipped due to active effect"))
        
        # Log only every 10th step or when there's a significant change
        if changes and (self._step_count % 10 == 0 or self._significant_change(changes)):
            logger.debug(f"Theme step {self._step_count} applied: {changes}")
        self._step_count += 1

    def _significant_change(self, changes):
        # Implement logic to determine if the change is significant
        # For example, check if any value has changed by more than 10%
        return any(abs(new - old) > 25 for _, _, new_values in changes 
                   for new, old in zip(new_values, self._last_values.get(_, [0]*8)))

    def _run_theme(self, theme_name):
        theme_data = self.themes[theme_name]
        logger.info(f"Starting theme: {theme_name}")
        while not self.stop_theme.is_set():
            start_time = time.time()
            self._generate_and_apply_theme_steps(theme_data)
            elapsed_time = time.time() - start_time
            sleep_time = max(0, 1 / self.frequency - elapsed_time)
            if self.stop_theme.wait(timeout=sleep_time):
                break
        logger.info(f"Theme {theme_name} stopped")

    def _generate_theme_step(self, theme_data, room_layout):
        step = {'rooms': {}}
        current_time = time.time()
        for room in room_layout.keys():
            if room not in self.room_effects:
                step['rooms'][room] = self._generate_room_channels(theme_data, current_time)
        return step

    def _generate_room_channels(self, theme_data, current_time):
        channels = {}
        overall_brightness = theme_data.get('overall_brightness', 0.5) * self.master_brightness
        color_variation = theme_data.get('color_variation', 0.5)
        intensity_fluctuation = theme_data.get('intensity_fluctuation', 0.5)
        transition_speed = theme_data.get('transition_speed', 0.5)

        # Use time-based oscillation for smooth transitions
        time_factor = current_time * transition_speed

        # Generate base colors using HSV color space for smoother transitions
        if 'blue_green_balance' in theme_data:  # Ocean theme
            hue = 0.5 + (math.sin(time_factor * 0.1) * 0.1)  # Oscillate around blue (0.5)
            blue_green_balance = theme_data.get('blue_green_balance', 0.8)
            saturation = 0.8 + (math.sin(time_factor * 0.2) * 0.2 * color_variation)
        elif 'green_blue_balance' in theme_data:  # Jungle theme
            hue = 0.3 + (math.sin(time_factor * 0.1) * 0.1)  # Oscillate around green (0.3)
            green_blue_balance = theme_data.get('green_blue_balance', 0.9)  # Increase green dominance
            saturation = 0.9 + (math.sin(time_factor * 0.2) * 0.1 * color_variation)  # Increase overall saturation
        else:
            hue = (math.sin(time_factor * 0.1) + 1) / 2
            saturation = color_variation

        value = overall_brightness * (1 + math.sin(time_factor * 2) * intensity_fluctuation)

        r, g, b = self._hsv_to_rgb(hue, saturation, value)

        # Apply theme-specific color balance
        if 'blue_green_balance' in theme_data:  # Ocean theme
            b = b * blue_green_balance
            g = g * (1 - blue_green_balance)
        elif 'green_blue_balance' in theme_data:  # Jungle theme
            g = g * green_blue_balance
            b = b * (1 - green_blue_balance)

        # Convert to 8-bit color values
        channels['total_dimming'] = int(value * 255)
        channels['r_dimming'] = int(r * 255)
        channels['g_dimming'] = int(g * 255)
        channels['b_dimming'] = int(b * 255)

        # Add white channel for RGBW fixtures
        channels['w_dimming'] = int(min(r, g, b) * 255 * 0.05)  # Significantly reduce white intensity for Jungle theme

        # Add strobe effect
        strobe_speed = theme_data.get('strobe_speed', 0)
        if strobe_speed > 0:
            channels['total_strobe'] = int(127 + (math.sin(time_factor * strobe_speed) + 1) * 64)
        else:
            channels['total_strobe'] = 0

        logger.debug(f"Generated room channels: {channels}")
        return channels

    def set_master_brightness(self, brightness):
        self.master_brightness = max(0.0, min(1.0, brightness))
        logger.info(f"Master brightness set to {self.master_brightness}")

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
                    fixture_id = (light['start_address'] - 1) // 8  # Assuming 8 channels per fixture
                    light_model = self.light_config_manager.get_light_config(light['model'])
                    fixture_values = [0] * 8  # Initialize all channels to 0
                    for channel, value in room_channels.items():
                        if channel in light_model['channels']:
                            channel_offset = light_model['channels'][channel]
                            fixture_values[channel_offset] = value
                    self.dmx_state_manager.update_fixture(fixture_id, fixture_values)
                    logger.debug(f"Applied theme step to room {room}, fixture {fixture_id}: {fixture_values}")
            else:
                logger.debug(f"Skipped theme application for room {room} due to active effect")

    def _reset_room_lights(self, room):
        room_layout = self.light_config_manager.get_room_layout()
        lights = room_layout.get(room, [])
        for light in lights:
            fixture_id = (light['start_address'] - 1) // 8
            self.dmx_state_manager.reset_fixture(fixture_id)
        logger.debug(f"Reset lights for room {room}")

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
                fixture_id = (start_address - 1) // 8  # Assuming 8 channels per fixture
                self.dmx_state_manager.reset_fixture(fixture_id)
        logger.info("All lights reset")

    def _significant_change(self, changes):
        # Implement logic to determine if the change is significant
        # For example, check if any value has changed by more than 10%
        return any(abs(new - old) > 25 for _, _, new_values in changes 
                   for new, old in zip(new_values, self._last_values.get(_, [0]*8)))


    def create_police_lights_effect(self):
        police_lights_effect = {
            "duration": 15.0,
            "steps": []
        }
        for i in range(15):  # 15 cycles to fill 15 seconds
            t = i * 1.0
            police_lights_effect["steps"].extend([
                {"time": t, "channels": {"total_dimming": 255, "r_dimming": 255, "b_dimming": 0, "g_dimming": 0, "w_dimming": 0, "total_strobe": 0, "function_selection": 0, "function_speed": 0}},
                {"time": t + 0.5, "channels": {"total_dimming": 255, "r_dimming": 0, "b_dimming": 255, "g_dimming": 0, "w_dimming": 0, "total_strobe": 0, "function_selection": 0, "function_speed": 0}}
            ])
        police_lights_effect["steps"].append({"time": 15.0, "channels": {"total_dimming": 0, "r_dimming": 0, "b_dimming": 0, "g_dimming": 0, "w_dimming": 0, "total_strobe": 0, "function_selection": 0, "function_speed": 0}})
        self.add_effect("Police Lights", police_lights_effect)
        logger.debug(f"Created Police Lights effect: {police_lights_effect}")
        logger.info(f"Police Lights effect created with {len(police_lights_effect['steps'])} steps over {police_lights_effect['duration']} seconds")

    def create_lightning_effect(self):
        lightning_effect = {
            "duration": 2.0,
            "description": "Simulates a lightning strike with bright flashes",
            "steps": [
                {"time": 0.0, "channels": {"total_dimming": 255, "r_dimming": 255, "g_dimming": 255, "b_dimming": 255, "w_dimming": 255, "total_strobe": 0, "function_selection": 0, "function_speed": 0}},
                {"time": 0.1, "channels": {"total_dimming": 0, "r_dimming": 0, "g_dimming": 0, "b_dimming": 0, "w_dimming": 0, "total_strobe": 0, "function_selection": 0, "function_speed": 0}},
                {"time": 0.3, "channels": {"total_dimming": 255, "r_dimming": 255, "g_dimming": 255, "b_dimming": 255, "w_dimming": 255, "total_strobe": 0, "function_selection": 0, "function_speed": 0}},
                {"time": 0.4, "channels": {"total_dimming": 0, "r_dimming": 0, "g_dimming": 0, "b_dimming": 0, "w_dimming": 0, "total_strobe": 0, "function_selection": 0, "function_speed": 0}},
                {"time": 0.7, "channels": {"total_dimming": 255, "r_dimming": 255, "g_dimming": 255, "b_dimming": 255, "w_dimming": 255, "total_strobe": 0, "function_selection": 0, "function_speed": 0}},
                {"time": 2.0, "channels": {"total_dimming": 0, "r_dimming": 0, "g_dimming": 0, "b_dimming": 0, "w_dimming": 0, "total_strobe": 0, "function_selection": 0, "function_speed": 0}}
            ]
        }
        self.add_effect("Lightning", lightning_effect)
        logger.debug(f"Created Lightning effect: {lightning_effect}")
        logger.info(f"Lightning effect created with {len(lightning_effect['steps'])} steps over {lightning_effect['duration']} seconds")

    def create_police_lights_effect(self):
        police_lights_effect = {
            "duration": 15.0,
            "description": "Alternating red and blue flashes simulating police lights",
            "steps": []
        }
        for i in range(15):  # 15 cycles to fill 15 seconds
            t = i * 1.0
            police_lights_effect["steps"].extend([
                {"time": t, "channels": {"total_dimming": 255, "r_dimming": 255, "b_dimming": 0, "g_dimming": 0, "w_dimming": 0, "total_strobe": 0, "function_selection": 0, "function_speed": 0}},
                {"time": t + 0.5, "channels": {"total_dimming": 255, "r_dimming": 0, "b_dimming": 255, "g_dimming": 0, "w_dimming": 0, "total_strobe": 0, "function_selection": 0, "function_speed": 0}}
            ])
        police_lights_effect["steps"].append({"time": 15.0, "channels": {"total_dimming": 0, "r_dimming": 0, "b_dimming": 0, "g_dimming": 0, "w_dimming": 0, "total_strobe": 0, "function_selection": 0, "function_speed": 0}})
        self.add_effect("PoliceLights", police_lights_effect)
        logger.debug(f"Created Police Lights effect: {police_lights_effect}")
        logger.info(f"Police Lights effect created with {len(police_lights_effect['steps'])} steps over {police_lights_effect['duration']} seconds")

    def create_gate_inspection_effect(self):
        gate_inspection_effect = {
            "duration": 6.0,
            "description": "Bright white light for gate inspection, lasting 5 seconds",
            "steps": [
                {"time": 0.0, "channels": {"total_dimming": 255, "r_dimming": 255, "g_dimming": 255, "b_dimming": 255, "w_dimming": 255, "total_strobe": 0, "function_selection": 0, "function_speed": 0}},
                {"time": 5.0, "channels": {"total_dimming": 255, "r_dimming": 255, "g_dimming": 255, "b_dimming": 255, "w_dimming": 255, "total_strobe": 0, "function_selection": 0, "function_speed": 0}},
                {"time": 6.0, "channels": {"total_dimming": 0, "r_dimming": 0, "g_dimming": 0, "b_dimming": 0, "w_dimming": 0, "total_strobe": 0, "function_selection": 0, "function_speed": 0}}
            ]
        }
        self.add_effect("GateInspection", gate_inspection_effect)
        logger.debug(f"Created Gate Inspection effect: {gate_inspection_effect}")
        logger.info(f"Gate Inspection effect created with {len(gate_inspection_effect['steps'])} steps over {gate_inspection_effect['duration']} seconds")

    def create_gate_greeters_effect(self):
        gate_greeters_effect = {
            "duration": 15.0,
            "description": "Welcoming effect with gentle color transitions and pulsing",
            "steps": []
        }
        
        colors = [
            (255, 223, 0),   # Warm Yellow
            (255, 105, 180), # Hot Pink
            (0, 191, 255),   # Deep Sky Blue
            (50, 205, 50),   # Lime Green
            (255, 165, 0)    # Orange
        ]
        
        step_duration = 0.5
        for i in range(30):
            color = colors[i % len(colors)]
            brightness = 128 + int(64 * math.sin(i * 0.2))  # Gentle pulsing effect
            gate_greeters_effect["steps"].append({
                "time": i * step_duration,
                "channels": {
                    "total_dimming": brightness,
                    "r_dimming": color[0],
                    "g_dimming": color[1],
                    "b_dimming": color[2],
                    "w_dimming": 0,
                    "total_strobe": 0,
                    "function_selection": 0,
                    "function_speed": 128
                }
            })
        
        gate_greeters_effect["steps"].append({
            "time": 15.0,
            "channels": {
                "total_dimming": 0,
                "r_dimming": 0,
                "g_dimming": 0,
                "b_dimming": 0,
                "w_dimming": 0,
                "total_strobe": 0,
                "function_selection": 0,
                "function_speed": 0
            }
        })
        
        self.add_effect("GateGreeters", gate_greeters_effect)
        logger.debug(f"Created Gate Greeters effect: {gate_greeters_effect}")
        logger.info(f"Gate Greeters effect created with {len(gate_greeters_effect['steps'])} steps over {gate_greeters_effect['duration']} seconds")

    def create_wrong_answer_effect(self):
        wrong_answer_effect = {
            "duration": 3.0,
            "description": "Three quick red flashes to indicate a wrong answer",
            "steps": []
        }
        
        # Red flash
        wrong_answer_effect["steps"].extend([
            {
                "time": 0.0,
                "channels": {
                    "total_dimming": 255,
                    "r_dimming": 255,
                    "g_dimming": 0,
                    "b_dimming": 0,
                    "w_dimming": 0,
                    "total_strobe": 0,
                    "function_selection": 0,
                    "function_speed": 0
                }
            },
            {
                "time": 0.5,
                "channels": {
                    "total_dimming": 0,
                    "r_dimming": 0,
                    "g_dimming": 0,
                    "b_dimming": 0,
                    "w_dimming": 0,
                    "total_strobe": 0,
                    "function_selection": 0,
                    "function_speed": 0
                }
            }
        ])
        
        # Repeat the flash twice more
        for i in range(2):
            wrong_answer_effect["steps"].extend([
                {
                    "time": 1.0 + i * 1.0,
                    "channels": {
                        "total_dimming": 255,
                        "r_dimming": 255,
                        "g_dimming": 0,
                        "b_dimming": 0,
                        "w_dimming": 0,
                        "total_strobe": 0,
                        "function_selection": 0,
                        "function_speed": 0
                    }
                },
                {
                    "time": 1.5 + i * 1.0,
                    "channels": {
                        "total_dimming": 0,
                        "r_dimming": 0,
                        "g_dimming": 0,
                        "b_dimming": 0,
                        "w_dimming": 0,
                        "total_strobe": 0,
                        "function_selection": 0,
                        "function_speed": 0
                    }
                }
            ])
        
        self.add_effect("WrongAnswer", wrong_answer_effect)
        logger.debug(f"Created Wrong Answer effect: {wrong_answer_effect}")
        logger.info(f"Wrong Answer effect created with {len(wrong_answer_effect['steps'])} steps over {wrong_answer_effect['duration']} seconds")

    def create_entrance_effect(self):
        entrance_effect = {
            "duration": 10.0,
            "description": "Green light ramp up and hold for Entrance",
            "steps": []
        }
        
        # Ramp up green light over 5 seconds
        for i in range(51):  # 0 to 255 in 50 steps
            entrance_effect["steps"].append({
                "time": i * 0.1,
                "channels": {
                    "total_dimming": 255,
                    "r_dimming": 0,
                    "g_dimming": i * 5,
                    "b_dimming": 0,
                    "w_dimming": 0,
                    "total_strobe": 0,
                    "function_selection": 0,
                    "function_speed": 0
                }
            })
        
        # Hold at max brightness for 5 seconds
        entrance_effect["steps"].append({
            "time": 10.0,
            "channels": {
                "total_dimming": 255,
                "r_dimming": 0,
                "g_dimming": 255,
                "b_dimming": 0,
                "w_dimming": 0,
                "total_strobe": 0,
                "function_selection": 0,
                "function_speed": 0
            }
        })
        
        self.add_effect("Entrance", entrance_effect)
        logger.debug(f"Created Entrance effect: {entrance_effect}")
        logger.info(f"Entrance effect created with {len(entrance_effect['steps'])} steps over {entrance_effect['duration']} seconds")

    def create_guy_line_climb_effect(self):
        guy_line_climb_effect = {
            "duration": 15.0,
            "description": "Simulates climbing with a vaporwave color scheme",
            "steps": []
        }
        
        # Generate 150 steps for smooth transitions (10 steps per second)
        for i in range(150):
            t = i * 0.1
            # Oscillate between vaporwave colors (pink, cyan, purple)
            red = int(127 + 127 * math.sin(t * 1.5))
            green = int(127 + 127 * math.sin(t * 1.5 + 2*math.pi/3))
            blue = int(127 + 127 * math.sin(t * 1.5 + 4*math.pi/3))
            
            guy_line_climb_effect["steps"].append({
                "time": t,
                "channels": {
                    "total_dimming": 255,
                    "r_dimming": red,
                    "g_dimming": green,
                    "b_dimming": blue,
                    "w_dimming": 0,
                    "total_strobe": 0,
                    "function_selection": 0,
                    "function_speed": 0
                }
            })
        
        # Add final step to turn off lights
        guy_line_climb_effect["steps"].append({
            "time": 15.0,
            "channels": {
                "total_dimming": 0,
                "r_dimming": 0,
                "g_dimming": 0,
                "b_dimming": 0,
                "w_dimming": 0,
                "total_strobe": 0,
                "function_selection": 0,
                "function_speed": 0
            }
        })
        
        self.add_effect("GuyLineClimb", guy_line_climb_effect)
        logger.debug(f"Created Guy Line Climb effect: {guy_line_climb_effect}")
        logger.info(f"Guy Line Climb effect created with {len(guy_line_climb_effect['steps'])} steps over {guy_line_climb_effect['duration']} seconds")

    def create_spark_pony_effect(self):
        spark_pony_effect = {
            "duration": 20.0,
            "description": "My Little Pony inspired colors with dynamic sparkles",
            "steps": []
        }
        
        # My Little Pony inspired colors
        pony_colors = [
            (255, 128, 180),  # Pink
            (130, 200, 255),  # Light Blue
            (255, 200, 100),  # Light Orange
            (200, 255, 150),  # Light Green
            (230, 150, 255),  # Lavender
            (255, 255, 150)   # Light Yellow
        ]
        
        # Generate 200 steps for smooth transitions (10 steps per second)
        for i in range(200):
            t = i * 0.1
            
            # Blend between two colors
            color_index = int(t / 4) % len(pony_colors)
            next_color_index = (color_index + 1) % len(pony_colors)
            blend_factor = (t % 4) / 4
            
            color1 = pony_colors[color_index]
            color2 = pony_colors[next_color_index]
            
            red = int(color1[0] * (1 - blend_factor) + color2[0] * blend_factor)
            green = int(color1[1] * (1 - blend_factor) + color2[1] * blend_factor)
            blue = int(color1[2] * (1 - blend_factor) + color2[2] * blend_factor)
            
            # Add dynamic sparkles
            white = 0
            if random.random() < 0.15:  # Increased to 15% chance of sparkle
                sparkle_intensity = int((math.sin(t * 30) + 1) * 127.5)  # Faster oscillating sparkle intensity
                white = random.randint(sparkle_intensity, 255)
                
                # Add occasional extra bright sparkles
                if random.random() < 0.3:  # 30% chance of extra bright sparkle
                    white = 255
            
            spark_pony_effect["steps"].append({
                "time": t,
                "channels": {
                    "total_dimming": 255,
                    "r_dimming": red,
                    "g_dimming": green,
                    "b_dimming": blue,
                    "w_dimming": white,
                    "total_strobe": 0,
                    "function_selection": 0,
                    "function_speed": 0
                }
            })
        
        # Add final step to turn off lights
        spark_pony_effect["steps"].append({
            "time": 20.0,
            "channels": {
                "total_dimming": 0,
                "r_dimming": 0,
                "g_dimming": 0,
                "b_dimming": 0,
                "w_dimming": 0,
                "total_strobe": 0,
                "function_selection": 0,
                "function_speed": 0
            }
        })
        
        self.add_effect("SparkPony", spark_pony_effect)
        logger.debug(f"Created Spark Pony effect: {spark_pony_effect}")
        logger.info(f"Spark Pony effect created with {len(spark_pony_effect['steps'])} steps over {spark_pony_effect['duration']} seconds")

    def create_porto_standby_effect(self):
        porto_standby_effect = {
            "duration": 20.0,
            "description": "Dim blue light ramping up, followed by red heartbeat",
            "steps": []
        }
        
        # Ramp up blue light over 7 seconds
        for i in range(71):  # 0 to 70 steps (0 to 7 seconds)
            t = i * 0.1
            blue_value = int((i / 70) * 127)  # Ramp up to 50% of max brightness (127)
            porto_standby_effect["steps"].append({
                "time": t,
                "channels": {
                    "total_dimming": 255,
                    "r_dimming": 0,
                    "g_dimming": 0,
                    "b_dimming": blue_value,
                    "w_dimming": 0,
                    "total_strobe": 0,
                    "function_selection": 0,
                    "function_speed": 0
                }
            })
        
        # Heartbeat effect from 7 to 20 seconds
        heartbeat_duration = 1.0  # 1 second per heartbeat
        for i in range(71, 200):  # 7.1 to 20 seconds
            t = i * 0.1
            phase = ((t - 7) % heartbeat_duration) / heartbeat_duration
            if phase < 0.1:  # Quick rise
                red_value = int(191 * (phase / 0.1))
            elif phase < 0.4:  # Quick fall
                red_value = int(191 * (1 - (phase - 0.1) / 0.3))
            else:  # Rest
                red_value = 0
            
            porto_standby_effect["steps"].append({
                "time": t,
                "channels": {
                    "total_dimming": 255,
                    "r_dimming": red_value,
                    "g_dimming": 0,
                    "b_dimming": 127,
                    "w_dimming": 0,
                    "total_strobe": 0,
                    "function_selection": 0,
                    "function_speed": 0
                }
            })
        
        # Final step to turn off lights
        porto_standby_effect["steps"].append({
            "time": 20.0,
            "channels": {
                "total_dimming": 0,
                "r_dimming": 0,
                "g_dimming": 0,
                "b_dimming": 0,
                "w_dimming": 0,
                "total_strobe": 0,
                "function_selection": 0,
                "function_speed": 0
            }
        })
        
        self.add_effect("PortoStandBy", porto_standby_effect)
        logger.debug(f"Created Porto StandBy effect: {porto_standby_effect}")
        logger.info(f"Porto StandBy effect created with {len(porto_standby_effect['steps'])} steps over {porto_standby_effect['duration']} seconds")

    def create_porto_hit_effect(self):
        porto_hit_effect = {
            "duration": 15.0,
            "description": "Green light blinking 5 times, then staying lit for 5 seconds, followed by red",
            "steps": []
        }
        
        # Green light blinking 5 times
        for i in range(5):
            t = i * 0.5
            # Green on
            porto_hit_effect["steps"].append({
                "time": t,
                "channels": {
                    "total_dimming": 255,
                    "r_dimming": 0,
                    "g_dimming": 255,
                    "b_dimming": 0,
                    "w_dimming": 0,
                    "total_strobe": 0,
                    "function_selection": 0,
                    "function_speed": 0
                }
            })
            # Green off
            porto_hit_effect["steps"].append({
                "time": t + 0.25,
                "channels": {
                    "total_dimming": 0,
                    "r_dimming": 0,
                    "g_dimming": 0,
                    "b_dimming": 0,
                    "w_dimming": 0,
                    "total_strobe": 0,
                    "function_selection": 0,
                    "function_speed": 0
                }
            })
        
        # Green light staying on for 5 seconds
        porto_hit_effect["steps"].append({
            "time": 2.5,
            "channels": {
                "total_dimming": 255,
                "r_dimming": 0,
                "g_dimming": 255,
                "b_dimming": 0,
                "w_dimming": 0,
                "total_strobe": 0,
                "function_selection": 0,
                "function_speed": 0
            }
        })
        
        # Switch to red at 7.5 seconds
        porto_hit_effect["steps"].append({
            "time": 7.5,
            "channels": {
                "total_dimming": 255,
                "r_dimming": 255,
                "g_dimming": 0,
                "b_dimming": 0,
                "w_dimming": 0,
                "total_strobe": 0,
                "function_selection": 0,
                "function_speed": 0
            }
        })
        
        # Final step to keep red on until the end
        porto_hit_effect["steps"].append({
            "time": 15.0,
            "channels": {
                "total_dimming": 255,
                "r_dimming": 255,
                "g_dimming": 0,
                "b_dimming": 0,
                "w_dimming": 0,
                "total_strobe": 0,
                "function_selection": 0,
                "function_speed": 0
            }
        })
        
        self.add_effect("PortoHit", porto_hit_effect)
        logger.debug(f"Created Porto Hit effect: {porto_hit_effect}")
        logger.info(f"Porto Hit effect created with {len(porto_hit_effect['steps'])} steps over {porto_hit_effect['duration']} seconds")

    def create_porto_hit_effect(self):
        porto_hit_effect = {
            "duration": 15.0,
            "description": "Green light blinking 5 times, then staying lit for 5 seconds, followed by red",
            "steps": []
        }
        
        # Green light blinking 5 times
        for i in range(5):
            t = i * 0.5
            # Green on
            porto_hit_effect["steps"].append({
                "time": t,
                "channels": {
                    "total_dimming": 255,
                    "r_dimming": 0,
                    "g_dimming": 255,
                    "b_dimming": 0,
                    "w_dimming": 0,
                    "total_strobe": 0,
                    "function_selection": 0,
                    "function_speed": 0
                }
            })
            # Green off
            porto_hit_effect["steps"].append({
                "time": t + 0.25,
                "channels": {
                    "total_dimming": 0,
                    "r_dimming": 0,
                    "g_dimming": 0,
                    "b_dimming": 0,
                    "w_dimming": 0,
                    "total_strobe": 0,
                    "function_selection": 0,
                    "function_speed": 0
                }
            })
        
        # Green light staying on for 5 seconds
        porto_hit_effect["steps"].append({
            "time": 2.5,
            "channels": {
                "total_dimming": 255,
                "r_dimming": 0,
                "g_dimming": 255,
                "b_dimming": 0,
                "w_dimming": 0,
                "total_strobe": 0,
                "function_selection": 0,
                "function_speed": 0
            }
        })
        
        # Switch to red at 7.5 seconds
        porto_hit_effect["steps"].append({
            "time": 7.5,
            "channels": {
                "total_dimming": 255,
                "r_dimming": 255,
                "g_dimming": 0,
                "b_dimming": 0,
                "w_dimming": 0,
                "total_strobe": 0,
                "function_selection": 0,
                "function_speed": 0
            }
        })
        
        # Final step to keep red on until the end
        porto_hit_effect["steps"].append({
            "time": 15.0,
            "channels": {
                "total_dimming": 255,
                "r_dimming": 255,
                "g_dimming": 0,
                "b_dimming": 0,
                "w_dimming": 0,
                "total_strobe": 0,
                "function_selection": 0,
                "function_speed": 0
            }
        })
        
        self.add_effect("PortoHit", porto_hit_effect)
        logger.debug(f"Created Porto Hit effect: {porto_hit_effect}")
        logger.info(f"Porto Hit effect created with {len(porto_hit_effect['steps'])} steps over {porto_hit_effect['duration']} seconds")

    def create_cuddle_puddle_effect(self):
        cuddle_puddle_effect = {
            "duration": 60.0,
            "description": "Intense Pink Heart Burning Man camp Cuddle Puddle simulation with fast transitions between Pink and Red",
            "steps": []
        }
        
        # Generate 1200 steps for faster transitions (20 steps per second)
        for i in range(1200):
            t = i * 0.05
            # Use sine waves for smooth transitions between Pink and Red
            red = int(200 + 55 * math.sin(t * 0.5))  # Red oscillates between 145 and 255
            pink = int(255 + 0 * math.sin(t * 0.7))  # Pink stays at 255 for maximum intensity
            
            cuddle_puddle_effect["steps"].append({
                "time": t,
                "channels": {
                    "total_dimming": 255,
                    "r_dimming": red,
                    "g_dimming": int(pink * 0.15),  # Slight green to make pink more vibrant
                    "b_dimming": int(pink * 0.25),  # Slight blue to make pink more vibrant
                    "w_dimming": 0,  # No white component
                    "total_strobe": 0,
                    "function_selection": 0,
                    "function_speed": 0
                }
            })
        
        # Final step to fade out
        cuddle_puddle_effect["steps"].append({
            "time": 60.0,
            "channels": {
                "total_dimming": 0,
                "r_dimming": 0,
                "g_dimming": 0,
                "b_dimming": 0,
                "w_dimming": 0,
                "total_strobe": 0,
                "function_selection": 0,
                "function_speed": 0
            }
        })
        
        self.add_effect("CuddlePuddle", cuddle_puddle_effect)
        logger.debug(f"Created Cuddle Puddle effect: {cuddle_puddle_effect}")
        logger.info(f"Cuddle Puddle effect created with {len(cuddle_puddle_effect['steps'])} steps over {cuddle_puddle_effect['duration']} seconds")

    def create_photobomb_bg_effect(self):
        photobomb_bg_effect = {
            "duration": 20.0,
            "description": "Rainbow dance party with steady strobe like at the Disco",
            "steps": []
        }
        
        # Generate 400 steps for smooth transitions (20 steps per second)
        for i in range(400):
            t = i * 0.05
            # Use sine waves for smooth color transitions
            hue = (math.sin(t * 0.2) + 1) / 2  # Oscillate hue between 0 and 1
            r, g, b = self._hsv_to_rgb(hue, 1, 1)
            
            photobomb_bg_effect["steps"].append({
                "time": t,
                "channels": {
                    "total_dimming": 255,
                    "r_dimming": int(r * 255),
                    "g_dimming": int(g * 255),
                    "b_dimming": int(b * 255),
                    "w_dimming": 0,
                    "total_strobe": 255,  # Steady strobe
                    "function_selection": 0,
                    "function_speed": 255  # Maximum strobe speed
                }
            })
        
        # Final step to fade out
        photobomb_bg_effect["steps"].append({
            "time": 60.0,
            "channels": {
                "total_dimming": 0,
                "r_dimming": 0,
                "g_dimming": 0,
                "b_dimming": 0,
                "w_dimming": 0,
                "total_strobe": 0,
                "function_selection": 0,
                "function_speed": 0
            }
        })
        
        self.add_effect("PhotoBomb-BG", photobomb_bg_effect)
        logger.debug(f"Created PhotoBomb-BG effect: {photobomb_bg_effect}")
        logger.info(f"PhotoBomb-BG effect created with {len(photobomb_bg_effect['steps'])} steps over {photobomb_bg_effect['duration']} seconds")

    def create_photobomb_spot_effect(self):
        photobomb_spot_effect = {
            "duration": 5.0,
            "description": "White light at full brightness for 5 seconds",
            "steps": [
                {
                    "time": 0.0,
                    "channels": {
                        "total_dimming": 255,
                        "r_dimming": 255,
                        "g_dimming": 255,
                        "b_dimming": 255,
                        "w_dimming": 255,
                        "total_strobe": 0,
                        "function_selection": 0,
                        "function_speed": 0
                    }
                },
                {
                    "time": 5.0,
                    "channels": {
                        "total_dimming": 255,
                        "r_dimming": 255,
                        "g_dimming": 255,
                        "b_dimming": 255,
                        "w_dimming": 255,
                        "total_strobe": 0,
                        "function_selection": 0,
                        "function_speed": 0
                    }
                }
            ]
        }
        
        self.add_effect("PhotoBomb-Spot", photobomb_spot_effect)
        logger.debug(f"Created PhotoBomb-Spot effect: {photobomb_spot_effect}")
        logger.info(f"PhotoBomb-Spot effect created with {len(photobomb_spot_effect['steps'])} steps over {photobomb_spot_effect['duration']} seconds")

    def apply_effect_to_all_rooms(self, effect_name):
        effect_data = self.get_effect(effect_name)
        if not effect_data:
            logger.error(f"{effect_name} effect not found")
            return False, f"{effect_name} effect not found"

        room_layout = self.light_config_manager.get_room_layout()
        
        async def apply_effect():
            tasks = []
            for room in room_layout.keys():
                tasks.append(self.apply_effect_to_room(room, effect_data))
            await asyncio.gather(*tasks)

        asyncio.run(apply_effect())
        
        logger.info(f"{effect_name} effect triggered in all rooms")
        return True, f"{effect_name} effect triggered in all rooms"
    async def _fade_to_black(self, room, fixture_ids, duration):
        start_time = time.time()
        while time.time() - start_time < duration:
            progress = (time.time() - start_time) / duration
            tasks = []
            for fixture_id in fixture_ids:
                current_values = self.dmx_state_manager.get_fixture_state(fixture_id)
                faded_values = [int(value * (1 - progress)) for value in current_values]
                tasks.append(self._update_fixture(fixture_id, faded_values))
            await asyncio.gather(*tasks)
            await asyncio.sleep(1 / self.frequency)

    async def _fade_to_theme(self, room, fixture_ids, duration):
        start_time = time.time()
        while time.time() - start_time < duration:
            progress = (time.time() - start_time) / duration
            tasks = []
            for fixture_id in fixture_ids:
                current_values = self.dmx_state_manager.get_fixture_state(fixture_id)
                theme_values = self._generate_theme_values(room)
                interpolated_values = [int(current + (theme - current) * progress)
                                       for current, theme in zip(current_values, theme_values)]
                tasks.append(self._update_fixture(fixture_id, interpolated_values))
            await asyncio.gather(*tasks)
            await asyncio.sleep(1 / self.frequency)

    async def _apply_effect_to_fixture(self, fixture_id, effect_data):
        try:
            await self.interrupt_handler.interrupt_fixture(
                fixture_id,
                effect_data['duration'],
                self._get_effect_step_values(effect_data)
            )
            logger.debug(f"Effect applied to fixture {fixture_id}")
        except Exception as e:
            error_msg = f"Error applying effect to fixture {fixture_id}: {str(e)}"
            logger.error(error_msg)

    async def _update_fixture(self, fixture_id, values):
        self.dmx_state_manager.update_fixture(fixture_id, values)
        await asyncio.sleep(0)  # Yield control to allow other coroutines to run
    def _fade_to_black(self, room, fixture_ids, duration):
        start_time = time.time()
        while time.time() - start_time < duration:
            progress = (time.time() - start_time) / duration
            for fixture_id in fixture_ids:
                current_values = self.dmx_state_manager.get_fixture_state(fixture_id)
                faded_values = [int(value * (1 - progress)) for value in current_values]
                self.dmx_state_manager.update_fixture(fixture_id, faded_values)
            time.sleep(1 / 44)  # 44Hz update rate

    async def _fade_to_theme(self, room, fixture_ids, duration):
        start_time = time.time()
        while time.time() - start_time < duration:
            progress = (time.time() - start_time) / duration
            tasks = []
            for fixture_id in fixture_ids:
                current_values = self.dmx_state_manager.get_fixture_state(fixture_id)
                theme_values = self._generate_theme_values(room)
                interpolated_values = [int(current + (theme - current) * progress)
                                       for current, theme in zip(current_values, theme_values)]
                tasks.append(self._update_fixture(fixture_id, interpolated_values))
            await asyncio.gather(*tasks)
            await asyncio.sleep(1 / self.frequency)

    def _generate_theme_values(self, room):
        # This method should generate the current theme values for the room
        # You'll need to implement this based on your theme logic
        # For now, we'll return a placeholder
        return [128, 64, 32, 0, 255, 0, 0, 0]
    def _apply_room_channels(self, room, lights, room_channels):
        for light in lights:
            start_address = light['start_address']
            light_model = self.light_config_manager.get_light_config(light['model'])
            fixture_id = (start_address - 1) // 8
            fixture_values = [0] * 8
            logger.debug(f"Applying theme to room {room}, light model {light['model']}")
            for channel, value in room_channels.items():
                if channel in light_model['channels']:
                    channel_offset = light_model['channels'][channel]
                    fixture_values[channel_offset] = value
                    logger.debug(f"  Setting channel {channel} (offset {channel_offset}) to value {value}")
                else:
                    logger.debug(f"  Channel {channel} not found in light model, skipping")
            self.dmx_state_manager.update_fixture(fixture_id, fixture_values)
            logger.debug(f"  Final fixture values: {fixture_values}")
