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
        logger.info(f"Attempting to connect to server at {uri}")
        try:
            logger.debug(f"WebSocket connection parameters: ping_interval=20, ping_timeout=20, extra_headers={{'Client-Type': 'RemoteUnit'}}")
            self.websocket = await websockets.connect(
                uri,
                ping_interval=20,
                ping_timeout=20,
                extra_headers={
                    "Client-Type": "RemoteUnit",
                },
                max_size=None  # Allow unlimited message size
            )
            logger.info(f"Successfully connected to server at {uri}")
            await self.send_status_update("connected")
        except websockets.exceptions.InvalidStatusCode as e:
            logger.error(f"Failed to connect to server: Invalid status code {e.status_code}")
            logger.debug(f"Server response headers: {e.headers}")
            logger.debug(f"Exception details: {str(e)}")
            try:
                response_text = await e.response.text()
                logger.debug(f"Server response body: {response_text}")
            except Exception as text_error:
                logger.debug(f"Unable to get response text: {str(text_error)}")
            self.websocket = None
        except Exception as e:
            logger.error(f"Failed to connect to server: {e}")
            logger.debug(f"Exception details: {type(e).__name__}: {str(e)}")
            self.websocket = None  # Ensure websocket is None if connection fails
        
    async def reconnect(self):
        logger.info("Attempting to reconnect...")
        await self.connect()
        if self.websocket:
            logger.info("Reconnected successfully")
        else:
            logger.error("Reconnection failed")
        
    async def send_status_update(self, status):
        if self.websocket:
            message = {
                "type": "status_update",
                "data": {
                    "unit_name": self.unit_name,
                    "status": status
                }
            }
            await self.websocket.send(json.dumps(message))
        else:
            logger.warning("Cannot send status update: WebSocket not connected")
        
    async def send_status_update(self, status):
        if self.websocket:
            message = {
                "type": "status_update",
                "data": {
                    "unit_name": self.unit_name,
                    "status": status
                }
            }
            await self.websocket.send(json.dumps(message))
        else:
            logger.warning("Cannot send status update: WebSocket not connected")

    async def disconnect(self):
        if self.websocket:
            await self.websocket.close()
            logger.info("Disconnected from server")

    async def listen(self):
        while True:
            if self.websocket is None:
                logger.warning("No active WebSocket connection. Attempting to reconnect...")
                await self.reconnect()
                if self.websocket is None:
                    await asyncio.sleep(5)
                    continue

            try:
                message = await self.websocket.recv()
                await self.handle_message(json.loads(message))
            except websockets.exceptions.ConnectionClosed:
                logger.warning("Connection to server closed. Attempting to reconnect...")
                await self.reconnect()
            except json.JSONDecodeError:
                logger.error("Received invalid JSON from server")
            except Exception as e:
                logger.error(f"Error in WebSocket communication: {e}")
                await self.reconnect()
            
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
