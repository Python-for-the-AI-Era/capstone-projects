# PriceGuard: Real-Time Monitoring System

## 1. System Architecture
- **Scraper:** Playwright (Headless Chromium) for JS-rendered content.
- **Queue:** Celery + Redis for reliable task scheduling.
- **Database:** PostgreSQL for historical price analysis.

## 2. Notification Logic
- **Target Hit:** Alerts trigger only when `current_price <= target`.
- **Anti-Spam:** Cooldown of 24 hours per product to preserve SMS credits.

## 3. Scalability
The current Docker setup supports up to 100 concurrent monitors. To scale to 10,000, we would move the scrapers to a **browserless.io** cluster.

## 4. Price Prediction (Stretch Goal)
Using `scikit-learn` LinearRegression, we analyze the slope of the last 30 days. If the slope is negative, we notify the user: *"Price is trending down; you might want to wait another 3 days!"*