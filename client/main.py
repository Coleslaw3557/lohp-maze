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

def monitor_triggers_thread(config, trigger_manager):
    last_trigger_time = {}
    rate_limit = config.get('rate_limit', 5)
    startup_delay = 10  # 10 seconds startup delay
    start_time = time.time()
    
    while True:
        current_time = time.time()
        if current_time - start_time < startup_delay:
            time.sleep(0.1)  # Sleep for 100ms during startup delay
            continue
        
        for trigger in config.get('triggers', []):
            if trigger['type'] == 'laser':
                current_state = GPIO.input(trigger['rx_pin'])
                trigger_name = trigger['name']
                
                if current_state == GPIO.LOW:
                    if trigger_name not in last_trigger_time or (current_time - last_trigger_time[trigger_name]) > rate_limit:
                        logger.info(f"Laser beam broken: {trigger_name} (TX: GPIO{trigger['tx_pin']}, RX: GPIO{trigger['rx_pin']})")
                        execute_action(trigger['action'], config.get('server_ip'))
                        last_trigger_time[trigger_name] = current_time
                elif current_state == GPIO.HIGH:
                    # Only remove from last_trigger_time if it's been more than rate_limit seconds
                    if trigger_name in last_trigger_time and (current_time - last_trigger_time[trigger_name]) > rate_limit:
                        last_trigger_time.pop(trigger_name, None)
                        logger.debug(f"Laser beam restored: {trigger_name} (TX: GPIO{trigger['tx_pin']}, RX: GPIO{trigger['rx_pin']})")
            elif trigger['type'] == 'adc':
                asyncio.run(trigger_manager.check_adc_trigger(trigger, lambda name: execute_action(trigger['action'], config.get('server_ip')), current_time))
        
        time.sleep(0.01)  # Check every 10ms

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
        trigger_manager = TriggerManager(config)
        logger.info(f"TriggerManager initialized with configuration from config file")
        await trigger_manager.setup_adc()  # Ensure ADC is set up asynchronously
        logger.info("ADC setup completed")
        
        # Start the continuous ADC reading task
        asyncio.create_task(trigger_manager.read_adc_continuously())
        logger.info("Started continuous ADC reading task")

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
        
        # Start the GPIO monitoring in a separate thread
        executor = ThreadPoolExecutor(max_workers=1)
        monitor_future = executor.submit(monitor_triggers_thread, config)

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
            executor.shutdown(wait=False)
            GPIO.cleanup()
    except Exception as e:
        log_and_exit(f"Unhandled exception in main: {str(e)}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        log_and_exit(f"Failed to run main: {str(e)}")
