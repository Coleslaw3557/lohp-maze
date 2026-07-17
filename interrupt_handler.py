import time
import logging
import asyncio

logger = logging.getLogger(__name__)


class InterruptHandler:
    """Temporarily takes fixtures over from the running theme to play an effect.

    Ownership is a token per fixture: starting a new interrupt replaces the
    token and the previous loop exits at its next tick. Cleanup only happens
    while still owning the fixture, so a takeover can never un-claim a fixture
    out from under the effect that now holds it (which would let the theme
    thread fight the effect for the fixture at 10Hz vs 44Hz).
    """

    def __init__(self, dmx_state_manager):
        self.dmx_state_manager = dmx_state_manager
        self.active_interrupts = {}  # fixture_id -> owner token

    def is_interrupted(self, fixture_id):
        return fixture_id in self.active_interrupts

    async def interrupt_fixture(self, fixture_id, duration, interrupt_sequence):
        token = object()
        if fixture_id in self.active_interrupts:
            logger.info(f"Taking over running effect on fixture {fixture_id}")
        self.active_interrupts[fixture_id] = token

        logger.debug(f"Starting effect on fixture {fixture_id} for {duration} seconds")
        start_time = time.time()
        try:
            while self.active_interrupts.get(fixture_id) is token:
                elapsed_time = time.time() - start_time
                if elapsed_time >= duration:
                    break
                self.dmx_state_manager.update_fixture(fixture_id, interrupt_sequence(elapsed_time),
                                                      override=True)
                await asyncio.sleep(1 / 44)  # 44Hz update rate
        finally:
            if self.active_interrupts.get(fixture_id) is token:
                del self.active_interrupts[fixture_id]
        return True
