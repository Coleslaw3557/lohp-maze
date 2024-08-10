import asyncio
import websockets
import json
import logging

logger = logging.getLogger(__name__)

class WebSocketHandler:
    def __init__(self, host_ip, host_name, port=8765):
        self.host_ip = host_ip
        self.host_name = host_name
        self.port = port
        self.websocket = None
        logger.info(f"WebSocketHandler initialized for {host_name} ({host_ip})")

    async def connect(self):
        try:
            self.websocket = await websockets.connect(f"ws://{self.host_ip}:{self.port}")
            logger.info(f"Connected to remote host: {self.host_name} ({self.host_ip})")
        except Exception as e:
            logger.error(f"Failed to connect to {self.host_name} ({self.host_ip}): {str(e)}")

    async def send_audio_command(self, command, audio_data=None):
        if not self.websocket:
            logger.info(f"No active connection. Attempting to connect to {self.host_name}")
            await self.connect()
        
        message = {
            "type": command,
            "data": audio_data
        }
        
        try:
            await self.websocket.send(json.dumps(message))
            logger.info(f"Sent {command} command to {self.host_name}")
        except Exception as e:
            logger.error(f"Failed to send {command} command to {self.host_name}: {str(e)}")

    async def receive_messages(self):
        while True:
            try:
                message = await self.websocket.recv()
                data = json.loads(message)
                if data['type'] == 'trigger_event':
                    logger.info(f"Received trigger event from {self.host_name}: {data['data']}")
                    # Add logic to process the trigger event
                    # For example:
                    # await self.process_trigger_event(data['data'])
                else:
                    logger.warning(f"Received unknown message type from {self.host_name}: {data['type']}")
            except websockets.exceptions.ConnectionClosed:
                logger.error(f"WebSocket connection closed for {self.host_name}. Attempting to reconnect...")
                await asyncio.sleep(5)  # Wait before trying to reconnect
                await self.connect()
            except json.JSONDecodeError:
                logger.error(f"Received invalid JSON from {self.host_name}")
            except Exception as e:
                logger.error(f"Error receiving message from {self.host_name}: {str(e)}")
                await asyncio.sleep(5)  # Wait before trying to reconnect
                await self.connect()

    async def process_trigger_event(self, event_data):
        # Implement the logic to process trigger events
        logger.info(f"Processing trigger event from {self.host_name}: {event_data}")
        # Add your event processing logic here
