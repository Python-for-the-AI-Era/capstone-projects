import random
from fastapi import FastAPI, BackgroundTasks, HTTPException, Header
from sqlalchemy import create_engine, text
import logging

app = FastAPI(title="Sendbox Webhook Receiver")

# Simple SQLite for demonstration
engine = create_engine("sqlite:///logistics.db")

async def process_delivery_update(webhook_id: str, status: str):
    """
    FAULTY LOGIC: This runs AFTER the 200 OK is sent.
    If it fails here, the partner (DHL/GIG) thinks we got it.
    """
    try:
        # Simulate intermittent DB timeout (12% failure rate)
        if random.random() < 0.12:
            raise Exception("Database Connection Timeout - Peak Load")
            
        with engine.connect() as conn:
            query = text("INSERT INTO updates (webhook_id, status) VALUES (:id, :st)")
            conn.execute(query, {"id": webhook_id, "st": status})
            conn.commit()
            print(f"Successfully processed {webhook_id}")
            
    except Exception as e:
        # This log goes to a console that nobody is watching at 2 AM
        logging.error(f"SILENT ERROR for {webhook_id}: {str(e)}")

@app.post("/webhooks/courier-partner")
async def receive_webhook(data: dict, background_tasks: BackgroundTasks):
    webhook_id = data.get("id")
    status = data.get("status")
    
    # Fire and forget... literally.
    background_tasks.add_task(process_delivery_update, webhook_id, status)
    
    return {"message": "Accepted"} # Always returns 200