"""
Validation pipeline for news articles.

Validates and cleans news article data before storage.
"""

import re
import logging
from typing import Optional, Dict, Any
from urllib.parse import urlparse

from scrapy.exceptions import DropItem

logger = logging.getLogger(__name__)


class ValidationPipeline:
    """
    Pipeline for validating and cleaning news article items.
    
    Validates required fields, cleans text content, and ensures
    data quality before storage.
    """
    
    def __init__(self, min_content_length: int = 500, max_content_length: int = 100000):
        """
        Initialize validation pipeline.
        
        Args:
            min_content_length: Minimum content length in characters
            max_content_length: Maximum content length in characters
        """
        self.min_content_length = min_content_length
        self.max_content_length = max_content_length
        
        # Statistics
        self.stats = {
            'items_processed': 0,
            'items_dropped': 0,
            'items_validated': 0,
            'validation_errors': {}
        }
        
        logger.info(f"ValidationPipeline initialized (min_length={min_content_length}, max_length={max_content_length})")
    
    def process_item(self, item, spider):
        """
        Process and validate news article item.
        
        Args:
            item: NewsArticleItem to validate
            spider: Spider instance
            
        Returns:
            Validated item or raises DropItem if invalid
            
        Raises:
            DropItem: If item fails validation
        """
        self.stats['items_processed'] += 1
        
        try:
            # Validate required fields
            self._validate_required_fields(item)
            
            # Clean and validate content
            item = self._clean_content(item)
            
            # Validate URLs
            item = self._validate_urls(item)
            
            # Validate metadata
            item = self._validate_metadata(item)
            
            # Mark as processed
            item['processed'] = True
            
            self.stats['items_validated'] += 1
            
            logger.debug(f"Item validated: {item['url']}")
            
            return item
            
        except DropItem as e:
            self.stats['items_dropped'] += 1
            
            # Track validation errors
            error_type = type(e).__name__
            self.stats['validation_errors'][error_type] = self.stats['validation_errors'].get(error_type, 0) + 1
            
            logger.warning(f"Item dropped: {e}")
            raise
    
    def _validate_required_fields(self, item):
        """Validate required fields are present."""
        required_fields = ['url', 'title', 'content', 'domain']
        
        for field in required_fields:
            if not item.get(field):
                raise DropItem(f"Missing required field: {field}")
        
        # Validate URL format
        if not self._is_valid_url(item['url']):
            raise DropItem(f"Invalid URL format: {item['url']}")
    
    def _clean_content(self, item):
        """Clean and validate article content."""
        # Clean title
        title = item['title'].strip()
        title = self._clean_text(title)
        
        if len(title) < 10:
            raise DropItem(f"Title too short: {len(title)} characters")
        
        if len(title) > 200:
            title = title[:200] + "..."
        
        item['title'] = title
        
        # Clean content
        content = item['content'].strip()
        content = self._clean_text(content)
        
        # Validate content length
        if len(content) < self.min_content_length:
            raise DropItem(f"Content too short: {len(content)} characters")
        
        if len(content) > self.max_content_length:
            content = content[:self.max_content_length] + "..."
        
        item['content'] = content
        
        # Update word count
        item['word_count'] = len(content.split())
        
        return item
    
    def _validate_urls(self, item):
        """Validate and clean URLs."""
        # Validate main URL
        if not self._is_valid_url(item['url']):
            raise DropItem(f"Invalid main URL: {item['url']}")
        
        # Validate image URLs
        if item.get('image_urls'):
            valid_images = []
            for img_url in item['image_urls']:
                if self._is_valid_url(img_url):
                    valid_images.append(img_url)
            item['image_urls'] = valid_images
        
        # Validate links
        if item.get('links'):
            valid_links = []
            for link in item['links']:
                if self._is_valid_url(link):
                    valid_links.append(link)
            item['links'] = valid_links
        
        return item
    
    def _validate_metadata(self, item):
        """Validate and clean metadata."""
        # Clean author
        if item.get('author'):
            author = item['author'].strip()
            author = self._clean_text(author)
            item['author'] = author if len(author) > 2 else None
        
        # Clean category
        if item.get('category'):
            category = item['category'].strip()
            category = self._clean_text(category)
            item['category'] = category if len(category) > 2 else None
        
        # Clean publication date
        if item.get('publication_date'):
            date = item['publication_date'].strip()
            date = self._clean_text(date)
            item['publication_date'] = date if len(date) > 5 else None
        
        # Validate domain
        if not self._is_valid_domain(item['domain']):
            raise DropItem(f"Invalid domain: {item['domain']}")
        
        return item
    
    def _clean_text(self, text: str) -> str:
        """Clean text content."""
        if not text:
            return ""
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove HTML entities
        text = re.sub(r'&[a-zA-Z0-9#]+;', '', text)
        
        # Remove non-printable characters except newlines
        text = re.sub(r'[^\x20-\x7E\n\r\t]', '', text)
        
        # Strip leading/trailing whitespace
        text = text.strip()
        
        return text
    
    def _is_valid_url(self, url: str) -> bool:
        """Check if URL is valid."""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
    
    def _is_valid_domain(self, domain: str) -> bool:
        """Check if domain is valid."""
        if not domain:
            return False
        
        # Basic domain validation
        domain_pattern = r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(domain_pattern, domain))
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get validation statistics.
        
        Returns:
            Dictionary with validation statistics
        """
        return self.stats.copy()
