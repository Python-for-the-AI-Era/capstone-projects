"""
Enhanced retry middleware for distributed crawling.

Provides intelligent retry logic with exponential backoff,
domain-specific retry policies, and comprehensive error handling.
"""

import time
import logging
from typing import Dict, List, Optional

from scrapy.http import Response
from scrapy.downloadermiddlewares.retry import RetryMiddleware
from scrapy.exceptions import IgnoreRequest
from scrapy.utils.response import response_status_message

logger = logging.getLogger(__name__)


class RetryMiddleware(RetryMiddleware):
    """
    Enhanced retry middleware with domain-specific policies and monitoring.
    
    Provides intelligent retry logic with exponential backoff,
    different retry policies per domain, and comprehensive error tracking.
    """
    
    def __init__(self, settings):
        """
        Initialize enhanced retry middleware.
        
        Args:
            settings: Scrapy settings object
        """
        super().__init__(settings)
        
        # Enhanced retry configuration
        self.retry_times = settings.getint('RETRY_TIMES', 3)
        self.retry_http_codes = set(settings.getlist('RETRY_HTTP_CODES', [500, 502, 503, 504, 408, 429]))
        self.retry_backoff_policy = settings.get('RETRY_BACKOFF_POLICY', 'exponential')
        self.retry_delay = settings.getint('RETRY_DELAY', 1)
        self.retry_max_delay = settings.getint('RETRY_MAX_DELAY', 60)
        
        # Domain-specific retry policies
        self.domain_retry_policies = self._load_domain_policies(settings)
        
        # Statistics
        self.retry_stats = {
            'total_retries': 0,
            'domain_retries': {},
            'status_code_retries': {},
            'successful_retries': 0,
            'failed_retries': 0
        }
        
        logger.info(f"Enhanced RetryMiddleware initialized with {len(self.domain_retry_policies)} domain policies")
    
    def _load_domain_policies(self, settings) -> Dict[str, Dict]:
        """Load domain-specific retry policies from settings."""
        # Default policies for Nigerian news sites
        default_policies = {
            'vanguardngr.com': {
                'max_retry_times': 5,
                'retry_http_codes': [500, 502, 503, 504, 408, 429, 403, 404],
                'base_delay': 2,
                'max_delay': 30,
                'backoff_factor': 2.0
            },
            'punchng.com': {
                'max_retry_times': 4,
                'retry_http_codes': [500, 502, 503, 504, 408, 429],
                'base_delay': 1,
                'max_delay': 20,
                'backoff_factor': 1.5
            },
            'thenationonlineng.net': {
                'max_retry_times': 3,
                'retry_http_codes': [500, 502, 503, 504, 408, 429],
                'base_delay': 3,
                'max_delay': 45,
                'backoff_factor': 2.5
            },
            'guardian.ng': {
                'max_retry_times': 4,
                'retry_http_codes': [500, 502, 503, 504, 408, 429, 503],
                'base_delay': 2,
                'max_delay': 25,
                'backoff_factor': 2.0
            },
            'default': {
                'max_retry_times': self.retry_times,
                'retry_http_codes': list(self.retry_http_codes),
                'base_delay': self.retry_delay,
                'max_delay': self.retry_max_delay,
                'backoff_factor': 2.0
            }
        }
        
        # Override with settings if provided
        custom_policies = settings.getdict('DOMAIN_RETRY_POLICIES', {})
        for domain, policy in custom_policies.items():
            if domain in default_policies:
                default_policies[domain].update(policy)
            else:
                default_policies[domain] = policy
        
        return default_policies
    
    def _get_domain_policy(self, request) -> Dict:
        """Get retry policy for the request's domain."""
        from urllib.parse import urlparse
        domain = urlparse(request.url).netloc
        
        return self.domain_retry_policies.get(domain, self.domain_retry_policies['default'])
    
    def _calculate_retry_delay(self, retry_count: int, policy: Dict) -> float:
        """Calculate retry delay based on policy and retry count."""
        if self.retry_backoff_policy == 'exponential':
            delay = policy['base_delay'] * (policy['backoff_factor'] ** retry_count)
        elif self.retry_backoff_policy == 'linear':
            delay = policy['base_delay'] * (retry_count + 1)
        else:  # fixed
            delay = policy['base_delay']
        
        return min(delay, policy['max_delay'])
    
    def _should_retry(self, response: Request, request, spider) -> bool:
        """Determine if request should be retried."""
        domain = self._get_domain_policy(request)
        max_retries = domain['max_retry_times']
        retry_codes = set(domain['retry_http_codes'])
        
        # Check if we've exceeded max retries
        if request.meta.get('retry_times', 0) >= max_retries:
            return False
        
        # Check if status code is retryable
        if response.status not in retry_codes:
            return False
        
        # Additional checks for specific status codes
        if response.status == 429:  # Rate limiting
            retry_after = response.headers.get('Retry-After')
            if retry_after:
                try:
                    delay = int(retry_after)
                    if delay > 300:  # Don't wait more than 5 minutes
                        return False
                except ValueError:
                    pass
        
        return True
    
    def process_response(self, request, response, spider):
        """
        Process response and handle retries.
        
        Args:
            request: Scrapy Request object
            response: Scrapy Response object
            spider: Spider instance
            
        Returns:
            Response object or None if request should be retried
        """
        if response.status >= 400:
            domain = self._get_domain_policy(request)
            retry_times = request.meta.get('retry_times', 0)
            
            # Update statistics
            self._update_retry_stats(request, response.status, domain)
            
            if self._should_retry(response, request, spider):
                # Calculate retry delay
                delay = self._calculate_retry_delay(retry_times, domain)
                
                # Update request metadata
                request.meta['retry_times'] = retry_times + 1
                request.meta['retry_delay'] = delay
                request.meta['retry_domain'] = domain
                
                # Log retry attempt
                spider.logger.warning(
                    f"Retrying {request.url} (status: {response.status}, "
                    f"retry: {retry_times + 1}/{domain['max_retry_times']}, "
                    f"delay: {delay}s)"
                )
                
                # Create new request with delay
                retry_request = request.copy()
                retry_request.dont_filter = True
                retry_request.meta['priority'] = request.meta.get('priority', 0) - 1  # Lower priority for retries
                
                return self._retry(retry_request, spider, delay)
            else:
                # Log final failure
                spider.logger.error(
                    f"Giving up on {request.url} after {retry_times} retries "
                    f"(status: {response.status})"
                )
                
                # Update failed retry count
                self.retry_stats['failed_retries'] += 1
                
        return response
    
    def _retry(self, request, spider, delay: float):
        """Retry request with specified delay."""
        # Add delay to request meta for download middleware
        request.meta['download_delay'] = delay
        
        # Update successful retry count
        self.retry_stats['successful_retries'] += 1
        
        return request
    
    def _update_retry_stats(self, request, status_code: int, domain: Dict):
        """Update retry statistics."""
        from urllib.parse import urlparse
        domain_name = urlparse(request.url).netloc
        
        # Update total retries
        self.retry_stats['total_retries'] += 1
        
        # Update domain retries
        if domain_name not in self.retry_stats['domain_retries']:
            self.retry_stats['domain_retries'][domain_name] = 0
        self.retry_stats['domain_retries'][domain_name] += 1
        
        # Update status code retries
        if status_code not in self.retry_stats['status_code_retries']:
            self.retry_stats['status_code_retries'][status_code] = 0
        self.retry_stats['status_code_retries'][status_code] += 1
    
    def spider_closed(self, spider):
        """Called when spider is closed."""
        if self.retry_stats['total_retries'] > 0:
            spider.logger.info("Retry Statistics:")
            spider.logger.info(f"  Total retries: {self.retry_stats['total_retries']}")
            spider.logger.info(f"  Successful retries: {self.retry_stats['successful_retries']}")
            spider.logger.info(f"  Failed retries: {self.retry_stats['failed_retries']}")
            
            # Domain retries
            spider.logger.info("  Domain retries:")
            for domain, count in sorted(self.retry_stats['domain_retries'].items(), 
                                        key=lambda x: x[1], reverse=True):
                spider.logger.info(f"    {domain}: {count}")
            
            # Status code retries
            spider.logger.info("  Status code retries:")
            for code, count in sorted(self.retry_stats['status_code_retries'].items(), 
                                      key=lambda x: x[1], reverse=True):
                spider.logger.info(f"    {code}: {count}")
    
    def get_stats(self) -> Dict:
        """
        Get retry statistics.
        
        Returns:
            Dictionary with retry statistics
        """
        return self.retry_stats.copy()


