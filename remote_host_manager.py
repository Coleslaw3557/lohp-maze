import json
import logging
import asyncio
import os
import random

logger = logging.getLogger(__name__)


class RemoteHostManager:
    def __init__(self, audio_manager=None, node_audio=None):
        # Keyed by websocket, one entry per CONNECTION: two clients on the same
        # IP (sim browser tab + a test unit, or two tabs) must coexist — an
        # IP-keyed registry silently replaces the first and strands its socket.
        self.clients = {}  # websocket -> {"name": unit_name, "rooms": [...], "ip": client_ip}
        self.audio_manager = audio_manager
        self.node_audio = node_audio  # NodeAudioManager: ESP32 node boxes with speakers
        self.background_music_task = None
        self.music_lock = asyncio.Lock()  # serializes background music start/stop

    async def update_client_rooms(self, unit_name, client_ip, rooms, websocket):
        self.clients[websocket] = {"name": unit_name, "rooms": rooms, "ip": client_ip}
        logger.info(f"Client {unit_name} ({client_ip}) associated with rooms: {rooms}")
        await self._send(websocket, {
            "type": "audio_files_to_download",
            "data": self.audio_manager.get_audio_files_to_download(),
        })

    def remove_client_by_websocket(self, websocket):
        client = self.clients.pop(websocket, None)
        if client:
            logger.info(f"Removed disconnected client {client['name']} ({client['ip']})")

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
            return all(results)
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
            'file_name': os.path.basename(audio_file),
            'volume': volume,
            'loop': audio_params.get('loop', False)
        }
        if rooms is None:
            return await self.send_audio_command(None, 'play_effect_audio', data)
        results = [await self.send_audio_command(room, 'play_effect_audio', data) for room in rooms]
        return all(results)

    # --- Background music ---

    def get_random_music_file(self):
        music_files = self.audio_manager.get_background_music_files()
        return random.choice(music_files) if music_files else None

    async def start_background_music(self):
        async with self.music_lock:
            await self._cancel_music_rotation()
            music_file = self.get_random_music_file()
            if not music_file:
                logger.error("No music files available for background music")
                return False
            success = await self.send_audio_command(None, 'start_background_music',
                                                    {"music_file": music_file})
            if success:
                self.background_music_task = asyncio.create_task(self._rotate_background_music())
            return success

    async def _rotate_background_music(self):
        while True:
            await asyncio.sleep(300)  # New track every 5 minutes
            music_file = self.get_random_music_file()
            if not music_file:
                return
            await self.send_audio_command(None, 'start_background_music', {"music_file": music_file})

    async def _cancel_music_rotation(self):
        """Caller must hold music_lock."""
        task, self.background_music_task = self.background_music_task, None
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Background music rotation ended with error: {e}")

    async def stop_background_music(self):
        async with self.music_lock:
            await self._cancel_music_rotation()
            return await self.send_audio_command(None, 'stop_background_music', {})
