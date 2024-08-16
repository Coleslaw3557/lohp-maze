import asyncio
import logging
import RPi.GPIO as GPIO

logger = logging.getLogger(__name__)

class TriggerManager:
    def __init__(self, triggers_config):
        self.triggers = triggers_config
        GPIO.setmode(GPIO.BCM)
        self.setup_triggers()

    def setup_triggers(self):
        for trigger in self.triggers:
            if trigger['type'] == 'laser':
                GPIO.setup(trigger['tx_pin'], GPIO.OUT)
                GPIO.output(trigger['tx_pin'], GPIO.HIGH)  # Turn on laser
                GPIO.setup(trigger['rx_pin'], GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
            elif trigger['type'] == 'gpio':
                GPIO.setup(trigger['pin'], GPIO.IN, pull_up_down=GPIO.PUD_UP)
        logger.info("GPIO triggers set up")

    async def monitor_triggers(self, callback):
        while True:
            for trigger in self.triggers:
                if trigger['type'] == 'laser':
                    if GPIO.input(trigger['rx_pin']) == GPIO.LOW:
                        await callback(trigger['name'])
                elif trigger['type'] == 'gpio':
                    if GPIO.input(trigger['pin']) == GPIO.LOW:
                        await callback(trigger['name'])
            await asyncio.sleep(0.1)  # Check every 100ms

    def cleanup(self):
        GPIO.cleanup()
        logger.info("GPIO cleanup completed")
