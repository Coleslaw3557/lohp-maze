import json
import logging
import asyncio
import aiofiles
import websockets
import os
from websocket_handler import WebSocketHandler

logger = logging.getLogger(__name__)

class RemoteHostManager:
    def __init__(self):
        self.remote_hosts = {}
        self.connected_clients = {}
        self.client_rooms = {}
        logger.info("RemoteHostManager initialized")

    def update_client_rooms(self, unit_name, ip, rooms, websocket, path):
        client_ip = websocket.remote_address[0]  # Get the actual client IP
        self.client_rooms[client_ip] = rooms
        self.connected_clients[client_ip] = websocket  # Store the WebSocket object
        self.remote_hosts[client_ip] = {"name": unit_name, "rooms": rooms}
        logger.info(f"Updated associated rooms for client {unit_name} ({client_ip}): {rooms}")
        for room in rooms:
            logger.info(f"Associating room {room} with client {unit_name} ({client_ip})")
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

    async def stream_audio_to_room(self, room, audio_file, audio_params):
        if not audio_file:
            logger.error(f"No audio file provided for room {room}")
            return

        client_ip = self.get_client_ip_by_room(room)
        if client_ip:
            logger.info(f"Streaming audio file to room {room} (Client IP: {client_ip})")
            try:
                audio_data = None
                file_name = 'stream.mp3'
                if isinstance(audio_file, str):
                    with open(audio_file, 'rb') as f:
                        audio_data = f.read()
                    file_name = os.path.basename(audio_file)
                elif isinstance(audio_file, bytes):
                    audio_data = audio_file
                else:
                    logger.error(f"Invalid audio_file parameter: {type(audio_file)}")
                    return
                
                if audio_data is None:
                    logger.error(f"No valid audio data for room {room}")
                    return

                success = await self.send_audio_command(room, 'audio_start', {
                    'file_name': file_name,
                    'volume': audio_params.get('volume', 1.0),
                    'loop': audio_params.get('loop', False)
                })
                if success:
                    await self.send_audio_command(room, 'audio_data', audio_data)
                    logger.info(f"Successfully streamed audio to room {room}")
                else:
                    logger.error(f"Failed to send audio command to room {room}")
            except IOError as e:
                logger.error(f"Error reading audio file: {str(e)}")
            except Exception as e:
                logger.error(f"Error streaming audio to room {room}: {str(e)}")
        else:
            logger.warning(f"No client IP found for room: {room}. Cannot stream audio.")

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
