"""
Scrapy items for Nigerian news articles.

Defines the data structure for news articles collected from
Nigerian news sites with proper validation and processing.
"""

import scrapy
from scrapy import Item, Field


class NewsArticleItem(Item):
    """
    News article item for Nigerian news sites.
    
    Contains all relevant fields for news article data including
    content, metadata, and crawling information.
    """
    
    # Basic article information
    url = Field()                    # Original URL
    title = Field()                  # Article title
    content = Field()                # Article content
    author = Field()                 # Article author
    publication_date = Field()       # Publication date
    category = Field()               # Article category
    domain = Field()                 # Source domain
    
    # Content metrics
    word_count = Field()             # Word count of content
    image_urls = Field()             # List of image URLs
    links = Field()                  # List of relevant links
    
    # Crawling metadata
    crawl_time = Field()             # Timestamp when crawled
    referer = Field()                # Referer URL
    source = Field()                  # Source of the URL (start_urls, extracted_link)
    
    # Processing metadata
    processed = Field()              # Whether item has been processed
    error = Field()                   # Any processing errors
    
    # Research-specific fields
    sentiment_score = Field()         # Sentiment analysis score
    bias_indicators = Field()         # Bias indicators
    language = Field()               # Article language
    keywords = Field()               # Extracted keywords
    
    class Meta:
        """Item metadata."""
        fields = {
            'url': {'type': str},
            'title': {'type': str},
            'content': {'type': str},
            'author': {'type': str},
            'publication_date': {'type': str},
            'category': {'type': str},
            'domain': {'type': str},
            'word_count': {'type': int},
            'image_urls': {'type': list},
            'links': {'type': list},
            'crawl_time': {'type': float},
            'referer': {'type': str},
            'source': {'type': str},
            'processed': {'type': bool},
            'error': {'type': str},
            'sentiment_score': {'type': float},
            'bias_indicators': {'type': list},
            'language': {'type': str},
            'keywords': {'type': list},
        }


class CrawlStatsItem(Item):
    """
    Crawl statistics item for monitoring.
    
    Contains statistics about crawling performance and health.
    """
    
    spider_name = Field()             # Spider name
    timestamp = Field()               # Timestamp
    items_scraped = Field()           # Number of items scraped
    pages_crawled = Field()           # Number of pages crawled
    errors = Field()                  # Number of errors
    domains_crawled = Field()         # List of domains
    crawl_rate = Field()              # Items per minute
    error_rate = Field()              # Error rate
    
    class Meta:
        fields = {
            'spider_name': {'type': str},
            'timestamp': {'type': float},
            'items_scraped': {'type': int},
            'pages_crawled': {'type': int},
            'errors': {'type': int},
            'domains_crawled': {'type': list},
            'crawl_rate': {'type': float},
            'error_rate': {'type': float},
        }
