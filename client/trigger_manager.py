import asyncio
import logging
import RPi.GPIO as GPIO
import time

logger = logging.getLogger(__name__)

class TriggerManager:
    def __init__(self, triggers_config):
        self.triggers = triggers_config
        GPIO.setmode(GPIO.BCM)
        self.setup_triggers()
        self.start_time = time.time()
        self.cooldown_period = 5  # 5 seconds cooldown
        self.laser_cooldowns = {}  # Dictionary to store cooldown times for each laser

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
            else:
                logger.info(f"Initial cooldown active. {self.cooldown_period - (current_time - self.start_time):.1f} seconds remaining.")
            await asyncio.sleep(0.1)  # Check every 100ms

    def check_laser_cooldown(self, laser_name, current_time):
        last_trigger_time = self.laser_cooldowns.get(laser_name, 0)
        return current_time - last_trigger_time > 5  # 5 seconds cooldown

    def set_laser_cooldown(self, laser_name, current_time):
        self.laser_cooldowns[laser_name] = current_time

    def cleanup(self):
        GPIO.cleanup()
        logger.info("GPIO cleanup completed")
