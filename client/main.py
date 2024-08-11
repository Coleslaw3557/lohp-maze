import asyncio
import logging
import websockets
import time
from websocket_client import WebSocketClient
from audio_manager import AudioManager
from trigger_manager import TriggerManager
from config_manager import ConfigManager
from sync_manager import SyncManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    config = ConfigManager('config.json')
    audio_manager = AudioManager(config.get('cache_dir'), config)
    await audio_manager.initialize()  # Initialize and download audio files
    trigger_manager = TriggerManager(config.get('triggers'))
    sync_manager = SyncManager()
    
    ws_client = WebSocketClient(
        config,
        audio_manager,
        trigger_manager,
        sync_manager
    )

    uri = f"ws://{config.get('server_ip')}:8765"
    
    while True:
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
            logger.info("Attempting to reconnect in 5 seconds...")
            await asyncio.sleep(5)
        except KeyboardInterrupt:
            logger.info("Shutting down client...")
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            logger.info("Attempting to reconnect in 5 seconds...")
            await asyncio.sleep(5)

    await ws_client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
