import json
import logging
import asyncio
import random
import time

logger = logging.getLogger(__name__)


class RemoteHostManager:
    def __init__(self, audio_manager=None, node_audio=None, rng=None):
        # Keyed by websocket, one entry per CONNECTION: two clients on the same
        # IP (sim browser tab + a test unit, or two tabs) must coexist — an
        # IP-keyed registry silently replaces the first and strands its socket.
        self.clients = {}  # websocket -> {"name": unit_name, "rooms": [...], "ip": client_ip}
        self.audio_manager = audio_manager
        self.node_audio = node_audio  # NodeAudioManager: ESP32 node boxes with speakers
        self._rng = rng or random.SystemRandom()
        self.maze_ambience_lock = asyncio.Lock()
        # room -> ambience pool that should be looping there right now, asked
        # of each registered provider (the floor show, the room-background
        # runner) whenever a client registers: a reloaded sim tab or a
        # rebooted unit rejoins live beds instead of waiting for a restart.
        self.maze_bed_providers = []
        self.bed_providers = []
        # called with the client's room list when a client disconnects (the
        # room-background runner un-marks beds that just lost their player)
        self.client_gone_hooks = []

    async def update_client_rooms(self, unit_name, client_ip, rooms, websocket):
        self.clients[websocket] = {"name": unit_name, "rooms": rooms, "ip": client_ip}
        logger.info(f"Client {unit_name} ({client_ip}) associated with rooms: {rooms}")
        await self._send(websocket, {
            "type": "audio_files_to_download",
            "data": self.audio_manager.get_audio_files_to_download(),
        })
        await self._resend_maze_beds(websocket)
        await self._resend_beds(websocket, rooms)

    async def _resend_maze_beds(self, websocket):
        """Hand a just-registered client the maze-wide bed if one is live."""
        for provider in self.maze_bed_providers:
            provided = provider()
            if not provided:
                continue
            if isinstance(provided, tuple):
                effect_name, file_name, *rest = provided
                audio_params = {'file': file_name}
                if rest and rest[0] is not None:
                    audio_params['sync_started_at_s'] = rest[0]
                data = self._ambience_payload(effect_name, audio_params)
            else:
                effect_name = provided
                data = self._ambience_payload(effect_name)
            if data is None:
                continue
            if await self._send(websocket, {"type": "start_maze_ambience", "data": data}):
                logger.info(f"Maze bed '{effect_name}' re-sent to the new client")
            break

    async def _resend_beds(self, websocket, rooms):
        """Hand a just-registered client every bed its rooms should already be
        playing. Sent to this ONE socket — clients already looping the bed
        must not have it restarted under them."""
        for room in rooms:
            for provider in self.bed_providers:
                provided = provider(room)
                if not provided:
                    continue
                if isinstance(provided, tuple):
                    effect_name, file_name = provided
                    data = self._ambience_payload(effect_name, {'file': file_name})
                else:
                    effect_name = provided
                    data = self._ambience_payload(effect_name)
                if data is None:
                    continue
                if await self._send(websocket, {"type": "play_room_ambience",
                                                "room": room, "data": data}):
                    logger.info(f"Bed '{effect_name}' re-sent to the new client for {room}")
                break

    def remove_client_by_websocket(self, websocket):
        client = self.clients.pop(websocket, None)
        if client:
            logger.info(f"Removed disconnected client {client['name']} ({client['ip']})")
            for hook in self.client_gone_hooks:
                try:
                    hook(client["rooms"])
                except Exception as e:
                    logger.error(f"client_gone hook failed: {e}", exc_info=True)

    def get_connected_clients_info(self):
        return [{'ip': client['ip'], 'rooms': client['rooms'], 'name': client['name']}
                for client in self.clients.values()]

    async def terminate_client(self, client_ip):
        """Close every connection from client_ip (the /api/terminate_client contract)."""
        sockets = [ws for ws, client in self.clients.items() if client["ip"] == client_ip]
        if not sockets:
            logger.warning(f"Client {client_ip} not found in connected clients")
            return False
        ok = True
        for ws in sockets:
            self.clients.pop(ws, None)
            try:
                await ws.close()
                logger.info(f"Client {client_ip} terminated successfully")
            except Exception as e:
                logger.error(f"Error terminating client {client_ip}: {e}")
                ok = False
        return ok

    def get_websockets_by_room(self, room, warn_if_empty=True):
        """All clients covering a room (a real unit and the sim web UI can both
        claim it — every one of them must get the room's audio)."""
        sockets = [ws for ws, client in self.clients.items()
                   if room.lower() in [r.lower() for r in client["rooms"]]]
        if not sockets and warn_if_empty:
            logger.warning(f"No audio client found for room: {room}")
        return sockets

    def has_audio_client(self, room):
        """Whether anything can play audio for this room right now — a connected
        unit, or the room's own ESP32 speaker node. Lets a caller skip quietly
        and try again later instead of logging a failure per attempt."""
        if self.get_websockets_by_room(room, warn_if_empty=False):
            return True
        return bool(self.node_audio) and self.node_audio.enabled_for(room)

    def audio_rooms(self):
        """Every room something could play audio in right now: any room a
        connected client covers, plus the rooms with a speaker node. Names
        come back in whatever casing they registered with (the maze ambient
        scatter picks its random room from this)."""
        rooms = {r for client in self.clients.values() for r in client["rooms"]}
        if self.node_audio:
            rooms.update(self.node_audio.enabled_rooms())
        return sorted(rooms)

    async def _send(self, websocket, message):
        client = self.clients.get(websocket)
        label = f"{client['name']} ({client['ip']})" if client else "unregistered client"
        try:
            await websocket.send(json.dumps(message))
            return True
        except Exception as e:
            logger.error(f"Error sending {message.get('type')} to {label}: {e}")
            return False

    async def send_audio_command(self, room, command, data=None):
        """Send a command to the client covering `room`, or to all clients if room is None.

        Rooms with an ESP32 speaker node (node_audio_config.json) get the same
        command mirrored over the ESPHome native API. That path is additive —
        the WS copy still goes out, so the sim's browser audio client keeps
        working — and fire-and-forget, so a dead node never delays an effect."""
        message = {"type": command, "data": data if data is not None else {}}
        node_handled = bool(self.node_audio) and self.node_audio.handle_command(room, command, data)
        if room is None:
            results = [await self._send(ws, message) for ws in list(self.clients)]
            return bool(node_handled) or (bool(results) and all(results))
        message["room"] = room
        sockets = self.get_websockets_by_room(room, warn_if_empty=not node_handled)
        if not sockets:
            if node_handled:
                logger.debug(f"Room {room}: {command} handled by the audio node only (no WS client)")
                return True
            logger.error(f"No connected client found for room: {room}. Cannot send {command}.")
            return False
        results = [await self._send(ws, message) for ws in sockets]
        return all(results)

    async def play_effect_audio(self, effect_name, rooms=None, audio_params=None):
        """
        Tell clients to play the audio for an effect. With `rooms`, targets the client
        covering each room; without, sends once to every connected client.
        Audio file and volume come from audio_config.json unless overridden in audio_params.
        """
        audio_params = audio_params or {}
        audio_file = audio_params.get('file') or self.audio_manager.get_random_audio_file(effect_name)
        if not audio_file:
            logger.info(f"No audio configured for effect: {effect_name}")
            return True  # No audio is not a failure
        volume = audio_params.get('volume')
        if volume is None:  # an explicit 0 must stay 0, so no `or` fallback
            volume = self.audio_manager.get_audio_config(effect_name).get(
                'volume', self.audio_manager.audio_config.get('default_volume', 0.7))
        data = {
            'effect_name': effect_name,
            'file_name': audio_file,
            'volume': volume,
            'loop': audio_params.get('loop', False)
        }
        if rooms is None:
            return await self.send_audio_command(None, 'play_effect_audio', data)
        results = [await self.send_audio_command(room, 'play_effect_audio', data) for room in rooms]
        return all(results)

    # --- Room ambience (looping beds) ---

    def _ambience_payload(self, effect_name, audio_params=None):
        """The play_room_ambience payload for one pool pick, or None if the
        pool is empty. Shared by room-wide starts and single-socket resends."""
        audio_params = audio_params or {}
        audio_file = audio_params.get('file') or self.audio_manager.get_random_audio_file(effect_name)
        if not audio_file:
            return None
        volume = audio_params.get('volume')
        if volume is None:  # an explicit 0 must stay 0, so no `or` fallback
            volume = self.audio_manager.get_audio_config(effect_name).get(
                'volume', self.audio_manager.audio_config.get('default_volume', 0.7))
        playback = self.audio_manager.ambience_playback(effect_name, audio_file, audio_params)
        data = {
            'effect_name': effect_name,
            'file_name': audio_file,
            'volume': volume,
            **playback,
        }
        if audio_params.get('sync_started_at_s') is not None:
            data['sync_started_at_s'] = audio_params['sync_started_at_s']
        node_file = self.audio_manager.prepare_node_ambience_stream(effect_name, audio_file, playback)
        if node_file:
            data.update({
                'node_file_name': node_file,
                'node_loop': False,
                'node_duration_s': data.get('play_for_s'),
            })
        return data

    async def start_maze_ambience(self, effect_name, audio_params=None):
        """Start the maze-wide ambience bed on its own channel.

        Room-local beds have priority in clients/nodes; effect audio and
        ambient one-shots mix over the bed.
        """
        async with self.maze_ambience_lock:
            data = self._ambience_payload(effect_name, audio_params)
            if data is None:
                logger.info(f"No maze ambience audio configured for {effect_name}")
                return None
            data['sync_started_at_s'] = time.monotonic()
            ok = await self.send_audio_command(None, 'start_maze_ambience', data)
            return data if ok else None

    async def stop_maze_ambience(self):
        async with self.maze_ambience_lock:
            return await self.send_audio_command(None, 'stop_maze_ambience', {})

    async def retry_node_maze_ambience(self):
        if not self.node_audio:
            return False
        return self.node_audio.retry_maze_ambience_on_disconnected_nodes()

    async def start_room_ambience(self, room, effect_name, audio_params=None):
        """Start a looping bed in one room, on a channel of its own.

        An ambience bed is NOT owned by an effect: a room-scoped `audio_stop`
        (which every effect takeover issues) leaves it running, the same way
        maze ambience is left alone, so accent effects mix over the bed
        instead of replacing it. Only `stop_room_ambience` ends it.
        Returns the file that was started, or None when nothing was.
        """
        data = self._ambience_payload(effect_name, audio_params)
        if data is None:
            logger.info(f"No ambience audio configured for {effect_name}")
            return None
        ok = await self.send_audio_command(room, 'play_room_ambience', data)
        return data if ok else None

    async def stop_room_ambience(self, room):
        return await self.send_audio_command(room, 'stop_room_ambience', {})
