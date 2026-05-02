import asyncio
from fastapi import WebSocket
from redis.asyncio import Redis

async def auction_broadcaster(websocket: WebSocket, auction_id: str, r: Redis):
    await websocket.accept()
    pubsub = r.pubsub()
    await pubsub.subscribe(f"auction_updates:{auction_id}")
    
    # STRETCH GOAL: On connect, fetch the last 50 bids from a Redis List
    
    try:
        async for message in pubsub.listen():
            if message['type'] == 'message':
                await websocket.send_text(message['data'])
    except Exception:
        await pubsub.unsubscribe(f"auction_updates:{auction_id}")