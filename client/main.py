import asyncio
import logging
import websockets
import time
import sys
import traceback
from websocket_client import WebSocketClient
from audio_manager import AudioManager
from trigger_manager import TriggerManager
from config_manager import ConfigManager
from sync_manager import SyncManager

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    filename='client.log',
                    filemode='a')
logger = logging.getLogger(__name__)

# Add a stream handler to also log to console
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

def log_and_exit(error_message):
    logger.critical(f"Critical error: {error_message}")
    logger.critical(f"Traceback: {traceback.format_exc()}")
    sys.exit(1)

async def main():
    try:
        config = ConfigManager('config.json')
        audio_manager = AudioManager(config.get('cache_dir'), config)
        logger.info("Initializing AudioManager")
        await audio_manager.initialize()  # Initialize and download audio files
        logger.info("AudioManager initialization complete")
        trigger_manager = TriggerManager(config.get('triggers'))
        sync_manager = SyncManager()
        
        ws_client = WebSocketClient(
            config,
            audio_manager,
            trigger_manager,
            sync_manager
        )

        uri = f"ws://{config.get('server_ip')}:8765"
        max_retries = 5
        retry_delay = 5
        
        while True:
            for attempt in range(max_retries):
                try:
                    async with websockets.connect(uri) as websocket:
                        logger.info(f"Connected to WebSocket server at {uri}")
                        await ws_client.set_websocket(websocket)
                        await asyncio.gather(
                            ws_client.listen(),
                            trigger_manager.monitor_triggers(ws_client.send_trigger_event)
                        )
                except websockets.exceptions.WebSocketException as e:
                    logger.error(f"WebSocket connection error: {e}")
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (2 ** attempt)
                        logger.info(f"Attempting to reconnect in {wait_time} seconds... (Attempt {attempt + 1}/{max_retries})")
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"Failed to connect after {max_retries} attempts. Waiting for 60 seconds before trying again.")
                        await asyncio.sleep(60)
                        break
                except KeyboardInterrupt:
                    logger.info("Shutting down client...")
                    await ws_client.disconnect()
                    return
                except Exception as e:
                    logger.error(f"Unexpected error: {e}")
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (2 ** attempt)
                        logger.info(f"Attempting to reconnect in {wait_time} seconds... (Attempt {attempt + 1}/{max_retries})")
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"Failed to connect after {max_retries} attempts. Waiting for 60 seconds before trying again.")
                        await asyncio.sleep(60)
                        break

        await ws_client.disconnect()
    except Exception as e:
        log_and_exit(f"Unhandled exception in main: {str(e)}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        log_and_exit(f"Failed to run main: {str(e)}")
