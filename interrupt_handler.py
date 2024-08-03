import time
import logging

logger = logging.getLogger(__name__)

class InterruptHandler:
    def __init__(self, dmx_state_manager):
        self.dmx_state_manager = dmx_state_manager

    def interrupt_fixture(self, fixture_id, duration, interrupt_sequence):
        logger.info(f"Starting effect on fixture {fixture_id} for {duration} seconds")
        
        start_time = time.time()
        end_time = start_time + duration
        step_count = 0
        while time.time() < end_time:
            elapsed_time = time.time() - start_time
            new_values = interrupt_sequence(elapsed_time)
            self.dmx_state_manager.update_fixture(fixture_id, new_values, override=True)
            logger.debug(f"Step {step_count}: Fixture {fixture_id}, Elapsed time: {elapsed_time:.3f}s, New values: {new_values}")
            time.sleep(0.025)  # 40Hz update rate
            step_count += 1

        logger.info(f"Effect completed for fixture {fixture_id}.")
        logger.debug(f"Completed {step_count} steps for fixture {fixture_id} over {duration} seconds")

    def interrupt_room(self, room, duration, interrupt_sequence):
        room_layout = self.dmx_state_manager.light_config.get_room_layout()
        if room in room_layout:
            for light in room_layout[room]:
                self.interrupt_fixture(light['fixture_id'], duration, interrupt_sequence)
        else:
            logger.warning(f"Room {room} not found in layout")
