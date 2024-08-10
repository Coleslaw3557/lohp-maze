import json
import logging
import asyncio
import aiofiles
from websocket_handler import WebSocketHandler

logger = logging.getLogger(__name__)

class RemoteHostManager:
    def __init__(self, config_file='remote_host_config.json'):
        self.config_file = config_file
        self.remote_hosts = {}
        self.connected_clients = {}
        self.client_rooms = {}
        self.load_config()
        logger.info("RemoteHostManager initialized")

    def update_client_rooms(self, ip, rooms):
        self.client_rooms[ip] = rooms
        self.connected_clients[ip] = ip  # Store the IP as the WebSocket connection
        self.remote_hosts[ip] = {"name": f"Unit-{ip}", "rooms": rooms}
        self.save_config()
        logger.info(f"Updated associated rooms for client {ip}: {rooms}")
        for room in rooms:
            logger.info(f"Associating room {room} with client {ip}")

    def load_config(self):
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
                self.remote_hosts = config.get('remote_hosts', {})
            logger.info(f"Successfully loaded configuration from {self.config_file}")
            logger.info(f"Remote hosts configuration: {self.remote_hosts}")
        except FileNotFoundError:
            logger.error(f"Configuration file {self.config_file} not found.")
            self.remote_hosts = {}
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from {self.config_file}.")
            self.remote_hosts = {}

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
        websocket = self.get_host_by_room(room)
        if websocket:
            logger.info(f"Sending {command} command to room {room}")
            try:
                message = {
                    "type": command,
                    "data": audio_data.decode('utf-8') if audio_data else None
                }
                await websocket.send(json.dumps(message))
                logger.info(f"Successfully sent {command} command to room {room}")
                return True
            except Exception as e:
                logger.error(f"Error sending {command} command to room {room}: {str(e)}")
                return False
        else:
            logger.error(f"No connected client found for room: {room}. Cannot send {command} command.")
            logger.info(f"Connected clients: {list(self.connected_clients.keys())}")
            logger.info(f"Remote hosts configuration: {self.remote_hosts}")
            return False

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

    async def stream_audio_to_room(self, room, audio_file):
        host = self.get_host_by_room(room)
        if host:
            logger.info(f"Streaming audio file {audio_file} to room {room}")
            try:
                if isinstance(audio_file, str):
                    with open(audio_file, 'rb') as f:
                        audio_data = f.read()
                elif isinstance(audio_file, bool):
                    logger.error(f"Invalid audio_file parameter: {audio_file}")
                    return
                else:
                    audio_data = audio_file
                
                success = await self.send_audio_command(room, 'audio_start', audio_data)
                if not success:
                    logger.error(f"Failed to send audio command to room {room}")
            except IOError as e:
                logger.error(f"Error reading audio file {audio_file}: {str(e)}")
            except Exception as e:
                logger.error(f"Error streaming audio to room {room}: {str(e)}")
                await self.reconnect_and_retry(host, 'audio_start', audio_data)
        else:
            logger.warning(f"No remote host found for room: {room}. Cannot stream audio.")

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

    def save_config(self):
        try:
            with open(self.config_file, 'w') as f:
                json.dump({"remote_hosts": self.remote_hosts}, f, indent=4)
            logger.info(f"Configuration saved to {self.config_file}")
        except IOError:
            logger.error(f"Error writing to {self.config_file}")
