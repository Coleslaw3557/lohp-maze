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
                "associated_rooms": self.config.get('associated_rooms', [])
            }
        }
        await self.send_message(message)
        logger.info(f"Sent client_connected message: {message}")
        
        # Wait for and handle the connection response
        try:
            response = await asyncio.wait_for(self.websocket.recv(), timeout=5.0)
            response_data = json.loads(response)
            if response_data.get('type') == 'connection_response':
                logger.info(f"Received connection response: {response_data}")
                if response_data.get('status') == 'success':
                    logger.info("Connection acknowledged by server")
                else:
                    logger.error(f"Connection error: {response_data.get('message')}")
            else:
                logger.warning(f"Unexpected response type: {response_data.get('type')}")
        except asyncio.TimeoutError:
            logger.error("Timeout waiting for connection response")
        except Exception as e:
            logger.error(f"Error handling connection response: {str(e)}")

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
        max_retries = 5
        retry_delay = 5
        for attempt in range(max_retries):
            try:
                uri = f"ws://{self.server_ip}:{self.server_port}"
                logger.info(f"Attempting to reconnect to {uri} (Attempt {attempt + 1}/{max_retries})")
                websocket = await websockets.connect(uri, ping_interval=20, ping_timeout=20)
                await self.set_websocket(websocket)
                logger.info("Reconnected to server")
                return True
            except Exception as e:
                logger.error(f"Failed to reconnect: {e}")
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    logger.info(f"Retrying in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error("Max retries reached. Unable to reconnect.")
        return False

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
            'status_update_response': self.handle_status_update_response
        }

        message_type = message.get('type')
        handler = handlers.get(message_type)

        if handler:
            logger.info(f"Handling message type: {message_type}")
            await handler(message)
        elif message_type is None:
            logger.warning("Received message without 'type' field")
        else:
            logger.warning(f"Unknown message type received: {message_type}")

    async def handle_audio_start(self, message):
        audio_data = message.get('data')
        if audio_data:
            audio_file = audio_data.get('audio_file')
            if audio_file:
                await self.audio_manager.start_audio(audio_data, audio_file)
            else:
                logger.warning("Received audio_start without audio_file")
        else:
            logger.warning("Received audio_start without data")

    async def handle_audio_stop(self, message):
        room = message.get('room')
        if room in self.config.get('associated_rooms', []):
            await self.audio_manager.stop_audio()
        else:
            logger.warning(f"Received audio_stop for unassociated room: {room}")

    async def handle_connection_response(self, data):
        logger.info(f"Received connection response: {data}")

    async def handle_status_update_response(self, data):
        logger.info(f"Received status update response: {data}")

    async def handle_effect_trigger(self, data):
        logger.info(f"Received effect trigger: {data}")
        # TODO: Implement effect trigger handling
