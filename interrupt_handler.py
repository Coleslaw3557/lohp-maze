import time
import logging

logger = logging.getLogger(__name__)

class InterruptHandler:
    def __init__(self, dmx_state_manager):
        self.dmx_state_manager = dmx_state_manager

    def interrupt_fixture(self, fixture_id, duration, interrupt_sequence):
        self.dmx_state_manager.reset_fixture(fixture_id)
        
        start_time = time.time()
        while time.time() - start_time < duration:
            new_values = interrupt_sequence(fixture_id, time.time() - start_time)
            self.dmx_state_manager.update_fixture(fixture_id, new_values)
            time.sleep(0.025)  # 40Hz update rate

        self.dmx_state_manager.reset_fixture(fixture_id)

    def interrupt_room(self, room, duration, interrupt_sequence):
        room_layout = self.dmx_state_manager.light_config.get_room_layout()
        if room in room_layout:
            for light in room_layout[room]:
                self.interrupt_fixture(light['fixture_id'], duration, interrupt_sequence)
        else:
            logger.warning(f"Room {room} not found in layout")
