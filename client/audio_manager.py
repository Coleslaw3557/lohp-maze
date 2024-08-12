import asyncio
import os
import logging
import simpleaudio as sa
import random

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

    async def play_effect_audio(self, file_name, volume=1.0, loop=False):
        full_path = os.path.join(self.cache_dir, 'audio_files', file_name)
        
        if not os.path.exists(full_path):
            logger.error(f"Audio file not found: {full_path}")
            return False
        
        await self.stop_audio()
        try:
            wave_obj = sa.WaveObject.from_wave_file(full_path)
            play_obj = wave_obj.play()
            self.current_audio = play_obj
            
            logger.info(f"Started playing audio file: {file_name}, volume: {volume}, loop: {loop}")
            
            # Set volume
            play_obj.set_volume(volume)
            
            # Handle looping
            while loop and not self.stop_event.is_set():
                while play_obj.is_playing() and not self.stop_event.is_set():
                    await asyncio.sleep(0.1)
                if not self.stop_event.is_set():
                    play_obj = wave_obj.play()
                    play_obj.set_volume(volume)
            
            # Wait for the audio to finish or be stopped if not looping
            if not loop:
                while play_obj.is_playing() and not self.stop_event.is_set():
                    await asyncio.sleep(0.1)
            
            if self.stop_event.is_set():
                play_obj.stop()
                logger.info(f"Audio playback stopped for file: {file_name}")
            else:
                logger.info(f"Audio playback completed for file: {file_name}")
            
            return True
        except Exception as e:
            logger.error(f"Error playing audio file {file_name}: {str(e)}", exc_info=True)
            return False

    async def stop_audio(self):
        if self.current_audio:
            self.stop_event.set()
            self.current_audio.stop()
            logger.info("Stopped current audio playback")
            self.current_audio = None
            self.stop_event.clear()

    async def play_cached_audio(self, effect_name, volume=1.0, loop=False):
        # This method is not needed as we're playing MP3 files directly
        pass
