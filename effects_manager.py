import json
import logging
import asyncio
from effects import *
from theme_manager import ThemeManager
from effect_utils import get_effect_step_values

logger = logging.getLogger(__name__)

class EffectsManager:
    def __init__(self, config_file='effects_config.json', light_config_manager=None, dmx_state_manager=None, interrupt_handler=None):
        self.config_file = config_file
        self.effects = self.load_config()
        self.room_effects = {}
        self.light_config_manager = light_config_manager
        self.dmx_state_manager = dmx_state_manager
        self.interrupt_handler = interrupt_handler
        self.theme_manager = ThemeManager(dmx_state_manager, light_config_manager)
        
        if self.interrupt_handler is None:
            logger.warning("InterruptHandler not provided. Some features may not work correctly.")
        else:
            logger.info(f"InterruptHandler successfully initialized: {self.interrupt_handler}")
        
        # Initialize all effects
        self.initialize_effects()

    def update_frequency(self, new_frequency):
        self.theme_manager.frequency = new_frequency
        logger.info(f"Update frequency set to {new_frequency} Hz")

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
        except IOError:
            logger.error(f"Error writing to {self.config_file}")

    def get_effect(self, effect_name):
        return self.effects.get(effect_name)

    def add_effect(self, effect_name, effect_data):
        self.effects[effect_name] = effect_data
        self.save_config()

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

    async def apply_effect_to_room(self, room, effect_data):
        room_layout = self.light_config_manager.get_room_layout()
        lights = room_layout.get(room, [])
        fixture_ids = [(light['start_address'] - 1) // 8 for light in lights]
        
        logger.info(f"Applying effect to room '{room}'")
        logger.debug(f"Effect data: {effect_data}")
        logger.debug(f"Fixture IDs for room: {fixture_ids}")
        
        self.room_effects[room] = True
        
        tasks = [self._apply_effect_to_fixture(fixture_id, effect_data) for fixture_id in fixture_ids]
        await asyncio.gather(*tasks)
        
        logger.info(f"Effect application completed in room '{room}'")
        
        self.room_effects.pop(room, None)
        
        return True

    async def _apply_effect_to_fixture(self, fixture_id, effect_data):
        try:
            await self.interrupt_handler.interrupt_fixture(
                fixture_id,
                effect_data['duration'],
                get_effect_step_values(effect_data)
            )
            logger.debug(f"Effect applied to fixture {fixture_id}")
        except Exception as e:
            logger.error(f"Error applying effect to fixture {fixture_id}: {str(e)}")

    def get_all_effects(self):
        return self.effects

    def get_effects_list(self):
        return {name: data.get('description', 'No description available') 
                for name, data in self.effects.items()}

    def set_master_brightness(self, brightness):
        self.theme_manager.set_master_brightness(brightness)

    def set_current_theme(self, theme_name):
        return self.theme_manager.set_current_theme(theme_name)

    def stop_current_theme(self):
        self.theme_manager.stop_current_theme()

    def get_all_themes(self):
        return self.theme_manager.get_all_themes()

    def get_theme(self, theme_name):
        return self.theme_manager.get_theme(theme_name)

    def initialize_effects(self):
        effects = [
            ("Lightning", create_lightning_effect()),
            ("PoliceLights", create_police_lights_effect()),
            ("GateInspection", create_gate_inspection_effect()),
            ("GateGreeters", create_gate_greeters_effect()),
            ("WrongAnswer", create_wrong_answer_effect()),
            ("CorrectAnswer", create_correct_answer_effect()),
            ("Entrance", create_entrance_effect()),
            ("GuyLineClimb", create_guy_line_climb_effect()),
            ("SparkPony", create_spark_pony_effect()),
            ("PortoStandBy", create_porto_standby_effect()),
            ("PortoHit", create_porto_hit_effect()),
            ("CuddlePuddle", create_cuddle_puddle_effect()),
            ("PhotoBomb-BG", create_photobomb_bg_effect()),
            ("PhotoBomb-Spot", create_photobomb_spot_effect()),
            ("DeepPlaya-BG", create_deep_playa_bg_effect()),
        ]
        for effect_name, effect_data in effects:
            self.add_effect(effect_name, effect_data)
        logger.info(f"Initialized {len(effects)} effects")

    async def apply_effect_to_all_rooms(self, effect_name):
        effect_data = self.get_effect(effect_name)
        if not effect_data:
            logger.error(f"{effect_name} effect not found")
            return False, f"{effect_name} effect not found"

        room_layout = self.light_config_manager.get_room_layout()
        
        tasks = [self.apply_effect_to_room(room, effect_data) for room in room_layout.keys()]
        await asyncio.gather(*tasks)
        
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
                get_effect_step_values(effect_data)
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
