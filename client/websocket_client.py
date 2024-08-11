import json
import logging
import websockets
import asyncio
import time

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
        self.time_offset = 0  # Time offset between client and server

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
        if isinstance(message, str):
            try:
                message = json.loads(message)
            except json.JSONDecodeError:
                logger.error("Received invalid JSON message")
                return

        if not message:
            logger.warning("Received empty message")
            return

        logger.info(f"Received message: {message}")

        handlers = {
            'audio_start': self.handle_audio_start,
            'audio_stop': self.handle_audio_stop,
            'play_cached_audio': self.handle_play_cached_audio,
            'sync_time': self.handle_sync_time,
            'effect_trigger': self.handle_effect_trigger,
            'connection_response': self.handle_connection_response,
            'status_update_response': self.handle_status_update_response,
            'prepare_audio': self.handle_prepare_audio,
            'play_audio': self.handle_play_audio,
            'prepare_execution': self.handle_prepare_execution
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

    async def handle_prepare_execution(self, message):
        effect_id = message['effect_id']
        server_execution_time = message['execution_time']
        
        # Prepare for execution (e.g., load audio, prepare lighting sequences)
        await self.prepare_effect(effect_id)
        
        # Send ready signal
        ready_message = {
            "type": "client_ready",
            "effect_id": effect_id
        }
        await self.send_message(ready_message)
        logger.info(f"Sent client_ready message: {ready_message}")
        
        # Calculate the local execution time
        local_execution_time = server_execution_time - self.time_offset
        
        # Add a small buffer time (e.g., 50ms) to account for processing differences
        buffer_time = 0.05
        adjusted_execution_time = local_execution_time + buffer_time
        
        # Wait for adjusted execution time
        await self.wait_for_execution(adjusted_execution_time)

    async def prepare_effect(self, effect_id):
        # Prepare audio and lighting for the effect
        await self.audio_manager.prepare_audio_for_effect(effect_id)
        # Add any other preparation steps here

    async def wait_for_execution(self, execution_time):
        current_time = time.time()
        wait_time = execution_time - current_time
        if wait_time > 0:
            await asyncio.sleep(wait_time)
        
        # Execute the effect
        await self.execute_effect()

    async def execute_effect(self):
        # Trigger audio playback
        await self.audio_manager.play_prepared_audio()
        # Add any other effect execution steps here

    async def handle_prepare_audio(self, message):
        audio_data = message.get('data', {})
        file_name = audio_data.get('file')
        if file_name:
            await self.audio_manager.prepare_audio(file_name, audio_data.get('params', {}))
        else:
            logger.warning("Received prepare_audio without file name")

    async def handle_play_audio(self, message):
        room = message.get('room')
        if room in self.config.get('associated_rooms', []):
            prepared_audio = self.audio_manager.prepared_audio
            if prepared_audio:
                file_name = next(iter(prepared_audio))
                await self.audio_manager.play_prepared_audio(file_name)
            else:
                logger.warning("No prepared audio found for playback")
        else:
            logger.warning(f"Received play_audio command for unassociated room: {room}")

    async def handle_sync_time(self, message):
        server_time = message.get('server_time')
        if server_time is not None:
            client_time = time.time()
            self.time_offset = server_time - client_time
            self.sync_manager.sync_time(server_time)
            logger.info(f"Time synchronized. Offset: {self.time_offset:.6f} seconds")
        else:
            logger.warning("Received sync_time message without server_time")

    async def handle_play_cached_audio(self, message):
        audio_data = message.get('data')
        if audio_data:
            effect_name = audio_data.get('effect_name')
            volume = audio_data.get('volume', 1.0)
            loop = audio_data.get('loop', False)
            if effect_name:
                await self.audio_manager.play_cached_audio(effect_name, volume, loop)
            else:
                logger.warning("Received play_cached_audio without effect_name")
        else:
            logger.warning("Received play_cached_audio without data")

    async def handle_audio_start(self, message):
        audio_data = message.get('data')
        if audio_data:
            file_name = audio_data.get('file_name')
            volume = audio_data.get('volume', 1.0)
            loop = audio_data.get('loop', False)
            if file_name:
                self.audio_manager.prepare_audio(file_name, volume, loop)
            else:
                logger.warning("Received audio_start without file_name")
        else:
            logger.warning("Received audio_start without data")

    async def listen(self):
        while True:
            try:
                message = await self.websocket.recv()
                if isinstance(message, str):
                    try:
                        data = json.loads(message)
                        await self.handle_message(data)
                    except json.JSONDecodeError:
                        logger.error("Received invalid JSON message")
                elif isinstance(message, bytes):
                    logger.info(f"Received audio data: {len(message)} bytes")
                    await self.audio_manager.receive_audio_data(message)
                else:
                    logger.warning(f"Received unknown message type: {type(message)}")
            except websockets.exceptions.ConnectionClosed:
                logger.error("WebSocket connection closed. Attempting to reconnect...")
                await self.reconnect()
            except Exception as e:
                logger.error(f"Error in WebSocket communication: {e}")
                await self.reconnect()

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
        effect_id = data.get('effect_id')
        execution_time = data.get('execution_time')
        
        if effect_id and execution_time:
            await self.prepare_effect(effect_id)
            await self.schedule_effect_execution(effect_id, execution_time)
        else:
            logger.warning("Received incomplete effect trigger data")

    async def prepare_effect(self, effect_id):
        # Prepare the effect (e.g., load audio, prepare lighting sequences)
        logger.info(f"Preparing effect: {effect_id}")
        # TODO: Implement effect preparation

    async def schedule_effect_execution(self, effect_id, execution_time):
        current_time = time.time()
        delay = max(0, execution_time - current_time)
        if delay > 0:
            logger.info(f"Scheduling effect {effect_id} to execute in {delay:.2f} seconds")
            await asyncio.sleep(delay)
        try:
            await self.execute_effect(effect_id)
        except Exception as e:
            logger.error(f"Error executing effect {effect_id}: {str(e)}")

    async def execute_effect(self, effect_id):
        logger.info(f"Executing effect: {effect_id}")
        # TODO: Implement effect execution
