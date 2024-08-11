import time
import logging

logger = logging.getLogger(__name__)

class SyncManager:
    def __init__(self):
        self.offset = 0
        self.last_sync_time = 0

    def sync_time(self, server_time):
        current_time = time.time()
        self.offset = server_time - current_time
        self.last_sync_time = current_time
        logger.info(f"Time synchronized. Offset: {self.offset:.6f} seconds")

    def get_synced_time(self):
        return time.time() + self.offset

    def get_time_offset(self):
        return self.offset

    def should_resync(self):
        return time.time() - self.last_sync_time > 300  # Resync every 5 minutes
