# TASK: Measure Ops/Sec for each implementation.
# 1. LockedCounter (Slowest due to lock contention)
# 2. QueueCounter (Good for decoupling)
# 3. RedisCounter (Best for distributed systems)
# 4. BatchCounter (The Stretch Goal - Periodic Redis flush)