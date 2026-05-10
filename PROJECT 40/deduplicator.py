import hashlib
import json
import logging
import redis
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from config import settings

logger = logging.getLogger(__name__)


class ContentDeduplicator:
    """Handles content deduplication using Redis for storage"""
    
    def __init__(self):
        try:
            self.redis_client = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                db=settings.redis_db,
                decode_responses=True
            )
            # Test connection
            self.redis_client.ping()
            logger.info("Redis connection established")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis_client = None
    
    def _generate_content_hash(self, content: str) -> str:
        """Generate SHA-256 hash of content"""
        if not content:
            return ""
        
        # Normalize content by removing whitespace and converting to lowercase
        normalized_content = ' '.join(content.lower().split())
        return hashlib.sha256(normalized_content.encode('utf-8')).hexdigest()
    
    def is_new_content(self, url: str, content: str) -> bool:
        """Check if content is new compared to previously stored content"""
        if not self.redis_client:
            logger.warning("Redis not available, assuming content is new")
            return True
        
        try:
            content_hash = self._generate_content_hash(content)
            hash_key = f"content_hash:{url}"
            
            # Get existing hash
            existing_hash = self.redis_client.get(hash_key)
            
            if existing_hash is None:
                # First time seeing this URL
                logger.info(f"First time seeing URL: {url}")
                return True
            
            if existing_hash == content_hash:
                # Content hasn't changed
                logger.debug(f"Content unchanged for: {url}")
                return False
            else:
                # Content has changed
                logger.info(f"Content changed for: {url}")
                return True
                
        except Exception as e:
            logger.error(f"Error checking content newness for {url}: {e}")
            return True  # Assume new content on error
    
    def store_content_hash(self, url: str, content: str, ttl_days: int = 30):
        """Store content hash with expiration"""
        if not self.redis_client:
            logger.warning("Redis not available, skipping hash storage")
            return
        
        try:
            content_hash = self._generate_content_hash(content)
            hash_key = f"content_hash:{url}"
            
            # Store hash with TTL (30 days by default)
            self.redis_client.setex(
                hash_key, 
                timedelta(days=ttl_days), 
                content_hash
            )
            
            # Store metadata about when this was seen
            metadata_key = f"content_meta:{url}"
            metadata = {
                'url': url,
                'hash': content_hash,
                'scraped_at': datetime.utcnow().isoformat(),
                'content_length': len(content)
            }
            
            self.redis_client.setex(
                metadata_key,
                timedelta(days=ttl_days),
                json.dumps(metadata)
            )
            
            logger.debug(f"Stored content hash for: {url}")
            
        except Exception as e:
            logger.error(f"Error storing content hash for {url}: {e}")
    
    def get_content_metadata(self, url: str) -> Optional[Dict[str, Any]]:
        """Get metadata about previously scraped content"""
        if not self.redis_client:
            return None
        
        try:
            metadata_key = f"content_meta:{url}"
            metadata_json = self.redis_client.get(metadata_key)
            
            if metadata_json:
                return json.loads(metadata_json)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting content metadata for {url}: {e}")
            return None
    
    def cleanup_old_hashes(self, days_old: int = 90):
        """Clean up old content hashes"""
        if not self.redis_client:
            return
        
        try:
            # Find all keys with our prefix
            hash_keys = self.redis_client.keys("content_hash:*")
            meta_keys = self.redis_client.keys("content_meta:*")
            
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            deleted_count = 0
            
            # Check and delete old metadata entries
            for key in meta_keys:
                try:
                    metadata_json = self.redis_client.get(key)
                    if metadata_json:
                        metadata = json.loads(metadata_json)
                        scraped_at = datetime.fromisoformat(metadata['scraped_at'])
                        
                        if scraped_at < cutoff_date:
                            # Delete both hash and metadata
                            url = metadata['url']
                            hash_key = f"content_hash:{url}"
                            
                            self.redis_client.delete(hash_key)
                            self.redis_client.delete(key)
                            deleted_count += 1
                            
                except Exception as e:
                    logger.error(f"Error processing key {key}: {e}")
                    continue
            
            logger.info(f"Cleaned up {deleted_count} old content entries")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about stored content"""
        if not self.redis_client:
            return {"error": "Redis not available"}
        
        try:
            hash_count = len(self.redis_client.keys("content_hash:*"))
            meta_count = len(self.redis_client.keys("content_meta:*"))
            
            # Get memory usage
            info = self.redis_client.info('memory')
            memory_used = info.get('used_memory_human', 'Unknown')
            
            return {
                'stored_hashes': hash_count,
                'stored_metadata': meta_count,
                'memory_usage': memory_used,
                'redis_connected': True
            }
            
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {"error": str(e), "redis_connected": False}
    
    def force_refresh_url(self, url: str):
        """Force refresh a URL by deleting its stored hash"""
        if not self.redis_client:
            return
        
        try:
            hash_key = f"content_hash:{url}"
            meta_key = f"content_meta:{url}"
            
            self.redis_client.delete(hash_key)
            self.redis_client.delete(meta_key)
            
            logger.info(f"Forced refresh for URL: {url}")
            
        except Exception as e:
            logger.error(f"Error forcing refresh for {url}: {e}")
