import time
import logging
import asyncio

logger = logging.getLogger(__name__)

class InterruptHandler:
    def __init__(self, dmx_state_manager, theme_manager):
        self.dmx_state_manager = dmx_state_manager
        self.theme_manager = theme_manager
        self.active_interrupts = {}
        self.interrupted_fixtures = set()
        self.original_states = {}
        self.fixture_locks = {fixture_id: threading.Lock() for fixture_id in range(dmx_state_manager.num_fixtures)}

    async def interrupt_fixture(self, fixture_id, duration, interrupt_sequence):
        async with self.fixture_locks[fixture_id]:
            logger.info(f"Starting effect on fixture {fixture_id} for {duration} seconds")
            
            # Store the original state
            self.original_states[fixture_id] = self.dmx_state_manager.get_fixture_state(fixture_id)
            
            # Mark the fixture as interrupted
            self.interrupted_fixtures.add(fixture_id)
            
            # Create a unique identifier for this interrupt
            interrupt_id = id(interrupt_sequence)
            
            # Cancel any existing interrupt for this fixture
            if fixture_id in self.active_interrupts:
                logger.info(f"Cancelling existing effect on fixture {fixture_id}")
                self.active_interrupts[fixture_id]['active'] = False

            # Set up the new interrupt
            self.active_interrupts[fixture_id] = {'id': interrupt_id, 'active': True}
            
            start_time = time.time()
            end_time = start_time + duration
            step_count = 0
            try:
                while time.time() < end_time and self.active_interrupts.get(fixture_id, {}).get('id') == interrupt_id:
                    if not self.active_interrupts[fixture_id]['active']:
                        logger.info(f"Effect on fixture {fixture_id} was cancelled")
                        break
                    
                    elapsed_time = time.time() - start_time
                    new_values = interrupt_sequence(elapsed_time)
                    self.dmx_state_manager.update_fixture(fixture_id, new_values, override=True)
                    logger.debug(f"Step {step_count}: Fixture {fixture_id}, Elapsed time: {elapsed_time:.3f}s, New values: {new_values}")
                    await asyncio.sleep(1 / 44)  # 44Hz update rate
                    step_count += 1
                
                # Ensure we run for the full duration if not cancelled
                if self.active_interrupts.get(fixture_id, {}).get('id') == interrupt_id:
                    remaining_time = end_time - time.time()
                    if remaining_time > 0:
                        await asyncio.sleep(remaining_time)
            finally:
                if self.active_interrupts.get(fixture_id, {}).get('id') == interrupt_id:
                    del self.active_interrupts[fixture_id]
                
                # Remove the fixture from interrupted set and restore original state
                self.interrupted_fixtures.remove(fixture_id)
                if fixture_id in self.original_states:
                    self.dmx_state_manager.update_fixture(fixture_id, self.original_states[fixture_id], override=True)
                    del self.original_states[fixture_id]

            logger.info(f"Effect completed for fixture {fixture_id}.")
            logger.debug(f"Completed {step_count} steps for fixture {fixture_id} over {duration} seconds")
            return True

    def interrupt_fixture_sync(self, fixture_id, duration, interrupt_sequence):
        logger.info(f"Starting effect on fixture {fixture_id} for {duration} seconds")
        
        self.active_interrupts[fixture_id] = {'active': True}
        start_time = time.time()
        end_time = start_time + duration
        step_count = 0
        try:
            while time.time() < end_time:
                elapsed_time = time.time() - start_time
                new_values = interrupt_sequence(elapsed_time)
                self.dmx_state_manager.update_fixture(fixture_id, new_values, override=True)
                logger.debug(f"Step {step_count}: Fixture {fixture_id}, Elapsed time: {elapsed_time:.3f}s, New values: {new_values}")
                time.sleep(1 / 44)  # 44Hz update rate
                step_count += 1
        finally:
            if fixture_id in self.active_interrupts:
                del self.active_interrupts[fixture_id]

        logger.info(f"Effect completed for fixture {fixture_id}.")
        logger.debug(f"Completed {step_count} steps for fixture {fixture_id} over {duration} seconds")

    def interrupt_room(self, room, duration, interrupt_sequence):
        room_layout = self.dmx_state_manager.light_config.get_room_layout()
        if room in room_layout:
            for light in room_layout[room]:
                self.interrupt_fixture_sync(light['fixture_id'], duration, interrupt_sequence)
        else:
            logger.warning(f"Room {room} not found in layout")

    def is_fixture_interrupted(self, fixture_id):
        return fixture_id in self.active_interrupts
