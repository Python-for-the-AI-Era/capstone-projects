from fastapi import FastAPI, Depends, HTTPException, Header, Response
from limiter import RateLimiter
import redis.asyncio as redis

app = FastAPI()
r = redis.from_url("redis://localhost:6379", decode_responses=True)
limiter = RateLimiter(r)

def get_user_tier(authorization: str = Header(...)):
    # Simulating JWT decoding. In a real app, this comes from the token.
    # Returns: (user_id, limit)
    if "enterprise" in authorization: return ("ent_1", float('inf'))
    if "paid" in authorization: return ("paid_1", 10000)
    return ("free_1", 100)

@app.get("/data/census")
async def get_census_data(user_info=Depends(get_user_tier)):
    user_id, limit = user_info
    
    # TASK: Integrate the RateLimiter here.
    # If not allowed, raise HTTPException(status_code=429, detail="Too Many Requests")
    # TASK: Set X-RateLimit headers in the response.
    
    return {"data": "Nigeria Census Data 2026"}