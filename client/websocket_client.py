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
        self.connection_established = False
        self.connection_lock = asyncio.Lock()

    async def set_websocket(self, websocket):
        self.websocket = websocket
        if not self.connection_established:
            async with self.connection_lock:
                if not self.connection_established:
                    await self.send_client_connected()
                    await self.send_status_update("connected")
                    self.connection_established = True

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
                    self.connection_established = False
            else:
                logger.warning(f"Unexpected response type: {response_data.get('type')}")
        except asyncio.TimeoutError:
            logger.error("Timeout waiting for connection response")
            self.connection_established = False
        except Exception as e:
            logger.error(f"Error handling connection response: {str(e)}")
            self.connection_established = False

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
            'play_audio': self.handle_play_audio,
            'prepare_execution': self.handle_prepare_execution,
            'prepare_effect': self.handle_prepare_effect,
            'execute_effect': self.handle_execute_effect,
            'run_effect_all_rooms': self.handle_run_effect_all_rooms,
            'play_effect_audio': self.handle_play_effect_audio,
            'audio_files_to_download': self.handle_audio_files_to_download
        }

        message_type = message.get('type')
        handler = handlers.get(message_type)

        if handler:
            logger.info(f"Handling message type: {message_type}")
            await handler(message)
        elif message_type is None:
            logger.warning("Received message without 'type' field")
            await self.handle_typeless_message(message)
        else:
            logger.warning(f"Unknown message type received: {message_type}")

    async def handle_play_cached_audio(self, message):
        audio_data = message.get('data', {})
        effect_name = audio_data.get('effect_name')
        volume = audio_data.get('volume', 1.0)
        loop = audio_data.get('loop', False)
        if effect_name:
            await self.audio_manager.play_effect_audio(effect_name, volume, loop)
        else:
            logger.warning("Received play_cached_audio without effect_name")

    async def handle_audio_files_to_download(self, message):
        audio_files = message.get('data', [])
        logger.info(f"Received list of audio files to download: {audio_files}")
        await self.audio_manager.download_audio_files()

    async def handle_typeless_message(self, message):
        """
        Handle messages without a 'type' field.
        """
        logger.info(f"Handling typeless message: {message}")
        # Add any specific handling for typeless messages here
        if 'status' in message and 'message' in message:
            logger.info(f"Received status update: {message['status']} - {message['message']}")
        else:
            logger.warning("Unrecognized typeless message format")

    async def handle_prepare_execution(self, message):
        effect_id = message['effect_id']
        
        # Prepare for execution (e.g., load audio, prepare lighting sequences)
        await self.prepare_effect(effect_id)
        
        # Send ready signal
        ready_message = {
            "type": "client_ready",
            "effect_id": effect_id
        }
        await self.send_message(ready_message)
        logger.info(f"Sent client_ready message: {ready_message}")

    async def prepare_effect(self, effect_id):
        # Prepare audio and lighting for the effect
        await self.audio_manager.prepare_audio_for_effect(effect_id)
        # Add any other preparation steps here

    async def handle_play_audio(self, message):
        audio_data = message.get('data', {})
        effect_name = audio_data.get('effect_name')
        file_name = audio_data.get('file')
        
        if effect_name and file_name:
            await self.audio_manager.play_effect_audio(effect_name, file_name)
            logger.info(f"Playing audio for effect: {effect_name}, file: {file_name}")
        else:
            logger.warning(f"Received incomplete play_audio message: effect_name={effect_name}, file={file_name}")

    async def handle_prepare_effect(self, message):
        effect_id = message.get('effect_id')
        if effect_id:
            await self.prepare_effect(effect_id)
            logger.info(f"Prepared effect: {effect_id}")
        else:
            logger.warning("Received prepare_effect message without effect_id")

    async def handle_execute_effect(self, message):
        effect_id = message['effect_id']
        
        # Execute the effect immediately
        await self.execute_effect(effect_id)

    async def execute_effect(self, effect_id):
        # Trigger audio playback
        await self.audio_manager.play_prepared_audio()
        # Add any other effect execution steps here
        logger.info(f"Executed effect: {effect_id}")

    async def handle_run_effect_all_rooms(self, message):
        effect_name = message.get('effect_name')
        effect_id = message.get('effect_id')
        if effect_name and effect_id:
            await self.prepare_effect(effect_id)
            await self.execute_effect(effect_id)
            logger.info(f"Executed effect '{effect_name}' (ID: {effect_id}) for all rooms")
        else:
            logger.warning("Received incomplete run_effect_all_rooms message")

    async def handle_play_effect_audio(self, message):
        room = message.get('room')
        effect_name = message.get('data', {}).get('effect_name')
        if room in self.config.get('associated_rooms', []) and effect_name:
            await self.audio_manager.play_effect_audio(effect_name)
            logger.info(f"Playing effect audio for '{effect_name}' in room '{room}'")
        else:
            logger.warning(f"Received play_effect_audio command for unassociated room or missing effect name: {room}, {effect_name}")

    async def handle_sync_time(self, message):
        server_time = message.get('server_time')
        if server_time is not None:
            client_time = time.time()
            self.time_offset = server_time - client_time
            self.sync_manager.sync_time(server_time)
            logger.info(f"Time synchronized. Offset: {self.time_offset:.6f} seconds")
        else:
            logger.warning("Received sync_time message without server_time")

    async def handle_play_effect_audio(self, message):
        audio_data = message.get('data', {})
        file_name = audio_data.get('file_name')
        volume = audio_data.get('volume', 1.0)
        loop = audio_data.get('loop', False)
        if file_name:
            await self.audio_manager.play_effect_audio(file_name, volume, loop)
        else:
            logger.warning("Received play_effect_audio without file_name")
                        'loop': loop
                    }
                })
            else:
                logger.warning(f"No audio file found for effect: {effect_name}")
        else:
            logger.warning("Received play_effect_audio without effect_name")

    async def handle_audio_start(self, message):
        audio_data = message.get('data')
        if audio_data:
            file_name = audio_data.get('file_name')
            effect_name = audio_data.get('effect_name')
            volume = audio_data.get('volume', 1.0)
            loop = audio_data.get('loop', False)
            if file_name:
                await self.audio_manager.play_effect_audio(file_name, volume, loop)
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

    async def execute_effect(self, effect_id):
        try:
            logger.info(f"Executing effect: {effect_id}")
            # TODO: Implement effect execution
        except Exception as e:
            logger.error(f"Error executing effect {effect_id}: {str(e)}")

    async def execute_effect(self, effect_id):
        logger.info(f"Executing effect: {effect_id}")
        # TODO: Implement effect execution
