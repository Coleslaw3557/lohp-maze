import asyncio
import os
import logging
from urllib.parse import quote
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
        self.maze_ambience_player = None
        self.effect_players = []
        # Room beds (the Cuddle floor show's lava rumble): their own player per
        # room so effect audio mixes OVER them and stop_effects never cuts them.
        self.ambience_players = {}  # room key -> player

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
        self.reap_ended_effects()
        player = self.vlc_instance.media_player_new()
        media = self._new_media(full_path, loop)
        player.set_media(media)
        media.release()  # the player holds its own reference
        player.audio_set_volume(int(volume * 100))
        player.play()
        self.effect_players.append(player)
        return player

    def _new_media(self, full_path, loop):
        # Looping uses VLC's native input-repeat: restarting a player from its
        # own EndReached callback (the old approach) is the documented libVLC
        # deadlock pattern, and it sometimes restarted the wrong player.
        media = self.vlc_instance.media_new(full_path)
        if loop:
            media.add_option('input-repeat=65535')
        return media

    def start_maze_ambience(self, full_path, volume, loop=True):
        self.stop_maze_ambience()
        self.maze_ambience_player = self.vlc_instance.media_player_new()
        media = self._new_media(full_path, loop)
        self.maze_ambience_player.set_media(media)
        media.release()  # the player holds its own reference
        self.maze_ambience_player.audio_set_volume(int(volume * 100))
        self.maze_ambience_player.play()

    def stop_maze_ambience(self):
        if self.maze_ambience_player:
            self.maze_ambience_player.stop()
            self.maze_ambience_player.release()
            self.maze_ambience_player = None

    def play_ambience(self, room_key, full_path, volume, loop=True):
        """Start (or replace) this zone's bed for one room."""
        self.stop_ambience(room_key)
        player = self.vlc_instance.media_player_new()
        media = self._new_media(full_path, loop)
        player.set_media(media)
        media.release()  # the player holds its own reference
        player.audio_set_volume(int(volume * 100))
        player.play()
        self.ambience_players[room_key] = player
        return player

    def stop_ambience(self, room_key=None):
        keys = [room_key] if room_key is not None else list(self.ambience_players)
        for key in keys:
            player = self.ambience_players.pop(key, None)
            if player:
                player.stop()
                player.release()

    def stop_effects(self):
        for player in self.effect_players:
            player.stop()
            player.release()
        self.effect_players.clear()

    def reap_ended_effects(self):
        """Release finished players so hours of triggers don't leak VLC objects."""
        still_active = []
        for player in self.effect_players:
            if player.get_state() in (vlc.State.Ended, vlc.State.Error, vlc.State.Stopped):
                player.release()
            else:
                still_active.append(player)
        self.effect_players = still_active


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
        self.maze_ambience_volume = 0.5
        # The maze-wide ambience file that SHOULD be playing. Zones with a
        # room bed skip it; the bed overrides maze ambience in that room and
        # the zone rejoins it when the room bed stops.
        self.current_maze_ambience_file = None
        self.current_maze_ambience_loop = True

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
        full_path = (
            self.preloaded_audio.get(file_name)
            or self.preloaded_audio.get(os.path.basename(file_name))
        )
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
        logger.info(f"Playing '{file_name}' (volume {volume}, loop {loop}) "
                    f"in zones: {[z.name for z, _ in players]}")
        # Confirm off the message loop so a slow start never delays or reorders
        # the commands that arrive after this one
        asyncio.create_task(self._confirm_effect_playback(file_name, players))
        return True

    async def _confirm_effect_playback(self, file_name, players):
        await asyncio.sleep(0.3)
        for zone, player in players:
            if player not in zone.effect_players:
                continue  # already stopped or reaped; don't touch a released player
            if not player.is_playing() and player.get_state() != vlc.State.Ended:
                logger.warning(f"Playback did not start for {file_name} in zone '{zone.name}'")

    def stop_audio(self, room=None):
        """Stop effect playback in the room's zone (all zones when room is None).
        Maze ambience and room beds are deliberately untouched:
        both have their own stop command, and stopping a room's effect must not
        silence the active bed the effect was playing over."""
        for zone in self.zones_for_room(room):
            zone.stop_effects()
        logger.info(f"Stopped effect audio ({'room ' + room if room else 'all zones'})")

    async def play_room_ambience(self, file_name, volume=1.0, loop=True, room=None):
        """Start a looping bed for one room (the floor show's rumble under
        Cuddle Cross). Mixes under effect audio and survives audio_stop."""
        full_path = (
            self.preloaded_audio.get(file_name)
            or self.preloaded_audio.get(os.path.basename(file_name))
        )
        if not full_path:
            logger.warning(f"Ambience file not found: {file_name}")
            return False
        zones = self.zones_for_room(room)
        if not zones:
            logger.warning(f"No audio zone covers room: {room}")
            return False
        key = (room or '__all__').lower()
        started = []
        for zone in zones:
            if zone.vlc_instance is None:
                logger.warning(f"Zone '{zone.name}' has no audio output; skipping ambience {file_name}")
                continue
            try:
                zone.play_ambience(key, full_path, volume, loop)
                started.append(zone.name)
            except Exception as e:
                logger.error(f"Zone '{zone.name}': failed to start ambience {file_name}: {e}",
                             exc_info=True)
                continue
            # A room's own background overrides the maze-wide ambience on its
            # speaker (it comes back in stop_room_ambience when the bed ends).
            if zone.maze_ambience_player:
                zone.stop_maze_ambience()
                logger.info(f"Zone '{zone.name}': room background overrides maze ambience")
        if not started:
            return False
        logger.info(f"Ambience '{file_name}' (volume {volume}, loop {loop}) "
                    f"for {room or 'all rooms'} in zones: {started}")
        return True

    def stop_room_ambience(self, room=None):
        key = (room or '__all__').lower()
        for zone in self.zones_for_room(room):
            zone.stop_ambience(key if room else None)
            self._resume_maze_ambience_if_due(zone)
        logger.info(f"Stopped ambience ({'room ' + room if room else 'all zones'})")
        return True

    def _resume_maze_ambience_if_due(self, zone):
        """A bed just ended in this zone: if no other room bed holds the zone,
        the maze-wide ambience takes the speaker back."""
        if not self.current_maze_ambience_file or zone.ambience_players:
            return
        if zone.vlc_instance is None or zone.maze_ambience_player:
            return
        full_path = self.preloaded_audio.get(self.current_maze_ambience_file)
        if not full_path:
            return
        try:
            zone.start_maze_ambience(
                full_path, self.maze_ambience_volume, self.current_maze_ambience_loop)
            logger.info(f"Zone '{zone.name}': maze ambience resumes after the room background")
        except Exception as e:
            logger.error(f"Zone '{zone.name}': failed to resume maze ambience: {e}", exc_info=True)

    async def start_maze_ambience(self, file_name, volume=None, loop=True):
        full_path = (
            self.preloaded_audio.get(file_name)
            or self.preloaded_audio.get(os.path.basename(file_name))
        )
        if not full_path:
            logger.warning(f"Specified maze ambience file not found: {file_name}")
            return False

        logger.info(f"Starting maze ambience: {file_name}")
        self.current_maze_ambience_file = file_name
        self.current_maze_ambience_loop = bool(loop)
        vol = self.maze_ambience_volume if volume is None else volume
        started_zones = []
        deferred = []
        for zone in self.zones.values():
            if zone.vlc_instance is None:
                logger.warning(f"Zone '{zone.name}' has no audio output; skipping maze ambience")
                continue
            if zone.ambience_players:
                # The room's own background owns this speaker; it picks up
                # maze ambience when its bed stops.
                deferred.append(zone.name)
                continue
            try:
                zone.start_maze_ambience(full_path, vol, loop)
                started_zones.append(zone)
            except Exception as e:
                logger.error(f"Zone '{zone.name}': failed to start maze ambience: {e}", exc_info=True)
        if deferred:
            logger.info(f"Maze ambience deferred to room backgrounds in zones: {deferred}")
        if not started_zones:
            return bool(deferred)
        asyncio.create_task(self._confirm_maze_ambience_playback(file_name, started_zones))
        return True

    async def _confirm_maze_ambience_playback(self, file_name, zones):
        for _ in range(10):  # Confirm playback within ~1 second
            await asyncio.sleep(0.1)
            # Re-read player each pass: it may have been replaced/stopped
            if any(zone.maze_ambience_player and zone.maze_ambience_player.is_playing()
                   for zone in zones):
                return
        logger.warning(f"Maze ambience playback did not start for {file_name}")

    async def stop_maze_ambience(self):
        for zone in self.zones.values():
            zone.stop_maze_ambience()
        self.current_maze_ambience_file = None
        self.current_maze_ambience_loop = True
        logger.info("Maze ambience stopped")
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
                            if not file_name:
                                continue
                            local_name = os.path.basename(file_name)
                            if local_name in self.preloaded_audio:
                                self.preloaded_audio[file_name] = self.preloaded_audio[local_name]
                            else:
                                await self.download_audio_file(session, file_name, audio_dir)
                else:
                    logger.error(f"Failed to get list of audio files to download. Status: {response.status}")

    async def download_audio_file(self, session, file_name, audio_dir):
        # Server refs may live in subdirs (audio_files/rooms/<Room>/...), but the
        # client cache is flat. Key both the exact server ref and its basename so
        # old basename-only commands and new path-preserving commands both work.
        local_name = os.path.basename(file_name)
        file_path = os.path.join(audio_dir, local_name)
        if os.path.exists(file_path):
            self.preloaded_audio[file_name] = file_path
            self.preloaded_audio[local_name] = file_path
            return
        try:
            async with session.get(f"{self.server_url}/api/audio/{quote(file_name)}") as response:
                if response.status == 200:
                    async with aiofiles.open(file_path, mode='wb') as f:
                        await f.write(await response.read())
                    logger.info(f"Downloaded audio file: {file_name}")
                    self.preloaded_audio[file_name] = file_path
                    self.preloaded_audio[local_name] = file_path
                elif response.status == 404:
                    logger.warning(f"Audio file not found on server: {file_name}")
                else:
                    logger.error(f"Failed to download audio file: {file_name}. Status: {response.status}")
        except Exception as e:
            logger.error(f"Error downloading audio file {file_name}: {e}")
