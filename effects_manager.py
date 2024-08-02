import json
import logging

logger = logging.getLogger(__name__)

class EffectsManager:
    def __init__(self, config_file='effects_config.json'):
        self.config_file = config_file
        self.effects = self.load_config()
        self.room_effects = {}

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
