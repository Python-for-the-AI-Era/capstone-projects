import threading

class GlobalCounter:
    def __init__(self):
        self.counts = {}

    def increment(self, page_id: str):
        """
        FAULTY NON-ATOMIC LOGIC:
        This is a 'Read-Modify-Write' operation.
        Thread A reads 10.
        Thread B reads 10.
        Thread A writes 11.
        Thread B writes 11. 
        Result: 11 (One increment is LOST).
        """
        if page_id not in self.counts:
            self.counts[page_id] = 0
        self.counts[page_id] += 1

# TASK: The student will use this to prove the race condition.