"""
Scrapy settings for distributed Nigerian news crawler.

Configures Redis-based distributed crawling, deduplication,
politeness controls, and monitoring.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Project settings
BOT_NAME = 'nigerian_news_crawler'
SPIDER_MODULES = ['crawler.spiders']
NEWSPIDER_MODULE = 'crawler.spiders'

# Redis settings for distributed crawling
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', '')

# Scrapy-Redis settings
SCHEDULER = "scrapy_redis.scheduler.Scheduler"
DUPEFILTER_CLASS = "scrapy_redis.dupefilter.RFPDupeFilter"
SCHEDULER_PERSIST = True
SCHEDULER_QUEUE_CLASS = 'scrapy_redis.queue.PriorityQueue'
SCHEDULER_FLUSH_ON_START = True

# Redis deduplication settings
DUPEFILTER_KEY = '%(spider)s:dupefilter'
QUEUE_KEY = '%(spider)s:requests'
QUEUE_SERIALIZER = 'scrapy_redis.queue.PriorityQueue'
QUEUE_PRIORITY_CLASS = 'scrapy_redis.queue.PriorityQueue'

# Custom deduplication with MD5 fingerprints
DUPEFILTER_DEBUG = False
DUPEFILTER_CLASS = 'crawler.middleware.RedisMD5DupeFilter'

# Politeness settings
CONCURRENT_REQUESTS = int(os.getenv('CONCURRENT_REQUESTS', 16))
CONCURRENT_REQUESTS_PER_DOMAIN = int(os.getenv('CONCURRENT_REQUESTS_PER_DOMAIN', 2))
DOWNLOAD_DELAY = float(os.getenv('DOWNLOAD_DELAY', 2))
RANDOMIZE_DOWNLOAD_DELAY = float(os.getenv('RANDOMIZE_DOWNLOAD_DELAY', 1))

# AutoThrottle settings
AUTOTHROTTLE_ENABLED = os.getenv('AUTOTHROTTLE_ENABLED', 'True').lower() == 'true'
AUTOTHROTTLE_START_DELAY = float(os.getenv('AUTOTHROTTLE_START_DELAY', 2))
AUTOTHROTTLE_MAX_DELAY = float(os.getenv('AUTOTHROTTLE_MAX_DELAY', 10))
AUTOTHROTTLE_TARGET_CONCURRENCY = float(os.getenv('AUTOTHROTTLE_TARGET_CONCURRENCY', 2.0))
AUTOTHROTTLE_DEBUG_STATS_CONS = os.getenv('AUTOTHROTTLE_DEBUG_STATS_CONS', 'False').lower() == 'true'

# Rate limiting
DOWNLOAD_TIMEOUT = int(os.getenv('DOWNLOAD_TIMEOUT', 30))
RESPONSE_TIMEOUT = int(os.getenv('RESPONSE_TIMEOUT', 30))
CONNECT_TIMEOUT = int(os.getenv('CONNECT_TIMEOUT', 10))

# HTTP cache settings for fault tolerance
HTTPCACHE_ENABLED = os.getenv('HTTPCACHE_ENABLED', 'True').lower() == 'true'
HTTPCACHE_EXPIRATION_SECS = int(os.getenv('HTTPCACHE_EXPIRATION_SECS', 3600))
HTTPCACHE_DIR = os.getenv('HTTPCACHE_DIR', 'httpcache')
HTTPCACHE_IGNORE_HTTP_CODES = [500, 502, 503, 504, 408, 429]
HTTPCACHE_IGNORE_MISSING = True
HTTPCACHE_IGNORE_SCHEMES = ['file']
HTTPCACHE_STORAGE = 'scrapy.extensions.httpcache.FilesystemCacheStorage'

# User agent and headers
USER_AGENT = os.getenv('CRAWLER_USER_AGENT', 'NigerianNewsResearchCrawler/1.0 (+https://university.edu/research)')
ROBOTSTXT_OBEY = True

# Middleware settings
DOWNLOADER_MIDDLEWARES = {
    'crawler.middleware.RandomUserAgentMiddleware': 400,
    'crawler.middleware.RetryMiddleware': 500,
    'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None,
    'scrapy.downloadermiddlewares.retry.RetryMiddleware': None,
    'scrapy.downloadermiddlewares.httpcache.HttpCacheMiddleware': 600,
    'scrapy.downloadermiddlewares.stats.StatsMiddleware': 700,
    'scrapy_redis.spiders.RedisMixin': 800,
}

SPIDER_MIDDLEWARES = {
    'scrapy.spidermiddlewares.depth.DepthMiddleware': 900,
    'scrapy.spidermiddlewares.httperror.HttpErrorMiddleware': 950,
    'scrapy.spidermiddlewares.offsite.OffsiteMiddleware': 1000,
    'scrapy.spidermiddlewares.referer.RefererMiddleware': 1001,
    'scrapy.spidermiddlewares.urllength.UrlLengthMiddleware': 1002,
    'scrapy.spidermiddlewares.depth.DepthMiddleware': 1003,
}

# Item pipelines
ITEM_PIPELINES = {
    'crawler.pipelines.ValidationPipeline': 200,
    'crawler.pipelines.DeduplicationPipeline': 300,
    'crawler.pipelines.SQLiteStoragePipeline': 400,
    'crawler.pipelines.PostgreSQLPipeline': 500,
    'crawler.pipelines.MonitoringPipeline': 600,
}

# Depth and crawling limits
DEPTH_LIMIT = 3
DEPTH_STATS = True
DEPTH_PRIORITY = 1

# Logging settings
LOG_LEVEL = os.getenv('CRAWLER_LOG_LEVEL', 'INFO')
LOG_FILE = 'logs/crawler.log'
LOG_ENCODING = 'utf-8'

# Stats collection
STATS_CLASS = 'scrapy_redis.stats.RedisStatsCollector'
STATS_ENABLED = True
STATS_DUMP_ENABLED = True

# Close spider settings
CLOSESPIDER_TIMEOUT = 300
CLOSESPIDER_PAGECOUNT = 0
CLOSESPIDER_ITEMCOUNT = 500000
CLOSESPIDER_ERRORCOUNT = 100

# Database settings
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///crawler_data.db')

# Monitoring settings
PROMETHEUS_ENABLED = True
PROMETHEUS_PORT = int(os.getenv('PROMETHEUS_PORT', 9090))
STATS_EXPORT_INTERVAL = int(os.getenv('STATS_EXPORT_INTERVAL', 60))
ALERT_THRESHOLD_ITEMS_PER_MINUTE = int(os.getenv('ALERT_THRESHOLD_ITEMS_PER_MINUTE', 100))

# Nigerian news sites configuration
BASE_DOMAINS = os.getenv('BASE_DOMAINS', 'vanguardngr.com,punchng.com,thenationonlineng.net,thisdaylive.com,guardian.ng,sunnewsonline.com,leadership.ng,dailytrust.com').split(',')
SEED_URLS = os.getenv('SEED_URLS', 'https://vanguardngr.com,https://punchng.com,https://thenationonlineng.net').split(',')

# Request settings
REQUESTS_PER_MINUTE = int(os.getenv('REQUESTS_PER_MINUTE', 120))
BANDWIDTH_LIMIT = int(os.getenv('BANDWIDTH_LIMIT', 1000000))

# Retry settings
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]
RETRY_BACKOFF_POLICY = 'exponential'

# Telnet console
TELNETCONSOLE_ENABLED = False
TELNETCONSOLE_HOST = '127.0.0.1'
TELNETCONSOLE_PORT = [6023, 6024, 6025, 6026, 6027]

# Extensions
EXTENSIONS = {
    'scrapy.extensions.closespider.CloseSpider': 500,
    'scrapy.extensions.statsmailer.StatsMailer': 600,
    'scrapy.extensions.logstats.LogStats': 700,
    'scrapy.extensions.telnet.TelnetConsole': 800,
    'crawler.monitoring.PrometheusStatsExtension': 900,
}

# Mail settings for alerts
MAIL_ENABLED = False
MAIL_FROM = 'crawler@university.edu'
MAIL_HOST = 'localhost'
MAIL_PORT = 25

# Custom settings for research crawler
RESEARCH_MODE = True
SAVE_RAW_HTML = True
EXTRACT_IMAGES = False
FOLLOW_REDIRECTS = True
REDIRECT_MAX_TIMES = 5

# URL filtering
URL_FILTERS_ENABLED = True
ALLOWED_DOMAINS = BASE_DOMAINS
ALLOWED_REGEX = [r'.*/(news|article|story|post)/.*/']
DENIED_REGEX = [r'.*/(tag|category|author)/.*/', r'.*/(login|register|contact).*/']

# Content filtering
MIN_CONTENT_LENGTH = 500
MAX_CONTENT_LENGTH = 1000000
CONTENT_TYPE_WHITELIST = ['text/html', 'text/plain', 'application/xhtml+xml']

# Performance tuning
REACTOR_THREADPOOL_MAXSIZE = 20
LOGSTATS_INTERVAL = 60.0
