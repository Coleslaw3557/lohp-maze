import asyncio
import logging
import websockets
from websocket_client import WebSocketClient
from audio_manager import AudioManager
from trigger_manager import TriggerManager
from config_manager import ConfigManager
from sync_manager import SyncManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    config = ConfigManager('config.json')
    audio_manager = AudioManager(config.get('cache_dir'))
    trigger_manager = TriggerManager(config.get('triggers'))
    sync_manager = SyncManager()
    
    ws_client = WebSocketClient(
        config.get('server_ip'),
        config.get('server_port'),
        config.get('unit_name'),
        audio_manager,
        trigger_manager,
        sync_manager
    )

    uri = f"ws://{config.get('server_ip')}:{config.get('server_port')}/ws"
    
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
    except KeyboardInterrupt:
        logger.info("Shutting down client...")
    finally:
        await ws_client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
