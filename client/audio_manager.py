import asyncio
import aiofiles
import os
import logging
from pydub import AudioSegment
from pydub.playback import _play_with_simpleaudio
import io
import threading
import math
import aiohttp
import simpleaudio as sa
import time

logger = logging.getLogger(__name__)

class AudioManager:
    def __init__(self, cache_dir, config):
        self.cache_dir = cache_dir
        self.config = config
        self.current_audio = None
        self.stop_event = threading.Event()
        self.prepared_audio = {}
        self.audio_files = [
            "lightning.mp3",
            # Add other audio files here
        ]
        self.current_effect_audio = None
        self.preloaded_audio = {}

    async def initialize(self):
        logger.info("Initializing AudioManager")
        await self.download_all_audio_files()
        await self.preload_audio_files()
        logger.info("AudioManager initialization complete")

    async def preload_audio_files(self):
        logger.info("Preloading audio files")
        for audio_file in self.audio_files:
            file_path = os.path.join(self.cache_dir, 'audio_files', audio_file)
            if os.path.exists(file_path):
                audio = AudioSegment.from_mp3(file_path)
                self.preloaded_audio[audio_file] = audio
        logger.info(f"Preloaded {len(self.preloaded_audio)} audio files")

    async def download_all_audio_files(self):
        logger.info(f"Starting download of {len(self.audio_files)} audio files")
        for audio_file in self.audio_files:
            success = await self.download_audio(audio_file)
            if not success:
                logger.error(f"Failed to download {audio_file}")
        logger.info("Finished attempting to download all audio files")

    async def prepare_audio(self, file_name, effect_name, volume=1.0, loop=False):
        full_path = os.path.join(self.cache_dir, 'audio_files', file_name)
        
        if not os.path.exists(full_path):
            logger.error(f"Audio file not found: {full_path}")
            return False
        
        self.prepared_audio[effect_name] = {
            'file_name': full_path,
            'volume': volume,
            'loop': loop
        }
        logger.info(f"Prepared audio for effect: {effect_name}")
        return True

    def get_prepared_audio(self):
        if self.prepared_audio:
            return next(iter(self.prepared_audio.values()))
        return None

    async def play_effect_audio(self, effect_name, file_name):
        full_path = os.path.join(self.cache_dir, 'audio_files', os.path.basename(file_name))
        
        if not os.path.exists(full_path):
            logger.error(f"Audio file not found: {full_path}")
            return False
        
        self.stop_audio()
        try:
            audio = AudioSegment.from_mp3(full_path)
            self.current_audio = full_path
            self.stop_event.clear()
            
            await asyncio.to_thread(self._play_audio, audio, False)  # Assuming no loop by default
            
            logger.info(f"Started playing audio for effect: {effect_name}, file: {file_name}")
            return True
        except Exception as e:
            logger.error(f"Error playing audio for effect {effect_name}: {str(e)}", exc_info=True)
            return False

    async def download_audio(self, file_name):
        # Remove 'audio_files/' prefix if present
        if file_name.startswith('audio_files/'):
            file_name = file_name[len('audio_files/'):]
        
        server_url = f"http://{self.config.get('server_ip')}:5000/api/audio/{file_name}"
        max_retries = 3
        retry_delay = 5

        for attempt in range(max_retries):
            try:
                logger.info(f"Attempting to download audio file from: {server_url} (Attempt {attempt + 1}/{max_retries})")
                async with aiohttp.ClientSession() as session:
                    async with session.get(server_url) as response:
                        if response.status == 200:
                            content = await response.read()
                            full_path = os.path.join(self.cache_dir, 'audio_files', file_name)
                            os.makedirs(os.path.dirname(full_path), exist_ok=True)
                            async with aiofiles.open(full_path, 'wb') as f:
                                await f.write(content)
                            logger.info(f"Successfully downloaded audio file: {file_name}")
                            return True
                        elif response.status == 404:
                            logger.error(f"Audio file not found on server: {file_name}")
                            logger.error(f"Server response: {await response.text()}")
                            return False
                        else:
                            logger.error(f"Failed to download audio file: {file_name}. Status code: {response.status}")
                            logger.error(f"Server response: {await response.text()}")
            except aiohttp.ClientError as e:
                logger.error(f"Network error while downloading {file_name}: {str(e)}")
            except IOError as e:
                logger.error(f"IO error while saving {file_name}: {str(e)}")
            except Exception as e:
                logger.error(f"Unexpected error while downloading {file_name}: {str(e)}")
            
            if attempt < max_retries - 1:
                logger.info(f"Retrying download in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
            else:
                logger.error(f"Failed to download {file_name} after {max_retries} attempts")
                return False

    async def play_prepared_audio(self, file_name):
        if file_name in self.prepared_audio:
            audio_info = self.prepared_audio[file_name]
            if os.path.exists(audio_info['file_name']):
                self.stop_audio()
                try:
                    audio = AudioSegment.from_mp3(audio_info['file_name'])
                    volume = audio_info['volume']
                    audio = audio + (20 * math.log10(volume))
                    
                    self.current_audio = audio_info['file_name']
                    self.stop_event.clear()
                    
                    threading.Thread(target=self._play_audio, args=(audio, audio_info['loop'])).start()
                    
                    logger.info(f"Started playing audio: {audio_info['file_name']} (volume: {volume}, loop: {audio_info['loop']})")
                except Exception as e:
                    logger.error(f"Error playing audio: {str(e)}", exc_info=True)
            else:
                logger.error(f"Prepared audio file not found: {audio_info['file_name']}")
        else:
            logger.warning(f"No prepared audio found for: {file_name}")

    async def play_cached_audio(self, effect_name, volume=1.0, loop=False):
        file_name = f"{effect_name.lower()}.mp3"
        if file_name in self.preloaded_audio:
            self.stop_audio()
            try:
                audio = self.preloaded_audio[file_name]
                audio = audio + (20 * math.log10(volume))
                
                self.current_audio = file_name
                self.stop_event.clear()
                
                play_obj = _play_with_simpleaudio(audio)
                
                if loop:
                    threading.Thread(target=self._loop_audio, args=(play_obj, audio)).start()
                else:
                    threading.Thread(target=self._wait_for_completion, args=(play_obj,)).start()
                
                logger.info(f"Started playing cached audio: {file_name} (volume: {volume}, loop: {loop})")
            except Exception as e:
                logger.error(f"Error playing cached audio: {str(e)}", exc_info=True)
        else:
            logger.error(f"Preloaded audio not found for effect: {effect_name}")

    async def receive_audio_data(self, audio_data):
        file_name = f"temp_audio_{time.time()}.mp3"
        file_path = os.path.join(self.cache_dir, 'audio_files', file_name)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        logger.info(f"Saving received audio data to: {file_path}")
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(audio_data)
        
        self.stop_audio()
        
        try:
            # Decode and play the MP3 file
            logger.info(f"Decoding MP3 file: {file_path}")
            audio = AudioSegment.from_mp3(file_path)
            volume = 1.0  # Default volume
            audio = audio + (20 * math.log10(volume))  # Adjust volume (pydub uses dB)
            
            self.current_audio = file_name
            self.stop_event.clear()
            
            # Start playback in a separate thread
            logger.info(f"Starting audio playback: {self.current_audio}")
            threading.Thread(target=self._play_audio, args=(audio, False)).start()
            
            logger.info(f"Started playing audio: {file_name} (volume: {volume}, loop: False)")
        except Exception as e:
            logger.error(f"Error playing received audio: {str(e)}", exc_info=True)

    def stop_audio(self):
        if self.current_audio:
            self.stop_event.set()
            logger.info(f"Stopped playing audio: {self.current_audio}")
            self.current_audio = None

    def _loop_audio(self, play_obj, audio):
        while not self.stop_event.is_set():
            play_obj.wait_done()
            if self.stop_event.is_set():
                break
            play_obj = _play_with_simpleaudio(audio)
        play_obj.stop()
        self.current_audio = None

    def _wait_for_completion(self, play_obj):
        play_obj.wait_done()
        if not self.stop_event.is_set():
            self.current_audio = None

    def _play_audio(self, audio, loop=False):
        play_obj = _play_with_simpleaudio(audio)
        if loop:
            while not self.stop_event.is_set():
                play_obj.wait_done()
                if self.stop_event.is_set():
                    break
                play_obj = _play_with_simpleaudio(audio)
        else:
            self._wait_for_completion(play_obj)
        play_obj.stop()
        self.current_audio = None

    async def cache_audio(self, file_name, audio_data):
        file_path = os.path.join(self.cache_dir, file_name)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(audio_data)
        
        logger.info(f"Cached audio file: {file_name}")
