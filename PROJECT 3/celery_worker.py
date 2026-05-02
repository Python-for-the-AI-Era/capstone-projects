from celery import Celery

# Student must configure this to use Redis or RabbitMQ
celery_app = Celery('tasks', broker='redis://localhost:6379/0')

@celery_app.task(bind=True)
def process_webhook_task(self, webhook_id, status):
    """
    TASK: Move the logic from app.py to here.
    Implement:
    1. Idempotency check (Has this ID been seen?)
    2. Retry logic with exponential backoff.
    """
    pass