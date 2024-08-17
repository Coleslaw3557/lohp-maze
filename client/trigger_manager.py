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
        self.setup_triggers()
        self.start_time = time.time()
        self.cooldown_period = config.get('cooldown_period', 5)
        self.startup_delay = config.get('startup_delay', 10)
        self.trigger_cooldowns = {}
        self.laser_intact_times = {}  # New attribute to track when laser beams became intact
        self.setup_adc()
        
        # Constants for button detection
        self.COOLDOWN_TIME = config.get('cooldown_time', 0.2)
        self.CONNECTED_THRESHOLD = config.get('connected_threshold', 0.3)
        
        # Initialize filters for button detection
        self.filters = {f"Button {i+1}": {'last_voltage': 0, 'last_press': 0} for i in range(4)}

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
        for trigger in self.triggers:
            if trigger['type'] == 'laser':
                GPIO.setup(trigger['tx_pin'], GPIO.OUT)
                GPIO.output(trigger['tx_pin'], GPIO.HIGH)  # Turn on laser
                GPIO.setup(trigger['rx_pin'], GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Use pull-up resistor
                logger.info(f"Laser trigger set up: {trigger['name']}, TX pin {trigger['tx_pin']}, RX pin {trigger['rx_pin']}")
            elif trigger['type'] == 'gpio':
                if 'pin' in trigger:
                    GPIO.setup(trigger['pin'], GPIO.IN, pull_up_down=GPIO.PUD_UP)
                    logger.info(f"GPIO trigger set up: {trigger['name']}, pin {trigger['pin']}")
                else:
                    logger.warning(f"GPIO trigger {trigger['name']} is missing 'pin' configuration")
        logger.info("All triggers set up")

    def setup_adc(self):
        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            self.ads1 = ADS.ADS1115(i2c, address=0x48)  # ADC1 for Cuddle Cross buttons
            
            self.button_channels = {
                'Button 1': AnalogIn(self.ads1, ADS.P0),
                'Button 2': AnalogIn(self.ads1, ADS.P1),
                'Button 3': AnalogIn(self.ads1, ADS.P2),
                'Button 4': AnalogIn(self.ads1, ADS.P3)
            }
            logger.info("ADC setup completed for Cuddle Cross buttons (0x48)")
        except Exception as e:
            logger.error(f"Error setting up ADC: {str(e)}")
            self.ads1 = None
            self.button_channels = {}

    async def monitor_triggers(self, callback):
        while True:
            current_time = time.time()
            if current_time - self.start_time < self.startup_delay:
                await asyncio.sleep(0.1)  # Sleep for 100ms during startup delay
                continue
            
            for trigger in self.triggers:
                if trigger['type'] == 'laser':
                    beam_status = GPIO.input(trigger['rx_pin'])
                    if beam_status == GPIO.LOW:  # Beam is broken (LOW when using pull-down resistor)
                        if self.check_laser_cooldown(trigger['name'], current_time):
                            logger.info(f"Laser beam broken: {trigger['name']} (TX: GPIO{trigger['tx_pin']}, RX: GPIO{trigger['rx_pin']})")
                            await callback(trigger['name'])
                            self.set_trigger_cooldown(trigger['name'], current_time)
                        else:
                            logger.debug(f"Laser beam broken but in cooldown: {trigger['name']}")
                    else:
                        # Beam is intact
                        GPIO.output(trigger['tx_pin'], GPIO.HIGH)
                        logger.debug(f"Laser beam intact: {trigger['name']} (TX: GPIO{trigger['tx_pin']}, RX: GPIO{trigger['rx_pin']})")
                elif trigger['type'] == 'adc':
                    self.check_cuddle_cross_buttons()
            
            await asyncio.sleep(0.01)  # Check every 10ms for more responsive detection

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
