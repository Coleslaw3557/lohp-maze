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

logger = logging.getLogger(__name__)

class TriggerManager:
    def __init__(self, config):
        self.config = config
        self.associated_rooms = config.get('associated_rooms', [])
        logger.info(f"Associated rooms: {self.associated_rooms}")
        all_triggers = config.get('triggers', [])
        logger.info(f"Total triggers in config: {len(all_triggers)}")
        self.triggers = [trigger for trigger in all_triggers if not trigger.get('room') or trigger.get('room') in self.associated_rooms]
        logger.info(f"Filtered triggers for associated rooms: {len(self.triggers)}")
        for trigger in self.triggers:
            logger.info(f"Trigger: {trigger['name']}, Type: {trigger['type']}, Room: {trigger.get('room', 'Not specified')}")
        GPIO.setmode(GPIO.BCM)
        self.start_time = time.time()
        self.cooldown_period = config.get('cooldown_period', 5)
        self.startup_delay = config.get('startup_delay', 10)
        self.trigger_cooldowns = {}
        self.laser_intact_times = {}
        self.button_cooldowns = {}
        self.button_cooldown_period = 3  # 3 seconds cooldown for buttons
        
        # Constants for detection
        self.COOLDOWN_TIME = 0.2
        self.CONNECTED_THRESHOLD = 0.5
        self.PIEZO_THRESHOLD = 2.0
        self.KNOCK_THRESHOLD = 2.5
        self.VOLTAGE_CHANGE_THRESHOLD = 0.5
        self.DEBUG_THRESHOLD = 0.1
        self.BUTTON_DEBOUNCE_TIME = 0.1
        
        # Determine the ADC configuration based on the unit's config
        self.adc_config = self.determine_adc_config()
        
        # Initialize piezo-related attributes only if piezo triggers are configured
        if any(trigger['type'] == 'piezo' for trigger in self.triggers):
            self.piezo_attempts = 0
            self.piezo_settings = config.get('piezo_settings', {
                'attempts_required': 3,
                'correct_answer_probability': 0.25
            })
        else:
            self.piezo_attempts = None
            self.piezo_settings = None
        
        # Initialize based on configured triggers
        self.setup_triggers()
        asyncio.create_task(self.setup_adc())
        self.initialize_filters()

    def determine_adc_config(self):
        adc_config = {}
        associated_rooms = self.config.get('associated_rooms', [])
        for trigger in self.triggers:
            if trigger['type'] in ['adc', 'piezo']:
                # Only include triggers for associated rooms
                if 'room' not in trigger or trigger['room'] in associated_rooms:
                    adc_address = trigger.get('adc_address', '0x48')
                    if adc_address not in adc_config:
                        adc_config[adc_address] = []
                    adc_config[adc_address].append(trigger)
        return adc_config

    def check_cuddle_cross_buttons(self):
        if not self.button_channels:
            logger.warning("No button channels available. ADC might not be set up correctly.")
            return

        current_time = time.time()
        for button_name, channel in self.button_channels.items():
            try:
                value = channel.value
                voltage = channel.voltage
                button_status = self.get_button_status(voltage)
                
                logger.info(f"{button_name}: Value: {value}, Voltage: {voltage:.3f}V, Status: {button_status}")
                
                if button_status == "Button pressed":
                    if current_time - self.filters[button_name]['last_press'] > self.COOLDOWN_TIME:
                        logger.info(f"{button_name} pressed")
                        self.filters[button_name]['last_press'] = current_time
                        self.trigger_effect(button_name)
                elif button_status == "Button not pressed":
                    if self.filters[button_name]['last_voltage'] < 0.1:
                        logger.info(f"{button_name} released")
                
                self.filters[button_name]['last_voltage'] = voltage
            except Exception as e:
                logger.error(f"Error reading {button_name}: {str(e)}")

    def check_piezo_sensors(self):
        if not self.piezo_channels:
            logger.warning("No piezo channels available. ADC might not be set up correctly.")
            return

        current_time = time.time()
        for piezo_name, channel in self.piezo_channels.items():
            try:
                value = channel.value
                voltage = channel.voltage
                
                logger.debug(f"Piezo {piezo_name}: Value: {value}, Voltage: {voltage:.3f}V")
                
                if voltage > self.PIEZO_THRESHOLD:
                    if current_time - self.filters[f'Piezo {piezo_name}']['last_trigger'] > self.COOLDOWN_TIME:
                        logger.info(f"Piezo {piezo_name} triggered")
                        self.filters[f'Piezo {piezo_name}']['last_trigger'] = current_time
                        self.trigger_effect(f"Porto Room Piezo {piezo_name + 1}")
                
                self.filters[f'Piezo {piezo_name}']['last_voltage'] = voltage
            except Exception as e:
                logger.error(f"Error reading Piezo {piezo_name}: {str(e)}")

    def get_button_status(self, voltage):
        if voltage < 0.1:  # Adjusted threshold for button press
            return "Button pressed"
        elif voltage > 3.0:  # Adjusted threshold for button not pressed
            return "Button not pressed"
        else:
            return None  # Ignore voltages outside the specified range

    async def check_adc_trigger(self, trigger, callback, current_time):
        channel_info = self.adc_channels.get(trigger['name'])
        if channel_info is None:
            logger.warning(f"No channel found for trigger {trigger['name']}")
            return

        try:
            value = channel_info['channel'].value
            voltage = channel_info['channel'].voltage
        except Exception as e:
            logger.error(f"Error reading ADC for {trigger['name']}: {str(e)}")
            return

        button_status = self.get_button_status(voltage)
        logger.debug(f"Button status for {trigger['name']}: {button_status}")
        
        if button_status == "Button pressed":
            if current_time - channel_info['last_trigger_time'] > self.BUTTON_DEBOUNCE_TIME:
                if current_time - self.button_cooldowns.get(trigger['name'], 0) > self.button_cooldown_period:
                    logger.info(f"Button pressed: {trigger['name']}")
                    channel_info['last_trigger_time'] = current_time
                    self.button_cooldowns[trigger['name']] = current_time
                    try:
                        await self.execute_trigger_action(trigger)
                    except Exception as e:
                        logger.error(f"Error executing action for {trigger['name']}: {str(e)}")
                else:
                    logger.debug(f"Button {trigger['name']} in cooldown period")
            else:
                logger.debug(f"Button {trigger['name']} debounced")
        elif button_status == "Button not pressed":
            if channel_info['last_value'] < 0.1:
                logger.debug(f"Button {trigger['name']} released")
        
        channel_info['last_value'] = voltage

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
            url = action['url'].replace('${server_ip}', self.config.get('server_ip'))
            headers = action.get('headers', {})
            data = action.get('data', {})
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.request(action['method'], url, headers=headers, json=data) as response:
                        if response.status == 200:
                            response_text = await response.text()
                            logger.info(f"Triggered action for {trigger_name}. Response: {response_text}")
                        else:
                            logger.error(f"Failed to trigger action for {trigger_name}. Status code: {response.status}")
            except Exception as e:
                logger.error(f"Error triggering action for {trigger_name}: {str(e)}")
        else:
            logger.error(f"Unsupported action type for trigger {trigger_name}: {action['type']}")

    def setup_triggers(self):
        self.active_triggers = []
        logger.info(f"Setting up triggers for associated rooms: {self.associated_rooms}")
        logger.info(f"Total triggers to set up: {len(self.triggers)}")
        for trigger in self.triggers:
            trigger_room = trigger.get('room', 'Not specified')
            
            if trigger['type'] == 'laser':
                GPIO.setup(trigger['tx_pin'], GPIO.OUT)
                GPIO.output(trigger['tx_pin'], GPIO.HIGH)  # Turn on laser
                GPIO.setup(trigger['rx_pin'], GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
                logger.info(f"Laser trigger set up: {trigger['name']}, TX pin {trigger['tx_pin']}, RX pin {trigger['rx_pin']}, Room: {trigger_room}")
                self.active_triggers.append(trigger)
            elif trigger['type'] == 'gpio':
                if 'pin' in trigger:
                    GPIO.setup(trigger['pin'], GPIO.IN, pull_up_down=GPIO.PUD_UP)
                    logger.info(f"GPIO trigger set up: {trigger['name']}, pin {trigger['pin']}, Room: {trigger_room}")
                    self.active_triggers.append(trigger)
                else:
                    logger.warning(f"GPIO trigger {trigger['name']} is missing 'pin' configuration")
            elif trigger['type'] in ['adc', 'piezo']:
                logger.info(f"ADC/Piezo trigger registered: {trigger['name']}, Room: {trigger_room}")
                self.active_triggers.append(trigger)
            else:
                logger.warning(f"Unknown trigger type for {trigger['name']}: {trigger['type']}")
        
        logger.info(f"Set up {len(self.active_triggers)} triggers for associated rooms: {self.associated_rooms}")

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

            # Add a delay to allow ADC readings to stabilize
            await asyncio.sleep(2)

            # Test reading from each channel
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

        # Log the associated rooms for debugging
        associated_rooms = self.config.get('associated_rooms', [])
        logger.info(f"Associated rooms for this unit: {associated_rooms}")

        # Schedule ADC reading
        asyncio.create_task(self.read_adc_continuously())

    async def monitor_triggers(self, callback):
        # Start the continuous ADC reading task
        asyncio.create_task(self.read_adc_continuously())

        while True:
            current_time = time.time()
            if current_time - self.start_time < self.startup_delay:
                await asyncio.sleep(0.1)  # Sleep for 100ms during startup delay
                continue
            
            for trigger in self.active_triggers:
                if trigger['type'] == 'laser':
                    await self.check_laser_trigger(trigger, callback, current_time)
                elif trigger['type'] == 'gpio':
                    await self.check_gpio_trigger(trigger, callback, current_time)
                elif trigger['type'] == 'piezo':
                    await self.check_piezo_trigger(trigger, callback, current_time)
            
            await asyncio.sleep(0.01)  # Check every 10ms for more responsive detection

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

    async def read_adc_continuously(self):
        while True:
            current_time = time.time()
            tasks = []
            for trigger in self.triggers:
                if trigger['type'] == 'adc':
                    channel_info = self.adc_channels.get(trigger['name'])
                    if channel_info:
                        tasks.append(self.read_and_check_adc(trigger, channel_info, current_time))
            await asyncio.gather(*tasks)
            await asyncio.sleep(0.05)  # Check every 50ms to reduce CPU usage

    async def read_and_check_adc(self, trigger, channel_info, current_time):
        try:
            voltage = channel_info['channel'].voltage
            await self.check_adc_trigger(trigger, self.trigger_effect, current_time)
        except Exception as e:
            logger.error(f"Error reading ADC for {trigger['name']}: {str(e)}")

    async def monitor_triggers(self, callback):
        while True:
            current_time = time.time()
            if current_time - self.start_time < self.startup_delay:
                await asyncio.sleep(0.1)  # Sleep for 100ms during startup delay
                continue
            
            tasks = []
            for trigger in self.active_triggers:
                if trigger['type'] == 'laser':
                    tasks.append(self.check_laser_trigger(trigger, callback, current_time))
                elif trigger['type'] == 'gpio':
                    tasks.append(self.check_gpio_trigger(trigger, callback, current_time))
                elif trigger['type'] == 'piezo':
                    tasks.append(self.check_piezo_trigger(trigger, callback, current_time))
            
            await asyncio.gather(*tasks)
            await asyncio.sleep(0.01)  # Check every 10ms for more responsive detection

    async def check_laser_trigger(self, trigger, callback, current_time):
        rx_state = GPIO.input(trigger['rx_pin'])
        if rx_state == GPIO.LOW:  # Laser beam is broken
            if self.check_trigger_cooldown(trigger['name'], current_time):
                logger.info(f"Laser beam broken: {trigger['name']}")
                self.set_trigger_cooldown(trigger['name'], current_time)
                await callback(trigger['name'])
        else:
            # Reset the cooldown if the beam is restored
            self.trigger_cooldowns.pop(trigger['name'], None)

    async def check_piezo_trigger(self, trigger, callback, current_time):
        channel = self.piezo_channels[trigger['adc_channel']]
        adc_name = f"ADC2 A{trigger['adc_channel']}"
        voltage = channel.voltage
        
        if voltage > self.CONNECTED_THRESHOLD:
            voltage_change = abs(voltage - self.filters[adc_name]['last_voltage'])
            
            if voltage_change > self.DEBUG_THRESHOLD:
                logger.debug(f"Debug: Change detected on {adc_name}: {voltage_change:.3f}V")
                
                if (voltage > self.KNOCK_THRESHOLD and 
                    voltage_change > self.VOLTAGE_CHANGE_THRESHOLD and 
                    current_time - self.filters[adc_name]['last_knock'] > self.COOLDOWN_TIME):
                    logger.info(f"Knock detected on {adc_name}")
                    self.filters[adc_name]['last_knock'] = current_time
                    asyncio.create_task(self.handle_piezo_trigger(trigger, callback))
            
            self.filters[adc_name]['last_voltage'] = voltage
        elif self.filters[adc_name]['last_voltage'] > self.CONNECTED_THRESHOLD:
            logger.warning(f"Sensor disconnected or low voltage on {adc_name}: {voltage:.3f}V")
        
        self.filters[adc_name]['last_voltage'] = voltage

    async def handle_piezo_trigger(self, trigger, callback):
        self.piezo_attempts += 1
        logger.info(f"Piezo trigger {trigger['name']} activated. Attempt {self.piezo_attempts}")

        if self.piezo_attempts >= self.piezo_settings['attempts_required']:
            if random.random() < self.piezo_settings['correct_answer_probability']:
                effect_name = "CorrectAnswer"
                self.piezo_attempts = 0  # Reset attempts on correct answer
            else:
                effect_name = "WrongAnswer"
        else:
            effect_name = "WrongAnswer"

        logger.info(f"Triggering effect: {effect_name}")
        action_data = trigger['action']['data'].copy()  # Create a copy of the original data
        action_data['effect_name'] = effect_name
        try:
            await callback(trigger['name'])
            logger.info(f"Successfully triggered effect: {effect_name}")
        except Exception as e:
            logger.error(f"Failed to trigger effect {effect_name}: {str(e)}")

        # Reset attempts if it's a wrong answer and we've reached the required attempts
        if effect_name == "WrongAnswer" and self.piezo_attempts >= self.piezo_settings['attempts_required']:
            self.piezo_attempts = 0

    def check_laser_cooldown(self, trigger_name, current_time):
        last_trigger_time = self.trigger_cooldowns.get(trigger_name, 0)
        cooldown_period = 15  # 15-second cooldown
        
        # Check if the cooldown period has passed
        if current_time - last_trigger_time > cooldown_period:
            return True
        
        time_left = cooldown_period - (current_time - last_trigger_time)
        logger.debug(f"Laser {trigger_name} in cooldown. Time left: {time_left:.2f}s")
        return False

    def check_trigger_cooldown(self, trigger_name, current_time):
        last_trigger_time = self.trigger_cooldowns.get(trigger_name, 0)
        if trigger_name.startswith('laser_'):
            cooldown_period = 15  # 15-second cooldown for laser triggers
            return current_time - last_trigger_time > cooldown_period
        return True  # No cooldown for other triggers

    def set_trigger_cooldown(self, trigger_name, current_time):
        self.trigger_cooldowns[trigger_name] = current_time

    def cleanup(self):
        GPIO.cleanup()
        logger.info("GPIO cleanup completed")
    def initialize_filters(self):
        self.filters = {}
        for trigger in self.triggers:
            if trigger['type'] in ['adc', 'piezo']:
                self.filters[trigger['name']] = {'last_voltage': 0, 'last_trigger': 0}
        logger.info("Filters initialized for configured triggers")
    async def check_button_trigger(self, trigger, channel, current_time):
        try:
            voltage = channel.voltage
            button_status = self.get_button_status(voltage)
            
            if button_status == "Button pressed":
                if self.check_trigger_cooldown(trigger['name'], current_time):
                    logger.info(f"Button pressed: {trigger['name']}")
                    self.set_trigger_cooldown(trigger['name'], current_time)
                    await self.trigger_effect(trigger['name'])
        except Exception as e:
            logger.error(f"Error checking button trigger {trigger['name']}: {str(e)}")

    async def check_piezo_trigger(self, trigger, channel, current_time):
        if 'piezo' not in self.config.get('triggers', []):
            return  # Skip if piezo triggers are not configured

        try:
            voltage = channel.voltage
            
            if voltage > self.PIEZO_THRESHOLD:
                if self.check_trigger_cooldown(trigger['name'], current_time):
                    logger.info(f"Piezo triggered: {trigger['name']}")
                    self.set_trigger_cooldown(trigger['name'], current_time)
                    await self.handle_piezo_trigger(trigger, self.trigger_effect)
        except Exception as e:
            logger.error(f"Error checking piezo trigger {trigger['name']}: {str(e)}")
    async def execute_trigger_action(self, trigger):
        action = trigger.get('action')
        if not action:
            logger.error(f"No action defined for trigger: {trigger['name']}")
            return

        if action['type'] == 'curl':
            url = action['url'].replace('${server_ip}', self.config.get('server_ip'))
            headers = action.get('headers', {})
            data = action.get('data', {})
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.request(action['method'], url, headers=headers, json=data) as response:
                        if response.status == 200:
                            response_text = await response.text()
                            logger.info(f"Triggered action for {trigger['name']}. Response: {response_text}")
                        else:
                            logger.error(f"Failed to trigger action for {trigger['name']}. Status code: {response.status}")
            except Exception as e:
                logger.error(f"Error triggering action for {trigger['name']}: {str(e)}")
        else:
            logger.error(f"Unsupported action type for trigger {trigger['name']}: {action['type']}")
