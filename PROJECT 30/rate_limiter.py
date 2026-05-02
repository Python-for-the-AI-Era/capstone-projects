import redis

r = redis.Redis(host='localhost', port=6379, db=0)

def check_rate_limit(email: str):
    key = f"pwd_reset_limit:{email}"
    count = r.incr(key)
    if count == 1:
        r.expire(key, 3600) # 1 hour window
    if count > 3:
        return False # Rate limit exceeded
    return True