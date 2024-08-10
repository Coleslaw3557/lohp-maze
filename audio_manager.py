import json
import logging
import os

logger = logging.getLogger(__name__)

class AudioManager:
    def __init__(self, config_file='audio_config.json', audio_dir='audio_files'):
        self.config_file = config_file
        self.audio_dir = audio_dir
        self.audio_config = self.load_config()

    def load_config(self):
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Configuration file {self.config_file} not found.")
            return {"effects": {}, "default_volume": 0.7}
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from {self.config_file}.")
            return {"effects": {}, "default_volume": 0.7}

    def get_audio_file(self, effect_name):
        effect_config = self.audio_config['effects'].get(effect_name, {})
        audio_file = effect_config.get('audio_file')
        if audio_file:
            return os.path.join(self.audio_dir, audio_file)
        return None

    def get_audio_config(self, effect_name):
        return self.audio_config['effects'].get(effect_name, {})

    def prepare_audio_stream(self, effect_name):
        audio_file = self.get_audio_file(effect_name)
        if audio_file and os.path.exists(audio_file):
            with open(audio_file, 'rb') as f:
                return f.read()
        return None
