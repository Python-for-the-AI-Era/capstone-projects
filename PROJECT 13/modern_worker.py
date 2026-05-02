import asyncio
import httpx
from celery import Celery

app = Celery('push_alert', broker='redis://localhost:6379/0')

async def send_batch_async(batch, message, semaphore):
    async with semaphore:
        async with httpx.AsyncClient() as client:
            # TASK: Dispatch all notifications in this batch concurrently
            # using asyncio.gather.
            pass

@app.task
def dispatch_batch_task(batch, message):
    """
    Each Celery worker picks up a batch of 500.
    It then uses asyncio to hammer the API with 20-50 concurrent connections.
    """
    semaphore = asyncio.Semaphore(20) # Back-pressure to not overwhelm the NIC
    return asyncio.run(send_batch_async(batch, message, semaphore))