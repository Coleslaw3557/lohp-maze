import asyncio
import RPi.GPIO as GPIO
import logging

logger = logging.getLogger(__name__)

class TriggerManager:
    def __init__(self, triggers_config):
        self.triggers = triggers_config
        GPIO.setmode(GPIO.BCM)
        self.setup_triggers()

    def setup_triggers(self):
        for trigger in self.triggers:
            if trigger['type'] == 'gpio':
                GPIO.setup(trigger['pin'], GPIO.IN, pull_up_down=GPIO.PUD_UP)
                logger.info(f"Set up GPIO trigger on pin {trigger['pin']}")

    async def monitor_triggers(self, callback):
        while True:
            for trigger in self.triggers:
                if trigger['type'] == 'gpio':
                    if GPIO.input(trigger['pin']) == GPIO.LOW:
                        logger.info(f"Trigger activated: {trigger['name']}")
                        await callback(trigger['name'])
                        await asyncio.sleep(0.5)  # Debounce
            await asyncio.sleep(0.1)

    def cleanup(self):
        GPIO.cleanup()
        logger.info("Cleaned up GPIO")
