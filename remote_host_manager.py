import json
import logging
import asyncio
import os
import random

logger = logging.getLogger(__name__)


class RemoteHostManager:
    def __init__(self, audio_manager=None):
        self.remote_hosts = {}       # client_ip -> {"name": unit_name, "rooms": [...]}
        self.connected_clients = {}  # client_ip -> websocket
        self.client_rooms = {}       # client_ip -> [rooms]
        self.audio_manager = audio_manager
        self.background_music_task = None

    def update_client_rooms(self, unit_name, client_ip, rooms, websocket):
        self.client_rooms[client_ip] = rooms
        self.connected_clients[client_ip] = websocket
        self.remote_hosts[client_ip] = {"name": unit_name, "rooms": rooms}
        logger.info(f"Client {unit_name} ({client_ip}) associated with rooms: {rooms}")
        self.send_audio_files_to_download(client_ip)

    def send_audio_files_to_download(self, client_ip):
        message = {
            "type": "audio_files_to_download",
            "data": self.audio_manager.get_audio_files_to_download()
        }
        websocket = self.connected_clients.get(client_ip)
        if websocket:
            asyncio.create_task(websocket.send(json.dumps(message)))
        else:
            logger.error(f"No WebSocket connection found for client {client_ip}")

    def remove_client_by_websocket(self, websocket):
        for client_ip, ws in list(self.connected_clients.items()):
            if ws is websocket:
                self.connected_clients.pop(client_ip, None)
                self.client_rooms.pop(client_ip, None)
                self.remote_hosts.pop(client_ip, None)
                logger.info(f"Removed disconnected client {client_ip}")

    def get_connected_clients_info(self):
        return [
            {
                'ip': client_ip,
                'rooms': self.client_rooms.get(client_ip, []),
                'name': self.remote_hosts.get(client_ip, {}).get('name', f'Client-{client_ip}')
            }
            for client_ip in self.connected_clients
        ]

    async def terminate_client(self, client_ip):
        websocket = self.connected_clients.get(client_ip)
        if not websocket:
            logger.warning(f"Client {client_ip} not found in connected clients")
            return False
        try:
            await websocket.close()
            self.connected_clients.pop(client_ip, None)
            self.client_rooms.pop(client_ip, None)
            self.remote_hosts.pop(client_ip, None)
            logger.info(f"Client {client_ip} terminated successfully")
            return True
        except Exception as e:
            logger.error(f"Error terminating client {client_ip}: {e}")
            return False

    def get_client_ip_by_room(self, room):
        for ip, rooms in self.client_rooms.items():
            if room.lower() in [r.lower() for r in rooms]:
                return ip
        logger.warning(f"No client IP found for room: {room}")
        return None

    async def _send(self, client_ip, message):
        websocket = self.connected_clients.get(client_ip)
        if not websocket:
            logger.error(f"Client {client_ip} is not connected. Cannot send {message.get('type')}.")
            return False
        try:
            await websocket.send(json.dumps(message))
            return True
        except Exception as e:
            logger.error(f"Error sending {message.get('type')} to client {client_ip}: {e}")
            return False

    async def send_audio_command(self, room, command, data=None):
        """Send a command to the client covering `room`, or to all clients if room is None."""
        message = {"type": command, "data": data if data is not None else {}}
        if room is None:
            results = [await self._send(ip, message) for ip in list(self.connected_clients)]
            return all(results)
        message["room"] = room
        client_ip = self.get_client_ip_by_room(room)
        if not client_ip:
            logger.error(f"No connected client found for room: {room}. Cannot send {command}.")
            return False
        return await self._send(client_ip, message)

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
        audio_config = self.audio_manager.get_audio_config(effect_name)
        volume = audio_params.get('volume') or audio_config.get(
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
        music_files = [f for f in os.listdir('music') if f.endswith('.mp3')]
        return random.choice(music_files) if music_files else None

    async def start_background_music(self):
        await self._cancel_music_rotation()
        music_file = self.get_random_music_file()
        if not music_file:
            logger.error("No music files available for background music")
            return False
        success = await self.send_audio_command(None, 'start_background_music', {"music_file": music_file})
        if success:
            self.background_music_task = asyncio.create_task(self._rotate_background_music())
        return success

    async def _rotate_background_music(self):
        try:
            while True:
                await asyncio.sleep(300)  # New track every 5 minutes
                music_file = self.get_random_music_file()
                if not music_file:
                    break
                await self.send_audio_command(None, 'start_background_music', {"music_file": music_file})
        finally:
            self.background_music_task = None

    async def _cancel_music_rotation(self):
        if self.background_music_task is not None:
            self.background_music_task.cancel()
            try:
                await self.background_music_task
            except asyncio.CancelledError:
                pass
            self.background_music_task = None

    async def stop_background_music(self):
        await self._cancel_music_rotation()
        return await self.send_audio_command(None, 'stop_background_music', {})
