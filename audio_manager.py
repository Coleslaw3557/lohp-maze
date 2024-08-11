import json
import logging
import os

logger = logging.getLogger(__name__)

try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False
    logger.warning("pydub module not found. Some audio functionality may be limited.")

class AudioManager:
    def __init__(self, config_file='audio_config.json', audio_dir='audio_files'):
        self.config_file = config_file
        self.audio_dir = audio_dir
        self.audio_config = self.load_config()
        logger.info("AudioManager initialized")
        
        # Add default configurations for all effects
        default_effects = [
            'Lightning', 'PoliceLights', 'GateInspection', 'GateGreeters',
            'WrongAnswer', 'CorrectAnswer', 'Entrance', 'GuyLineClimb',
            'SparkPony', 'PortoStandBy', 'PortoHit', 'CuddlePuddle',
            'PhotoBomb-BG', 'PhotoBomb-Spot', 'DeepPlaya-BG', 'ImageEnhancement'
        ]
        
        for effect in default_effects:
            if effect not in self.audio_config['effects']:
                self.audio_config['effects'][effect] = {
                    'audio_file': f'{effect.lower().replace("-", "_")}.mp3',
                    'volume': 1.0,
                    'loop': False
                }
        
        self.save_config()  # Save the updated configuration

    def get_audio_files_to_download(self):
        """
        Returns a list of audio files that should be downloaded by the client.
        """
        audio_files = []
        for effect, config in self.audio_config['effects'].items():
            audio_file = config.get('audio_file')
            if audio_file:
                full_path = os.path.join(self.audio_dir, audio_file)
                if os.path.exists(full_path):
                    audio_files.append(audio_file)
                else:
                    logger.warning(f"Audio file not found for effect {effect}: {full_path}")
        return audio_files

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
        audio_file = effect_config.get('audio_file')
        
        possible_filenames = [
            audio_file,
            f"{effect_name.lower()}.mp3",
            f"{effect_name.lower().replace(' ', '_')}.mp3",
            f"{effect_name.lower().replace('-', '_')}.mp3"
        ]
        
        for filename in possible_filenames:
            if filename:
                full_path = os.path.join(self.audio_dir, filename)
                logger.debug(f"Trying audio file for effect '{effect_name}': {full_path}")
                if os.path.exists(full_path):
                    logger.info(f"Found audio file for effect '{effect_name}': {full_path}")
                    return full_path
        
        logger.warning(f"No audio file found for effect: {effect_name}")
        return None

    def create_silent_mp3(self, file_path):
        try:
            # Create an empty file as a fallback
            with open(file_path, 'wb') as f:
                f.write(b'')
            logger.info(f"Created empty file as fallback: {file_path}")
        except Exception as e:
            logger.error(f"Error creating empty file: {str(e)}")

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
