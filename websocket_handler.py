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

    async def connect(self):
        try:
            self.websocket = await websockets.connect(f"ws://{self.host_ip}:{self.port}")
            logger.info(f"Connected to remote host: {self.host_name} ({self.host_ip})")
        except Exception as e:
            logger.error(f"Failed to connect to {self.host_name} ({self.host_ip}): {str(e)}")

    async def send_audio_command(self, command, audio_data=None):
        if not self.websocket:
            await self.connect()
        
        message = {
            "type": command,
            "data": audio_data
        }
        
        try:
            await self.websocket.send(json.dumps(message))
            logger.info(f"Sent {command} command to {self.host_name}")
        except Exception as e:
            logger.error(f"Failed to send command to {self.host_name}: {str(e)}")

    async def receive_messages(self):
        while True:
            try:
                message = await self.websocket.recv()
                data = json.loads(message)
                if data['type'] == 'trigger_event':
                    # Handle trigger event
                    logger.info(f"Received trigger event from {self.host_name}: {data['data']}")
                    # Add logic to process the trigger event
            except Exception as e:
                logger.error(f"Error receiving message from {self.host_name}: {str(e)}")
                await asyncio.sleep(5)  # Wait before trying to reconnect
                await self.connect()
