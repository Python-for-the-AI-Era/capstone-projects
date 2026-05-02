# Research Crawler: Resilience Protocol

## 1. Resilience Strategy
- **The Redis Frontier:** The 'To-Do List' of URLs is stored in Redis. If the server reboots, the workers simply reconnect and continue exactly where they left off.
- **HTTP Caching:** We enabled `HTTPCACHE_ENABLED`. If a specific page fails to parse, we can re-run the logic against the locally cached HTML instead of hitting the news site again.

## 2. Politeness & Ethics
- **Autothrottle:** The crawler automatically slows down if the news site's response time increases. This prevents us from accidentally performing a DoS attack on local news infrastructure.
- **Identity:** Every request includes a `USER_AGENT` identifying the university research department and a contact email.

## 3. Storage
- **Atomic Writes:** Using PostgreSQL's `ON CONFLICT DO NOTHING` ensures that even if two workers try to archive the same page simultaneously, the database remains consistent.

## 4. Scaling
To speed up the crawl, simply spin up a new Docker container with the same `REDIS_URL`. The new worker will automatically start pulling URLs from the central queue.