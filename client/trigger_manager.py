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
        self.piezo_settings = config.get('piezo_settings', {})
        GPIO.setmode(GPIO.BCM)
        self.setup_triggers()
        self.start_time = time.time()
        self.cooldown_period = config.get('cooldown_period', 5)
        self.startup_delay = config.get('startup_delay', 10)
        self.trigger_cooldowns = {}
        self.laser_intact_times = {}  # New attribute to track when laser beams became intact
        self.piezo_attempts = 0
        self.setup_adc()
        self.resistor_ladder_cooldown = config.get('resistor_ladder_cooldown', 1)
        self.last_resistor_ladder_trigger = 0
        
        # Constants for knock detection
        self.KNOCK_THRESHOLD = config.get('knock_threshold', 0.05)
        self.VOLTAGE_CHANGE_THRESHOLD = config.get('voltage_change_threshold', 0.01)
        self.COOLDOWN_TIME = config.get('cooldown_time', 0.2)
        self.DEBUG_THRESHOLD = config.get('debug_threshold', 0.005)
        self.CONNECTED_THRESHOLD = config.get('connected_threshold', 0.3)
        
        # Initialize filters for knock detection
        self.filters = {f"ADC2 A{i}": {'last_voltage': 0, 'last_knock': 0} for i in range(3)}

    def check_resistor_ladder(self):
        current_time = time.time()
        if current_time - self.last_resistor_ladder_trigger < self.resistor_ladder_cooldown:
            return

        adc1_a0_voltage = self.gate_resistor_ladder1.voltage if self.gate_resistor_ladder1 else 0
        adc1_a1_voltage = self.gate_resistor_ladder2.voltage if self.gate_resistor_ladder2 else 0

        logger.debug(f"Resistor Ladder 1 voltage: {adc1_a0_voltage:.2f}V")
        logger.debug(f"Resistor Ladder 2 voltage: {adc1_a1_voltage:.2f}V")

        # Define voltage ranges for each button combination
        voltage_ranges = {
            (0.3, 0.5): "Button 1",
            (0.6, 0.8): "Button 2",
            (0.9, 1.1): "Button 3",
            (1.2, 1.4): "Buttons 1 and 2",
            (1.5, 1.7): "Buttons 1 and 3",
            (1.8, 2.0): "Buttons 2 and 3",
            (2.1, 2.3): "All Buttons"
        }

        for ladder, voltage in [("Ladder 1", adc1_a0_voltage), ("Ladder 2", adc1_a1_voltage)]:
            for (lower, upper), button_combo in voltage_ranges.items():
                if lower <= voltage <= upper:
                    logger.info(f"Resistor {ladder}: {button_combo} pressed")
                    self.trigger_effect("Gate", f"Gate{button_combo.replace(' ', '')}")
                    self.last_resistor_ladder_trigger = current_time
                    return

    def trigger_effect(self, room, effect_name):
        url = "http://localhost:5000/api/run_effect"
        headers = {"Content-Type": "application/json"}
        data = {"room": room, "effect_name": effect_name}
        try:
            response = requests.post(url, headers=headers, json=data)
            if response.status_code == 200:
                logger.info(f"Triggered effect {effect_name} in room {room}")
            else:
                logger.error(f"Failed to trigger effect. Status code: {response.status_code}")
        except Exception as e:
            logger.error(f"Error triggering effect: {str(e)}")

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
        i2c = busio.I2C(board.SCL, board.SDA)
        self.ads1 = ADS.ADS1115(i2c, address=0x48)  # ADC1 for Gate Room
        self.ads2 = ADS.ADS1115(i2c, address=0x49)  # ADC2 for Porto Room
        
        self.gate_resistor_ladder1 = AnalogIn(self.ads1, ADS.P0)
        self.gate_resistor_ladder2 = AnalogIn(self.ads1, ADS.P1)
        
        self.piezo_channels = [
            AnalogIn(self.ads2, ADS.P0),
            AnalogIn(self.ads2, ADS.P1),
            AnalogIn(self.ads2, ADS.P2)
        ]
        logger.info("ADC setup completed for Gate Room (0x48) and Porto Room (0x49)")

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
                elif trigger['type'] == 'gpio':
                    if 'pin' in trigger:
                        pin_state = GPIO.input(trigger['pin'])
                        if pin_state == GPIO.LOW:
                            if self.check_trigger_cooldown(f"{trigger['name']}_gpio", current_time):
                                logger.info(f"GPIO trigger activated: {trigger['name']} (GPIO{trigger['pin']})")
                                await callback(trigger['name'])
                                self.set_trigger_cooldown(f"{trigger['name']}_gpio", current_time)
                        else:
                            # Reset the cooldown when the GPIO state changes back to HIGH
                            self.set_trigger_cooldown(f"{trigger['name']}_gpio", 0)
                elif trigger['type'] == 'piezo':
                        await self.check_piezo_trigger(trigger, callback, current_time)
            
            # Check resistor ladder states
            self.check_resistor_ladder()
            
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
        
        # Check if the cooldown period has passed
        if current_time - last_trigger_time > 15:  # 15-second cooldown
            return True
        
        logger.debug(f"Laser {trigger_name} in cooldown. Time since last trigger: {current_time - last_trigger_time:.2f}s")
        return False

    def check_trigger_cooldown(self, trigger_name, current_time):
        last_trigger_time = self.trigger_cooldowns.get(trigger_name, 0)
        if trigger_name.startswith('laser_'):
            return current_time - last_trigger_time > 15  # 15-second cooldown for laser triggers
        return True  # No cooldown for other triggers

    def set_trigger_cooldown(self, trigger_name, current_time):
        self.trigger_cooldowns[trigger_name] = current_time

    def cleanup(self):
        GPIO.cleanup()
        logger.info("GPIO cleanup completed")
