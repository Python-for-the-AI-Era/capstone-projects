import time
import httpx

def dispatch_notifications_legacy(recipients, message):
    """
    FAULTY SERIAL LOGIC:
    If each HTTP call takes 100ms (50ms latency + 50ms processing):
    1,000,000 * 0.1s = 100,000 seconds (~27 hours).
    Even with 10 workers, it's still nearly 3 hours.
    """
    results = []
    with httpx.Client() as client:
        for user_id in recipients:
            # Sequential blocking calls
            resp = client.post("https://mock-fcm.google.com/send", json={
                "to": user_id,
                "body": message
            })
            results.append(resp.status_code)
    return results