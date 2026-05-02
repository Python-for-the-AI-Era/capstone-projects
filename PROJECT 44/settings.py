# Task 1: Distributed URL Frontier
SCHEDULER = "scrapy_redis.scheduler.Scheduler"
DUPEFILTER_CLASS = "scrapy_redis.dupefilter.RFPDupeFilter"

# Persistence: Don't clear Redis queue on pause/stop
SCHEDULER_PERSIST = True

# Task 3: Politeness (The "Good Citizen" Config)
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 2.0
AUTOTHROTTLE_MAX_DELAY = 60.0
CONCURRENT_REQUESTS_PER_DOMAIN = 2
DOWNLOAD_DELAY = 2