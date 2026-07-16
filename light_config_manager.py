import json
import logging

logger = logging.getLogger(__name__)


class LightConfigManager:
    def __init__(self, config_file='light_config.json'):
        self.config_file = config_file
        self.light_configs = self.load_config()

    def load_config(self):
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            logger.info(f"Light configuration loaded from {self.config_file}")
            return config
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Error loading {self.config_file}: {e}")
            return {'light_models': {}, 'room_layout': {}}

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

    def get_light_models(self):
        return self.light_configs.get('light_models', {})
