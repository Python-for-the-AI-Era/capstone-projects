"""
Custom middleware for the distributed web crawler.

Includes Redis-based deduplication, retry logic, and user agent rotation.
"""

from .redis_dupefilter import RedisMD5DupeFilter
from .retry_middleware import RetryMiddleware
from .user_agent_middleware import RandomUserAgentMiddleware

__all__ = [
    'RedisMD5DupeFilter',
    'RetryMiddleware', 
    'RandomUserAgentMiddleware'
]
