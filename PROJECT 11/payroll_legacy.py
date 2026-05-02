import time
import logging
from celery import Celery

app = Celery('payroll', broker='redis://localhost:6379/0')

@app.task(name="process_monthly_payroll_legacy")
def process_monthly_payroll_legacy(employee_ids):
    """
    FAULTY SERIAL LOGIC:
    1. If the bank takes 10s per person, 5,000 people = 13.8 hours.
    2. If it fails at person #2,500, the first 2,499 are paid, 
       but we have no easy way to resume for the rest.
    """
    for emp_id in employee_ids:
        try:
            # Mock Bank API call
            print(f"Paying employee {emp_id}...")
            time.sleep(10) # The "Silent Killer" slow API
        except Exception as e:
            # THE SWALLOW: The error is logged but the task doesn't fail
            # so Celery thinks everything is "SUCCESS"
            logging.error(f"Failed to pay {emp_id}: {e}")
            continue 
    return "Payroll Processed"