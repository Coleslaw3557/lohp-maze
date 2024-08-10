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
        self.websocket_handlers = {}
        self.load_config()
        logger.info("RemoteHostManager initialized")

    def load_config(self):
        try:
            with open(self.config_file, 'r') as f:
                self.remote_hosts = json.load(f)['remote_hosts']
            logger.info(f"Successfully loaded configuration from {self.config_file}")
            logger.info(f"Remote hosts configuration: {self.remote_hosts}")
        except FileNotFoundError:
            logger.error(f"Configuration file {self.config_file} not found.")
            self.remote_hosts = {}
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from {self.config_file}.")
            self.remote_hosts = {}

    async def initialize_websocket_connections(self):
        logger.info("Initializing WebSocket connections")
        for ip, host_info in self.remote_hosts.items():
            self.websocket_handlers[ip] = WebSocketHandler(ip, host_info['name'])
            await self.websocket_handlers[ip].connect()
            logger.debug(f"WebSocket handler created and connected for {host_info['name']} ({ip})")
        logger.info(f"WebSocket connections initialized for {len(self.websocket_handlers)} hosts")

    def get_host_by_room(self, room):
        for ip, host_info in self.remote_hosts.items():
            if room.lower() in [r.lower() for r in host_info['rooms']]:
                logger.debug(f"Found host for room {room}: {host_info['name']} ({ip})")
                return self.websocket_handlers[ip]
        logger.warning(f"No host found for room: {room}")
        return None

    async def send_audio_command(self, room, command, audio_data=None):
        host = self.get_host_by_room(room)
        if host:
            logger.info(f"Sending {command} command to room {room}")
            try:
                await host.send_audio_command(command, audio_data)
            except Exception as e:
                logger.error(f"Error sending {command} command to room {room}: {str(e)}")
                await self.reconnect_and_retry(host, command, audio_data)
        else:
            logger.warning(f"No remote host found for room: {room}. Cannot send {command} command.")

    async def reconnect_and_retry(self, host, command, audio_data):
        logger.info(f"Attempting to reconnect to {host.host_name}")
        await host.connect()
        if host.websocket:
            logger.info(f"Reconnected to {host.host_name}. Retrying command.")
            await host.send_audio_command(command, audio_data)
        else:
            logger.error(f"Failed to reconnect to {host.host_name}")

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
                
                await self.send_audio_command(room, 'audio_start', audio_data)
            except IOError as e:
                logger.error(f"Error reading audio file {audio_file}: {str(e)}")
            except Exception as e:
                logger.error(f"Error streaming audio to room {room}: {str(e)}")
        else:
            logger.warning(f"No remote host found for room: {room}. Cannot stream audio.")

    def save_config(self):
        try:
            with open(self.config_file, 'w') as f:
                json.dump({"remote_hosts": self.remote_hosts}, f, indent=4)
            logger.info(f"Configuration saved to {self.config_file}")
        except IOError:
            logger.error(f"Error writing to {self.config_file}")
