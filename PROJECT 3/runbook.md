# Sendbox Webhook Reliability Runbook

## The Problem
Explain why `BackgroundTasks` was the wrong choice for financial/logistics data updates.

## The Celery Solution
1. **Idempotency Strategy:** How did you handle duplicate webhooks from GIG/DHL?
2. **Retry Strategy:** What is the `max_retries` and `countdown` logic?
3. **Dead Letter Queue:** What happens to a webhook that fails 5 times in a row?

## Operational Monitoring
- How do we use `GET /admin/webhooks` to see current failures?
- How do we manually trigger a "Re-run" of failed tasks?

## Signature Verification (Stretch Goal)
Explain the HMAC-SHA256 process used to ensure webhooks actually came from our partners.