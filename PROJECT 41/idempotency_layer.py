import redis

r = redis.Redis(host='localhost', port=6379, db=0)

def is_duplicate_request(user_id, product_id):
    key = f"order_lock:{user_id}:{product_id}"
    # Set the key only if it doesn't exist (NX) with a 60s expiry (EX)
    if not r.set(key, "active", nx=True, ex=60):
        return True # It's a duplicate
    return False