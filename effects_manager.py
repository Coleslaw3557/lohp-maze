import json
import logging

logger = logging.getLogger(__name__)

class EffectsManager:
    def __init__(self, config_file='effects_config.json'):
        self.config_file = config_file
        self.effects = self.load_config()

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

    def add_effect(self, room, effect_data):
        self.effects[room] = effect_data
        self.save_config()
        logger.info(f"Effect added for room: {room}")

    def update_effect(self, room, effect_data):
        if room in self.effects:
            self.effects[room] = effect_data
            self.save_config()
            logger.info(f"Effect updated for room: {room}")
        else:
            logger.warning(f"No effect found for room: {room}")

    def remove_effect(self, room):
        if room in self.effects:
            del self.effects[room]
            self.save_config()
            logger.info(f"Effect removed for room: {room}")
        else:
            logger.warning(f"No effect found for room: {room}")

    def get_all_effects(self):
        return self.effects

    def create_cop_dodge_effect(self):
        cop_dodge_effect = {
            "duration": 5.0,
            "steps": [
                {"time": 0, "channels": {"r_dimming": 255, "b_dimming": 0}},
                {"time": 0.5, "channels": {"r_dimming": 0, "b_dimming": 255}},
                {"time": 1, "channels": {"r_dimming": 255, "b_dimming": 0}},
                {"time": 1.5, "channels": {"r_dimming": 0, "b_dimming": 255}},
                {"time": 2, "channels": {"r_dimming": 255, "b_dimming": 0}},
                {"time": 2.5, "channels": {"r_dimming": 0, "b_dimming": 255}},
                {"time": 3, "channels": {"r_dimming": 255, "b_dimming": 0}},
                {"time": 3.5, "channels": {"r_dimming": 0, "b_dimming": 255}},
                {"time": 4, "channels": {"r_dimming": 255, "b_dimming": 0}},
                {"time": 4.5, "channels": {"r_dimming": 0, "b_dimming": 255}},
                {"time": 5, "channels": {"r_dimming": 0, "b_dimming": 0}}
            ]
        }
        self.add_effect("Cop Dodge", cop_dodge_effect)
