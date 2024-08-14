import json
import logging
import os
import random
import threading
from mutagen.mp3 import MP3

logger = logging.getLogger(__name__)

class AudioManager:
    def __init__(self, config_file='audio_config.json', audio_dir='audio_files', music_dir='music'):
        self.config_file = config_file
        self.audio_dir = audio_dir
        self.music_dir = music_dir
        self.audio_config = self.load_config()
        self.last_played = {}
        self.background_music = []
        self.stop_flag = threading.Event()
        logger.info("AudioManager initialized")

    def get_audio_files_to_download(self):
        """
        Returns a list of all audio files that should be downloaded by the client.
        """
        audio_files = []
        for effect, config in self.audio_config['effects'].items():
            audio_files.extend(config.get('audio_files', []))
        
        # Add background music files separately
        music_files = self.get_background_music_files()
        
        return {
            'effects': list(set(audio_files)),
            'music': music_files
        }

    def get_background_music_files(self):
        """
        Returns a list of all background music files from the music directory.
        """
        if os.path.exists(self.music_dir):
            return [f for f in os.listdir(self.music_dir) if f.endswith('.mp3')]
        else:
            logger.warning(f"Music directory not found: {self.music_dir}")
            return []

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

    def get_random_audio_file(self, effect_name):
        effect_config = self.audio_config['effects'].get(effect_name, {})
        audio_files = effect_config.get('audio_files', [])
        
        if not audio_files:
            logger.warning(f"No audio files found for effect: {effect_name}")
            return None
        
        if len(audio_files) > 1:
            available_files = [file for file in audio_files if file != self.last_played.get(effect_name)]
            if not available_files:
                available_files = audio_files
        else:
            available_files = audio_files
        
        selected_file = random.choice(available_files)
        self.last_played[effect_name] = selected_file
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
