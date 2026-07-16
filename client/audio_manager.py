import asyncio
import os
import logging
import time
import aiohttp
import aiofiles
import vlc

logger = logging.getLogger(__name__)


class ZonePlayer:
    """VLC playback bound to one audio output device (one zone of rooms)."""

    def __init__(self, name, alsa_device=None):
        self.name = name
        self.alsa_device = alsa_device
        self.vlc_instance = self._initialize_vlc()
        self.background_player = None
        self.effect_players = []

    def _initialize_vlc(self):
        # vlc.Instance returns None on failure rather than raising
        if self.alsa_device:
            instance = vlc.Instance(f'--aout=alsa --alsa-audio-device={self.alsa_device}')
            if instance is None:
                logger.error(f"Zone '{self.name}': VLC could not initialize ALSA output {self.alsa_device}")
            else:
                logger.info(f"Zone '{self.name}': VLC bound to ALSA device {self.alsa_device}")
            return instance
        # No device configured: fall back through common audio outputs (legacy single-zone mode)
        for aout in ['pulse', 'alsa', 'oss', 'jack']:
            instance = vlc.Instance(f'--aout={aout}')
            if instance is not None:
                logger.info(f"Zone '{self.name}': VLC initialized with audio output {aout}")
                return instance
            logger.warning(f"Zone '{self.name}': failed to initialize VLC with {aout}")
        logger.error(f"Zone '{self.name}': could not initialize VLC; audio will not work")
        return None

    def play_effect(self, full_path, volume, loop):
        """Start an effect file. Returns the player (caller confirms playback)."""
        player = self.vlc_instance.media_player_new()
        player.set_media(self.vlc_instance.media_new(full_path))
        player.audio_set_volume(int(volume * 100))
        player.play()
        if loop:
            player.event_manager().event_attach(vlc.EventType.MediaPlayerEndReached, self._loop_effect)
        self.effect_players.append(player)
        return player

    def _loop_effect(self, event):
        for player in self.effect_players:
            if player.get_state() == vlc.State.Ended:
                player.set_position(0)
                player.play()
                break

    def start_music(self, full_path, volume):
        self.stop_music()
        self.background_player = self.vlc_instance.media_player_new()
        self.background_player.set_media(self.vlc_instance.media_new(full_path))
        self.background_player.audio_set_volume(int(volume * 100))
        self.background_player.play()
        self.background_player.event_manager().event_attach(
            vlc.EventType.MediaPlayerEndReached, self._loop_music)

    def _loop_music(self, event):
        if self.background_player:
            self.background_player.set_position(0)
            self.background_player.play()

    def stop_music(self):
        if self.background_player:
            self.background_player.stop()
            self.background_player.release()
            self.background_player = None

    def stop_effects(self):
        for player in self.effect_players:
            player.stop()
        self.effect_players.clear()


