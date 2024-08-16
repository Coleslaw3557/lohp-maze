import asyncio
import logging
import time
import random
import board
import busio
import RPi.GPIO as GPIO
from adafruit_blinka.microcontroller.generic_linux.i2c import I2C
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
from collections import deque
import requests

logger = logging.getLogger(__name__)

class TriggerManager:
    def __init__(self, triggers_config, piezo_settings):
        self.triggers = triggers_config
        self.piezo_settings = piezo_settings
        GPIO.setmode(GPIO.BCM)
        self.setup_triggers()
        self.start_time = time.time()
        self.cooldown_period = 5  # 5 seconds cooldown
        self.laser_cooldowns = {}  # Dictionary to store cooldown times for each laser
        self.piezo_attempts = 0
        self.setup_adc()
        self.resistor_ladder_cooldown = 1  # 1 second cooldown for resistor ladder triggers
        self.last_resistor_ladder_trigger = 0
        
        # Constants for knock detection
        self.KNOCK_THRESHOLD = 0.05
        self.VOLTAGE_CHANGE_THRESHOLD = 0.01
        self.COOLDOWN_TIME = 0.2
        self.DEBUG_THRESHOLD = 0.005
        self.CONNECTED_THRESHOLD = 0.3
        
        # Initialize filters for knock detection
        self.filters = {
            "ADC2 A0": {'last_voltage': 0, 'last_knock': 0},
            "ADC2 A1": {'last_voltage': 0, 'last_knock': 0},
            "ADC2 A2": {'last_voltage': 0, 'last_knock': 0}
        }

    def check_resistor_ladder(self):
        current_time = time.time()
        if current_time - self.last_resistor_ladder_trigger < self.resistor_ladder_cooldown:
            return

        adc1_a0_voltage = self.gate_resistor_ladder1.voltage if self.gate_resistor_ladder1 else 0
        adc1_a1_voltage = self.gate_resistor_ladder2.voltage if self.gate_resistor_ladder2 else 0

        if adc1_a0_voltage > 2.0:  # All three buttons pressed on ADC1 A0
            self.trigger_effect("Gate", "GateInspection")
            self.last_resistor_ladder_trigger = current_time
        elif adc1_a1_voltage > 2.0:  # All three buttons pressed on ADC1 A1
            self.trigger_effect("Gate", "GateGreeters")
            self.last_resistor_ladder_trigger = current_time

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
                GPIO.setup(trigger['rx_pin'], GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
            elif trigger['type'] == 'gpio':
                if 'pin' in trigger:
                    GPIO.setup(trigger['pin'], GPIO.IN, pull_up_down=GPIO.PUD_UP)
                else:
                    logger.warning(f"GPIO trigger {trigger['name']} is missing 'pin' configuration")
        logger.info("GPIO triggers set up")

    def setup_adc(self):
        i2c = busio.I2C(board.SCL, board.SDA)
        self.ads = ADS.ADS1115(i2c)
        self.piezo_channels = [
            AnalogIn(self.ads, ADS.P0),
            AnalogIn(self.ads, ADS.P1),
            AnalogIn(self.ads, ADS.P2)
        ]
        logger.info("ADC setup completed")

    async def monitor_triggers(self, callback):
        while True:
            current_time = time.time()
            if current_time - self.start_time > self.cooldown_period:
                for trigger in self.triggers:
                    if trigger['type'] == 'laser':
                        if GPIO.input(trigger['rx_pin']) == GPIO.LOW:
                            if self.check_laser_cooldown(trigger['name'], current_time):
                                await callback(trigger['name'])
                                self.set_laser_cooldown(trigger['name'], current_time)
                        else:
                            # Ensure laser is on and ready
                            GPIO.output(trigger['tx_pin'], GPIO.HIGH)
                    elif trigger['type'] == 'gpio':
                        if 'pin' in trigger and GPIO.input(trigger['pin']) == GPIO.LOW:
                            await callback(trigger['name'])
                    elif trigger['type'] == 'piezo':
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
                
                # Check resistor ladder states
                self.check_resistor_ladder()
            else:
                logger.info(f"Initial cooldown active. {self.cooldown_period - (current_time - self.start_time):.1f} seconds remaining.")
            await asyncio.sleep(0.01)  # Check every 10ms for more responsive detection

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

    def check_laser_cooldown(self, laser_name, current_time):
        last_trigger_time = self.laser_cooldowns.get(laser_name, 0)
        return current_time - last_trigger_time > 5  # 5 seconds cooldown

    def set_laser_cooldown(self, laser_name, current_time):
        self.laser_cooldowns[laser_name] = current_time

    def cleanup(self):
        GPIO.cleanup()
        logger.info("GPIO cleanup completed")
