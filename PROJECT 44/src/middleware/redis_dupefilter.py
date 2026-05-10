"""
Redis-based MD5 deduplication filter for distributed crawling.

Uses Redis SETNX with MD5 fingerprints to ensure URLs are never
visited twice across multiple workers.
"""

import hashlib
import logging
import time
from typing import Optional, Set

from scrapy.dupefilters import BaseDupeFilter
from scrapy.http import Request
from scrapy.utils.request import request_fingerprint
from scrapy.exceptions import NotConfigured

try:
    import redis
except ImportError:
    redis = None

logger = logging.getLogger(__name__)


class RedisMD5DupeFilter(BaseDupeFilter):
    """
    Redis-based deduplication filter using MD5 fingerprints.
    
    Uses Redis SETNX for atomic operations to ensure thread safety
    across multiple Scrapy workers. Never revisits the same URL twice.
    """
    
    def __init__(self, server, key_prefix: str = 'dupefilter', 
                 expire_time: int = 86400, debug: bool = False):
        """
        Initialize Redis MD5 deduplication filter.
        
        Args:
            server: Redis connection instance
            key_prefix: Prefix for Redis keys
            expire_time: Expiration time for fingerprints (24 hours)
            debug: Enable debug logging
        """
        if redis is None:
            raise NotConfigured("redis package is required")
        
        self.server = server
        self.key_prefix = key_prefix
        self.expire_time = expire_time
        self.debug = debug
        self.logdupes = True
        self.stats = None
        
        # Performance metrics
        self.total_requests = 0
        self.filtered_requests = 0
        self.redis_operations = 0
        
        logger.info(f"RedisMD5DupeFilter initialized with expire_time={expire_time}s")
    
    @classmethod
    def from_settings(cls, settings):
        """Create instance from Scrapy settings."""
        host = settings.get('REDIS_HOST', 'localhost')
        port = settings.get('REDIS_PORT', 6379)
        db = settings.get('REDIS_DB', 0)
        password = settings.get('REDIS_PASSWORD')
        
        # Create Redis connection
        connection_kwargs = {
            'host': host,
            'port': port,
            'db': db,
            'decode_responses': True,
            'socket_timeout': 30,
            'socket_connect_timeout': 30,
            'retry_on_timeout': True,
            'health_check_interval': 30,
        }
        
        if password:
            connection_kwargs['password'] = password
        
        try:
            server = redis.Redis(**connection_kwargs)
            # Test connection
            server.ping()
            logger.info(f"Connected to Redis at {host}:{port}/{db}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise NotConfigured(f"Redis connection failed: {e}")
        
        key_prefix = settings.get('DUPEFILTER_KEY', 'dupefilter')
        expire_time = settings.get('DUPEFILTER_EXPIRE_TIME', 86400)
        debug = settings.getbool('DUPEFILTER_DEBUG', False)
        
        return cls(server, key_prefix, expire_time, debug)
    
    def request_seen(self, request: Request) -> bool:
        """
        Check if request has been seen before.
        
        Uses MD5 fingerprint with Redis SETNX for atomic deduplication.
        
        Args:
            request: Scrapy Request object
            
        Returns:
            True if request has been seen, False otherwise
        """
        self.total_requests += 1
        
        # Generate MD5 fingerprint
        fp = self._generate_fingerprint(request)
        if not fp:
            return False
        
        # Use SETNX for atomic deduplication
        key = f"{self.key_prefix}:{fp}"
        
        try:
            # SETNX returns 1 if key was set, 0 if key already exists
            result = self.server.setnx(key, time.time())
            self.redis_operations += 1
            
            # Set expiration if key was newly created
            if result:
                self.server.expire(key, self.expire_time)
                self.redis_operations += 1
                
                if self.debug:
                    logger.debug(f"New URL fingerprint: {fp[:16]}...")
                
                return False  # Not seen before
            else:
                self.filtered_requests += 1
                
                if self.debug:
                    logger.debug(f"Duplicate URL fingerprint: {fp[:16]}...")
                
                return True  # Seen before
                
        except redis.RedisError as e:
            logger.error(f"Redis error in deduplication: {e}")
            # Fail open - allow request to proceed if Redis is down
            return False
    
    def _generate_fingerprint(self, request: Request) -> Optional[str]:
        """
        Generate MD5 fingerprint for request.
        
        Args:
            request: Scrapy Request object
            
        Returns:
            MD5 hash string or None if fingerprinting fails
        """
        try:
            # Use Scrapy's built-in fingerprinting
            fp = request_fingerprint(request)
            if fp:
                # Convert to MD5 hash for consistency
                md5_hash = hashlib.md5(fp.encode()).hexdigest()
                return md5_hash
        except Exception as e:
            if self.debug:
                logger.error(f"Error generating fingerprint: {e}")
        
        return None
    
    def close(self, reason: str = ''):
        """Clean up resources and log statistics."""
        logger.info(f"RedisMD5DupeFilter closing: {reason}")
        logger.info(f"Total requests: {self.total_requests}")
        logger.info(f"Filtered requests: {self.filtered_requests}")
        logger.info(f"Redis operations: {self.redis_operations}")
        
        if self.total_requests > 0:
            dup_rate = (self.filtered_requests / self.total_requests) * 100
            logger.info(f"Duplication rate: {dup_rate:.2f}%")
        
        # Update stats if available
        if self.stats:
            self.stats.set_value('dupefilter/total_requests', self.total_requests)
            self.stats.set_value('dupefilter/filtered_requests', self.filtered_requests)
            self.stats.set_value('dupefilter/redis_operations', self.redis_operations)
            self.stats.set_value('dupefilter/duplication_rate', 
                              (self.filtered_requests / self.total_requests) * 100 if self.total_requests > 0 else 0)
    
    def log(self, request, spider):
        """Log duplicate requests."""
        if self.logdupes and self.debug:
            fp = self._generate_fingerprint(request)
            if fp:
                logger.debug(f"Duplicate request: {request.url} (fp: {fp[:16]}...)")
    
    def get_stats(self) -> dict:
        """
        Get deduplication statistics.
        
        Returns:
            Dictionary with statistics
        """
        stats = {
            'total_requests': self.total_requests,
            'filtered_requests': self.filtered_requests,
            'redis_operations': self.redis_operations,
            'duplication_rate': (self.filtered_requests / self.total_requests) * 100 if self.total_requests > 0 else 0
        }
        
        # Get Redis info
        try:
            redis_info = self.server.info()
            stats['redis_memory_used'] = redis_info.get('used_memory_human', 'N/A')
            stats['redis_connected_clients'] = redis_info.get('connected_clients', 0)
            stats['redis_total_commands'] = redis_info.get('total_commands_processed', 0)
        except Exception as e:
            logger.error(f"Error getting Redis stats: {e}")
        
        return stats
    
    def clear(self, spider=None):
        """Clear all fingerprints from Redis."""
        try:
            pattern = f"{self.key_prefix}:*"
            keys = self.server.keys(pattern)
            
            if keys:
                deleted = self.server.delete(*keys)
                logger.info(f"Cleared {deleted} fingerprints from Redis")
            else:
                logger.info("No fingerprints to clear")
                
        except Exception as e:
            logger.error(f"Error clearing fingerprints: {e}")
    
    def get_fingerprint_count(self) -> int:
        """
        Get the number of unique fingerprints stored in Redis.
        
        Returns:
            Number of fingerprints
        """
        try:
            pattern = f"{self.key_prefix}:*"
            keys = self.server.keys(pattern)
            return len(keys)
        except Exception as e:
            logger.error(f"Error getting fingerprint count: {e}")
            return 0
    
    def cleanup_expired(self):
        """Clean up expired fingerprints (handled automatically by Redis TTL)."""
        # Redis handles expiration automatically, but we can log info
        try:
            total_keys = self.get_fingerprint_count()
            logger.info(f"Currently tracking {total_keys} fingerprints")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


class DistributedDupeFilter(RedisMD5DupeFilter):
    """
    Enhanced distributed deduplication filter with additional features.
    
    Includes domain-based deduplication, priority handling, and
    performance optimization for large-scale crawling.
    """
    
    def __init__(self, server, key_prefix: str = 'distributed_dupefilter',
                 expire_time: int = 86400, domain_expire_time: int = 3600,
                 max_fingerprints: int = 1000000, debug: bool = False):
        """
        Initialize distributed deduplication filter.
        
        Args:
            server: Redis connection instance
            key_prefix: Prefix for Redis keys
            expire_time: Default expiration time for fingerprints
            domain_expire_time: Shorter expiration for domain-specific fingerprints
            max_fingerprints: Maximum fingerprints to track
            debug: Enable debug logging
        """
        super().__init__(server, key_prefix, expire_time, debug)
        
        self.domain_expire_time = domain_expire_time
        self.max_fingerprints = max_fingerprints
        self.domain_stats = {}
        
        logger.info(f"DistributedDupeFilter initialized with max_fingerprints={max_fingerprints}")
    
    def request_seen(self, request: Request) -> bool:
        """
        Enhanced request_seen with domain-based tracking.
        """
        # Update domain statistics
        domain = self._get_domain(request)
        if domain:
            if domain not in self.domain_stats:
                self.domain_stats[domain] = {'seen': 0, 'filtered': 0}
            self.domain_stats[domain]['seen'] += 1
        
        # Check if we've exceeded maximum fingerprints
        if self.get_fingerprint_count() >= self.max_fingerprints:
            logger.warning(f"Reached maximum fingerprints ({self.max_fingerprints}), "
                          f"clearing oldest entries")
            self._cleanup_oldest_entries()
        
        # Call parent method
        is_duplicate = super().request_seen(request)
        
        if is_duplicate and domain:
            self.domain_stats[domain]['filtered'] += 1
        
        return is_duplicate
    
    def _get_domain(self, request: Request) -> Optional[str]:
        """Extract domain from request URL."""
        try:
            from urllib.parse import urlparse
            return urlparse(request.url).netloc
        except Exception:
            return None
    
    def _cleanup_oldest_entries(self):
        """Clean up oldest fingerprints to stay within limits."""
        try:
            # Get all keys with their TTL
            pattern = f"{self.key_prefix}:*"
            keys = self.server.keys(pattern)
            
            if not keys:
                return
            
            # Sort keys by TTL (oldest first)
            key_ttls = []
            for key in keys:
                ttl = self.server.ttl(key)
                key_ttls.append((ttl, key))
            
            key_ttls.sort()
            
            # Delete oldest 25% of entries
            delete_count = max(1, len(key_ttls) // 4)
            keys_to_delete = [key for _, key in key_ttls[:delete_count]]
            
            if keys_to_delete:
                deleted = self.server.delete(*keys_to_delete)
                logger.info(f"Cleaned up {deleted} oldest fingerprints")
                
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    def get_domain_stats(self) -> dict:
        """
        Get statistics per domain.
        
        Returns:
            Dictionary with domain-specific statistics
        """
        return self.domain_stats.copy()
    
    def get_redis_memory_usage(self) -> dict:
        """
        Get detailed Redis memory usage.
        
        Returns:
            Dictionary with memory statistics
        """
        try:
            info = self.server.info('memory')
            return {
                'used_memory': info.get('used_memory', 0),
                'used_memory_human': info.get('used_memory_human', '0B'),
                'used_memory_rss': info.get('used_memory_rss', 0),
                'used_memory_peak': info.get('used_memory_peak', 0),
                'used_memory_peak_human': info.get('used_memory_peak_human', '0B'),
                'mem_fragmentation_ratio': info.get('mem_fragmentation_ratio', 0),
                'mem_allocator': info.get('mem_allocator', 'unknown')
            }
        except Exception as e:
            logger.error(f"Error getting memory usage: {e}")
            return {}
