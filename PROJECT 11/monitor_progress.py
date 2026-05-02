@app.task(bind=True)
def payment_task_with_progress(self, emp_id, current_idx, total):
    # Update state so the user sees "Processing 2500/5000"
    self.update_state(
        state='PROGRESS',
        meta={'current': current_idx, 'total': total, 'percent': (current_idx/total)*100}
    )
    # ... call bank API ...