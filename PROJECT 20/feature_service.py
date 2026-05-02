async def get_transaction_velocity(user_id: str):
    """
    Computes 'transactions in last hour' using Redis.
    - ZREMRANGEBYSCORE: Remove transactions older than 1 hour.
    - ZADD: Add current transaction timestamp.
    - ZCARD: Count remaining items.
    """
    now = time.time()
    key = f"velocity:{user_id}"
    await r.zremrangebyscore(key, 0, now - 3600)
    await r.zadd(key, {str(now): now})
    return await r.zcard(key)