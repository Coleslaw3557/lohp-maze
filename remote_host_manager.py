import json
import logging
import asyncio
import aiofiles
import websockets
import os
import time
from websocket_handler import WebSocketHandler

logger = logging.getLogger(__name__)

from sync_manager import SyncManager

class RemoteHostManager:
    def __init__(self):
        self.remote_hosts = {}
        self.connected_clients = {}
        self.client_rooms = {}
        self.prepared_audio = {}
        self.sync_manager = SyncManager()
        self.audio_sent_to_clients = {}
        self.client_ready_status = {}
        logger.info("RemoteHostManager initialized")

    def clear_audio_sent_to_clients(self):
        self.audio_sent_to_clients.clear()
        logger.info("Cleared audio sent to clients tracking")

    async def notify_clients_of_execution(self, effect_id):
        connected_clients = [client for client in self.connected_clients if self.is_client_connected(client)]
        
        # Send execute message immediately
        execute_message = {
            "type": "execute_effect",
            "effect_id": effect_id
        }
        await self.broadcast_message(execute_message)
        
        logger.info(f"Notified all clients to execute effect {effect_id}")
        return True

    def is_client_connected(self, client):
        return client in self.connected_clients and self.connected_clients[client].open

    async def broadcast_message(self, message):
        for websocket in self.connected_clients.values():
            await websocket.send(json.dumps(message))

    def set_client_ready(self, effect_id, client_ip):
        if effect_id in self.client_ready_status and client_ip in self.client_ready_status[effect_id]:
            self.client_ready_status[effect_id][client_ip].set()
            logger.info(f"Client {client_ip} ready for effect {effect_id}")
        else:
            logger.warning(f"Received ready status for unknown client {client_ip} or effect {effect_id}")

    async def trigger_audio_playback(self, room, effect_name):
        client_ip = self.get_client_ip_by_room(room)
        if client_ip:
            return await self.send_audio_command(room, 'play_effect_audio', {'effect_name': effect_name})
        else:
            logger.error(f"No client IP found for room: {room}")
            return False

    async def prepare_audio_stream(self, room, audio_file, audio_params, effect_name):
        client_ip = self.get_client_ip_by_room(room)
        if client_ip:
            self.prepared_audio[client_ip] = {
                'file': audio_file,
                'params': audio_params,
                'effect_name': effect_name
            }
            await self.send_audio_command(room, 'prepare_audio', self.prepared_audio[client_ip])
        else:
            logger.error(f"No client IP found for room: {room}")

    async def play_prepared_audio(self, room):
        client_ip = self.get_client_ip_by_room(room)
        if client_ip and client_ip in self.prepared_audio:
            success = await self.send_audio_command(room, 'play_audio', {})
            if success:
                del self.prepared_audio[client_ip]
            return success
        else:
            logger.error(f"No prepared audio found for room: {room}")
            return False

    def update_client_rooms(self, unit_name, ip, rooms, websocket, path):
        client_ip = websocket.remote_address[0]  # Get the actual client IP
        self.client_rooms[client_ip] = rooms
        self.connected_clients[client_ip] = websocket  # Store the WebSocket object
        self.remote_hosts[client_ip] = {"name": unit_name, "rooms": rooms}
        logger.info(f"Updated associated rooms for client {unit_name} ({client_ip}): {rooms}")
        for room in rooms:
            logger.info(f"Associating room {room} with client {unit_name} ({client_ip})")
            # Ensure each room is associated with a client IP
            if room not in self.room_to_client_ip:
                self.room_to_client_ip[room] = client_ip
            else:
                logger.warning(f"Room {room} is already associated with another client. Updating to {client_ip}")
                self.room_to_client_ip[room] = client_ip
        logger.debug(f"WebSocket path: {path}")  # Log the path for debugging

    async def initialize_websocket_connections(self):
        logger.info("WebSocket connections will be initialized when clients connect")

    def get_host_by_room(self, room):
        for ip, rooms in self.client_rooms.items():
            if room.lower() in [r.lower() for r in rooms]:
                logger.debug(f"Found host for room {room}: {ip}")
                if ip in self.connected_clients:
                    return self.connected_clients[ip]
                else:
                    logger.warning(f"Host found for room {room}, but not connected: {ip}")
                    return None
        logger.warning(f"No host configuration found for room: {room}")
        return None

    async def send_audio_command(self, room, command, audio_data=None):
        client_ip = self.get_client_ip_by_room(room)
        if client_ip:
            if client_ip in self.connected_clients:
                websocket = self.connected_clients[client_ip]
                logger.info(f"Sending {command} command for room {room} to client {client_ip}")
                try:
                    if command == 'audio_start':
                        message = {
                            "type": command,
                            "room": room,
                            "data": {
                                "file_name": "audio.mp3",
                                "volume": 1.0,
                                "loop": False
                            }
                        }
                        await websocket.send(json.dumps(message))
                        if isinstance(audio_data, bytes):
                            await websocket.send(audio_data)
                    elif command == 'audio_data':
                        if isinstance(audio_data, bytes):
                            await websocket.send(audio_data)
                        else:
                            logger.error(f"Invalid audio data type for {command} command")
                            return False
                    else:
                        message = {
                            "type": command,
                            "room": room,
                            "data": audio_data
                        }
                        await websocket.send(json.dumps(message))
                    
                    logger.info(f"Successfully sent {command} command for room {room} to client {client_ip}")
                    return True
                except Exception as e:
                    logger.error(f"Error sending {command} command for room {room} to client {client_ip}: {str(e)}")
            else:
                logger.error(f"Client {client_ip} for room {room} is not connected. Cannot send {command} command.")
        else:
            logger.error(f"No client IP found for room: {room}. Cannot send {command} command.")
        return False

    def update_client_rooms(self, unit_name, ip, rooms, websocket):
        client_ip = websocket.remote_address[0]  # Get the actual client IP
        self.client_rooms[client_ip] = rooms
        self.connected_clients[client_ip] = websocket  # Store the WebSocket object
        self.remote_hosts[client_ip] = {"name": unit_name, "rooms": rooms}
        logger.info(f"Updated associated rooms for client {unit_name} ({client_ip}): {rooms}")
        for room in rooms:
            logger.info(f"Associating room {room} with client {unit_name} ({client_ip})")

    def get_client_ip_by_room(self, room):
        for ip, rooms in self.client_rooms.items():
            if room.lower() in [r.lower() for r in rooms]:
                return ip
        for ip, data in self.remote_hosts.items():
            if room.lower() in [r.lower() for r in data.get('rooms', [])]:
                return ip
        logger.warning(f"No client IP found for room: {room}")
        return None

    def is_client_connected(self, client):
        return client in self.connected_clients and self.connected_clients[client].open

    async def reconnect_websocket(self, room):
        ip = self.get_ip_by_room(room)
        if ip:
            try:
                uri = f"ws://{ip}:8765"
                websocket = await websockets.connect(uri)
                self.connected_clients[ip] = websocket
                logger.info(f"Reconnected WebSocket for room {room}")
            except Exception as e:
                logger.error(f"Failed to reconnect WebSocket for room {room}: {str(e)}")

    def get_ip_by_room(self, room):
        for ip, data in self.remote_hosts.items():
            if room in data.get('rooms', []):
                return ip
        return None

    async def reconnect_and_retry(self, host, command, audio_data):
        max_retries = 3
        for attempt in range(max_retries):
            logger.info(f"Attempting to reconnect to {host.host_name} (Attempt {attempt + 1}/{max_retries})")
            await host.connect()
            if host.websocket:
                logger.info(f"Reconnected to {host.host_name}. Retrying command.")
                try:
                    success = await host.send_audio_command(command, audio_data)
                    if success:
                        return True
                    else:
                        logger.error(f"Failed to send command after reconnection (Attempt {attempt + 1}/{max_retries})")
                except Exception as e:
                    logger.error(f"Error sending command after reconnection: {str(e)}")
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
        logger.error(f"Failed to reconnect to {host.host_name} after {max_retries} attempts")
        return False

    def handle_trigger_event(self, room, trigger):
        logger.info(f"Trigger event received from room {room}: {trigger}")
        # Add logic to handle the trigger event (e.g., start an effect)
        # For example:
        # self.effect_manager.trigger_effect(room, trigger)

    async def stream_audio_to_room(self, room, audio_file, audio_params, effect_name):
        if not audio_file:
            logger.error(f"No audio file provided for room {room}")
            return False

        client_ip = self.get_client_ip_by_room(room)
        if not client_ip:
            logger.warning(f"No client IP found for room: {room}. Cannot stream audio.")
            return False

        logger.info(f"Streaming audio file to room {room} (Client IP: {client_ip})")
        try:
            # Check if this client has already received the audio for this effect
            if client_ip not in self.audio_sent_to_clients:
                self.audio_sent_to_clients[client_ip] = set()
            
            if effect_name in self.audio_sent_to_clients[client_ip]:
                logger.info(f"Audio for effect '{effect_name}' already sent to client {client_ip}. Instructing client to play cached audio.")
                return await self.send_audio_command(room, 'play_cached_audio', {
                    'effect_name': effect_name,
                    'volume': audio_params.get('volume', 1.0),
                    'loop': audio_params.get('loop', False)
                })

            audio_data = await self._get_audio_data(audio_file)
            if not audio_data:
                logger.error(f"Failed to get audio data for file: {audio_file}")
                return False

            file_name = self._get_file_name(audio_file)

            # Send audio_start command
            success = await self.send_audio_command(room, 'audio_start', {
                'file_name': file_name,
                'effect_name': effect_name,
                'volume': audio_params.get('volume', 1.0),
                'loop': audio_params.get('loop', False)
            })
            if not success:
                logger.error(f"Failed to send audio_start command to client {client_ip} for room {room}")
                return False

            logger.info(f"Sent audio_start command for {file_name} to room {room}")
            await asyncio.sleep(0.1)  # Add a small delay before sending audio data

            # Send audio data
            websocket = self.connected_clients.get(client_ip)
            if websocket:
                try:
                    await websocket.send(audio_data)
                    logger.info(f"Successfully streamed audio data ({len(audio_data)} bytes) to client {client_ip} for room {room}")
                    self.audio_sent_to_clients[client_ip].add(effect_name)
                    return True
                except Exception as e:
                    logger.error(f"Failed to send audio data to client {client_ip} for room {room}: {str(e)}")
                    return False
            else:
                logger.error(f"No WebSocket connection found for client {client_ip}")
                return False
        except Exception as e:
            logger.error(f"Error streaming audio to client {client_ip} for room {room}: {str(e)}")
            return False

    async def _get_audio_data(self, audio_file):
        if isinstance(audio_file, str):
            try:
                async with aiofiles.open(audio_file, 'rb') as f:
                    return await f.read()
            except IOError as e:
                logger.error(f"Error reading audio file: {str(e)}")
        elif isinstance(audio_file, bytes):
            return audio_file
        elif audio_file is True:  # Handle the case where audio_file is a boolean
            logger.warning("Audio file is True, but no actual file provided")
            return None
        else:
            logger.error(f"Invalid audio_file parameter: {type(audio_file)}")
        return None

    def _get_file_name(self, audio_file):
        if isinstance(audio_file, str):
            return os.path.basename(audio_file)
        return 'stream.mp3'

    async def send_audio_command(self, room, command, data):
        client_ip = self.get_client_ip_by_room(room)
        if client_ip:
            if client_ip in self.connected_clients:
                websocket = self.connected_clients[client_ip]
                logger.info(f"Sending {command} command for room {room} to client {client_ip}")
                try:
                    if command == 'audio_start':
                        message = {
                            "type": command,
                            "room": room,
                            "data": {
                                "file_name": "audio.mp3",
                                "volume": 1.0,
                                "loop": False
                            }
                        }
                        await websocket.send(json.dumps(message))
                        if isinstance(data, bytes):
                            await websocket.send(data)
                    elif command == 'audio_data':
                        await websocket.send(data)
                        logger.info(f"Sent audio data for room {room} to client {client_ip}")
                    else:
                        message = {
                            "type": command,
                            "room": room,
                            "data": data
                        }
                        await websocket.send(json.dumps(message))
                    
                    logger.info(f"Successfully sent {command} command for room {room} to client {client_ip}")
                    return True
                except Exception as e:
                    logger.error(f"Error sending {command} command for room {room} to client {client_ip}: {str(e)}")
            else:
                logger.error(f"Client {client_ip} for room {room} is not connected. Cannot send {command} command.")
        else:
            logger.error(f"No client IP found for room: {room}. Cannot send {command} command.")
        return False

    async def reconnect_and_retry(self, host, command, audio_data):
        max_retries = 3
        for attempt in range(max_retries):
            logger.info(f"Attempting to reconnect to {host.host_name} (Attempt {attempt + 1}/{max_retries})")
            await host.connect()
            if host.websocket:
                logger.info(f"Reconnected to {host.host_name}. Retrying command.")
                try:
                    await host.send_audio_command(command, audio_data)
                    return
                except Exception as e:
                    logger.error(f"Failed to send command after reconnection: {str(e)}")
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
        logger.error(f"Failed to reconnect to {host.host_name} after {max_retries} attempts")

    # Configuration is now managed in memory, no need for save_config method
