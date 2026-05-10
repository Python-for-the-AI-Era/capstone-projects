import scrapy
from bs4 import BeautifulSoup


class StanbicSpider(scrapy.Spider):
    name = 'stanbic_spider'
    start_urls = ['https://www.stanbicbank.co.ug']
    
    def parse(self, response):
        """
        Parse the main page and extract banking information
        """
        # Use BeautifulSoup for parsing (this will trigger the lxml dependency issue)
        soup = BeautifulSoup(response.text, 'lxml')
        
        self.log(f"Successfully parsed page: {response.url}")
        self.log(f"Page title: {soup.title.string if soup.title else 'No title'}")
        
        # Extract some basic information
        yield {
            'url': response.url,
            'title': soup.title.string if soup.title else '',
            'status_code': response.status,
            'links_count': len(soup.find_all('a')),
        }
        
        # Follow some links for demonstration
        for link in soup.find_all('a', href=True)[:3]:  # Limit to 3 links for demo
            absolute_url = response.urljoin(link['href'])
            yield scrapy.Request(
                absolute_url,
                callback=self.parse_page,
                meta={'link_text': link.get_text(strip=True)}
            )
    
    def parse_page(self, response):
        """
        Parse individual pages
        """
        soup = BeautifulSoup(response.text, 'lxml')
        
        yield {
            'url': response.url,
            'title': soup.title.string if soup.title else '',
            'link_text': response.meta.get('link_text', ''),
            'status_code': response.status,
        }
