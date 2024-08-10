import time
import logging

logger = logging.getLogger(__name__)

class SyncManager:
    def __init__(self):
        self.offset = 0

    def sync_time(self, server_time):
        current_time = time.time()
        self.offset = server_time - current_time
        logger.info(f"Time synchronized. Offset: {self.offset:.6f} seconds")

    def get_synced_time(self):
        return time.time() + self.offset
