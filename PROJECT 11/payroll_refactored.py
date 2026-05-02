from celery import group, chord
from celery_app import app # Standard Celery config

@app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def process_single_payment(self, emp_id):
    """
    TASK: Implement the Rate Limiting logic here.
    Check Redis for tokens before calling the BankAPI.
    """
    pass

@app.task
def send_payroll_summary(results):
    """
    The Callback: Runs only after all 5,000 tasks are done.
    """
    total_paid = sum(1 for r in results if r is True)
    return f"Completed! {total_paid} employees paid."

# The student should call it like this:
# workflow = chord(group(process_single_payment.s(i) for i in ids))(send_payroll_summary.s())