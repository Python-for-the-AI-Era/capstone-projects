# Automated Competitive Intelligence Pipeline

## 1. Monitoring Scope
- **Sources:** 5 Competitor domains (Pricing, Blog, Career pages).
- **Frequency:** Every Monday at 08:00 WAT via **Celery Beat**.

## 2. Intelligence Logic
- **Cost Optimization:** Redis content hashing ensures we only pay for LLM tokens when a competitor actually updates their site.
- **Analysis:** GPT-4o-mini is tuned for high-density information extraction, filtering out marketing fluff.

## 3. Delivery Channels
- **HTML Email:** Optimized for Outlook/Gmail mobile.
- **PDF Archive:** High-fidelity document for long-term storage and internal sharing.

## 4. Maintenance
Spiders are containerized in Docker. If a competitor changes their site structure, the Playwright selector logs will trigger a Slack alert for quick adjustment.