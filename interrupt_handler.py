import time
import logging
import asyncio

logger = logging.getLogger(__name__)


class InterruptHandler:
    """Temporarily takes fixtures over from the running theme to play an effect."""

    def __init__(self, dmx_state_manager):
        self.dmx_state_manager = dmx_state_manager
        self.active_interrupts = {}
        self.interrupted_fixtures = set()
        self.interrupt_end_times = {}

    async def interrupt_fixture(self, fixture_id, duration, interrupt_sequence):
        logger.info(f"Starting effect on fixture {fixture_id} for {duration} seconds")
        self.interrupted_fixtures.add(fixture_id)

        interrupt_id = id(interrupt_sequence)
        if fixture_id in self.active_interrupts:
            logger.info(f"Cancelling existing effect on fixture {fixture_id}")
            self.active_interrupts[fixture_id]['active'] = False
        self.active_interrupts[fixture_id] = {'id': interrupt_id, 'active': True}

        start_time = time.time()
        end_time = start_time + duration
        self.interrupt_end_times[fixture_id] = end_time
        try:
            while time.time() < end_time and self.active_interrupts.get(fixture_id, {}).get('id') == interrupt_id:
                if not self.active_interrupts[fixture_id]['active']:
                    logger.info(f"Effect on fixture {fixture_id} was cancelled")
                    break
                elapsed_time = time.time() - start_time
                new_values = interrupt_sequence(elapsed_time)
                self.dmx_state_manager.update_fixture(fixture_id, new_values, override=True)
                await asyncio.sleep(1 / 44)  # 44Hz update rate
        finally:
            if self.active_interrupts.get(fixture_id, {}).get('id') == interrupt_id:
                del self.active_interrupts[fixture_id]
            self.interrupted_fixtures.discard(fixture_id)
            self.interrupt_end_times.pop(fixture_id, None)

        logger.info(f"Effect completed for fixture {fixture_id}.")
        return True
