# Incident Report: Friday Night 503 Errors

## Executive Summary
**Date:** [Insert Date]
**Status:** [Fixed/Investigating]
**Impact:** Payment webhooks failing under high concurrency.

## Technical Root Cause
Explain why `asyncpg pool exhausted` occurred and why the connections weren't returning to the pool.

## Resolution
1. How did you fix the `get_db` dependency?
2. What pool settings were changed in `database.py`?
3. How does the new health check help prevent this in the future?

## Performance Metrics
* **P99 Latency (Before):** * **P99 Latency (After):** ```

---

### Instructions for the "Staff Member" (The Student)
1. **Spin up the API:** `uvicorn main:app --reload`
2. **Run the crash script:** Observe how the first 10 requests hang, and the next 5 wait forever until the pool times out.
3. **Monitor:** Realize you have no way to see the DB status—you must build the `/health/db` endpoint using `database.engine.pool.status()`.
4. **The Fix:** Apply the `try/finally` block to the generator and configure the `pool_timeout`.