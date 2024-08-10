import asyncio
import logging

logger = logging.getLogger(__name__)

class TriggerManager:
    def __init__(self, triggers_config):
        self.triggers = triggers_config
        logger.warning("GPIO functionality is not available in this environment")

    def setup_triggers(self):
        logger.info("Trigger setup skipped (no GPIO available)")

    async def monitor_triggers(self, callback):
        logger.info("Trigger monitoring skipped (no GPIO available)")
        while True:
            await asyncio.sleep(60)  # Sleep to keep the coroutine running

    def cleanup(self):
        logger.info("No GPIO cleanup needed")
