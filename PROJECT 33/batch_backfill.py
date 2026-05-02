import asyncio
import asyncpg

async def backfill():
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    
    # Process 10k rows at a time to stay under the radar
    batch_size = 10000
    while True:
        # TASK: Update a chunk of rows where the new column is still NULL
        result = await conn.execute("""
            UPDATE sensor_readings 
            SET energy_source_id = 1 
            WHERE id IN (
                SELECT id FROM sensor_readings 
                WHERE energy_source_id IS NULL 
                LIMIT $1
            )
        """, batch_size)
        
        if result == "UPDATE 0":
            break # Backfill complete
            
        await asyncio.sleep(0.1) # Yield to production traffic
    await conn.close()