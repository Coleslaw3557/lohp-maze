import json
import logging
from websocket_handler import WebSocketHandler

logger = logging.getLogger(__name__)

class RemoteHostManager:
    def __init__(self, config_file='remote_host_config.json'):
        self.config_file = config_file
        self.remote_hosts = self.load_config()
        self.websocket_handlers = {}
        logger.info("RemoteHostManager initialized")

    def load_config(self):
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)['remote_hosts']
            logger.info(f"Successfully loaded configuration from {self.config_file}")
            return config
        except FileNotFoundError:
            logger.error(f"Configuration file {self.config_file} not found.")
            return {}
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from {self.config_file}.")
            return {}

    def initialize_websocket_connections(self):
        logger.info("Initializing WebSocket connections")
        for ip, host_info in self.remote_hosts.items():
            self.websocket_handlers[ip] = WebSocketHandler(ip, host_info['name'])
            logger.debug(f"WebSocket handler created for {host_info['name']} ({ip})")
        logger.info(f"WebSocket connections initialized for {len(self.websocket_handlers)} hosts")

    def get_host_by_room(self, room):
        for ip, host_info in self.remote_hosts.items():
            if room in host_info['rooms']:
                logger.debug(f"Found host for room {room}: {host_info['name']} ({ip})")
                return self.websocket_handlers[ip]
        logger.warning(f"No host found for room: {room}")
        return None

    async def send_audio_command(self, room, command, audio_data=None):
        host = self.get_host_by_room(room)
        if host:
            logger.info(f"Sending {command} command to room {room}")
            await host.send_audio_command(command, audio_data)
        else:
            logger.warning(f"No remote host found for room: {room}. Cannot send {command} command.")

    def handle_trigger_event(self, room, trigger):
        logger.info(f"Trigger event received from room {room}: {trigger}")
        # Add logic to handle the trigger event (e.g., start an effect)
        # For example:
        # self.effect_manager.trigger_effect(room, trigger)
