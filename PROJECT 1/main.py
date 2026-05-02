from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import asyncio
import database

app = FastAPI()

@app.get("/webhook/flutterwave")
async def handle_webhook(db: AsyncSession = Depends(database.get_db)):
    # Simulating a slow database query or a network hang during peak hours
    # This keeps the connection busy for too long
    await db.execute(text("SELECT pg_sleep(30)")) 
    await db.commit()
    return {"status": "payment processed"}

# TASK 2: User needs to implement /health/db here