import asyncio
import logging
import websockets
import time
import sys
import traceback
import random
import RPi.GPIO as GPIO
import requests
from websocket_client import WebSocketClient
from audio_manager import AudioManager
from trigger_manager import TriggerManager
from config_manager import ConfigManager
from sync_manager import SyncManager

# Set up logging
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

# Set logging levels for specific modules
logging.getLogger('websockets').setLevel(logging.DEBUG)
logging.getLogger('asyncio').setLevel(logging.DEBUG)
logging.getLogger('aiohttp').setLevel(logging.DEBUG)
logging.getLogger('pydub').setLevel(logging.DEBUG)

# Ensure all loggers propagate to the root logger
for name in logging.root.manager.loggerDict:
    logging.getLogger(name).propagate = True
    logging.getLogger(name).setLevel(logging.DEBUG)

def log_and_exit(error_message):
    logger.critical(f"Critical error: {error_message}")
    logger.critical(f"Traceback: {traceback.format_exc()}")
    sys.exit(1)

def setup_gpio(config):
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    
    for trigger in config.get('triggers', []):
        if trigger['type'] == 'laser':
            GPIO.setup(trigger['tx_pin'], GPIO.OUT)
            GPIO.output(trigger['tx_pin'], GPIO.HIGH)  # Turn on laser
            GPIO.setup(trigger['rx_pin'], GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

def execute_action(action, server_ip):
    if action['type'] == 'curl':
        url = action['url'].replace('${server_ip}', server_ip)
        try:
            response = requests.request(
                action['method'],
                url,
                headers=action['headers'],
                json=action['data']
            )
            logger.info(f"Action executed: {response.status_code}")
        except Exception as e:
            logger.error(f"Error executing action: {str(e)}")

async def monitor_triggers(config):
    last_trigger_time = {}
    rate_limit = config.get('rate_limit', 5)
    
    while True:
        for trigger in config.get('triggers', []):
            if trigger['type'] == 'laser':
                current_state = GPIO.input(trigger['rx_pin'])
                trigger_name = trigger['name']
                
                if current_state == GPIO.LOW and trigger_name not in last_trigger_time:
                    current_time = time.time()
                    if trigger_name not in last_trigger_time or (current_time - last_trigger_time[trigger_name]) > rate_limit:
                        logger.info(f"Trigger activated: {trigger_name}")
                        execute_action(trigger['action'], config.get('server_ip'))
                        last_trigger_time[trigger_name] = current_time
                elif current_state == GPIO.HIGH:
                    last_trigger_time.pop(trigger_name, None)
        
        await asyncio.sleep(0.1)  # Check every 100ms

async def main():
    try:
        config = ConfigManager('config-unit-b.json')
        audio_manager = AudioManager(config.get('cache_dir'), config)
        logger.info("Initializing AudioManager")
        await audio_manager.initialize()  # Initialize and download audio files
        logger.info("AudioManager initialization complete")
        trigger_manager = TriggerManager(config.get('triggers', []))
        sync_manager = SyncManager()
        
        ws_client = WebSocketClient(
            config,
            audio_manager,
            trigger_manager,
            sync_manager
        )

        # Remove the setup_gpio call as it's now handled by TriggerManager

        # Background music is not started automatically
        logger.info("Background music is ready to be started manually")

        uri = f"ws://{config.get('server_ip')}:{config.get('server_port', 8765)}"
        
        async def handle_connection():
            try:
                logger.info(f"Attempting to connect to WebSocket server at {uri}")
                async with websockets.connect(uri) as websocket:
                    logger.info(f"Connected to WebSocket server at {uri}")
                    await ws_client.set_websocket(websocket)
                    logger.debug(f"WebSocket connection details: {websocket.remote_address}")
                    logger.info("Starting WebSocket listener and trigger monitor")
                    await asyncio.gather(
                        ws_client.listen(),
                        monitor_triggers(config)
                    )
            except websockets.exceptions.WebSocketException as e:
                logger.error(f"WebSocket connection error: {e}")
                logger.critical("Connection lost. Exiting process.")
                sys.exit(1)
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                logger.critical("Connection lost due to unexpected error. Exiting process.")
                sys.exit(1)

        async def run_background_tasks():
            while True:
                await sync_manager.sync_time_with_server()
                await asyncio.sleep(300)  # Sync every 5 minutes

        try:
            await asyncio.gather(
                handle_connection(),
                run_background_tasks()
            )
        except KeyboardInterrupt:
            logger.info("Shutting down client...")
        finally:
            await ws_client.disconnect()
            GPIO.cleanup()
    except Exception as e:
        log_and_exit(f"Unhandled exception in main: {str(e)}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        log_and_exit(f"Failed to run main: {str(e)}")
