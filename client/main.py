import asyncio
import logging
import websockets
import time
import sys
import traceback
import random
import RPi.GPIO as GPIO
import requests
import threading
from concurrent.futures import ThreadPoolExecutor
import asyncio
import os
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

# Remove the setup_gpio function as it's now in trigger_manager.py

def execute_action(action, server_ip):
    if action['type'] == 'curl':
        url = action['url'].replace('${server_ip}', server_ip)
        try:
            # Use a separate thread to execute the request
            def make_request():
                response = requests.request(
                    action['method'],
                    url,
                    headers=action['headers'],
                    json=action['data']
                )
                logger.info(f"Action executed: {response.status_code}")
            
            threading.Thread(target=make_request).start()
        except Exception as e:
            logger.error(f"Error executing action: {str(e)}")

# Remove the monitor_triggers_thread function as it's now handled by TriggerManager

async def monitor_triggers(config, trigger_queue):
    # This function is kept for compatibility, but it's not used anymore
    pass

async def process_triggers(trigger_queue, config):
    while True:
        try:
            trigger_name, action = await trigger_queue.get()
            execute_action(action, config.get('server_ip'))
        except Exception as e:
            logger.error(f"Error processing trigger: {str(e)}")
        await asyncio.sleep(0.01)

async def main():
    try:
        config_file = os.environ.get('UNIT_CONFIG', 'config-unit-a.json')
        config = ConfigManager(config_file)
        try:
            audio_manager = AudioManager(config.get('cache_dir'), config)
            logger.info("Initializing AudioManager")
            await audio_manager.initialize()  # Initialize and download audio files
            logger.info("AudioManager initialization complete")
        except ValueError as e:
            log_and_exit(f"Configuration error: {str(e)}")
        
        # Initialize TriggerManager with the new setup
        trigger_manager = TriggerManager(config)
        logger.info(f"TriggerManager initialized with configuration from config file")
        await trigger_manager.setup()  # New setup method that includes ADC setup
        logger.info("TriggerManager setup completed")
        
        # Start monitoring triggers
        asyncio.create_task(trigger_manager.monitor_triggers(lambda name: execute_action(trigger_manager.get_action(name), config.get('server_ip'))))
        logger.info("Started trigger monitoring task")

        sync_manager = SyncManager()
        
        ws_client = WebSocketClient(
            config,
            audio_manager,
            trigger_manager,
            sync_manager
        )

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
                    logger.info("Starting WebSocket listener")
                    await ws_client.listen()
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
            trigger_manager.cleanup()
    except Exception as e:
        log_and_exit(f"Unhandled exception in main: {str(e)}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        log_and_exit(f"Failed to run main: {str(e)}")
