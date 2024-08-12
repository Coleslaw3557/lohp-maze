import asyncio
import os
import logging
import simpleaudio as sa
import random
from pydub import AudioSegment
import io
import math
import aiohttp
import aiofiles

logger = logging.getLogger(__name__)

class AudioManager:
    def __init__(self, cache_dir, config):
        self.cache_dir = cache_dir
        self.config = config
        self.current_audio = None
        self.stop_event = asyncio.Event()
        self.preloaded_audio = {}
        self.server_url = f"http://{config.get('server_ip')}:{config.get('server_port', 5000)}"
        self.background_music = None
        self.background_music_volume = 0.5

    async def initialize(self):
        logger.info("Initializing AudioManager")
        await self.preload_existing_audio_files()
        await self.download_audio_files()
        await self.start_background_music()
        logger.info(f"AudioManager initialization complete. Preloaded audio files: {list(self.preloaded_audio.keys())}")

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
        full_path = os.path.join(self.cache_dir, 'audio_files', file_name)
        if not os.path.exists(full_path):
            logger.error(f"Audio file not found: {full_path}")
            return False
        
        try:
            logger.info(f"Playing audio file: {full_path}")
            
            # Mute background music
            if self.background_music:
                self.background_music.set_volume(0)
            
            # Load the audio file (MP3 or WAV)
            audio = AudioSegment.from_file(full_path)
            
            # Adjust volume
            audio = audio + (20 * math.log10(volume))
            
            # Convert to raw PCM data
            raw_data = audio.raw_data
            num_channels = audio.channels
            sample_width = audio.sample_width
            frame_rate = audio.frame_rate
            
            # Play the audio
            play_obj = sa.play_buffer(
                raw_data,
                num_channels,
                sample_width,
                frame_rate
            )
            self.current_audio = play_obj
            
            logger.info(f"Started playing audio file: {file_name}, volume: {volume}")
            
            play_obj.wait_done()
            
            logger.info(f"Audio playback completed for file: {file_name}")
            
            # Unmute background music
            if self.background_music:
                self.background_music.set_volume(self.background_music_volume)
            
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

    async def start_background_music(self):
        music_files = [f for f in self.preloaded_audio.keys() if f.startswith('The 7th Continent Soundscape')]
        if not music_files:
            logger.warning(f"No background music files found in {self.cache_dir}/audio_files")
            logger.info(f"Available audio files: {list(self.preloaded_audio.keys())}")
            return

        logger.info(f"Found {len(music_files)} background music files: {music_files}")

        while True:
            random.shuffle(music_files)
            for music_file in music_files:
                if self.stop_event.is_set():
                    return

                full_path = self.preloaded_audio[music_file]
                logger.info(f"Attempting to play background music: {full_path}")
                try:
                    audio = AudioSegment.from_file(full_path)
                    audio = audio + (20 * math.log10(self.background_music_volume))
                    raw_data = audio.raw_data
                    num_channels = audio.channels
                    sample_width = audio.sample_width
                    frame_rate = audio.frame_rate

                    play_obj = sa.play_buffer(
                        raw_data,
                        num_channels,
                        sample_width,
                        frame_rate
                    )
                    self.background_music = play_obj
                    logger.info(f"Started playing background music: {music_file}")
                    
                    while play_obj.is_playing() and not self.stop_event.is_set():
                        await asyncio.sleep(1)
                    
                    if self.stop_event.is_set():
                        play_obj.stop()
                        return

                except Exception as e:
                    logger.error(f"Error playing background music {music_file}: {str(e)}", exc_info=True)

            if self.stop_event.is_set():
                return
