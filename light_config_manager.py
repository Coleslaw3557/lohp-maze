import json
import logging
import time

logger = logging.getLogger(__name__)

from dmx_interface import DMXOutputManager

class LightConfigManager:
    def __init__(self, config_file='light_config.json', dmx_state_manager=None):
        self.config_file = config_file
        self.light_configs = self.load_config()
        self.dmx_state_manager = dmx_state_manager
        if self.dmx_state_manager is None:
            logger.warning("DMX State Manager not provided. Some features may not work correctly.")
        self.dmx_interface = None  # Remove this line if it exists

    def load_config(self):
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            logger.info(f"Light configuration loaded from {self.config_file}")
            return config
        except FileNotFoundError:
            logger.error(f"Configuration file {self.config_file} not found.")
            return {'light_models': {}, 'room_layout': {}}
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from {self.config_file}.")
            return {'light_models': {}, 'room_layout': {}}

    def save_config(self):
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.light_configs, f, indent=4)
            logger.info(f"Light configuration saved to {self.config_file}")
        except IOError:
            logger.error(f"Error writing to {self.config_file}")

    def get_light_config(self, model):
        config = self.light_configs.get('light_models', {}).get(model, {})
        if not config:
            logger.warning(f"No configuration found for light model: {model}")
        return config

    def get_room_layout(self):
        layout = self.light_configs.get('room_layout', {})
        if not layout:
            logger.warning("Room layout is empty")
        return layout

    def update_room_layout(self, new_layout):
        for room, lights in new_layout.items():
            for light in lights:
                light['start_address'] = int(light['start_address'])
        self.light_configs['room_layout'] = new_layout
        self.save_config()
        logger.info("Room layout updated and saved")

    def add_room(self, room_name, lights):
        self.light_configs['room_layout'][room_name] = lights
        self.save_config()
        logger.info(f"Room '{room_name}' added to layout")

    def update_room(self, room_name, lights):
        if room_name in self.light_configs['room_layout']:
            self.light_configs['room_layout'][room_name] = lights
            self.save_config()
            logger.info(f"Room '{room_name}' updated in layout")
        else:
            logger.warning(f"Room '{room_name}' not found in layout")

    def remove_room(self, room_name):
        if room_name in self.light_configs['room_layout']:
            del self.light_configs['room_layout'][room_name]
            self.save_config()
            logger.info(f"Room '{room_name}' removed from layout")
        else:
            logger.warning(f"Room '{room_name}' not found in layout")

    def get_light_models(self):
        return self.light_configs.get('light_models', {})

    def add_light_model(self, model, config):
        if model in self.light_configs.get('light_models', {}):
            logger.warning(f"Overwriting existing configuration for light model: {model}")
        self.light_configs.setdefault('light_models', {})[model] = config
        self.save_config()
        logger.info(f"Added configuration for light model: {model}")

    def update_light_model(self, model, config):
        if model not in self.light_configs.get('light_models', {}):
            logger.warning(f"No existing configuration found for light model: {model}")
        self.light_configs.setdefault('light_models', {})[model] = config
        self.save_config()
        logger.info(f"Updated configuration for light model: {model}")

    def remove_light_model(self, model):
        if model in self.light_configs.get('light_models', {}):
            del self.light_configs['light_models'][model]
            self.save_config()
            logger.info(f"Removed configuration for light model: {model}")
        else:
            logger.warning(f"No configuration found for light model: {model}")

    def validate_config(self):
        for model, config in self.light_configs.get('light_models', {}).items():
            if 'channels' not in config:
                logger.error(f"Invalid configuration for {model}: 'channels' field missing")
                return False
        return True

    def test_effect(self, room, effect_data):
        if self.dmx_state_manager is None:
            return False, ["DMX State Manager not initialized. Cannot test effect."]

        room_layout = self.get_room_layout()
        log_messages = []

        if room not in room_layout:
            log_messages.append(f"Room not found: {room}")
            return False, log_messages

        lights = room_layout[room]
        log_messages.append(f"Testing effect in room: {room}")
        log_messages.append(f"Number of lights: {len(lights)}")

        for step_index, step in enumerate(effect_data['steps']):
            log_messages.append(f"Step {step_index + 1}:")
            for light in lights:
                start_address = light['start_address']
                light_model = self.get_light_config(light['model'])
                fixture_id = (start_address - 1) // 8
                fixture_values = [0] * 8
                log_messages.append(f"  Light: {light['model']} (Start Address: {start_address})")
                for channel, value in step['channels'].items():
                    if channel in light_model['channels']:
                        channel_offset = light_model['channels'][channel]
                        fixture_values[channel_offset] = value
                        log_messages.append(f"    Channel: {channel}, DMX Address: {start_address + channel_offset}, Value: {value}")
                    else:
                        log_messages.append(f"    Warning: Channel {channel} not found in light model")
                self.dmx_state_manager.update_fixture(fixture_id, fixture_values)
            log_messages.append(f"  Waiting for {step['time']} seconds")
            time.sleep(step['time'])

        # Reset channels after effect
        log_messages.append("Resetting channels after effect")
        for light in lights:
            start_address = light['start_address']
            fixture_id = (start_address - 1) // 8
            self.dmx_state_manager.reset_fixture(fixture_id)

        return True, log_messages
