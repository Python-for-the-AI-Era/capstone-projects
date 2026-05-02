import httpx
import asyncio
import time

async def stress_test():
    async with httpx.AsyncClient() as client:
        latencies = []
        for _ in range(1000):
            start = time.perf_counter()
            await client.post("http://localhost:8000/v1/score", json=mock_data)
            latencies.append(time.perf_counter() - start)
        
        p99 = sorted(latencies)[int(len(latencies) * 0.99)]
        print(f"P99 Latency: {p99 * 1000:.2f}ms") # Must be < 50ms