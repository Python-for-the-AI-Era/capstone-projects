from celery import group, chord
from modern_worker import dispatch_batch_task, finalize_broadcast

def start_broadcast(user_ids, message):
    # TASK: Slice user_ids into batches of 500
    batches = [user_ids[i:i + 500] for i in range(0, len(user_ids), 500)]
    
    # TASK: Create a Celery group of tasks
    job = group(dispatch_batch_task.s(batch, message) for batch in batches)
    
    # TASK: Wrap in a chord to trigger finalize_broadcast when done
    callback = finalize_broadcast.s(broadcast_id="ABC-123")
    chord(job)(callback)