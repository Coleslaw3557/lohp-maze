import asyncio
import websockets
import json
import logging
from websockets.exceptions import ConnectionClosed

logger = logging.getLogger(__name__)

class WebSocketClient:
    def __init__(self, server_ip, server_port, unit_name, audio_manager, trigger_manager, sync_manager):
        self.server_ip = server_ip
        self.server_port = server_port
        self.unit_name = unit_name
        self.audio_manager = audio_manager
        self.trigger_manager = trigger_manager
        self.sync_manager = sync_manager
        self.websocket = None
        self.reconnect_interval = 5  # seconds

    async def connect(self):
        """
        Establish a WebSocket connection to the server.
        """
        uri = f"ws://{self.server_ip}:{self.server_port}/ws"
        logger.info(f"Attempting to connect to server at {uri}")
        try:
            self.websocket = await websockets.connect(
                uri,
                ping_interval=20,
                ping_timeout=20,
                max_size=None  # Allow unlimited message size
            )
            logger.info(f"Successfully connected to server at {uri}")
            await self.send_status_update("connected")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to server: {e}")
            return False

    async def reconnect(self):
        """
        Attempt to reconnect to the server.
        """
        while True:
            logger.info("Attempting to reconnect...")
            if await self.connect():
                logger.info("Reconnected successfully")
                break
            else:
                logger.error("Reconnection failed")
                await asyncio.sleep(self.reconnect_interval)

    async def send_message(self, message):
        """
        Send a message to the server.
        """
        if self.websocket and not self.websocket.closed:
            try:
                await self.websocket.send(json.dumps(message))
            except Exception as e:
                logger.error(f"Error sending message: {e}")
                await self.reconnect()
        else:
            logger.warning("Cannot send message: WebSocket not connected")
            await self.reconnect()

    async def send_status_update(self, status):
        """
        Send a status update to the server.
        """
        message = {
            "type": "status_update",
            "data": {
                "unit_name": self.unit_name,
                "status": status
            }
        }
        await self.send_message(message)

    async def send_trigger_event(self, trigger_name):
        """
        Send a trigger event to the server.
        """
        message = {
            "type": "trigger_event",
            "data": {
                "unit_name": self.unit_name,
                "trigger": trigger_name
            }
        }
        await self.send_message(message)

    async def disconnect(self):
        """
        Disconnect from the server.
        """
        if self.websocket:
            await self.websocket.close()
            logger.info("Disconnected from server")

    async def listen(self):
        """
        Listen for incoming messages from the server.
        """
        while True:
            try:
                if not self.websocket or self.websocket.closed:
                    await self.reconnect()
                    continue

                message = await self.websocket.recv()
                await self.handle_message(json.loads(message))
            except ConnectionClosed:
                logger.warning("Connection to server closed. Attempting to reconnect...")
                await self.reconnect()
            except json.JSONDecodeError:
                logger.error("Received invalid JSON from server")
            except Exception as e:
                logger.error(f"Error in WebSocket communication: {e}")
                await self.reconnect()

    async def handle_message(self, message):
        """
        Handle incoming messages from the server.
        """
        handlers = {
            'audio_start': self.audio_manager.start_audio,
            'audio_stop': self.audio_manager.stop_audio,
            'sync_time': self.sync_manager.sync_time,
            'effect_trigger': self.handle_effect_trigger
        }

        message_type = message.get('type')
        handler = handlers.get(message_type)

        if handler:
            await handler(message.get('data'))
        else:
            logger.warning(f"Unknown message type received: {message_type}")

    async def handle_effect_trigger(self, data):
        """
        Handle effect trigger messages.
        """
        # TODO: Implement effect trigger handling
        logger.info(f"Received effect trigger: {data}")
