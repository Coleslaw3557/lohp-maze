import asyncio
import logging
import RPi.GPIO as GPIO
import time
import random
import board
import busio
from busio import I2C
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

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
        self.piezo_channels = [AnalogIn(self.ads, ADS.P0), AnalogIn(self.ads, ADS.P1), AnalogIn(self.ads, ADS.P2)]
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
                        if channel.voltage > trigger['threshold']:
                            await self.handle_piezo_trigger(trigger, callback)
            else:
                logger.info(f"Initial cooldown active. {self.cooldown_period - (current_time - self.start_time):.1f} seconds remaining.")
            await asyncio.sleep(0.1)  # Check every 100ms

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

        trigger['action']['data']['effect_name'] = effect_name
        await callback(trigger['name'])

    def check_laser_cooldown(self, laser_name, current_time):
        last_trigger_time = self.laser_cooldowns.get(laser_name, 0)
        return current_time - last_trigger_time > 5  # 5 seconds cooldown

    def set_laser_cooldown(self, laser_name, current_time):
        self.laser_cooldowns[laser_name] = current_time

    def cleanup(self):
        GPIO.cleanup()
        logger.info("GPIO cleanup completed")
