import logging
from datetime import datetime
from celery import current_task
from celery_app import app
from scraper import CompetitorScraper
from intelligence_engine import extract_insights
from deduplicator import ContentDeduplicator
from reporter import create_report
from delivery import send_email
from config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@app.task(bind=True, name='scrape_competitor')
def scrape_competitor_task(self, competitor_data):
    """Scrape a single competitor's pages"""
    scraper = CompetitorScraper()
    deduplicator = ContentDeduplicator()
    
    try:
        # Update task state
        self.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': 3, 'status': f'Scraping {competitor_data["name"]}'}
        )
        
        scraped_data = {
            'name': competitor_data['name'],
            'pages': []
        }
        
        # Scrape each page type
        page_types = ['blog_url', 'pricing_url', 'careers_url']
        for i, page_type in enumerate(page_types):
            if page_type in competitor_data:
                url = competitor_data[page_type]
                content = scraper.get_page_content(url)
                
                if content:
                    # Check if content is new
                    if deduplicator.is_new_content(url, content):
                        # Extract insights using LLM
                        insights = extract_insights(content)
                        
                        scraped_data['pages'].append({
                            'url': url,
                            'type': page_type.replace('_url', ''),
                            'content': content,
                            'insights': insights,
                            'scraped_at': datetime.utcnow().isoformat()
                        })
                        
                        # Store content hash for deduplication
                        deduplicator.store_content_hash(url, content)
                
                # Update progress
                self.update_state(
                    state='PROGRESS',
                    meta={'current': i + 1, 'total': 3, 'status': f'Processed {page_type}'}
                )
        
        return scraped_data
        
    except Exception as exc:
        logger.error(f"Error scraping {competitor_data['name']}: {exc}")
        raise self.retry(exc=exc, countdown=60, max_retries=3)


@app.task(bind=True, name='run_weekly_intelligence_report')
def run_weekly_intelligence_report(self):
    """Main orchestration task for weekly competitive intelligence report"""
    logger.info("Starting weekly competitive intelligence report")
    
    try:
        # Update task state
        self.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': len(settings.competitors), 'status': 'Starting report generation'}
        )
        
        # Scrape all competitors in parallel
        competitor_tasks = []
        for i, competitor in enumerate(settings.competitors):
            task = scrape_competitor_task.delay(competitor)
            competitor_tasks.append(task)
            
        # Wait for all tasks to complete
        results = []
        for i, task in enumerate(competitor_tasks):
            try:
                result = task.get(timeout=600)  # 10 minute timeout per competitor
                if result and result['pages']:  # Only include competitors with new content
                    results.append(result)
                    
                # Update progress
                self.update_state(
                    state='PROGRESS',
                    meta={'current': i + 1, 'total': len(settings.competitors), 'status': f'Completed {competitor["name"]}'}
                )
                
            except Exception as exc:
                logger.error(f"Error processing competitor {competitor['name']}: {exc}")
                continue
        
        if not results:
            logger.info("No new content found across all competitors")
            return {"status": "completed", "message": "No new content found"}
        
        # Generate report
        self.update_state(
            state='PROGRESS',
            meta={'current': len(settings.competitors), 'total': len(settings.competitors) + 1, 'status': 'Generating report'}
        )
        
        html_report, pdf_path = create_report(results)
        
        # Send email
        self.update_state(
            state='PROGRESS',
            meta={'current': len(settings.competitors) + 1, 'total': len(settings.competitors) + 2, 'status': 'Sending email'}
        )
        
        send_email(html_report, pdf_path)
        
        logger.info("Weekly competitive intelligence report completed successfully")
        
        return {
            "status": "completed",
            "competitors_processed": len(results),
            "total_pages_scraped": sum(len(r['pages']) for r in results),
            "report_sent": True
        }
        
    except Exception as exc:
        logger.error(f"Error in weekly intelligence report: {exc}")
        raise self.retry(exc=exc, countdown=300, max_retries=2)


@app.task(name='test_scraping')
def test_scraping_task():
    """Test task to verify scraping functionality"""
    logger.info("Running test scraping task")
    
    # Test with first competitor
    if settings.competitors:
        test_competitor = settings.competitors[0]
        scraper = CompetitorScraper()
        
        # Test one page
        test_url = test_competitor.get('blog_url')
        if test_url:
            content = scraper.get_page_content(test_url)
            if content:
                insights = extract_insights(content)
                return {
                    "status": "success",
                    "url": test_url,
                    "content_length": len(content),
                    "insights_sample": insights[:200] if insights else None
                }
            else:
                return {"status": "no_content", "url": test_url}
        else:
            return {"status": "no_url", "competitor": test_competitor['name']}
    
    return {"status": "no_competitors"}
