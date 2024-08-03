import threading
import time
import logging
import math

logger = logging.getLogger(__name__)

class SequenceRunner(threading.Thread):
    def __init__(self, dmx_state_manager):
        super().__init__()
        self.dmx_state_manager = dmx_state_manager
        self.running = True
        self.time_offset = 0
        self.FREQUENCY = 44  # Default to 44Hz update rate

    def run(self):
        while self.running:
            self.update_sequence()
            time.sleep(1 / self.FREQUENCY)

    def update_sequence(self):
        current_time = time.time() + self.time_offset
        for fixture_id in range(21):
            new_values = self.calculate_new_values(fixture_id, current_time)
            self.dmx_state_manager.update_fixture(fixture_id, new_values)

    def calculate_new_values(self, fixture_id, current_time):
        # This is a simple example of color morphing. You can make this more complex.
        hue = (math.sin(current_time * 0.1 + fixture_id * 0.5) + 1) / 2
        r, g, b = self.hsv_to_rgb(hue, 1, 1)
        return [int(r * 255), int(g * 255), int(b * 255), 0, 0, 0, 0, 0]

    def hsv_to_rgb(self, h, s, v):
        if s == 0.0:
            return (v, v, v)
        i = int(h * 6.)
        f = (h * 6.) - i
        p, q, t = v * (1. - s), v * (1. - s * f), v * (1. - s * (1. - f))
        i %= 6
        if i == 0:
            return (v, t, p)
        if i == 1:
            return (q, v, p)
        if i == 2:
            return (p, v, t)
        if i == 3:
            return (p, q, v)
        if i == 4:
            return (t, p, v)
        if i == 5:
            return (v, p, q)

    def stop(self):
        self.running = False
