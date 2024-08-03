import time
import logging

logger = logging.getLogger(__name__)

class InterruptHandler:
    def __init__(self, dmx_state_manager):
        self.dmx_state_manager = dmx_state_manager

    def interrupt_fixture(self, fixture_id, duration, interrupt_sequence):
        original_state = self.dmx_state_manager.get_fixture_state(fixture_id)
        
        start_time = time.time()
        end_time = start_time + duration
        while time.time() < end_time:
            elapsed_time = time.time() - start_time
            new_values = interrupt_sequence(fixture_id, elapsed_time)
            self.dmx_state_manager.update_fixture(fixture_id, new_values)
            time.sleep(0.025)  # 40Hz update rate

        # Restore the original state after the effect
        self.dmx_state_manager.update_fixture(fixture_id, original_state)

    def interrupt_room(self, room, duration, interrupt_sequence):
        room_layout = self.dmx_state_manager.light_config.get_room_layout()
        if room in room_layout:
            for light in room_layout[room]:
                self.interrupt_fixture(light['fixture_id'], duration, interrupt_sequence)
        else:
            logger.warning(f"Room {room} not found in layout")
