import asyncio
import os
import logging
import simpleaudio as sa
import random
from pydub import AudioSegment
import io

logger = logging.getLogger(__name__)

class AudioManager:
    def __init__(self, cache_dir, config):
        self.cache_dir = cache_dir
        self.config = config
        self.current_audio = None
        self.stop_event = asyncio.Event()
        self.preloaded_audio = {}

    async def initialize(self):
        logger.info("Initializing AudioManager")
        await self.preload_existing_audio_files()
        await self.download_audio_files()
        logger.info(f"AudioManager initialization complete. Preloaded audio files: {list(self.preloaded_audio.keys())}")

    async def preload_existing_audio_files(self):
        logger.info("Preloading existing audio files")
        audio_dir = os.path.join(self.cache_dir, 'audio_files')
        if os.path.exists(audio_dir):
            audio_files = os.listdir(audio_dir)
            for audio_file in audio_files:
                if audio_file.endswith('.mp3'):
                    file_path = os.path.join(audio_dir, audio_file)
                    self.preloaded_audio[audio_file] = file_path
            logger.info(f"Preloaded {len(self.preloaded_audio)} existing audio files")
        else:
            logger.info("No existing audio files found")

    async def download_audio_files(self):
        # This method should be implemented to download any missing audio files
        # For now, we'll assume all files are already present
        pass

    def play_effect_audio(self, file_name, volume=1.0):
        full_path = os.path.join(self.cache_dir, 'audio_files', file_name)
        if not os.path.exists(full_path):
            logger.error(f"Audio file not found: {full_path}")
            return False
        
        self.stop_audio()
        try:
            logger.info(f"Playing audio file: {full_path}")
            
            # Load the audio file (MP3 or WAV)
            audio = AudioSegment.from_file(full_path)
            
            # Adjust volume
            audio = audio + (20 * math.log10(volume))
            
            # Export as WAV to a bytes buffer
            buffer = io.BytesIO()
            audio.export(buffer, format="wav")
            buffer.seek(0)
            
            # Play the audio
            wave_obj = sa.WaveObject.from_wave_read(wave.open(buffer))
            play_obj = wave_obj.play()
            self.current_audio = play_obj
            
            logger.info(f"Started playing audio file: {file_name}, volume: {volume}")
            
            play_obj.wait_done()
            
            logger.info(f"Audio playback completed for file: {file_name}")
            return True
        except Exception as e:
            logger.error(f"Error playing audio file {file_name} (full path: {full_path}): {str(e)}", exc_info=True)
            return False

    def get_audio_file_for_effect(self, effect_name):
        audio_config = self.config.get('effects', {}).get(effect_name, {})
        audio_files = audio_config.get('audio_files', [])
        if audio_files:
            chosen_file = random.choice(audio_files)
            full_path = os.path.join(self.cache_dir, 'audio_files', chosen_file)
            if os.path.exists(full_path):
                logger.info(f"Selected audio file '{full_path}' for effect '{effect_name}'")
                return full_path
            else:
                logger.warning(f"Audio file '{full_path}' not found for effect '{effect_name}'")
        else:
            logger.warning(f"No audio files found for effect '{effect_name}' in config")
        return None

    def stop_audio(self):
        if self.current_audio:
            self.stop_event.set()
            self.current_audio.stop()
            logger.info("Stopped current audio playback")
            self.current_audio = None
            self.stop_event.clear()
