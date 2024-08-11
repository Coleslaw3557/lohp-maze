import asyncio
import aiofiles
import os
import logging
from pydub import AudioSegment
from pydub.playback import play
import io
import threading
import math
import aiohttp

logger = logging.getLogger(__name__)

class AudioManager:
    def __init__(self, cache_dir, config):
        self.cache_dir = cache_dir
        self.config = config
        self.current_audio = None
        self.stop_event = threading.Event()
        self.prepared_audio = None
        self.audio_files = [
            "audio_files/lightning.mp3",
            # Add other audio files here
        ]

    async def initialize(self):
        await self.download_all_audio_files()

    async def download_all_audio_files(self):
        for audio_file in self.audio_files:
            await self.download_audio(audio_file)

    async def prepare_audio(self, file_name, params):
        full_path = os.path.join(self.cache_dir, file_name)
        if not os.path.exists(full_path):
            success = await self.download_audio(file_name)
            if not success:
                logger.error(f"Failed to prepare audio: {file_name}")
                return False
        
        if os.path.exists(full_path):
            self.prepared_audio = {
                'file_name': full_path,
                'volume': params.get('volume', 1.0),
                'loop': params.get('loop', False)
            }
            logger.info(f"Prepared audio: {full_path} (volume: {self.prepared_audio['volume']}, loop: {self.prepared_audio['loop']})")
            return True
        else:
            logger.error(f"Audio file not found after download attempt: {full_path}")
            return False

    async def download_audio(self, file_name):
        server_url = f"http://{self.config.get('server_ip')}:5000/api/audio/{file_name}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(server_url) as response:
                    if response.status == 200:
                        content = await response.read()
                        full_path = os.path.join(self.cache_dir, file_name)
                        os.makedirs(os.path.dirname(full_path), exist_ok=True)
                        async with aiofiles.open(full_path, 'wb') as f:
                            await f.write(content)
                        logger.info(f"Downloaded audio file: {file_name}")
                        return True
                    elif response.status == 404:
                        logger.error(f"Audio file not found on server: {file_name}")
                        return False
                    else:
                        logger.error(f"Failed to download audio file: {file_name}. Status code: {response.status}")
                        logger.error(f"Response content: {await response.text()}")
                        return False
        except aiohttp.ClientError as e:
            logger.error(f"Network error while downloading {file_name}: {str(e)}")
        except IOError as e:
            logger.error(f"IO error while saving {file_name}: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error while downloading {file_name}: {str(e)}")
        return False

    async def play_prepared_audio(self):
        if self.prepared_audio:
            if os.path.exists(self.prepared_audio['file_name']):
                self.stop_audio()
                try:
                    audio = AudioSegment.from_mp3(self.prepared_audio['file_name'])
                    volume = self.prepared_audio['volume']
                    audio = audio + (20 * math.log10(volume))
                    
                    self.current_audio = self.prepared_audio['file_name']
                    self.stop_event.clear()
                    
                    threading.Thread(target=self._play_audio, args=(audio, self.prepared_audio['loop'])).start()
                    
                    logger.info(f"Started playing audio: {self.prepared_audio['file_name']} (volume: {volume}, loop: {self.prepared_audio['loop']})")
                except Exception as e:
                    logger.error(f"Error playing audio: {str(e)}", exc_info=True)
            else:
                logger.error(f"Prepared audio file not found: {self.prepared_audio['file_name']}")
            self.prepared_audio = None
        else:
            logger.warning("No prepared audio to play")

    async def receive_audio_data(self, audio_data):
        if self.prepared_audio:
            file_path = os.path.join(self.cache_dir, self.prepared_audio['file_name'])
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            logger.info(f"Saving audio data to: {file_path}")
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(audio_data)
            
            self.stop_audio()
            
            try:
                # Decode and play the MP3 file
                logger.info(f"Decoding MP3 file: {file_path}")
                audio = AudioSegment.from_mp3(file_path)
                volume = self.prepared_audio['volume']
                audio = audio + (20 * math.log10(volume))  # Adjust volume (pydub uses dB)
                
                self.current_audio = self.prepared_audio['file_name']
                self.stop_event.clear()
                
                # Start playback in a separate thread
                logger.info(f"Starting audio playback: {self.current_audio}")
                threading.Thread(target=self._play_audio, args=(audio, self.prepared_audio['loop'])).start()
                
                logger.info(f"Started playing audio: {self.prepared_audio['file_name']} (volume: {volume}, loop: {self.prepared_audio['loop']})")
            except Exception as e:
                logger.error(f"Error playing audio: {str(e)}", exc_info=True)
            
            self.prepared_audio = None
        else:
            logger.warning("Received audio data without preparation")

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
