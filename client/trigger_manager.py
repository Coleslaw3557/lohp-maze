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
                            await callback(trigger['name'])
                    elif trigger['type'] == 'gpio':
                        if 'pin' in trigger and GPIO.input(trigger['pin']) == GPIO.LOW:
                            await callback(trigger['name'])
            else:
                logger.info(f"Trigger cooldown active. {self.cooldown_period - (current_time - self.start_time):.1f} seconds remaining.")
            await asyncio.sleep(0.1)  # Check every 100ms

    def cleanup(self):
        GPIO.cleanup()
        logger.info("GPIO cleanup completed")