class AdaptiveRetryMiddleware(RetryMiddleware):
    """
    Adaptive retry middleware that adjusts retry behavior based on success rates.
    
    Monitors domain-specific success rates and adjusts retry policies
    dynamically to optimize crawling efficiency.
    """
    
    def __init__(self, settings):
        """
        Initialize adaptive retry middleware.
        
        Args:
            settings: Scrapy settings object
        """
        super().__init__(settings)
        
        # Adaptive configuration
        self.adaptive_enabled = settings.getbool('ADAPTIVE_RETRY_ENABLED', True)
        self.success_rate_window = settings.getint('SUCCESS_RATE_WINDOW', 100)
        self.min_success_rate = settings.getfloat('MIN_SUCCESS_RATE', 0.8)
        self.max_retry_adjustment = settings.getfloat('MAX_RETRY_ADJUSTMENT', 2.0)
        
        # Domain performance tracking
        self.domain_performance = {}
        
        logger.info(f"AdaptiveRetryMiddleware initialized (enabled: {self.adaptive_enabled})")
    
    def _update_domain_performance(self, domain: str, success: bool):
        """Update domain performance tracking."""
        if domain not in self.domain_performance:
            self.domain_performance[domain] = {
                'total_requests': 0,
                'successful_requests': 0,
                'success_rate': 0.0,
                'last_updated': time.time()
            }
        
        perf = self.domain_performance[domain]
        perf['total_requests'] += 1
        if success:
            perf['successful_requests'] += 1
        
        # Calculate success rate
        perf['success_rate'] = perf['successful_requests'] / perf['total_requests']
        perf['last_updated'] = time.time()
        
        # Adjust retry policy if adaptive is enabled
        if self.adaptive_enabled:
            self._adjust_retry_policy(domain, perf)
    
    def _adjust_retry_policy(self, domain: str, performance: Dict):
        """Adjust retry policy based on domain performance."""
        success_rate = performance['success_rate']
        
        # Get current policy
        current_policy = self.domain_retry_policies.get(domain, self.domain_retry_policies['default'])
        original_max_retries = current_policy['max_retry_times']
        
        # Adjust max retries based on success rate
        if success_rate < self.min_success_rate:
            # Decrease max retries for poorly performing domains
            new_max_retries = max(1, int(original_max_retries * 0.5))
        elif success_rate > 0.95:
            # Increase max retries for highly successful domains
            new_max_retries = int(original_max_retries * self.max_retry_adjustment)
        else:
            # Keep original for moderate performance
            new_max_retries = original_max_retries
        
        # Update policy if it changed
        if new_max_retries != original_max_retries:
            current_policy['max_retry_times'] = new_max_retries
            logger.info(f"Adjusted retry policy for {domain}: max_retries {original_max_retries} → {new_max_retries} "
                        f"(success_rate: {success_rate:.3f})")
    
    def process_response(self, request, response, spider):
        """
        Process response with adaptive retry logic.
        
        Args:
            request: Scrapy Request object
            response: Scrapy Response object
            spider: Spider instance
            
        Returns:
            Response object or None if request should be retried
        """
        # Update domain performance tracking
        from urllib.parse import urlparse
        domain = urlparse(request.url).netloc
        success = response.status < 400
        
        self._update_domain_performance(domain, success)
        
        # Call parent method
        return super().process_response(request, response, spider)
    
    def get_domain_performance(self) -> Dict:
        """
        Get domain performance statistics.
        
        Returns:
            Dictionary with domain performance data
        """
        return self.domain_performance.copy()
    
    def get_stats(self) -> Dict:
        """
        Get comprehensive retry statistics.
        
        Returns:
            Dictionary with retry and performance statistics
        """
        stats = super().get_stats()
        stats['adaptive_enabled'] = self.adaptive_enabled
        stats['domain_performance'] = self.domain_performance.copy()
        stats['performance_tracking'] = {
            'total_domains': len(self.domain_performance),
            'avg_success_rate': 0.0
        }
        
        if self.domain_performance:
            total_success_rate = sum(p['success_rate'] for p in self.domain_performance.values())
            stats['performance_tracking']['avg_success_rate'] = total_success_rate / len(self.domain_performance)
        
        return stats
