import threading
import logging

logger = logging.getLogger(__name__)

class DMXStateManager:
    def __init__(self, num_fixtures, channels_per_fixture):
        self.state = [0] * (num_fixtures * channels_per_fixture)
        self.locks = [threading.Lock() for _ in range(num_fixtures)]

    def update_fixture(self, fixture_id, channel_values):
        with self.locks[fixture_id]:
            start_index = fixture_id * 8
            self.state[start_index:start_index + 8] = channel_values

    def get_full_state(self):
        return [int(value) for value in self.state]

    def reset_fixture(self, fixture_id):
        with self.locks[fixture_id]:
            start_index = fixture_id * 8
            self.state[start_index:start_index + 8] = [0] * 8

    def get_fixture_state(self, fixture_id):
        with self.locks[fixture_id]:
            start_index = fixture_id * 8
            return self.state[start_index:start_index + 8]
