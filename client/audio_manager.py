import asyncio
import os
import logging
import random
import io
import math
import aiohttp
import aiofiles
import threading
import pyaudio
from pydub import AudioSegment

logger = logging.getLogger(__name__)

class AudioManager:
    def __init__(self, cache_dir, config):
        self.cache_dir = cache_dir
        self.config = config
        self.preloaded_audio = {}
        self.server_url = f"http://{config.get('server_ip')}:{config.get('server_port', 5000)}"
        self.background_music = None
        self.background_music_volume = 0.5
        self.effect_audio = None
        self.effect_volume = 1.0
        self.mixer = None  # Remove AudioSegment usage
        self.pyaudio = pyaudio.PyAudio()
        self.stream = None
        self.is_playing = False
        self.play_thread = None
        self.lock = threading.Lock()

    async def initialize(self):
        logger.info("Initializing AudioManager")
        await self.preload_existing_audio_files()
        await self.download_audio_files()
        logger.info(f"AudioManager initialization complete. Preloaded audio files: {list(self.preloaded_audio.keys())}")
        # Remove automatic start of background music

    async def preload_existing_audio_files(self):
        logger.info("Preloading existing audio files")
        audio_dir = os.path.join(self.cache_dir, 'audio_files')
        if os.path.exists(audio_dir):
            audio_files = os.listdir(audio_dir)
            logger.info(f"Found {len(audio_files)} files in {audio_dir}")
            for audio_file in audio_files:
                if audio_file.endswith(('.mp3', '.wav')):
                    file_path = os.path.join(audio_dir, audio_file)
                    self.preloaded_audio[audio_file] = file_path
                    logger.debug(f"Preloaded audio file: {audio_file}")
            logger.info(f"Preloaded {len(self.preloaded_audio)} existing audio files")
            logger.debug(f"Preloaded audio files: {list(self.preloaded_audio.keys())}")
        else:
            logger.warning(f"Audio directory not found: {audio_dir}")

    async def download_audio_files(self):
        logger.info("Downloading new audio files")
        audio_dir = os.path.join(self.cache_dir, 'audio_files')
        os.makedirs(audio_dir, exist_ok=True)

        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.server_url}/api/audio_files_to_download") as response:
                if response.status == 200:
                    files_to_download = await response.json()
                    for category, file_list in files_to_download.items():
                        for file_name in file_list:
                            if file_name and file_name not in self.preloaded_audio:
                                await self.download_audio_file(session, file_name, audio_dir)
                else:
                    logger.error(f"Failed to get list of audio files to download. Status: {response.status}")

        # Download background music files
        await self.download_background_music_files()

    async def download_audio_file(self, session, file_name, audio_dir):
        file_path = os.path.join(audio_dir, file_name)
        if not os.path.exists(file_path):
            try:
                async with session.get(f"{self.server_url}/api/audio/{file_name}") as response:
                    if response.status == 200:
                        async with aiofiles.open(file_path, mode='wb') as f:
                            await f.write(await response.read())
                        logger.info(f"Downloaded audio file: {file_name}")
                        self.preloaded_audio[file_name] = file_path
                    elif response.status == 404:
                        logger.warning(f"Audio file not found on server: {file_name}")
                    else:
                        logger.error(f"Failed to download audio file: {file_name}. Status: {response.status}")
            except Exception as e:
                logger.error(f"Error downloading audio file {file_name}: {str(e)}")
        else:
            logger.info(f"Audio file already exists: {file_name}")

    async def download_background_music_files(self):
        logger.info("Downloading background music files")
        music_dir = os.path.join(self.cache_dir, 'audio_files')
        os.makedirs(music_dir, exist_ok=True)

        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.server_url}/api/audio_files_to_download") as response:
                if response.status == 200:
                    files_to_download = await response.json()
                    music_files = files_to_download.get('music', [])
                    for file_name in music_files:
                        if file_name and file_name not in self.preloaded_audio:
                            await self.download_audio_file(session, file_name, music_dir)
                else:
                    logger.error(f"Failed to get list of background music files. Status: {response.status}")

    def play_effect_audio(self, file_name, volume=1.0):
        full_path = os.path.join(self.audio_dir, file_name)
        if not os.path.exists(full_path):
            logger.error(f"Audio file not found: {full_path}")
            return False
        
        try:
            logger.info(f"Playing effect audio file: {full_path}")
            
            # Stop any currently playing audio
            self.stop_audio()
            
            # Set the stop flag to False
            self.stop_flag.clear()
            
            # Start a new thread to play the audio
            self.play_thread = threading.Thread(target=self._play_audio_thread, args=(full_path, volume))
            self.play_thread.start()
            
            logger.info(f"Started playing effect audio file: {file_name}, volume: {volume}")
            
            return True
        except Exception as e:
            logger.error(f"Error playing effect audio file {file_name} (full path: {full_path}): {str(e)}", exc_info=True)
            return False

    def _play_audio_thread(self, file_path, volume):
        try:
            audio = MP3(file_path)
            
            # Open a PyAudio stream
            stream = self.pyaudio.open(format=self.pyaudio.get_format_from_width(2),
                                       channels=audio.info.channels,
                                       rate=audio.info.sample_rate,
                                       output=True)
            
            # Open the MP3 file
            with open(file_path, 'rb') as f:
                data = f.read()
            
            # Play audio
            chunk_size = 1024
            offset = 0
            while offset < len(data):
                if self.stop_flag.is_set():
                    break
                chunk = data[offset:offset + chunk_size]
                stream.write(chunk)
                offset += chunk_size
            
            # Close the stream
            stream.stop_stream()
            stream.close()
            
            logger.info(f"Finished playing effect audio file: {file_path}")
        except Exception as e:
            logger.error(f"Error in audio playback thread: {str(e)}", exc_info=True)
        finally:
            self.current_stream = None

    def stop_audio(self):
        if self.play_thread and self.play_thread.is_alive():
            self.stop_flag.set()
            self.play_thread.join()
        if self.current_stream:
            self.current_stream.stop_stream()
            self.current_stream.close()
            self.current_stream = None
        logger.info("Audio playback stopped")

    def stop_effect_audio(self):
        if self.effect_audio:
            self.effect_audio = None
            self.mix_audio()
            logger.info("Stopped effect audio")

    def mix_audio(self):
        # This method needs to be reimplemented using PyAudio
        # For now, we'll return a placeholder
        return b'\x00' * 44100  # 1 second of silence (assuming 16-bit mono at 44.1kHz)

    def audio_callback(self, in_data, frame_count, time_info, status):
        with self.lock:
            if not self.is_playing:
                return (bytes(frame_count * 4), pyaudio.paContinue)
            
            mixed = self.mix_audio()
            data = mixed.raw_data
            return (data, pyaudio.paContinue)

    def start_audio_stream(self):
        self.stream = self.pyaudio.open(format=self.pyaudio.get_format_from_width(2),
                                        channels=2,
                                        rate=44100,
                                        output=True,
                                        stream_callback=self.audio_callback)
        self.stream.start_stream()

    def stop_audio_stream(self):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.stream = None

    def play_audio(self):
        if self.play_thread and self.play_thread.is_alive():
            return

        self.play_thread = threading.Thread(target=self._play_audio)
        self.play_thread.start()

    def _play_audio(self):
        self.is_playing = True
        if not self.stream:
            self.start_audio_stream()

    def stop_audio(self):
        self.is_playing = False
        if self.play_thread:
            self.play_thread.join()
        self.stop_audio_stream()

    def stop_audio(self):
        self.active_audio_streams.clear()
        self.mix_audio()
        logger.info("Stopped all audio playback")

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
        self.active_audio_streams.clear()
        self.mix_audio()
        logger.info("Stopped all audio playback")

    async def start_background_music(self, music_file):
        if not music_file:
            logger.warning("No music file specified for background music")
            return

        full_path = self.preloaded_audio.get(music_file)
        if not full_path:
            logger.warning(f"Specified music file not found: {music_file}")
            return

        logger.info(f"Starting background music: {music_file}")

        try:
            # Load the MP3 file
            audio = AudioSegment.from_mp3(full_path)
            
            # Convert to raw PCM data
            raw_data = audio.raw_data
            
            # Set as current background music
            with self.lock:
                self.background_music = raw_data
                self.background_music_info = {
                    'channels': audio.channels,
                    'width': audio.sample_width,
                    'framerate': audio.frame_rate
                }
            
            # Start playing if not already playing
            self.play_audio()
            
            logger.info(f"Started playing background music: {music_file}")

        except Exception as e:
            logger.error(f"Error playing background music {music_file}: {str(e)}", exc_info=True)
    def mix_audio(self):
        # This method needs to be reimplemented using PyAudio
        # For now, we'll just log a message
        logger.info("mix_audio method called, but not implemented yet")
