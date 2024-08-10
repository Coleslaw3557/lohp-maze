import threading
import logging

logger = logging.getLogger(__name__)

class DMXStateManager:
    def __init__(self, num_fixtures, channels_per_fixture):
        self.num_fixtures = num_fixtures
        self.channels_per_fixture = channels_per_fixture
        self.state = [0] * (num_fixtures * channels_per_fixture)
        self.locks = [threading.Lock() for _ in range(num_fixtures)]

    def update_fixture(self, fixture_id, channel_values, override=False):
        with self.locks[fixture_id]:
            start_index = fixture_id * self.channels_per_fixture
            if override:
                self.state[start_index:start_index + self.channels_per_fixture] = channel_values
            else:
                for i, value in enumerate(channel_values):
                    if value is not None:
                        self.state[start_index + i] = value

    def get_full_state(self):
        return [int(value) for value in self.state]

    def reset_fixture(self, fixture_id):
        with self.locks[fixture_id]:
            start_index = fixture_id * self.channels_per_fixture
            self.state[start_index:start_index + self.channels_per_fixture] = [0] * self.channels_per_fixture

    def reset_all_fixtures(self):
        for fixture_id in range(self.num_fixtures):
            self.reset_fixture(fixture_id)

    def get_fixture_state(self, fixture_id):
        with self.locks[fixture_id]:
            start_index = fixture_id * self.channels_per_fixture
            return self.state[start_index:start_index + self.channels_per_fixture]
