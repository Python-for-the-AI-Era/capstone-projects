import redis.asyncio as redis

# The student must implement the logic to store messages in a stream
# and fetch them by ID during reconnection.
redis_client = redis.from_url("redis://localhost:6379", decode_responses=True)