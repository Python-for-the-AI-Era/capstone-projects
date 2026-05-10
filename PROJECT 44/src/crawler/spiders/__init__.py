"""
Spider classes for Nigerian news sites.

Includes distributed Redis-based spiders for collecting news articles
with proper politeness controls and fault tolerance.
"""

from .nigerian_news import NigerianNewsSpider
from .vanguard_spider import VanguardSpider
from .punch_spider import PunchSpider
from .guardian_spider import GuardianSpider

__all__ = [
    'NigerianNewsSpider',
    'VanguardSpider',
    'PunchSpider', 
    'GuardianSpider'
]
