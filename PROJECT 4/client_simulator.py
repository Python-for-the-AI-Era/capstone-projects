import asyncio
import websockets
import json

async def simulate_trader():
    uri = "ws://localhost:8000/ws/feed"
    async with websockets.connect(uri) as websocket:
        print("Connected to Tradespark...")
        for i in range(10):
            msg = await websocket.recv()
            print(f"Received: {msg}")
            
            if i == 5:
                print("!!! SIMULATING NETWORK CRASH (Dirty Disconnect) !!!")
                # We exit without calling websocket.close()
                return 

if __name__ == "__main__":
    asyncio.run(simulate_trader())
    # After this finishes, the student should check the server logs 
    # to see that the server still thinks 1 client is connected.