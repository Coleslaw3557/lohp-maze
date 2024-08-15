import json
import logging
import asyncio
import aiofiles
import websockets
import os
import time
import random
from websocket_handler import WebSocketHandler

logger = logging.getLogger(__name__)

from sync_manager import SyncManager

class RemoteHostManager:
    def __init__(self, audio_manager=None):
        self.remote_hosts = {}
        self.connected_clients = {}
        self.client_rooms = {}
        self.room_to_client_ip = {}
        self.prepared_audio = {}
        self.sync_manager = SyncManager()
        self.audio_sent_to_clients = {}
        self.client_ready_status = {}
        self.audio_manager = audio_manager
        logger.info("RemoteHostManager initialized")

    def get_connected_clients(self):
        return list(self.connected_clients.keys())

    def get_connected_clients_info(self):
        clients_info = []
        for client_ip, websocket in self.connected_clients.items():
            client_info = {
                'ip': client_ip,
                'rooms': self.client_rooms.get(client_ip, []),
                'name': self.remote_hosts.get(client_ip, {}).get('name', f'Client-{client_ip}')
            }
            clients_info.append(client_info)
        return clients_info

    async def play_audio_for_all_clients(self, effect_name, audio_params):
        audio_success = True
        for websocket in self.connected_clients.values():
            client_success = await self.send_audio_command_ws(websocket, 'play_effect_audio', {
                'effect_name': effect_name,
                'file_name': audio_params.get('file'),
                'volume': audio_params.get('volume', 1.0),
                'loop': audio_params.get('loop', False)
            })
            audio_success = audio_success and client_success
        return audio_success

    async def send_audio_command_ws(self, websocket, command, audio_data):
        try:
            message = {
                "type": command,
                "data": audio_data
            }
            await websocket.send(json.dumps(message))
            logger.info(f"Successfully sent {command} command to client")
            return True
        except Exception as e:
            logger.error(f"Error sending {command} command to client: {str(e)}")
            return False

    async def send_audio_command(self, client_ip, command, audio_data=None):
        if client_ip in self.connected_clients:
            websocket = self.connected_clients[client_ip]
            logger.info(f"Sending {command} command to client {client_ip}")
            try:
                message = {
                    "type": command,
                    "data": audio_data
                }
                await websocket.send(json.dumps(message))
                logger.info(f"Successfully sent {command} command to client {client_ip}")
                return True
            except Exception as e:
                logger.error(f"Error sending {command} command to client {client_ip}: {str(e)}")
        else:
            logger.error(f"Client {client_ip} is not connected. Cannot send {command} command.")
        return False

    def get_rooms_for_remote_unit(self, remote_unit):
        return self.client_rooms.get(remote_unit, [])

    def get_client_ip_by_room(self, room):
        if isinstance(room, list):
            rooms = room
        else:
            rooms = [room]
        
        for room in rooms:
            if room in self.room_to_client_ip:
                client_ips = self.room_to_client_ip[room]
                if client_ips:
                    return next(iter(client_ips))  # Return the first client IP associated with the room
        
        logger.warning(f"No client IP found for room(s): {rooms}")
        return None

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

    async def play_audio_in_room(self, rooms, effect_name, audio_params):
        if isinstance(rooms, str):
            rooms = [rooms]
        
        tasks = []
        for room in rooms:
            client_ip = self.get_client_ip_by_room(room)
            if not client_ip:
                logger.error(f"No client IP found for room: {room}")
                continue

            # Get the specific audio file for the effect
            audio_file = self.audio_manager.get_audio_file(effect_name)
            if not audio_file:
                logger.error(f"No audio file found for effect: {effect_name}")
                continue

            logger.info(f"Instructing client to play audio file '{audio_file}' for effect '{effect_name}' in room {room}")
            tasks.append(self.send_audio_command(room, 'play_effect_audio', {
                'effect_name': effect_name,
                'file_name': audio_file,
                'volume': audio_params.get('volume', 1.0),
                'loop': audio_params.get('loop', False)
            }))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            success = all(isinstance(result, bool) and result for result in results)
            return success
        else:
            logger.info(f"No audio tasks to execute for effect: {effect_name}")
            return True

    def update_client_rooms(self, unit_name, ip, rooms, websocket):
        client_ip = websocket.remote_address[0]  # Get the actual client IP
        self.client_rooms[client_ip] = rooms
        self.connected_clients[client_ip] = websocket  # Store the WebSocket object
        self.remote_hosts[client_ip] = {"name": unit_name, "rooms": rooms}
        logger.info(f"Updated associated rooms for client {unit_name} ({client_ip}): {rooms}")
        for room in rooms:
            logger.info(f"Associating room {room} with client {unit_name} ({client_ip})")
        
        # Update the reverse mapping of rooms to client IPs
        for room in rooms:
            if room not in self.room_to_client_ip:
                self.room_to_client_ip[room] = set()
            self.room_to_client_ip[room].add(client_ip)
        
        # Send the list of audio files to download
        self.send_audio_files_to_download(client_ip)

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

    async def send_audio_command(self, client_ip, command, audio_data=None):
        if client_ip in self.connected_clients:
            websocket = self.connected_clients[client_ip]
            logger.info(f"Sending {command} command to client {client_ip}")
            try:
                message = {
                    "type": command,
                    "data": audio_data
                }
                await websocket.send(json.dumps(message))
                logger.info(f"Successfully sent {command} command to client {client_ip}")
                return True
            except Exception as e:
                logger.error(f"Error sending {command} command to client {client_ip}: {str(e)}")
        else:
            logger.error(f"Client {client_ip} is not connected. Cannot send {command} command.")
        return False

    def update_client_rooms(self, unit_name, ip, rooms, websocket):
        client_ip = websocket.remote_address[0]  # Get the actual client IP
        self.client_rooms[client_ip] = rooms
        self.connected_clients[client_ip] = websocket  # Store the WebSocket object
        self.remote_hosts[client_ip] = {"name": unit_name, "rooms": rooms}
        logger.info(f"Updated associated rooms for client {unit_name} ({client_ip}): {rooms}")
        for room in rooms:
            logger.info(f"Associating room {room} with client {unit_name} ({client_ip})")
        
        # Send the list of audio files to download
        self.send_audio_files_to_download(client_ip)

    def send_audio_files_to_download(self, client_ip):
        audio_files = self.audio_manager.get_audio_files_to_download()
        message = {
            "type": "audio_files_to_download",
            "data": audio_files
        }
        websocket = self.connected_clients.get(client_ip)
        if websocket:
            asyncio.create_task(websocket.send(json.dumps(message)))
            logger.info(f"Sent list of audio files to download to client {client_ip}")
        else:
            logger.error(f"No WebSocket connection found for client {client_ip}")

    def get_client_ip_by_room(self, room):
        if isinstance(room, list):
            rooms = room
        else:
            rooms = [room]
        
        for room in rooms:
            for ip, client_rooms in self.client_rooms.items():
                if room.lower() in [r.lower() for r in client_rooms]:
                    return ip
            for ip, data in self.remote_hosts.items():
                if room.lower() in [r.lower() for r in data.get('rooms', [])]:
                    return ip
        
        logger.warning(f"No client IP found for room(s): {rooms}")
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

    # This method is not used and can be removed

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

    async def play_audio_in_room(self, rooms, effect_name, audio_params):
        if isinstance(rooms, str):
            rooms = [rooms]
        
        success = True
        for room in rooms:
            client_ip = self.get_client_ip_by_room(room)
            if not client_ip:
                logger.warning(f"No client IP found for room: {room}. Cannot play audio.")
                success = False
                continue

            audio_file = self.audio_manager.get_random_audio_file(effect_name)
            if not audio_file:
                logger.error(f"No audio file found for effect: {effect_name}")
                success = False
                continue

            logger.info(f"Instructing client to play audio for effect '{effect_name}' in room {room} (Client IP: {client_ip})")
            result = await self.send_audio_command(room, 'play_effect_audio', {
                'effect_name': effect_name,
                'file_name': os.path.basename(audio_file),
                'volume': audio_params.get('volume', 1.0),
                'loop': audio_params.get('loop', False)
            })
            success = success and result

        return success

    def __init__(self, audio_manager=None):
        self.remote_hosts = {}
        self.connected_clients = {}
        self.client_rooms = {}
        self.prepared_audio = {}
        self.sync_manager = SyncManager()
        self.audio_sent_to_clients = {}
        self.client_ready_status = {}
        self.audio_manager = audio_manager
        self.background_music_task = None
        logger.info("RemoteHostManager initialized")

    async def start_background_music(self):
        logger.info("Starting background music on all connected clients")
        if self.background_music_task is not None:
            logger.info("Background music task already running")
            return True

        success = True
        music_file = self.get_random_music_file()
        if not music_file:
            logger.error("No music files available for background music")
            return False
        
        message = {
            "type": "start_background_music",
            "data": {"music_file": music_file}
        }
        
        for client_ip, websocket in self.connected_clients.items():
            try:
                await websocket.send(json.dumps(message))
                logger.info(f"Successfully sent start_background_music command to client {client_ip}")
            except Exception as e:
                logger.error(f"Error starting background music for client {client_ip}: {str(e)}")
                success = False
        
        if success:
            self.background_music_task = asyncio.create_task(self.continue_background_music())
        return success

    def get_random_music_file(self):
        music_files = [f for f in os.listdir('music') if f.endswith('.mp3')]
        return random.choice(music_files) if music_files else None

    async def continue_background_music(self):
        try:
            while True:
                await asyncio.sleep(300)  # Wait for 5 minutes
                music_file = self.get_random_music_file()
                if music_file:
                    await self.start_background_music()
                else:
                    logger.warning("No music files available for background music")
                    break
        finally:
            self.background_music_task = None
            logger.info("Background music task ended")

    async def stop_background_music(self):
        logger.info("Stopping background music on all connected clients")
        success = True
        for client_ip in self.connected_clients:
            result = await self.send_audio_command(None, 'stop_background_music', {})
            success = success and result
        return success

    async def send_audio_command(self, room, command, data):
        if room is None:
            # If room is None, send the command to all connected clients
            success = True
            for client_ip, websocket in self.connected_clients.items():
                try:
                    message = {
                        "type": command,
                        "data": data if data is not None else {}
                    }
                    await websocket.send(json.dumps(message))
                    logger.info(f"Successfully sent {command} command to client {client_ip}")
                except Exception as e:
                    logger.error(f"Error sending {command} command to client {client_ip}: {str(e)}")
                    success = False
            return success
        else:
            client_ip = self.get_client_ip_by_room(room)
            if client_ip and client_ip in self.connected_clients:
                websocket = self.connected_clients[client_ip]
                logger.info(f"Sending {command} command for room {room} to client {client_ip}")
                try:
                    message = {
                        "type": command,
                        "room": room,
                        "data": data if data is not None else {}
                    }
                    await websocket.send(json.dumps(message))
                    
                    if command == 'audio_start' and isinstance(data, bytes):
                        await websocket.send(data)
                    
                    logger.info(f"Successfully sent {command} command for room {room} to client {client_ip}")
                    return True
                except Exception as e:
                    logger.error(f"Error sending {command} command for room {room} to client {client_ip}: {str(e)}")
            else:
                logger.error(f"No connected client found for room: {room}. Cannot send {command} command.")
            return False

    # This method is not used and can be removed

    # Configuration is now managed in memory, no need for save_config method
