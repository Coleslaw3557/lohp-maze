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
import random

logger = logging.getLogger(__name__)

class AudioManager:
    def __init__(self, cache_dir, config):
        self.cache_dir = cache_dir
        self.config = config
        self.current_audio = None
        self.stop_event = threading.Event()
        self.prepared_audio = {}
        self.preloaded_audio = {}
        self.glitch_intensity = 0.0

    async def initialize(self):
        logger.info("Initializing AudioManager")
        await self.preload_existing_audio_files()
        await self.download_audio_files()
        logger.info("AudioManager initialization complete")

    async def preload_existing_audio_files(self):
        logger.info("Preloading existing audio files")
        audio_dir = os.path.join(self.cache_dir, 'audio_files')
        if os.path.exists(audio_dir):
            audio_files = os.listdir(audio_dir)
            for audio_file in audio_files:
                if audio_file.endswith('.mp3'):
                    file_path = os.path.join(audio_dir, audio_file)
                    audio = AudioSegment.from_mp3(file_path)
                    self.preloaded_audio[audio_file] = audio
            logger.info(f"Preloaded {len(self.preloaded_audio)} existing audio files")
        else:
            logger.info("No existing audio files found")

    async def download_audio_files(self):
        server_url = f"http://{self.config.get('server_ip')}:5000/api/audio_files_to_download"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(server_url) as response:
                    if response.status == 200:
                        audio_files_to_download = await response.json()
                        logger.info(f"Received list of {len(audio_files_to_download)} audio files to download")
                        for audio_file in audio_files_to_download:
                            logger.info(f"Checking audio file: {audio_file}")
                            if audio_file not in self.preloaded_audio:
                                logger.info(f"Attempting to download: {audio_file}")
                                success = await self.download_audio(audio_file)
                                if success:
                                    logger.info(f"Successfully downloaded: {audio_file}")
                                    await self.preload_single_audio_file(audio_file)
                                else:
                                    logger.error(f"Failed to download {audio_file}")
                            else:
                                logger.info(f"Audio file already preloaded: {audio_file}")
                    else:
                        logger.error(f"Failed to get audio files list. Status code: {response.status}")
                        logger.error(f"Response content: {await response.text()}")
        except Exception as e:
            logger.error(f"Error downloading audio files: {str(e)}", exc_info=True)

    async def preload_single_audio_file(self, audio_file):
        file_path = os.path.join(self.cache_dir, 'audio_files', audio_file)
        if os.path.exists(file_path):
            audio = AudioSegment.from_mp3(file_path)
            self.preloaded_audio[audio_file] = audio
            logger.info(f"Preloaded audio file: {audio_file}")

    async def play_effect_audio(self, effect_name):
        audio_files = self.config.get('audio_config', {}).get('effects', {}).get(effect_name, {}).get('audio_files', [])
        if not audio_files:
            logger.error(f"No audio files found for effect: {effect_name}")
            return False
        
        file_name = random.choice(audio_files)
        full_path = os.path.join(self.cache_dir, 'audio_files', file_name)
        
        if not os.path.exists(full_path):
            logger.error(f"Audio file not found: {full_path}")
            return False
        
        self.stop_audio()
        try:
            audio = AudioSegment.from_mp3(full_path)
            self.current_audio = full_path
            self.stop_event.clear()
            
            await asyncio.to_thread(self._play_audio, audio, False)
            
            logger.info(f"Started playing audio for effect: {effect_name}, file: {file_name}")
            return True
        except Exception as e:
            logger.error(f"Error playing audio for effect {effect_name}: {str(e)}", exc_info=True)
            return False

    async def download_audio(self, file_name):
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
                            logger.info(f"File saved to: {full_path}")
                            return True
                        elif response.status == 404:
                            logger.error(f"Audio file not found on server: {file_name}")
                            logger.error(f"Response content: {await response.text()}")
                            return False
                        else:
                            logger.error(f"Failed to download audio file: {file_name}. Status code: {response.status}")
                            logger.error(f"Response content: {await response.text()}")
            except aiohttp.ClientError as e:
                logger.error(f"Network error while downloading {file_name}: {str(e)}", exc_info=True)
            except IOError as e:
                logger.error(f"IO error while saving {file_name}: {str(e)}", exc_info=True)
            except Exception as e:
                logger.error(f"Unexpected error while downloading {file_name}: {str(e)}", exc_info=True)
            
            if attempt < max_retries - 1:
                logger.info(f"Retrying download in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
            else:
                logger.error(f"Failed to download {file_name} after {max_retries} attempts")
                return False

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

    def apply_glitch_effect(self, audio):
        if self.glitch_intensity == 0:
            return audio

        glitched_audio = AudioSegment.empty()
        segment_length = 50  # ms
        for i in range(0, len(audio), segment_length):
            segment = audio[i:i+segment_length]
            if random.random() < self.glitch_intensity:
                effect = random.choice(['reverse', 'repeat', 'silence', 'pitch_shift'])
                if effect == 'reverse':
                    segment = segment.reverse()
                elif effect == 'repeat':
                    segment = segment * 2
                elif effect == 'silence':
                    segment = AudioSegment.silent(duration=segment_length)
                elif effect == 'pitch_shift':
                    octaves = random.uniform(-1, 1)
                    new_sample_rate = int(segment.frame_rate * (2.0 ** octaves))
                    segment = segment._spawn(segment.raw_data, overrides={'frame_rate': new_sample_rate})
            glitched_audio += segment

        return glitched_audio

    def set_glitch_intensity(self, intensity):
        self.glitch_intensity = max(0.0, min(1.0, intensity))
