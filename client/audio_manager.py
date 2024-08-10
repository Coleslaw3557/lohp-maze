import asyncio
import aiofiles
import os
import logging
import pygame

logger = logging.getLogger(__name__)

class AudioManager:
    def __init__(self, cache_dir):
        self.cache_dir = cache_dir
        self.current_audio = None
        pygame.mixer.init()

    async def start_audio(self, audio_data):
        file_path = os.path.join(self.cache_dir, audio_data['file'])
        
        if not os.path.exists(file_path):
            await self.cache_audio(audio_data['file'], audio_data['data'])
        
        self.stop_audio()
        
        try:
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.set_volume(audio_data.get('volume', 1.0))
            pygame.mixer.music.play(loops=-1 if audio_data.get('loop', False) else 0)
            self.current_audio = audio_data['file']
            logger.info(f"Started playing audio: {self.current_audio}")
        except Exception as e:
            logger.error(f"Error playing audio {file_path}: {e}")

    def stop_audio(self):
        if self.current_audio:
            pygame.mixer.music.stop()
            logger.info(f"Stopped playing audio: {self.current_audio}")
            self.current_audio = None

    async def cache_audio(self, file_name, audio_data):
        file_path = os.path.join(self.cache_dir, file_name)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(audio_data)
        
        logger.info(f"Cached audio file: {file_name}")
