import asyncio
import logging
import os
import sys
import traceback
import websockets
from websocket_client import WebSocketClient
from audio_manager import AudioManager
from config_manager import ConfigManager
# TriggerManager is imported lazily below: it needs the Pi GPIO stack,
# which is absent when running as an audio-only unit on a non-Pi host.

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)


def log_and_exit(error_message):
    logger.critical(f"Critical error: {error_message}")
    logger.critical(f"Traceback: {traceback.format_exc()}")
    sys.exit(1)


async def main():
    try:
        config_file = os.environ.get('UNIT_CONFIG', 'config-single-pi.json')
        config = ConfigManager(config_file)

        try:
            audio_manager = AudioManager(config.get('cache_dir'), config)
            await audio_manager.initialize()  # Download and preload audio files
        except ValueError as e:
            log_and_exit(f"Configuration error: {e}")

        trigger_manager = None
        if config.get('triggers'):
            from trigger_manager import TriggerManager
            trigger_manager = TriggerManager(config)
            await trigger_manager.setup()
            asyncio.create_task(trigger_manager.monitor_triggers())
            logger.info("Trigger monitoring started")
        else:
            logger.info("No triggers configured; running as audio-only unit")

        ws_client = WebSocketClient(config, audio_manager)
        uri = f"ws://{config.get('server_ip')}:{config.get('server_port', 8765)}"

        try:
            logger.info(f"Connecting to WebSocket server at {uri}")
            async with websockets.connect(uri) as websocket:
                await ws_client.set_websocket(websocket)
                await ws_client.listen()
        except Exception as e:
            logger.critical(f"WebSocket connection lost: {e}. Exiting process.")
            sys.exit(1)  # docker restart policy brings us back up
        finally:
            await ws_client.disconnect()
            if trigger_manager:
                trigger_manager.cleanup()
    except Exception as e:
        log_and_exit(f"Unhandled exception in main: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        log_and_exit(f"Failed to run main: {e}")
