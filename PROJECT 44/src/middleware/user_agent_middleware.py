"""
Random User Agent middleware for avoiding detection.

Rotates user agents to make the crawler appear more natural
and avoid being blocked by websites.
"""

import random
import logging
from typing import List

from scrapy import signals
from scrapy.http import HtmlResponse
from scrapy.downloadermiddlewares.useragent import UserAgentMiddleware

logger = logging.getLogger(__name__)


class RandomUserAgentMiddleware(UserAgentMiddleware):
    """
    Middleware that randomly rotates user agents for each request.
    
    Helps avoid detection and blocking by websites that monitor
    user agent patterns.
    """
    
    def __init__(self, user_agent_list: List[str] = None):
        """
        Initialize random user agent middleware.
        
        Args:
            user_agent_list: List of user agents to rotate through
        """
        super().__init__()
        
        # Default user agents for news crawling
        self.user_agent_list = user_agent_list or [
            # Modern browsers
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/121.0',
            
            # Mobile browsers
            'Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1',
            'Mozilla/5.0 (iPad; CPU OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1',
            'Mozilla/5.0 (Android 14; Mobile; rv:109.0) Gecko/121.0 Firefox/121.0',
            
            # Research-oriented user agents
            'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)',
            'Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)',
            'Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)',
            
            # Academic user agents
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 (compatible; UniversityResearchBot/1.0)',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 (compatible; MediaResearchCrawler/2.0)',
        ]
        
        # Statistics
        self.user_agent_stats = {}
        
        logger.info(f"RandomUserAgentMiddleware initialized with {len(self.user_agent_list)} user agents")
    
    @classmethod
    def from_crawler(cls, crawler):
        """Create instance from crawler."""
        # Get custom user agents from settings if provided
        user_agents = crawler.settings.getlist('USER_AGENT_LIST')
        
        if not user_agents:
            # Load default user agents for Nigerian news sites
            user_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
                'Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1',
                'Mozilla/5.0 (compatible; UniversityResearchBot/1.0; +https://university.edu/bot)',
            ]
        
        middleware = cls(user_agents)
        
        # Connect to spider signals
        crawler.signals.connect(middleware.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(middleware.spider_closed, signal=signals.spider_closed)
        
        return middleware
    
    def process_request(self, request, spider):
        """
        Process request and set random user agent.
        
        Args:
            request: Scrapy Request object
            spider: Spider instance
            
        Returns:
            None (continues processing)
        """
        # Select random user agent
        user_agent = random.choice(self.user_agent_list)
        
        # Set user agent in request headers
        request.headers.setdefault('User-Agent', user_agent)
        
        # Update statistics
        agent_key = self._get_agent_key(user_agent)
        self.user_agent_stats[agent_key] = self.user_agent_stats.get(agent_key, 0) + 1
        
        if spider.settings.getbool('USER_AGENT_DEBUG', False):
            spider.logger.debug(f"Using User-Agent: {user_agent}")
    
    def _get_agent_key(self, user_agent: str) -> str:
        """Get a short key for user agent statistics."""
        if 'Chrome' in user_agent:
            return 'Chrome'
        elif 'Firefox' in user_agent:
            return 'Firefox'
        elif 'Safari' in user_agent and 'Mobile' in user_agent:
            return 'Safari_Mobile'
        elif 'Safari' in user_agent:
            return 'Safari'
        elif 'Googlebot' in user_agent:
            return 'Googlebot'
        elif 'bingbot' in user_agent:
            return 'Bingbot'
        elif 'UniversityResearchBot' in user_agent:
            return 'UniversityBot'
        elif 'MediaResearchCrawler' in user_agent:
            return 'ResearchCrawler'
        else:
            return 'Other'
    
    def spider_opened(self, spider):
        """Called when spider is opened."""
        spider.logger.info(f"RandomUserAgentMiddleware: Using {len(self.user_agent_list)} user agents")
    
    def spider_closed(self, spider):
        """Called when spider is closed."""
        if self.user_agent_stats:
            total_requests = sum(self.user_agent_stats.values())
            spider.logger.info("User Agent Statistics:")
            
            # Sort by usage count
            sorted_stats = sorted(self.user_agent_stats.items(), key=lambda x: x[1], reverse=True)
            
            for agent_key, count in sorted_stats:
                percentage = (count / total_requests) * 100 if total_requests > 0 else 0
                spider.logger.info(f"  {agent_key}: {count} ({percentage:.1f}%)")
            
            spider.logger.info(f"Total requests processed: {total_requests}")
    
    def get_stats(self) -> dict:
        """
        Get user agent usage statistics.
        
        Returns:
            Dictionary with user agent statistics
        """
        return {
            'user_agent_list_length': len(self.user_agent_list),
            'user_agent_stats': self.user_agent_stats.copy(),
            'total_requests': sum(self.user_agent_stats.values())
        }


class DomainSpecificUserAgentMiddleware(RandomUserAgentMiddleware):
    """
    User agent middleware that uses different user agents for different domains.
    
    Some websites may block certain user agents, so we use domain-specific
    user agent rotation to maximize success rates.
    """
    
    def __init__(self, domain_user_agents: dict = None):
        """
        Initialize domain-specific user agent middleware.
        
        Args:
            domain_user_agents: Dictionary mapping domains to user agent lists
        """
        super().__init__()
        
        # Default domain-specific user agents
        self.domain_user_agents = domain_user_agents or {
            'vanguardngr.com': [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/604.1',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
            ],
            'punchng.com': [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
                'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
            ],
            'thenationonlineng.net': [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            ],
            'guardian.ng': [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/604.1',
                'Mozilla/5.0 (Android 14; Mobile; rv:109.0) Gecko/121.0 Firefox/121.0',
            ],
            'default': self.user_agent_list  # Fallback to default list
        }
        
        self.domain_stats = {}
        
        logger.info(f"DomainSpecificUserAgentMiddleware initialized for {len(self.domain_user_agents)} domains")
    
    def process_request(self, request, spider):
        """
        Process request with domain-specific user agent selection.
        
        Args:
            request: Scrapy Request object
            spider: Spider instance
            
        Returns:
            None (continues processing)
        """
        # Extract domain from request URL
        from urllib.parse import urlparse
        domain = urlparse(request.url).netloc
        
        # Get user agents for this domain
        domain_agents = self.domain_user_agents.get(domain, self.domain_user_agents['default'])
        
        # Select random user agent from domain-specific list
        user_agent = random.choice(domain_agents)
        
        # Set user agent in request headers
        request.headers.setdefault('User-Agent', user_agent)
        
        # Update statistics
        self.domain_stats[domain] = self.domain_stats.get(domain, 0) + 1
        
        if spider.settings.getbool('USER_AGENT_DEBUG', False):
            spider.logger.debug(f"Using User-Agent for {domain}: {user_agent}")
    
    def spider_closed(self, spider):
        """Called when spider is closed."""
        if self.domain_stats:
            total_requests = sum(self.domain_stats.values())
            spider.logger.info("Domain User Agent Statistics:")
            
            # Sort by usage count
            sorted_stats = sorted(self.domain_stats.items(), key=lambda x: x[1], reverse=True)
            
            for domain, count in sorted_stats:
                percentage = (count / total_requests) * 100 if total_requests > 0 else 0
                spider.logger.info(f"  {domain}: {count} ({percentage:.1f}%)")
            
            spider.logger.info(f"Total requests processed: {total_requests}")
    
    def get_stats(self) -> dict:
        """
        Get domain-specific user agent statistics.
        
        Returns:
            Dictionary with domain statistics
        """
        return {
            'domain_count': len(self.domain_user_agents),
            'domain_stats': self.domain_stats.copy(),
            'total_requests': sum(self.domain_stats.values())
        }
