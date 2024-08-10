import json
import logging
import websockets
import asyncio

logger = logging.getLogger(__name__)

class WebSocketClient:
    def __init__(self, config, audio_manager, trigger_manager, sync_manager):
        self.config = config
        self.server_ip = config.get('server_ip')
        self.server_port = int(config.get('server_port', 8765))  # Default to 8765 if None
        self.unit_name = config.get('unit_name')
        self.audio_manager = audio_manager
        self.trigger_manager = trigger_manager
        self.sync_manager = sync_manager
        self.websocket = None

    async def set_websocket(self, websocket):
        self.websocket = websocket
        await self.send_client_connected()
        await self.send_status_update("connected")

    async def send_client_connected(self):
        message = {
            "type": "client_connected",
            "data": {
                "unit_name": self.unit_name,
                "ip": self.server_ip,
                "associated_rooms": self.config.get('associated_rooms', [])
            }
        }
        await self.send_message(message)
        logger.info(f"Sent client_connected message: {message}")

    async def send_message(self, message):
        if self.websocket:
            await self.websocket.send(json.dumps(message))
        else:
            logger.warning("Cannot send message: WebSocket not connected")

    async def send_status_update(self, status):
        message = {
            "type": "status_update",
            "data": {
                "unit_name": self.unit_name,
                "status": status
            }
        }
        await self.send_message(message)

    async def send_trigger_event(self, trigger_name):
        message = {
            "type": "trigger_event",
            "data": {
                "unit_name": self.unit_name,
                "trigger": trigger_name
            }
        }
        await self.send_message(message)

    async def disconnect(self):
        if self.websocket:
            await self.websocket.close()
            logger.info("Disconnected from server")

    async def listen(self):
        while True:
            try:
                message = await self.websocket.recv()
                if message is None:
                    logger.warning("Received None message from server")
                    continue
                await self.handle_message(json.loads(message))
            except json.JSONDecodeError:
                logger.error("Received invalid JSON from server")
            except websockets.exceptions.ConnectionClosed:
                logger.error("WebSocket connection closed. Attempting to reconnect...")
                await self.reconnect()
            except Exception as e:
                logger.error(f"Error in WebSocket communication: {e}")
                await self.reconnect()

    async def reconnect(self):
        while True:
            try:
                uri = f"ws://{self.server_ip}:{self.server_port}"
                logger.info(f"Attempting to reconnect to {uri}")
                websocket = await websockets.connect(uri, ping_interval=20, ping_timeout=20)
                await self.set_websocket(websocket)
                logger.info("Reconnected to server")
                break
            except Exception as e:
                logger.error(f"Failed to reconnect: {e}")
                logger.info("Retrying in 5 seconds...")
                await asyncio.sleep(5)  # Wait before trying again

    async def handle_message(self, message):
        if not message:
            logger.warning("Received empty message")
            return

        logger.info(f"Received message: {message}")

        handlers = {
            'audio_start': self.handle_audio_start,
            'audio_stop': self.handle_audio_stop,
            'sync_time': self.sync_manager.sync_time,
            'effect_trigger': self.handle_effect_trigger,
            'connection_response': self.handle_connection_response,
            'status_update': self.handle_status_update
        }

        message_type = message.get('type')
        handler = handlers.get(message_type)

        if handler:
            logger.info(f"Handling message type: {message_type}")
            await handler(message)
        else:
            logger.warning(f"Unknown message type received: {message_type}")

    async def handle_audio_start(self, message):
        room = message.get('room')
        if room in self.config.get('associated_rooms', []):
            await self.audio_manager.start_audio(message.get('data'))
        else:
            logger.warning(f"Received audio_start for unassociated room: {room}")

    async def handle_audio_stop(self, message):
        room = message.get('room')
        if room in self.config.get('associated_rooms', []):
            await self.audio_manager.stop_audio()
        else:
            logger.warning(f"Received audio_stop for unassociated room: {room}")

    async def handle_connection_response(self, data):
        logger.info(f"Received connection response: {data}")

    async def handle_status_update(self, data):
        logger.info(f"Received status update: {data}")

    async def handle_effect_trigger(self, data):
        logger.info(f"Received effect trigger: {data}")
        # TODO: Implement effect trigger handling
