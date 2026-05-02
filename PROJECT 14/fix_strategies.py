import threading
import queue
import redis

# FIX 1: Mutual Exclusion (Locking)
class LockedCounter:
    def __init__(self):
        self.lock = threading.Lock()
        self.counts = {}

    def increment(self, page_id):
        with self.lock:
            # Atomic block
            pass

# FIX 2: Single-Writer Pattern (Queues)
class QueueCounter:
    def __init__(self):
        self.q = queue.Queue()
        # Student must start a background thread that consumes from self.q
        # and updates a local dict.

# FIX 3: External Atomic Ops (Redis)
class RedisCounter:
    def __init__(self):
        self.r = redis.Redis()

    def increment(self, page_id):
        # Use Redis INCR
        pass