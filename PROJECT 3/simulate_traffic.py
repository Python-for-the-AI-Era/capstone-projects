import httpx
import asyncio
import sqlite3

# Setup DB table
conn = sqlite3.connect("logistics.db")
conn.execute("CREATE TABLE IF NOT EXISTS updates (webhook_id TEXT, status TEXT)")
conn.close()

async def send_updates():
    async with httpx.AsyncClient() as client:
        for i in range(100):
            payload = {"id": f"WH-{i}", "status": "DELIVERED"}
            await client.post("http://127.0.0.1:8000/webhooks/courier-partner", json=payload)

    # Verification
    conn = sqlite3.connect("logistics.db")
    count = conn.execute("SELECT COUNT(*) FROM updates").fetchone()[0]
    print(f"\n--- RESULTS ---")
    print(f"Sent: 100 webhooks")
    print(f"Received in DB: {count}")
    print(f"Lost: {100 - count} updates ({(100-count)}% loss rate)")

if __name__ == "__main__":
    asyncio.run(send_updates())