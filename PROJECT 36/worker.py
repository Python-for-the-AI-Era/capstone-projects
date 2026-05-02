def send_email_task(user_id, template_id, email_data):
    key = generate_idempotency_key(user_id, template_id, email_data)
    
    # 1. Try to claim the task
    if not acquire_lock(key):
        print(f"Skipping duplicate: {key}")
        return

    try:
        # 2. Perform the actual sending
        # send_via_smtp(user_id, email_data)
        print(f"Successfully sent email: {key}")
    except Exception as e:
        # 3. Handle Failure: Release lock so it can be retried
        r.delete(key)
        print(f"Send failed. Lock released for retry: {e}")