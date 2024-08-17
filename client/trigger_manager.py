import asyncio
import logging
import time
import random
import board
import busio
import RPi.GPIO as GPIO
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
import aiohttp
import threading

logger = logging.getLogger(__name__)

class TriggerManager:
    def __init__(self, config):
        self.config = config
        self.associated_rooms = config.get('associated_rooms', [])
        self.triggers = [trigger for trigger in config.get('triggers', []) if not trigger.get('room') or trigger.get('room') in self.associated_rooms]
        self.log_trigger_info()

        GPIO.setmode(GPIO.BCM)
        self.start_time = time.time()
        self.cooldown_period = self.config.get('cooldown_period', 5)
        self.startup_delay = self.config.get('startup_delay', 10)
        self.trigger_cooldowns = {}
        self.laser_states = {}  # To keep track of laser beam states
        self.laser_tx_pins = []  # To store all laser transmitter pins
        self.laser_thread = None

        # Constants for detection
        self.COOLDOWN_TIME = 0.2
        self.CONNECTED_THRESHOLD = 0.5
        self.PIEZO_THRESHOLD = 2.0
        self.KNOCK_THRESHOLD = 2.5
        self.VOLTAGE_CHANGE_THRESHOLD = 0.5
        self.DEBUG_THRESHOLD = 0.1
        self.BUTTON_DEBOUNCE_TIME = 0.1

        self.adc_config = self.determine_adc_config()
        self.setup_piezo()
        self.setup_triggers()
        self.initialize_filters()
        self.start_laser_thread()  # Start the laser maintenance thread

    async def setup(self):
        await self.setup_adc()

    def log_trigger_info(self):
        logger.info(f"Associated rooms: {self.associated_rooms}")
        logger.info(f"Filtered triggers for associated rooms: {len(self.triggers)}")
        for trigger in self.triggers:
            logger.info(f"Trigger: {trigger['name']}, Type: {trigger['type']}, Room: {trigger.get('room', 'Not specified')}")

    def determine_adc_config(self):
        adc_config = {}
        for trigger in self.triggers:
            if trigger['type'] in ['adc', 'piezo']:
                adc_address = trigger.get('adc_address', '0x48')
                if adc_address not in adc_config:
                    adc_config[adc_address] = []
                adc_config[adc_address].append(trigger)
        return adc_config

    def setup_piezo(self):
        if any(trigger['type'] == 'piezo' for trigger in self.triggers):
            self.piezo_attempts = 0
            self.piezo_settings = self.config.get('piezo_settings', {
                'attempts_required': 3,
                'correct_answer_probability': 0.25
            })
        else:
            self.piezo_attempts = None
            self.piezo_settings = None

    def setup_triggers(self):
        self.active_triggers = []
        for trigger in self.triggers:
            if trigger['type'] == 'laser':
                self.setup_laser_trigger(trigger)
            elif trigger['type'] == 'gpio':
                self.setup_gpio_trigger(trigger)
            elif trigger['type'] in ['adc', 'piezo']:
                logger.info(f"ADC/Piezo trigger registered: {trigger['name']}, Room: {trigger.get('room', 'Not specified')}")
                self.active_triggers.append(trigger)
            else:
                logger.warning(f"Unknown trigger type for {trigger['name']}: {trigger['type']}")
        logger.info(f"Set up {len(self.active_triggers)} triggers for associated rooms: {self.associated_rooms}")

    def setup_laser_trigger(self, trigger):
        GPIO.setup(trigger['tx_pin'], GPIO.OUT)
        GPIO.output(trigger['tx_pin'], GPIO.HIGH)  # Turn on laser
        GPIO.setup(trigger['rx_pin'], GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        logger.info(f"Laser trigger set up: {trigger['name']}, TX pin {trigger['tx_pin']} (ON), RX pin {trigger['rx_pin']}, Room: {trigger.get('room', 'Not specified')}")
        self.active_triggers.append(trigger)
        self.laser_states[trigger['name']] = GPIO.input(trigger['rx_pin'])  # Initialize laser state
        self.laser_tx_pins.append(trigger['tx_pin'])  # Add TX pin to the list

    def keep_lasers_on(self):
        while True:
            for pin in self.laser_tx_pins:
                GPIO.output(pin, GPIO.HIGH)
            time.sleep(0.01)  # Small delay to prevent excessive CPU usage

    def start_laser_thread(self):
        self.laser_thread = threading.Thread(target=self.keep_lasers_on, daemon=True)
        self.laser_thread.start()

    def setup_gpio_trigger(self, trigger):
        if 'pin' in trigger:
            GPIO.setup(trigger['pin'], GPIO.IN, pull_up_down=GPIO.PUD_UP)
            logger.info(f"GPIO trigger set up: {trigger['name']}, pin {trigger['pin']}, Room: {trigger.get('room', 'Not specified')}")
            self.active_triggers.append(trigger)
        else:
            logger.warning(f"GPIO trigger {trigger['name']} is missing 'pin' configuration")

    async def setup_adc(self):
        if not self.adc_config:
            logger.info("No ADC triggers configured, skipping ADC setup")
            return

        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            self.ads_devices = {}
            self.adc_channels = {}

            for adc_address, triggers in self.adc_config.items():
                self.ads_devices[adc_address] = ADS.ADS1115(i2c, address=int(adc_address, 16))
                ads = self.ads_devices[adc_address]

                for trigger in triggers:
                    channel = trigger.get('channel')
                    if channel is not None:
                        sensor_channel = AnalogIn(ads, getattr(ADS, f'P{channel}'))
                        self.adc_channels[trigger['name']] = {
                            'channel': sensor_channel,
                            'type': trigger['type'],
                            'last_trigger_time': 0,
                            'last_value': 0
                        }
                        logger.info(f"Set up {trigger['type']} channel for {trigger['name']} on address {adc_address}, channel {channel}")
                    else:
                        logger.error(f"No channel specified for trigger: {trigger['name']}. Skipping this trigger.")

            logger.info("ADC setup completed for configured triggers")
            logger.info(f"ADC devices: {list(self.ads_devices.keys())}")
            logger.info(f"ADC channels: {list(self.adc_channels.keys())}")

            await asyncio.sleep(2)  # Allow ADC readings to stabilize

            for name, channel_info in self.adc_channels.items():
                try:
                    voltage = channel_info['channel'].voltage
                    logger.info(f"Initial reading for {name} ({channel_info['type']}): {voltage:.3f}V")
                except Exception as e:
                    logger.error(f"Error reading initial value for {name}: {str(e)}")

        except Exception as e:
            logger.error(f"Error setting up ADC: {str(e)}")
            self.ads_devices = {}
            self.adc_channels = {}

        asyncio.create_task(self.read_adc_continuously())

    def initialize_filters(self):
        self.filters = {}
        for trigger in self.triggers:
            if trigger['type'] in ['adc', 'piezo']:
                self.filters[trigger['name']] = {'last_voltage': 0, 'last_trigger': 0}
        logger.info("Filters initialized for configured triggers")

    async def monitor_triggers(self, callback):
        asyncio.create_task(self.read_adc_continuously())

        while True:
            current_time = time.time()
            if current_time - self.start_time < self.startup_delay:
                await asyncio.sleep(0.1)
                continue

            tasks = []
            for trigger in self.active_triggers:
                if trigger['type'] == 'laser':
                    tasks.append(self.check_laser_trigger(trigger, lambda name: callback(self.get_action(name)), current_time))
                elif trigger['type'] == 'gpio':
                    tasks.append(self.check_gpio_trigger(trigger, lambda name: callback(self.get_action(name)), current_time))
                elif trigger['type'] == 'piezo':
                    tasks.append(self.check_piezo_trigger(trigger, lambda name: callback(self.get_action(name)), current_time))
                elif trigger['type'] == 'adc':
                    tasks.append(self.check_adc_trigger(trigger, lambda name: callback(self.get_action(name)), current_time))

            await asyncio.gather(*tasks)
            await asyncio.sleep(0.01)

    async def read_adc_continuously(self):
        while True:
            current_time = time.time()
            tasks = []
            for trigger in self.triggers:
                if trigger['type'] in ['adc', 'piezo']:
                    channel_info = self.adc_channels.get(trigger['name'])
                    if channel_info:
                        tasks.append(self.read_and_check_adc(trigger, channel_info, current_time))
            await asyncio.gather(*tasks)
            await asyncio.sleep(0.05)

    async def read_and_check_adc(self, trigger, channel_info, current_time):
        try:
            voltage = channel_info['channel'].voltage
            await self.check_adc_trigger(trigger, self.trigger_effect, current_time)
        except Exception as e:
            logger.error(f"Error reading ADC for {trigger['name']}: {str(e)}")

    async def check_laser_trigger(self, trigger, callback, current_time):
        rx_state = GPIO.input(trigger['rx_pin'])
        trigger_name = trigger['name']
        
        if trigger_name not in self.laser_states:
            self.laser_states[trigger_name] = rx_state
            return  # Initialize state without triggering

        previous_state = self.laser_states[trigger_name]
        self.laser_states[trigger_name] = rx_state

        if previous_state == GPIO.HIGH and rx_state == GPIO.LOW:  # Laser beam was intact and is now broken
            if self.check_trigger_cooldown(trigger_name, current_time):
                logger.info(f"Laser beam broken: {trigger_name}")
                self.set_trigger_cooldown(trigger_name, current_time)
                if callback:
                    result = callback(trigger_name)
                    if asyncio.iscoroutine(result):
                        await result
                else:
                    logger.warning(f"No callback provided for trigger: {trigger_name}")
        elif previous_state == GPIO.LOW and rx_state == GPIO.HIGH:  # Laser beam was broken and is now intact
            logger.info(f"Laser beam restored: {trigger_name}")
            self.trigger_cooldowns.pop(trigger_name, None)

    async def check_gpio_trigger(self, trigger, callback, current_time):
        # Implementation for GPIO trigger check
        pass

    async def check_piezo_trigger(self, trigger, callback, current_time):
        channel_info = self.adc_channels.get(trigger['name'])
        if not channel_info:
            return

        try:
            voltage = channel_info['channel'].voltage
            if voltage > self.PIEZO_THRESHOLD:
                if self.check_trigger_cooldown(trigger['name'], current_time):
                    logger.info(f"Piezo triggered: {trigger['name']}")
                    self.set_trigger_cooldown(trigger['name'], current_time)
                    await self.handle_piezo_trigger(trigger, callback)
        except Exception as e:
            logger.error(f"Error checking piezo trigger {trigger['name']}: {str(e)}")

    async def check_adc_trigger(self, trigger, callback, current_time):
        channel_info = self.adc_channels.get(trigger['name'])
        if channel_info is None:
            return

        try:
            voltage = channel_info['channel'].voltage
            button_status = self.get_button_status(voltage)

            if button_status == "Button pressed":
                if self.check_trigger_cooldown(trigger['name'], current_time):
                    logger.info(f"Button pressed: {trigger['name']}")
                    self.set_trigger_cooldown(trigger['name'], current_time)
                    await callback(trigger['name'])
            elif button_status == "Button not pressed":
                self.trigger_cooldowns.pop(trigger['name'], None)
        except Exception as e:
            logger.error(f"Error reading ADC for {trigger['name']}: {str(e)}")

    def get_button_status(self, voltage):
        if voltage < 0.1:
            return "Button pressed"
        elif voltage > 3.0:
            return "Button not pressed"
        else:
            return None

    def check_trigger_cooldown(self, trigger_name, current_time):
        last_trigger_time, _ = self.trigger_cooldowns.get(trigger_name, (0, False))
        return current_time - last_trigger_time > self.cooldown_period

    def set_trigger_cooldown(self, trigger_name, current_time):
        self.trigger_cooldowns[trigger_name] = (current_time, True)

    async def handle_piezo_trigger(self, trigger, callback):
        self.piezo_attempts += 1
        logger.info(f"Piezo trigger {trigger['name']} activated. Attempt {self.piezo_attempts}")

        if self.piezo_attempts >= self.piezo_settings['attempts_required']:
            if random.random() < self.piezo_settings['correct_answer_probability']:
                effect_name = "CorrectAnswer"
                self.piezo_attempts = 0
            else:
                effect_name = "WrongAnswer"
        else:
            effect_name = "WrongAnswer"

        logger.info(f"Triggering effect: {effect_name}")
        action_data = trigger['action']['data'].copy()
        action_data['effect_name'] = effect_name
        try:
            await callback(trigger['name'])
            logger.info(f"Successfully triggered effect: {effect_name}")
        except Exception as e:
            logger.error(f"Failed to trigger effect {effect_name}: {str(e)}")

        if effect_name == "WrongAnswer" and self.piezo_attempts >= self.piezo_settings['attempts_required']:
            self.piezo_attempts = 0

    def is_associated_room(self, room):
        return room in self.associated_rooms

    def cleanup(self):
        GPIO.cleanup()
        logger.info("GPIO cleanup completed")

    async def trigger_effect(self, trigger_name):
        trigger = next((t for t in self.triggers if t['name'] == trigger_name), None)
        if not trigger:
            logger.error(f"No trigger found with name: {trigger_name}")
            return

        action = trigger.get('action')
        if not action:
            logger.error(f"No action defined for trigger: {trigger_name}")
            return

        if action['type'] == 'curl':
            await self.execute_curl_action(trigger, action)
        else:
            logger.error(f"Unsupported action type for trigger {trigger_name}: {action['type']}")

    def get_action(self, trigger_name):
        for trigger in self.triggers:
            if trigger['name'] == trigger_name:
                return trigger.get('action')
        logger.warning(f"No action found for trigger: {trigger_name}")
        return None

    async def execute_curl_action(self, trigger, action):
        url = action['url'].replace('${server_ip}', self.config.get('server_ip'))
        headers = action.get('headers', {})
        data = action.get('data', {})
        max_retries = 3
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.request(action['method'], url, headers=headers, json=data, timeout=10) as response:
                        response_text = await response.text()
                        if response.status == 200:
                            logger.info(f"Triggered action for {trigger['name']}. Response: {response_text}")
                            return response_text
                        else:
                            logger.warning(f"Failed to trigger action for {trigger['name']}. Status code: {response.status}. Response: {response_text}. Attempt {attempt + 1}/{max_retries}")
            except aiohttp.ClientError as e:
                logger.error(f"Network error triggering action for {trigger['name']}: {str(e)}. Attempt {attempt + 1}/{max_retries}")
            except asyncio.TimeoutError:
                logger.error(f"Timeout error triggering action for {trigger['name']}. Attempt {attempt + 1}/{max_retries}")
            except Exception as e:
                logger.error(f"Unexpected error triggering action for {trigger['name']}: {str(e)}. Attempt {attempt + 1}/{max_retries}")

            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff

        logger.error(f"Failed to trigger action for {trigger['name']} after {max_retries} attempts")
        return None

async def trigger_effect(self, trigger_name):
    trigger = next((t for t in self.triggers if t['name'] == trigger_name), None)
    if not trigger:
        logger.error(f"No trigger found with name: {trigger_name}")
        return

    action = trigger.get('action')
    if not action:
        logger.error(f"No action defined for trigger: {trigger_name}")
        return

    if action['type'] == 'curl':
        await self.execute_curl_action(trigger, action)
    else:
        logger.error(f"Unsupported action type for trigger {trigger_name}: {action['type']}")

    def cleanup(self):
        GPIO.cleanup()
        logger.info("GPIO cleanup completed")

    def get_action(self, trigger_name):
        for trigger in self.triggers:
            if trigger['name'] == trigger_name:
                return trigger.get('action')
        logger.warning(f"No action found for trigger: {trigger_name}")
        return None

# End of TriggerManager class
