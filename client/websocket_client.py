import asyncio
import websockets
import json
import logging

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

    async def connect(self):
        uri = f"ws://{self.server_ip}:{self.server_port}/ws"
        try:
            self.websocket = await websockets.connect(uri)
            logger.info(f"Connected to server at {uri}")
            await self.send_status_update("connected")
        except Exception as e:
            logger.error(f"Failed to connect to server: {e}")
            self.websocket = None  # Ensure websocket is None if connection fails

    async def disconnect(self):
        if self.websocket:
            await self.websocket.close()
            logger.info("Disconnected from server")

    async def listen(self):
        while True:
            if self.websocket is None:
                logger.warning("No active WebSocket connection. Attempting to connect...")
                await self.connect()
                if self.websocket is None:
                    await asyncio.sleep(5)
                    continue

            try:
                message = await self.websocket.recv()
                await self.handle_message(json.loads(message))
            except websockets.exceptions.ConnectionClosed:
                logger.warning("Connection to server closed. Attempting to reconnect...")
                self.websocket = None
            except Exception as e:
                logger.error(f"Error in WebSocket communication: {e}")
                self.websocket = None
            
            if self.websocket is None:
                await asyncio.sleep(5)

    async def handle_message(self, message):
        if message['type'] == 'audio_start':
            await self.audio_manager.start_audio(message['data'])
        elif message['type'] == 'audio_stop':
            await self.audio_manager.stop_audio()
        elif message['type'] == 'sync_time':
            self.sync_manager.sync_time(message['data'])
        elif message['type'] == 'effect_trigger':
            # Handle effect trigger if applicable
            pass

    async def send_status_update(self, status):
        message = {
            "type": "status_update",
            "data": {
                "unit_name": self.unit_name,
                "status": status
            }
        }
        await self.websocket.send(json.dumps(message))

    async def send_trigger_event(self, trigger_name):
        message = {
            "type": "trigger_event",
            "data": {
                "unit_name": self.unit_name,
                "trigger": trigger_name
            }
        }
        await self.websocket.send(json.dumps(message))
