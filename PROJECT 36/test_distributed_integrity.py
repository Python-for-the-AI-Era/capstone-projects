import concurrent.futures

def test_idempotency_under_pressure():
    # Simulate 100 simultaneous workers receiving the same event
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        futures = [
            executor.submit(send_email_task, "user_1", "welcome_tmpl", {"name": "Praise"}) 
            for _ in range(100)
        ]
        concurrent.futures.wait(futures)

    # ASSERT: Check your logs/DB to confirm 'send_via_smtp' was called exactly once.