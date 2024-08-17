import asyncio
import logging
import time
import random
import board
import busio
import RPi.GPIO as GPIO
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
import requests

logger = logging.getLogger(__name__)

class TriggerManager:
    def __init__(self, config):
        self.config = config
        self.triggers = config.get('triggers', [])
        GPIO.setmode(GPIO.BCM)
        self.start_time = time.time()
        self.cooldown_period = config.get('cooldown_period', 5)
        self.startup_delay = config.get('startup_delay', 10)
        self.trigger_cooldowns = {}
        self.laser_intact_times = {}
        
        # Constants for detection
        self.COOLDOWN_TIME = config.get('cooldown_time', 0.2)
        self.CONNECTED_THRESHOLD = config.get('connected_threshold', 0.3)
        self.PIEZO_THRESHOLD = config.get('piezo_threshold', 0.5)
        
        # Initialize based on configured triggers
        self.setup_triggers()
        self.setup_adc()
        self.initialize_filters()

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
        if voltage < 0.1:
            return "Button pressed"
        elif voltage > 0.5:  # Changed from 0.9 to 0.5 for more sensitivity
            return "Button not pressed"
        else:
            logger.warning(f"Voltage in undefined range: {voltage:.3f}V")
            return "Error: Voltage in undefined range"

    def trigger_effect(self, trigger_name):
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
                response = requests.request(action['method'], url, headers=headers, json=data)
                if response.status_code == 200:
                    logger.info(f"Triggered action for {trigger_name}. Response: {response.text}")
                else:
                    logger.error(f"Failed to trigger action for {trigger_name}. Status code: {response.status_code}")
            except Exception as e:
                logger.error(f"Error triggering action for {trigger_name}: {str(e)}")
        else:
            logger.error(f"Unsupported action type for trigger {trigger_name}: {action['type']}")

    def setup_triggers(self):
        associated_rooms = self.config.get('associated_rooms', [])
        self.active_triggers = []
        for trigger in self.triggers:
            if 'room' in trigger and trigger['room'] in associated_rooms:
                if trigger['type'] == 'laser':
                    GPIO.setup(trigger['tx_pin'], GPIO.OUT)
                    GPIO.output(trigger['tx_pin'], GPIO.HIGH)  # Turn on laser
                    GPIO.setup(trigger['rx_pin'], GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
                    logger.info(f"Laser trigger set up: {trigger['name']}, TX pin {trigger['tx_pin']}, RX pin {trigger['rx_pin']}")
                    self.active_triggers.append(trigger)
                elif trigger['type'] == 'gpio':
                    if 'pin' in trigger:
                        GPIO.setup(trigger['pin'], GPIO.IN, pull_up_down=GPIO.PUD_UP)
                        logger.info(f"GPIO trigger set up: {trigger['name']}, pin {trigger['pin']}")
                        self.active_triggers.append(trigger)
                    else:
                        logger.warning(f"GPIO trigger {trigger['name']} is missing 'pin' configuration")
                elif trigger['type'] in ['adc', 'piezo']:
                    logger.info(f"ADC/Piezo trigger registered: {trigger['name']}")
                    self.active_triggers.append(trigger)
            else:
                logger.info(f"Trigger {trigger['name']} not associated with this unit's rooms. Skipping setup.")
        logger.info(f"Set up {len(self.active_triggers)} triggers for associated rooms: {associated_rooms}")

    def setup_adc(self):
        adc_needed = any(trigger['type'] in ['adc', 'piezo'] for trigger in self.triggers)
        if not adc_needed:
            logger.info("No ADC triggers configured, skipping ADC setup")
            return

        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            self.ads1 = ADS.ADS1115(i2c, address=0x48)  # ADC1 for buttons
            self.ads2 = ADS.ADS1115(i2c, address=0x49)  # ADC2 for piezo sensors
            
            self.button_channels = {}
            self.piezo_channels = {}
            
            for trigger in self.triggers:
                if trigger['type'] == 'adc':
                    channel = trigger['channel']
                    self.button_channels[trigger['name']] = AnalogIn(self.ads1, getattr(ADS, f'P{channel}'))
                elif trigger['type'] == 'piezo':
                    channel = trigger['adc_channel']
                    self.piezo_channels[channel] = AnalogIn(self.ads2, getattr(ADS, f'P{channel}'))
            
            logger.info("ADC setup completed for configured triggers")
            logger.info(f"Button channels: {self.button_channels}")
            logger.info(f"Piezo channels: {self.piezo_channels}")
        except Exception as e:
            logger.error(f"Error setting up ADC: {str(e)}")
            self.ads1 = None
            self.ads2 = None
            self.button_channels = {}
            self.piezo_channels = {}

    async def monitor_triggers(self, callback):
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
                elif trigger['type'] == 'adc':
                    await self.check_adc_trigger(trigger, callback, current_time)
                elif trigger['type'] == 'piezo':
                    await self.check_piezo_trigger(trigger, callback, current_time)
            
            await asyncio.sleep(0.01)  # Check every 10ms for more responsive detection

    async def check_adc_trigger(self, trigger, callback, current_time):
        channel = self.button_channels.get(trigger['name'])
        if channel is None:
            logger.warning(f"No channel found for trigger {trigger['name']}")
            return

        voltage = channel.voltage
        button_status = self.get_button_status(voltage)
        
        logger.debug(f"ADC {trigger['name']}: Voltage: {voltage:.3f}V, Status: {button_status}")
        
        if button_status == "Button pressed":
            if self.check_trigger_cooldown(trigger['name'], current_time):
                logger.info(f"Button pressed: {trigger['name']}")
                self.set_trigger_cooldown(trigger['name'], current_time)
                await callback(trigger['name'])

    async def monitor_triggers(self, callback):
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
                elif trigger['type'] == 'adc':
                    await self.check_adc_trigger(trigger, callback, current_time)
                elif trigger['type'] == 'piezo':
                    await self.check_piezo_trigger(trigger, callback, current_time)
            
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
                    await self.handle_piezo_trigger(trigger, callback)
            
            self.filters[adc_name]['last_voltage'] = voltage
        else:
            logger.warning(f"Sensor not connected or low voltage on {adc_name}: {voltage:.3f}V")

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
        trigger['action']['data']['effect_name'] = effect_name
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
