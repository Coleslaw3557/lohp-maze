import json
import logging
import os
import warnings
import random
from pydub import AudioSegment

warnings.filterwarnings("ignore", category=RuntimeWarning, message="Couldn't find ffmpeg or avconv - defaulting to ffmpeg, but may not work")
logger = logging.getLogger(__name__)

class AudioManager:
    def __init__(self, config_file='audio_config.json', audio_dir='audio_files'):
        self.config_file = config_file
        self.audio_dir = audio_dir
        self.audio_config = self.load_config()
        logger.info("AudioManager initialized")

    def get_audio_files_to_download(self):
        """
        Returns a list of all audio files that should be downloaded by the client.
        """
        audio_files = []
        for effect, config in self.audio_config['effects'].items():
            audio_files.extend(config.get('audio_files', []))
        return list(set(audio_files))  # Remove duplicates

    def load_config(self):
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            logger.info(f"Successfully loaded audio configuration from {self.config_file}")
            return config
        except FileNotFoundError:
            logger.error(f"Configuration file {self.config_file} not found.")
            return {"effects": {}, "default_volume": 0.7}
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from {self.config_file}.")
            return {"effects": {}, "default_volume": 0.7}

    def get_audio_file(self, effect_name):
        effect_config = self.audio_config['effects'].get(effect_name, {})
        audio_files = effect_config.get('audio_files', [])
        
        if not audio_files:
            logger.warning(f"No audio files found for effect: {effect_name}")
            return None
        
        selected_file = random.choice(audio_files)
        full_path = os.path.join(self.audio_dir, selected_file)
        
        if os.path.exists(full_path):
            logger.info(f"Selected audio file for effect '{effect_name}': {full_path}")
            return full_path
        
        logger.warning(f"Selected audio file not found: {full_path}")
        return None

    def get_audio_config(self, effect_name):
        config = self.audio_config['effects'].get(effect_name, {})
        if config:
            logger.debug(f"Audio configuration for effect '{effect_name}': {config}")
        else:
            logger.warning(f"No audio configuration found for effect: {effect_name}")
        return config

    def prepare_audio_stream(self, effect_name):
        audio_file = self.get_audio_file(effect_name)
        if audio_file and os.path.exists(audio_file):
            logger.info(f"Preparing audio stream for effect: {effect_name}")
            with open(audio_file, 'rb') as f:
                return f.read()
        logger.error(f"Failed to prepare audio stream for effect: {effect_name}")
        return None

    def save_config(self):
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.audio_config, f, indent=4)
            logger.info(f"Audio configuration saved to {self.config_file}")
        except IOError:
            logger.error(f"Error writing to {self.config_file}")
