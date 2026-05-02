import time
from redis.asyncio import Redis

class RateLimiter:
    def __init__(self, redis_client: Redis):
        self.redis = redis_client

    async def is_allowed_fixed_window(self, user_id: str, limit: int, window: int = 3600):
        """
        FAULTY: Fixed Window with Race Condition.
        If two requests hit at the same microsecond, they might both see 
        the count as 99 and allow the request, resulting in 101/100.
        """
        key = f"rate_limit:{user_id}"
        current_count = await self.redis.get(key)
        
        if current_count and int(current_count) >= limit:
            return False
            
        await self.redis.incr(key)
        if not current_count:
            await self.redis.expire(key, window)
            
        return True

    # TASK: Replace the above with a Sliding Window using Sorted Sets (ZSET)
    # TASK: Move the ZSET logic into a Lua Script for atomicity.