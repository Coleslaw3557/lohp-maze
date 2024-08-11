import time
import uuid

class SyncManager:
    def __init__(self):
        self.effect_counter = 0

    def generate_effect_id(self):
        self.effect_counter += 1
        return f"{time.time()}-{self.effect_counter}-{uuid.uuid4().hex[:8]}"

    def get_sync_time(self):
        return time.time()
