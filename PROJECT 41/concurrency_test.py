import asyncio
import httpx

async def hammer_order_system():
    url = "http://localhost:8000/order/product/42"
    async with httpx.AsyncClient() as client:
        # Fire 50 requests at the exact same time
        tasks = [client.post(url, json={"user_id": i}) for i in range(50)]
        responses = await asyncio.gather(*tasks)
        
    successes = [r for r in responses if r.status_code == 200]
    print(f"Total Successes: {len(successes)}") # Usually > 1 in a buggy system