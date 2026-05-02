# feel free to use this or write your own to prove the system dies under load
import asyncio
import httpx
import time

async def send_webhook(client, id):
    try:
        # We hammer the endpoint that we know is slow
        resp = await client.get("http://127.0.0.1:8000/webhook/flutterwave", timeout=40)
        print(f"Request {id}: {resp.status_code}")
    except Exception as e:
        print(f"Request {id} failed: {e}")

async def main():
    async with httpx.AsyncClient() as client:
        # We send 15 requests to a pool that only holds 10 connections
        tasks = [send_webhook(client, i) for i in range(15)]
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    print("Starting stress test on Paylot API...")
    start = time.time()
    asyncio.run(main())
    print(f"Test finished in {time.time() - start:.2f} seconds")