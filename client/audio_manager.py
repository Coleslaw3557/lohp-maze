import asyncio
import aiofiles
import os
import logging
from pydub import AudioSegment
from pydub.playback import play
import io
import threading
import math

logger = logging.getLogger(__name__)

class AudioManager:
    def __init__(self, cache_dir):
        self.cache_dir = cache_dir
        self.current_audio = None
        self.stop_event = threading.Event()

    async def start_audio(self, audio_data, audio_file):
        file_name = audio_data['file_name'].lower()
        file_path = os.path.join(self.cache_dir, file_name)
        
        # Save the received audio file
        with open(file_path, 'wb') as f:
            f.write(audio_file)
        
        self.stop_audio()
        
        # Decode and play the MP3 file
        audio = AudioSegment.from_mp3(file_path)
        volume = audio_data.get('volume', 1.0)
        audio = audio + (20 * math.log10(volume))  # Adjust volume (pydub uses dB)
        
        self.current_audio = file_name
        self.stop_event.clear()
        
        # Start playback in a separate thread
        threading.Thread(target=self._play_audio, args=(audio, audio_data.get('loop', False))).start()
        
        logger.info(f"Started playing audio: {file_name} (volume: {volume}, loop: {audio_data.get('loop', False)})")

    def stop_audio(self):
        if self.current_audio:
            self.stop_event.set()
            logger.info(f"Stopped playing audio: {self.current_audio}")
            self.current_audio = None

    def _play_audio(self, audio, loop):
        while not self.stop_event.is_set():
            play(audio)
            if not loop:
                break
        self.current_audio = None

    async def cache_audio(self, file_name, audio_data):
        file_path = os.path.join(self.cache_dir, file_name)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(audio_data)
        
        logger.info(f"Cached audio file: {file_name}")
