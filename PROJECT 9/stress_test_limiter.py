import asyncio
import httpx
import time

async def hit_api(client, user_id):
    resp = await client.get(
        "/data/census", 
        headers={"Authorization": f"Bearer {user_id}_free"}
    )
    return resp.status_code

async def main():
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        # Hammer the API with 150 requests for a limit of 100
        tasks = [hit_api(client, "free_user") for _ in range(150)]
        results = await asyncio.gather(*tasks)
        
        successes = [r for r in results if r == 200]
        limited = [r for r in results if r == 429]
        
        print(f"Total Requests: 150")
        print(f"Successes (Expected 100): {len(successes)}")
        print(f"Rate Limited: {len(limited)}")

if __name__ == "__main__":
    asyncio.run(main())