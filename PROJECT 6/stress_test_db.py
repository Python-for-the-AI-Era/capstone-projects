import time
import asyncio
from sqlalchemy import text
from database import engine, AsyncSessionLocal

async def setup_big_data():
    """Simulates 1 million rows of orders."""
    print("Generating 1,000,000 rows... (This represents our 40M row production)")
    # (Student should implement an efficient bulk insert here)
    pass

async def run_slow_query():
    async with AsyncSessionLocal() as session:
        start = time.perf_counter()
        # EXPLAIN ANALYZE helps see the "Sequential Scan" (The enemy)
        result = await session.execute(text(
            "EXPLAIN ANALYZE SELECT sum(amount) FROM orders WHERE strftime('%m', created_at) = '06'"
        ))
        for row in result:
            print(row[0])
        end = time.perf_counter()
        print(f"Query took: {end - start:.4f} seconds")

if __name__ == "__main__":
    asyncio.run(run_slow_query())