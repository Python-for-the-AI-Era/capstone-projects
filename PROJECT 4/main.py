import asyncio
import random
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from manager import manager

app = FastAPI()

@app.websocket("/ws/feed")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Simulating live trade updates
            price_update = {
                "symbol": "BTC/USD", 
                "price": random.uniform(60000, 65000)
            }
            await manager.broadcast(price_update)
            await asyncio.sleep(1) # Send update every second
            
            # TASK: The student needs to implement the "Ping/Pong" logic here
            # and handle the ?last_id query parameter for reconnection.
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)