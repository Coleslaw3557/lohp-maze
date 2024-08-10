import json
import logging
from websocket_handler import WebSocketHandler

logger = logging.getLogger(__name__)

class RemoteHostManager:
    def __init__(self, config_file='remote_host_config.json'):
        self.config_file = config_file
        self.remote_hosts = self.load_config()
        self.websocket_handlers = {}

    def load_config(self):
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)['remote_hosts']
        except FileNotFoundError:
            logger.error(f"Configuration file {self.config_file} not found.")
            return {}
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from {self.config_file}.")
            return {}

    def initialize_websocket_connections(self):
        for ip, host_info in self.remote_hosts.items():
            self.websocket_handlers[ip] = WebSocketHandler(ip, host_info['name'])

    def get_host_by_room(self, room):
        for ip, host_info in self.remote_hosts.items():
            if room in host_info['rooms']:
                return self.websocket_handlers[ip]
        return None

    def send_audio_command(self, room, command, audio_data=None):
        host = self.get_host_by_room(room)
        if host:
            host.send_audio_command(command, audio_data)
        else:
            logger.warning(f"No remote host found for room: {room}")

    def handle_trigger_event(self, room, trigger):
        # Process trigger events from remote hosts
        logger.info(f"Trigger event received from room {room}: {trigger}")
        # Add logic to handle the trigger event (e.g., start an effect)
