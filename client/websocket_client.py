import json
import logging
import time
import os
import sys
import asyncio
import websockets

logger = logging.getLogger(__name__)


class WebSocketClient:
    def __init__(self, config, audio_manager):
        self.config = config
        self.unit_name = config.get('unit_name')
        self.audio_manager = audio_manager
        self.websocket = None
        self.connection_established = False

    async def set_websocket(self, websocket):
        self.websocket = websocket
        if not self.connection_established:
            await self.send_client_connected()
            await self.send_status_update("connected")
            self.connection_established = True

    async def send_client_connected(self):
        await self.send_message({
            "type": "client_connected",
            "data": {
                "unit_name": self.unit_name,
                "associated_rooms": self.config.get('associated_rooms', [])
            }
        })
        try:
            response = await asyncio.wait_for(self.websocket.recv(), timeout=5.0)
            response_data = json.loads(response)
            if response_data.get('status') == 'success':
                logger.info("Connection acknowledged by server")
            else:
                logger.error(f"Connection error: {response_data.get('message')}")
                self.connection_established = False
        except asyncio.TimeoutError:
            logger.error("Timeout waiting for connection response")
            self.connection_established = False
        except Exception as e:
            logger.error(f"Error handling connection response: {e}")
            self.connection_established = False

    async def send_message(self, message):
        if self.websocket:
            await self.websocket.send(json.dumps(message))
        else:
            logger.warning("Cannot send message: WebSocket not connected")

    async def send_status_update(self, status):
        await self.send_message({
            "type": "status_update",
            "data": {"unit_name": self.unit_name, "status": status}
        })

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
                logger.critical("WebSocket connection closed. Exiting so the container restarts.")
                sys.exit(1)
            except Exception as e:
                logger.error(f"Error in WebSocket communication: {e}")

    async def handle_message(self, message):
        message_type = message.get('type')
        # Audio commands run inline so they execute strictly in arrival order:
        # a stop must never overtake the play it was meant to stop (the server
        # sends stop-old + play-new back to back on every effect takeover).
        # None of them block: playback-start confirmation runs in the background.
        ordered_handlers = {
            'play_effect_audio': self.handle_play_effect_audio,
            'audio_stop': self.handle_audio_stop,
            'start_background_music': self.handle_start_background_music,
            'stop_background_music': self.handle_stop_background_music,
            'connection_response': self.handle_ack,
            'status_update_response': self.handle_ack,
        }
        # Long-running work must not block the receive loop
        background_handlers = {
            'audio_files_to_download': self.handle_audio_files_to_download,
            'shutdown': self.handle_shutdown,
        }
        if message_type in ordered_handlers:
            await ordered_handlers[message_type](message)
        elif message_type in background_handlers:
            asyncio.create_task(background_handlers[message_type](message))
        else:
            logger.warning(f"Unhandled message: {message}")

    async def handle_ack(self, message):
        logger.info(f"Server response: {message}")

    async def handle_play_effect_audio(self, message):
        room = message.get('room')
        audio_data = message.get('data', {})
        effect_name = audio_data.get('effect_name')
        file_name = audio_data.get('file_name')

        if room is not None and not self.audio_manager.zones_for_room(room):
            logger.warning(f"Received play_effect_audio for unassociated room: {room}")
            return
        if not file_name:
            logger.warning(f"Received play_effect_audio without file_name for effect '{effect_name}'")
            return

        try:
            success = await self.audio_manager.play_effect_audio(
                file_name, audio_data.get('volume', 1.0), audio_data.get('loop', False), room=room)
            if not success:
                logger.error(f"Failed to play audio file '{file_name}' for effect '{effect_name}'")
        except Exception:
            logger.exception(f"Error playing audio file '{file_name}' for effect '{effect_name}'")

    async def handle_audio_stop(self, message):
        room = message.get('room')
        if room is None or self.audio_manager.zones_for_room(room):
            self.audio_manager.stop_audio(room)
        else:
            logger.warning(f"Received audio_stop for unassociated room: {room}")

    async def handle_audio_files_to_download(self, message):
        logger.info("Server sent list of audio files to download")
        await self.audio_manager.download_audio_files()

    async def handle_start_background_music(self, message):
        music_file = message.get('data', {}).get('music_file')
        if music_file:
            await self.audio_manager.start_background_music(music_file)
        else:
            logger.error("Received start_background_music without a music file")

    async def handle_stop_background_music(self, message):
        await self.audio_manager.stop_background_music()

    async def handle_shutdown(self, message):
        logger.info("Received shutdown command from server")
        shutdown_time = message.get('shutdown_time')
        if shutdown_time:
            await asyncio.sleep(max(0, shutdown_time - time.time()))
        await self.disconnect()
        logger.info("Shutting down host system...")
        # Power off the host from inside the privileged container
        os.system('echo o > /proc/sysrq-trigger')
