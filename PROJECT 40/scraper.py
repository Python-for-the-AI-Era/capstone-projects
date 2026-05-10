import logging
import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential
from config import settings

logger = logging.getLogger(__name__)


class CompetitorScraper:
    """Handles web scraping of competitor websites using Playwright"""
    
    def __init__(self):
        self.user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        self.timeout = 30000  # 30 seconds
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def _get_page_content_async(self, url):
        """Async method to get page content using Playwright"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=self.user_agent,
                viewport={'width': 1920, 'height': 1080}
            )
            page = await context.new_page()
            
            # Set additional headers to look more like a real browser
            await page.set_extra_http_headers({
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            })
            
            try:
                # Navigate to page and wait for network idle
                await page.goto(url, wait_until="networkidle", timeout=self.timeout)
                
                # Wait a bit more for dynamic content to load
                await page.wait_for_timeout(2000)
                
                # Get page content
                content = await page.content()
                
                # Extract title and meta description for context
                title = await page.title()
                meta_desc = await page.eval_on_selector('meta[name="description"]', 'el => el ? el.content : ""')
                
                await browser.close()
                
                return {
                    'content': content,
                    'title': title,
                    'meta_description': meta_desc,
                    'url': url
                }
                
            except Exception as e:
                await browser.close()
                logger.error(f"Error scraping {url}: {e}")
                raise
    
    def get_page_content(self, url):
        """Synchronous wrapper for async page content retrieval"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        try:
            return loop.run_until_complete(self._get_page_content_async(url))
        except Exception as e:
            logger.error(f"Failed to scrape {url}: {e}")
            return None
    
    def extract_text_content(self, html_content):
        """Extract clean text content from HTML"""
        if not html_content:
            return ""
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
            
            # Get main content areas
            main_content = ""
            
            # Try to find main content areas
            for selector in ['main', 'article', '.content', '.post-content', '.blog-content']:
                main_element = soup.select_one(selector)
                if main_element:
                    main_content = main_element.get_text(strip=True)
                    break
            
            # If no main content found, get body text
            if not main_content:
                body = soup.find('body')
                if body:
                    main_content = body.get_text(strip=True)
            
            # Clean up text
            lines = (line.strip() for line in main_content.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            return text[:10000]  # Limit to 10k characters for LLM processing
            
        except Exception as e:
            logger.error(f"Error extracting text content: {e}")
            return html_content[:10000]  # Fallback to raw HTML
    
    def scrape_multiple_pages(self, urls):
        """Scrape multiple pages concurrently"""
        async def scrape_all():
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(user_agent=self.user_agent)
                
                tasks = []
                for url in urls:
                    task = self._scrape_single_page(context, url)
                    tasks.append(task)
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                await browser.close()
                
                return results
        
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        try:
            return loop.run_until_complete(scrape_all())
        except Exception as e:
            logger.error(f"Error in concurrent scraping: {e}")
            return []
    
    async def _scrape_single_page(self, context, url):
        """Helper method for concurrent scraping"""
        try:
            page = await context.new_page()
            await page.goto(url, wait_until="networkidle", timeout=self.timeout)
            await page.wait_for_timeout(2000)
            
            content = await page.content()
            title = await page.title()
            
            await page.close()
            
            return {
                'url': url,
                'content': content,
                'title': title,
                'success': True
            }
            
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return {
                'url': url,
                'content': None,
                'title': None,
                'success': False,
                'error': str(e)
            }
