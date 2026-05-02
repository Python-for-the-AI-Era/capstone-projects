import hashlib
import redis

r = redis.Redis(host='localhost', port=6379, db=0)

def generate_idempotency_key(user_id, template_id, data):
    """Create a unique hash for the specific email content."""
    raw_str = f"{user_id}:{template_id}:{hash(str(data))}"
    return f"email_lock:{hashlib.sha256(raw_str.encode()).hexdigest()}"

def acquire_lock(key, ttl=86400):
    # SETNX: Set if Not eXists. Atomic operation.
    # Returns True if we got the lock, False if someone else beat us.
    return r.set(key, "processing", nx=True, ex=ttl)