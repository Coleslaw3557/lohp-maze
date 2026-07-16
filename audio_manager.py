import json
import logging
import os
import random

logger = logging.getLogger(__name__)


class AudioManager:
    def __init__(self, config_file='audio_config.json', music_dir='music'):
        self.config_file = config_file
        self.music_dir = music_dir
        self.audio_config = self.load_config()

    def load_config(self):
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            logger.info(f"Loaded audio configuration from {self.config_file}")
            return config
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Error loading {self.config_file}: {e}")
            return {"effects": {}, "default_volume": 0.7}

    def get_audio_files_to_download(self):
        """All audio files (effects and music) a client should cache locally."""
        audio_files = []
        for config in self.audio_config['effects'].values():
            audio_files.extend(config.get('audio_files', []))
        return {
            'effects': list(set(audio_files)),
            'music': self.get_background_music_files()
        }

    def get_background_music_files(self):
        if os.path.exists(self.music_dir):
            return [f for f in os.listdir(self.music_dir) if f.endswith('.mp3')]
        logger.warning(f"Music directory not found: {self.music_dir}")
        return []

    def get_audio_config(self, effect_name):
        config = self.audio_config['effects'].get(effect_name, {})
        if not config:
            logger.warning(f"No audio configuration found for effect: {effect_name}")
        return config

    def get_random_audio_file(self, effect_name):
        audio_files = self.get_audio_config(effect_name).get('audio_files', [])
        if not audio_files:
            return None
        return random.choice(audio_files)
