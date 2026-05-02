import asyncio
import httpx
import time

async def hit_health(client):
    start = time.perf_counter()
    resp = await client.get("/health")
    print(f"Health Check: {resp.status_code} in {time.perf_counter() - start:.4f}s")

async def hit_reconcile(client):
    print("Launching Heavy Reconcile...")
    resp = await client.get("/reconcile")
    print(f"Reconcile: {resp.status_code}")

async def main():
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000") as client:
        # Start the heavy one first, then immediately try to get a health check
        task1 = asyncio.create_task(hit_reconcile(client))
        await asyncio.sleep(0.5) # Wait half a second
        task2 = asyncio.create_task(hit_health(client))
        
        await asyncio.gather(task1, task2)

if __name__ == "__main__":
    asyncio.run(main())