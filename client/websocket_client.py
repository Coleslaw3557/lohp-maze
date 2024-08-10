import json
import logging
import websockets
import asyncio

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

    async def set_websocket(self, websocket):
        self.websocket = websocket
        await self.send_status_update("connected")

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
                await self.set_websocket(await websockets.connect(f"ws://{self.server_ip}:{self.server_port}"))
                logger.info("Reconnected to server")
                break
            except Exception as e:
                logger.error(f"Failed to reconnect: {e}")
                await asyncio.sleep(5)  # Wait before trying again

    async def handle_message(self, message):
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
        logger.info(f"Received effect trigger: {data}")
        # TODO: Implement effect trigger handling