class AudioManager:
    """Downloads/caches audio from the server and plays it on one or more output zones.

    Config with a `zones` map routes each room's audio to its own device
    (e.g. one Pi driving several USB sound cards). Without `zones`, all
    associated rooms share the default output — the original one-Pi-per-unit mode.
    """

    def __init__(self, cache_dir, config):
        self.cache_dir = cache_dir
        self.config = config
        self.preloaded_audio = {}
        server_ip = config.get('server_ip')
        if not server_ip or server_ip.startswith('${'):
            logger.error(f"Server IP not properly set. Current value: {server_ip}")
            raise ValueError("Server IP is not properly configured")
        self.server_url = f"http://{server_ip}:{config.get('server_http_port', 5000)}"
        self.background_music_volume = 0.5
        self.last_music_change_time = 0
        self.music_change_cooldown = 5  # seconds

        zones_config = config.get('zones') or {
            'default': {'rooms': config.get('associated_rooms', []), 'alsa_device': None}
        }
        self.zones = {name: ZonePlayer(name, zone.get('alsa_device'))
                      for name, zone in zones_config.items()}
        self.room_to_zone = {}
        for name, zone in zones_config.items():
            for room in zone.get('rooms', []):
                if room.lower() in self.room_to_zone:
                    logger.warning(f"Room '{room}' is in multiple zones; using '{name}'")
                self.room_to_zone[room.lower()] = name
        logger.info(f"Audio zones: {[(z.name, z.alsa_device) for z in self.zones.values()]}")

    def zones_for_room(self, room=None):
        """ZonePlayers covering a room; all zones when room is None (whole-maze audio)."""
        if room is None:
            return list(self.zones.values())
        zone_name = self.room_to_zone.get(room.lower())
        return [self.zones[zone_name]] if zone_name else []

    # --- Playback ---

    async def play_effect_audio(self, file_name, volume=1.0, loop=False, room=None):
        full_path = self.preloaded_audio.get(file_name)
        if not full_path:
            logger.warning(f"Audio file not found: {file_name}")
            return False
        zones = self.zones_for_room(room)
        if not zones:
            logger.warning(f"No audio zone covers room: {room}")
            return False

        # One zone failing must not silence the others (whole-maze audio hits every zone)
        players = []
        for zone in zones:
            if zone.vlc_instance is None:
                logger.warning(f"Zone '{zone.name}' has no audio output; skipping {file_name}")
                continue
            try:
                players.append((zone, zone.play_effect(full_path, volume, loop)))
            except Exception as e:
                logger.error(f"Zone '{zone.name}': failed to start {file_name}: {e}", exc_info=True)
        if not players:
            return False
        await asyncio.sleep(0.1)  # Give playback a moment to start

        started = False
        for zone, player in players:
            if player.is_playing():
                started = True
                if not loop:
                    asyncio.create_task(self._reap_effect_player(zone, player))
            else:
                logger.warning(f"Playback did not start for {file_name} in zone '{zone.name}'")
        if started:
            logger.info(f"Playing '{file_name}' (volume {volume}, loop {loop}) "
                        f"in zones: {[z.name for z, _ in players]}")
        return started

    async def _reap_effect_player(self, zone, player):
        while player.is_playing():
            await asyncio.sleep(0.1)
        if player in zone.effect_players:
            zone.effect_players.remove(player)

    def stop_audio(self, room=None):
        """Stop all playback in the room's zone (all zones when room is None)."""
        for zone in self.zones_for_room(room):
            zone.stop_music()
            zone.stop_effects()
        logger.info(f"Stopped audio ({'room ' + room if room else 'all zones'})")

    async def start_background_music(self, music_file):
        current_time = time.time()
        if current_time - self.last_music_change_time < self.music_change_cooldown:
            logger.info(f"Ignoring music change request for {music_file} due to cooldown")
            return False
        full_path = self.preloaded_audio.get(music_file)
        if not full_path:
            logger.warning(f"Specified music file not found: {music_file}")
            return False

        logger.info(f"Starting background music: {music_file}")
        started_zones = []
        for zone in self.zones.values():
            if zone.vlc_instance is None:
                logger.warning(f"Zone '{zone.name}' has no audio output; skipping background music")
                continue
            try:
                zone.start_music(full_path, self.background_music_volume)
                started_zones.append(zone)
            except Exception as e:
                logger.error(f"Zone '{zone.name}': failed to start background music: {e}", exc_info=True)
        if not started_zones:
            return False

        for _ in range(10):  # Confirm playback within ~1 second
            await asyncio.sleep(0.1)
            if any(zone.background_player and zone.background_player.is_playing()
                   for zone in started_zones):
                self.last_music_change_time = current_time
                return True
        logger.warning(f"Background music playback did not start for {music_file}")
        return False

    async def stop_background_music(self):
        for zone in self.zones.values():
            zone.stop_music()
        self.last_music_change_time = 0  # Reset the cooldown timer
        logger.info("Background music stopped")
        return True

    # --- Cache / downloads ---

    async def initialize(self):
        logger.info("Initializing AudioManager")
        await self.preload_existing_audio_files()
        await self.download_audio_files()
        logger.info(f"AudioManager ready. Cached audio files: {len(self.preloaded_audio)}")

    async def preload_existing_audio_files(self):
        audio_dir = os.path.join(self.cache_dir, 'audio_files')
        if not os.path.exists(audio_dir):
            logger.warning(f"Audio directory not found: {audio_dir}")
            return
        for audio_file in os.listdir(audio_dir):
            if audio_file.endswith(('.mp3', '.wav')):
                self.preloaded_audio[audio_file] = os.path.join(audio_dir, audio_file)
        logger.info(f"Preloaded {len(self.preloaded_audio)} existing audio files")

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

    async def download_audio_file(self, session, file_name, audio_dir):
        file_path = os.path.join(audio_dir, file_name)
        if os.path.exists(file_path):
            self.preloaded_audio[file_name] = file_path
            return
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
            logger.error(f"Error downloading audio file {file_name}: {e}")
