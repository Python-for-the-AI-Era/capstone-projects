import redis

r = redis.Redis(host='localhost', port=6379, db=1)

def check_quota(project_key):
    """
    TASK: Use Redis to track the 'tokens' available for this minute.
    If tokens < 1, the worker must sleep or retry later.
    Ensure this is ATOMIC (use a Lua script or Redis transaction).
    """
    pass