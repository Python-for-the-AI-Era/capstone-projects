import redis.asyncio as redis

r = redis.from_url("redis://localhost:6379", decode_responses=True)

async def revoke_token(jti: str, expires_in_seconds: int):
    """
    On logout or password change, we blacklist the token.
    We set the TTL in Redis to the remaining life of the token 
    so it auto-cleans itself once it naturally expires.
    """
    await r.setex(f"blacklist:{jti}", expires_in_seconds, "revoked")

async def is_token_revoked(jti: str):
    return await r.exists(f"blacklist:{jti}")