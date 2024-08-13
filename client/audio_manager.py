import asyncio
import os
import logging
import random
import asyncio
import aiohttp
import aiofiles
import vlc
from concurrent.futures import ThreadPoolExecutor
import time

logger = logging.getLogger(__name__)

class AudioManager:
    def __init__(self, cache_dir, config):
        self.cache_dir = cache_dir
        self.config = config
        self.preloaded_audio = {}
        self.server_url = f"http://{config.get('server_ip')}:{config.get('server_port', 5000)}"
        self.background_music_player = None
        self.effect_players = []
        self.background_music_volume = 0.5
        self.effect_volume = 1.0
        self.vlc_instance = self.initialize_vlc()
        self.audio_lock = asyncio.Lock()
        self.last_music_change_time = 0
        self.music_change_cooldown = 5  # 5 seconds cooldown

    def initialize_vlc(self):
        audio_outputs = ['pulse', 'alsa', 'oss', 'jack']
        for aout in audio_outputs:
            try:
                instance = vlc.Instance(f'--aout={aout}')
                logger.info(f"Successfully initialized VLC with audio output: {aout}")
                return instance
            except Exception as e:
                logger.warning(f"Failed to initialize VLC with {aout}: {str(e)}")
        
        logger.error("Failed to initialize VLC with any audio output")
        # Instead of raising an exception, return None and log the error
        logger.error("Could not initialize VLC. Audio playback may not work.")
        return None

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

    async def play_effect_audio(self, file_name, volume=1.0, loop=False):
        logger.debug(f"Attempting to play effect audio: file_name={file_name}, volume={volume}, loop={loop}")
        full_path = self.preloaded_audio.get(file_name)
        if not full_path:
            logger.warning(f"Audio file not found: {file_name}")
            return False

        try:
            logger.info(f"Playing effect audio file: {file_name}")

            async with self.audio_lock:
                # Create a new media player for the effect
                effect_player = self.vlc_instance.media_player_new()
                media = self.vlc_instance.media_new(full_path)
                effect_player.set_media(media)

                # Set volume and start playing
                effect_player.audio_set_volume(int(volume * 100))
                effect_player.play()

                if loop:
                    event_manager = effect_player.event_manager()
                    event_manager.event_attach(vlc.EventType.MediaPlayerEndReached, self.loop_effect_audio)

                self.effect_players.append(effect_player)

            logger.info(f"Started playing effect audio file: {file_name}, volume: {volume}, loop: {loop}")

            # Wait for a short time to ensure playback has started
            await asyncio.sleep(0.1)

            if effect_player.is_playing():
                logger.info(f"Confirmed playback started for {file_name}")
                if not loop:
                    asyncio.create_task(self.wait_for_effect_completion(effect_player))
                return True
            else:
                logger.warning(f"Playback did not start for {file_name}")
                return False

        except Exception as e:
            logger.error(f"Error playing effect audio file {file_name}: {str(e)}", exc_info=True)
            return False

    async def wait_for_effect_completion(self, effect_player):
        while effect_player.is_playing():
            await asyncio.sleep(0.1)
        self.effect_players.remove(effect_player)

    def loop_effect_audio(self, event):
        # This method will be called when the effect audio reaches the end of the track
        for player in self.effect_players:
            if player.get_state() == vlc.State.Ended:
                player.set_position(0)
                player.play()
                break

    def stop_audio(self):
        if self.background_music_player:
            self.background_music_player.stop()
        for player in self.effect_players:
            player.stop()
        self.effect_players.clear()
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

    async def start_background_music(self, music_file):
        current_time = time.time()
        if current_time - self.last_music_change_time < self.music_change_cooldown:
            logger.info(f"Ignoring music change request for {music_file} due to cooldown")
            return

        if not music_file:
            logger.warning("No music file specified for background music")
            return

        full_path = self.preloaded_audio.get(music_file)
        if not full_path:
            logger.warning(f"Specified music file not found: {music_file}")
            return

        logger.info(f"Starting background music: {music_file}")

        try:
            async with self.audio_lock:
                # Stop any existing background music
                if self.background_music_player:
                    self.background_music_player.stop()

                # Create a new media player
                self.background_music_player = self.vlc_instance.media_player_new()
                media = self.vlc_instance.media_new(full_path)
                self.background_music_player.set_media(media)

                # Set volume and start playing
                self.background_music_player.audio_set_volume(int(self.background_music_volume * 100))
                self.background_music_player.play()

                # Set up event manager to handle looping
                event_manager = self.background_music_player.event_manager()
                event_manager.event_attach(vlc.EventType.MediaPlayerEndReached, self.loop_background_music)

            logger.info(f"Started playing background music: {music_file}")

            # Wait for a short time to ensure playback has started
            await asyncio.sleep(0.1)

            if self.background_music_player.is_playing():
                logger.info(f"Confirmed background music playback started for {music_file}")
                self.last_music_change_time = current_time
            else:
                logger.warning(f"Background music playback did not start for {music_file}")
                # Try to reinitialize VLC instance and retry playback
                self.vlc_instance = self.initialize_vlc()
                await self.start_background_music(music_file)

        except Exception as e:
            logger.error(f"Error playing background music {music_file}: {str(e)}", exc_info=True)
            # Try to reinitialize VLC instance
            self.vlc_instance = self.initialize_vlc()

    def loop_background_music(self, event):
        # This method will be called when the media player reaches the end of the track
        self.background_music_player.set_position(0)
        self.background_music_player.play()
    async def stop_background_music(self):
        logger.info("Stopping background music")
        if self.background_music_player:
            self.background_music_player.stop()
            self.background_music_player = None
        logger.info("Background music stopped")
