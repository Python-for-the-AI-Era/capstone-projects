"""
Main distributed spider for Nigerian news sites.

Redis-based distributed spider that crawls multiple Nigerian news sites
with proper politeness controls, deduplication, and fault tolerance.
"""

import logging
import time
from typing import Dict, List, Optional, Set, Any
from urllib.parse import urljoin, urlparse

from scrapy import Request, Spider
from scrapy_redis.spiders import RedisSpider
from scrapy.exceptions import CloseSpider
from scrapy.http import HtmlResponse

from crawler.items import NewsArticleItem
from crawler.utils.url_utils import normalize_url, is_valid_news_url

logger = logging.getLogger(__name__)


class NigerianNewsSpider(RedisSpider):
    """
    Distributed spider for Nigerian news sites.
    
    Uses Redis for distributed URL frontier and supports multiple
    Nigerian news sites with proper politeness controls.
    """
    
    name = 'nigerian_news'
    
    # Redis configuration
    redis_key = 'nigerian_news:start_urls'
    
    # Site configurations
    site_configs = {
        'vanguardngr.com': {
            'base_url': 'https://www.vanguardngr.com',
            'allowed_paths': ['/news/', '/article/', '/story/'],
            'blocked_paths': ['/tag/', '/category/', '/author/', '/search/'],
            'article_selectors': ['.post-content', '.entry-content', '.article-content'],
            'title_selectors': ['h1.entry-title', 'h1.post-title', '.post-title h1'],
            'date_selectors': ['.post-date', '.entry-date', '.post-meta .date'],
            'content_selectors': ['.entry-content p', '.post-content p', '.article-content p'],
            'author_selectors': ['.author-name', '.post-author', '.by-author'],
            'category_selectors': ['.category', '.post-category', '.entry-category'],
        },
        'punchng.com': {
            'base_url': 'https://punchng.com',
            'allowed_paths': ['/news/', '/article/', '/story/'],
            'blocked_paths': ['/tag/', '/category/', '/author/', '/search/'],
            'article_selectors': ['.entry-content', '.post-content', '.article-content'],
            'title_selectors': ['h1.entry-title', 'h1.post-title', '.post-title h1'],
            'date_selectors': ['.post-date', '.entry-date', '.post-meta .date'],
            'content_selectors': ['.entry-content p', '.post-content p', '.article-content p'],
            'author_selectors': ['.author-name', '.post-author', '.by-author'],
            'category_selectors': ['.category', '.post-category', '.entry-category'],
        },
        'thenationonlineng.net': {
            'base_url': 'https://thenationonlineng.net',
            'allowed_paths': ['/news/', '/article/', '/story/'],
            'blocked_paths': ['/tag/', '/category/', '/author/', '/search/'],
            'article_selectors': ['.entry-content', '.post-content', '.article-content'],
            'title_selectors': ['h1.entry-title', 'h1.post-title', '.post-title h1'],
            'date_selectors': ['.post-date', '.entry-date', '.post-meta .date'],
            'content_selectors': ['.entry-content p', '.post-content p', '.article-content p'],
            'author_selectors': ['.author-name', '.post-author', '.by-author'],
            'category_selectors': ['.category', '.post-category', '.entry-category'],
        },
        'guardian.ng': {
            'base_url': 'https://guardian.ng',
            'allowed_paths': ['/news/', '/article/', '/story/'],
            'blocked_paths': ['/tag/', '/category/', '/author/', '/search/'],
            'article_selectors': ['.entry-content', '.post-content', '.article-content'],
            'title_selectors': ['h1.entry-title', 'h1.post-title', '.post-title h1'],
            'date_selectors': ['.post-date', '.entry-date', '.post-meta .date'],
            'content_selectors': ['.entry-content p', '.post-content p', '.article-content p'],
            'author_selectors': ['.author-name', '.post-author', '.by-author'],
            'category_selectors': ['.category', '.post-category', '.entry-category'],
        },
        'sunnewsonline.com': {
            'base_url': 'https://www.sunnewsonline.com',
            'allowed_paths': ['/news/', '/article/', '/story/'],
            'blocked_paths': ['/tag/', '/category/', '/author/', '/search/'],
            'article_selectors': ['.entry-content', '.post-content', '.article-content'],
            'title_selectors': ['h1.entry-title', 'h1.post-title', '.post-title h1'],
            'date_selectors': ['.post-date', '.entry-date', '.post-meta .date'],
            'content_selectors': ['.entry-content p', '.post-content p', '.article-content p'],
            'author_selectors': ['.author-name', '.post-author', '.by-author'],
            'category_selectors': ['.category', '.post-category', '.entry-category'],
        },
        'leadership.ng': {
            'base_url': 'https://leadership.ng',
            'allowed_paths': ['/news/', '/article/', '/story/'],
            'blocked_paths': ['/tag/', '/category/', '/author/', '/search/'],
            'article_selectors': ['.entry-content', '.post-content', '.article-content'],
            'title_selectors': ['h1.entry-title', 'h1.post-title', '.post-title h1'],
            'date_selectors': ['.post-date', '.entry-date', '.post-meta .date'],
            'content_selectors': ['.entry-content p', '.post-content p', '.article-content p'],
            'author_selectors': ['.author-name', '.post-author', '.by-author'],
            'category_selectors': ['.category', '.post-category', '.entry-category'],
        },
        'dailytrust.com': {
            'base_url': 'https://www.dailytrust.com',
            'allowed_paths': ['/news/', '/article/', '/story/'],
            'blocked_paths': ['/tag/', '/category/', '/author/', '/search/'],
            'article_selectors': ['.entry-content', '.post-content', '.article-content'],
            'title_selectors': ['h1.entry-title', 'h1.post-title', '.post-title h1'],
            'date_selectors': ['.post-date', '.entry-date', '.post-meta .date'],
            'content_selectors': ['.entry-content p', '.post-content p', '.article-content p'],
            'author_selectors': ['.author-name', '.post-author', '.by-author'],
            'category_selectors': ['.category', '.post-category', '.entry-category'],
        },
    }
    
    def __init__(self, *args, **kwargs):
        """Initialize the spider."""
        super().__init__(*args, **kwargs)
        
        # Statistics tracking
        self.stats = {
            'items_scraped': 0,
            'domains_crawled': set(),
            'start_time': time.time(),
            'last_item_time': None,
            'errors': 0,
            'pages_crawled': 0
        }
        
        # Domain-specific settings
        self.domain_settings = {}
        
        logger.info(f"NigerianNewsSpider initialized with {len(self.site_configs)} sites")
    
    def start_requests(self):
        """Generate initial requests from Redis queue."""
        urls = self.get_start_urls()
        
        if not urls:
            logger.warning("No start URLs found in Redis queue")
            return
        
        logger.info(f"Starting crawl with {len(urls)} URLs")
        
        for url in urls:
            domain = urlparse(url).netloc
            self.stats['domains_crawled'].add(domain)
            
            yield Request(
                url,
                callback=self.parse,
                meta={
                    'domain': domain,
                    'crawl_time': time.time(),
                    'source': 'start_urls'
                },
                errback=self.handle_error
            )
    
    def parse(self, response):
        """
        Parse response and extract links and article data.
        
        Args:
            response: Scrapy Response object
            
        Yields:
            Request objects for follow-up pages
            NewsArticleItem objects for article pages
        """
        self.stats['pages_crawled'] += 1
        
        domain = response.meta.get('domain')
        if not domain:
            domain = urlparse(response.url).netloc
            response.meta['domain'] = domain
        
        # Extract article if this is an article page
        if self._is_article_page(response, domain):
            yield self._extract_article(response)
        
        # Extract links for follow-up
        links = self._extract_links(response, domain)
        
        for link in links:
            yield Request(
                link,
                callback=self.parse,
                meta={
                    'domain': urlparse(link).netloc,
                    'crawl_time': time.time(),
                    'source': 'extracted_link',
                    'referer': response.url
                },
                errback=self.handle_error
            )
    
    def _is_article_page(self, response: HtmlResponse, domain: str) -> bool:
        """Determine if the response contains an article."""
        config = self.site_configs.get(domain, {})
        
        # Check URL path
        path = urlparse(response.url).path
        if not any(path.startswith(allowed) for allowed in config.get('allowed_paths', [])):
            return False
        
        # Check if any blocked paths
        if any(path.startswith(blocked) for blocked in config.get('blocked_paths', [])):
            return False
        
        # Check for article content indicators
        article_indicators = config.get('article_selectors', [])
        if not article_indicators:
            return False
        
        for selector in article_indicators:
            if response.css(selector).get():
                return True
        
        return False
    
    def _extract_article(self, response: HtmlResponse) -> NewsArticleItem:
        """Extract article data from response."""
        domain = response.meta.get('domain')
        config = self.site_configs.get(domain, {})
        
        item = NewsArticleItem()
        
        # Basic fields
        item['url'] = response.url
        item['domain'] = domain
        item['crawl_time'] = response.meta.get('crawl_time', time.time())
        item['referer'] = response.meta.get('referer')
        
        # Extract title
        title_selectors = config.get('title_selectors', [])
        title = self._extract_text(response, title_selectors)
        item['title'] = title.strip() if title else None
        
        # Extract date
        date_selectors = config.get('date_selectors', [])
        date = self._extract_text(response, date_selectors)
        item['publication_date'] = date.strip() if date else None
        
        # Extract content
        content_selectors = config.get('content_selectors', [])
        content = self._extract_content(response, content_selectors)
        item['content'] = content.strip() if content else None
        
        # Extract author
        author_selectors = config.get('author_selectors', [])
        author = self._extract_text(response, author_selectors)
        item['author'] = author.strip() if author else None
        
        # Extract category
        category_selectors = config.get('category_selectors', [])
        category = self._extract_text(response, category_selectors)
        item['category'] = category.strip() if category else None
        
        # Extract additional metadata
        item['word_count'] = len(content.split()) if content else 0
        item['image_urls'] = self._extract_images(response)
        item['links'] = self._extract_article_links(response)
        
        # Update statistics
        self.stats['items_scraped'] += 1
        self.stats['last_item_time'] = time.time()
        
        logger.info(f"Extracted article: {item['title'][:50]}... from {domain}")
        
        return item
    
    def _extract_text(self, response: HtmlResponse, selectors: List[str]) -> Optional[str]:
        """Extract text using CSS selectors."""
        for selector in selectors:
            elements = response.css(selector)
            if elements:
                # Get text from first matching element
                text = elements[0].xpath('string()').get()
                if text:
                    return text.strip()
        return None
    
    def _extract_content(self, response: HtmlResponse, selectors: List[str]) -> Optional[str]:
        """Extract article content paragraphs."""
        content_parts = []
        
        for selector in selectors:
            paragraphs = response.css(f"{selector} p")
            for p in paragraphs:
                text = p.xpath('string()').get()
                if text and text.strip():
                    content_parts.append(text.strip())
        
        return '\n\n'.join(content_parts) if content_parts else None
    
    def _extract_images(self, response: HtmlResponse) -> List[str]:
        """Extract image URLs from article."""
        images = []
        
        # Extract from article content
        for img in response.css('img[src]'):
            src = img.css('::attr(src)').get()
            if src:
                # Convert relative URLs to absolute
                if src.startswith('/'):
                    base_url = f"https://{response.meta.get('domain')}"
                    src = urljoin(base_url, src)
                elif not src.startswith('http'):
                    src = urljoin(response.url, src)
                
                # Filter for news-related images
                if self._is_news_image(src):
                    images.append(src)
        
        return images[:10]  # Limit to first 10 images
    
    def _extract_article_links(self, response: HtmlResponse) -> List[str]:
        """Extract relevant links from article."""
        links = []
        
        # Extract from article content
        for link in response.css('a[href]'):
            href = link.css('::attr(href)').get()
            if href and self._is_relevant_link(href):
                # Convert to absolute URL
                if href.startswith('/'):
                    base_url = f"https://{response.meta.get('domain')}"
                    href = urljoin(base_url, href)
                elif not href.startswith('http'):
                    href = urljoin(response.url, href)
                
                links.append(href)
        
        return links[:5]  # Limit to first 5 links
    
    def _is_news_image(self, url: str) -> bool:
        """Check if image is likely a news image."""
        # Filter out non-news images
        skip_patterns = [
            'ads.', 'advertisement', 'banner', 'logo', 'icon', 'avatar',
            'thumbnail', 'button', 'social', 'share', 'comment'
        ]
        
        url_lower = url.lower()
        return not any(pattern in url_lower for pattern in skip_patterns)
    
    def _is_relevant_link(self, url: str) -> bool:
        """Check if link is relevant for crawling."""
        # Filter out irrelevant links
        skip_patterns = [
            'mailto:', 'tel:', 'javascript:', '#',
            'facebook.com', 'twitter.com', 'instagram.com',
            'youtube.com', 'linkedin.com', 'whatsapp.com',
            'login', 'register', 'contact', 'about', 'privacy',
            'terms', 'policy', 'advert', 'ads.'
        ]
        
        url_lower = url.lower()
        return not any(pattern in url_lower for pattern in skip_patterns)
    
    def _extract_links(self, response: HtmlResponse, domain: str) -> List[str]:
        """Extract links for follow-up crawling."""
        links = []
        
        # Get all links
        for link in response.css('a[href]'):
            href = link.css('::attr(href)').get()
            if not href:
                continue
            
            # Convert to absolute URL
            if href.startswith('/'):
                base_url = f"https://{domain}"
                href = urljoin(base_url, href)
            elif not href.startswith('http'):
                href = urljoin(response.url, href)
            
            # Check if link is from same domain and should be followed
            if self._should_follow_link(href, domain):
                links.append(href)
        
        return links
    
    def _should_follow_link(self, url: str, domain: str) -> bool:
        """Check if link should be followed."""
        # Check domain
        link_domain = urlparse(url).netloc
        if link_domain != domain:
            return False
        
        # Check path
        path = urlparse(url).path
        config = self.site_configs.get(domain, {})
        
        # Skip blocked paths
        if any(path.startswith(blocked) for blocked in config.get('blocked_paths', [])):
            return False
        
        # Only follow allowed paths
        if not any(path.startswith(allowed) for allowed in config.get('allowed_paths', [])):
            return False
        
        # Check if valid news URL
        if not is_valid_news_url(url):
            return False
        
        return True
    
    def handle_error(self, failure):
        """Handle request errors."""
        self.stats['errors'] += 1
        
        request = failure.request
        response = failure.value
        
        logger.error(f"Error crawling {request.url}: {response}")
        
        # Don't retry certain errors
        if hasattr(response, 'status'):
            if response.status in [404, 403, 404]:
                return None
        
        # For other errors, retry the request
        return failure.request.copy()
    
    def closed(self, reason):
        """Called when spider is closed."""
        duration = time.time() - self.stats['start_time']
        
        logger.info(f"Spider closed: {reason}")
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info(f"Items scraped: {self.stats['items_scraped']}")
        logger.info(f"Pages crawled: {self.stats['pages_crawled']}")
        logger.info(f"Domains crawled: {len(self.stats['domains_crawled'])}")
        logger.info(f"Errors: {self.stats['errors']}")
        
        if self.stats['pages_crawled'] > 0:
            items_per_minute = (self.stats['items_scraped'] / duration) * 60
            pages_per_minute = (self.stats['pages_crawled'] / duration) * 60
            logger.info(f"Items per minute: {items_per_minute:.2f}")
            logger.info(f"Pages per minute: {pages_per_minute:.2f}")
        
        # Update Redis stats
        self._update_redis_stats()
    
    def _update_redis_stats(self):
        """Update statistics in Redis."""
        try:
            from scrapy_redis.connection import get_redis_from_settings
            redis_client = get_redis_from_settings(self.settings)
            
            stats_key = f"{self.name}:stats"
            stats_data = {
                'items_scraped': self.stats['items_scraped'],
                'pages_crawled': self.stats['pages_crawled'],
                'domains_crawled': list(self.stats['domains_crawled']),
                'errors': self.stats['errors'],
                'duration': time.time() - self.stats['start_time'],
                'timestamp': time.time()
            }
            
            redis_client.hmset(stats_key, stats_data)
            redis_client.expire(stats_key, 86400)  # Expire in 24 hours
            
        except Exception as e:
            logger.error(f"Error updating Redis stats: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get spider statistics."""
        return {
            'items_scraped': self.stats['items_scraped'],
            'pages_crawled': self.stats['pages_crawled'],
            'domains_crawled': list(self.stats['domains_crawled']),
            'errors': self.stats['errors'],
            'duration': time.time() - self.stats['start_time'],
            'last_item_time': self.stats['last_item_time']
        }
