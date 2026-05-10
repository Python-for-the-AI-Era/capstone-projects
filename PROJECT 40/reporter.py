import logging
import os
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML, CSS
from config import settings

logger = logging.getLogger(__name__)


def create_report(competitor_data):
    """Generate HTML report and PDF from competitor intelligence data"""
    try:
        # Setup Jinja2 environment
        template_dir = os.path.join(os.path.dirname(__file__), 'templates')
        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template('weekly_report.html')
        
        # Calculate summary statistics
        summary_stats = calculate_summary_stats(competitor_data)
        
        # Render HTML template
        html_content = template.render(
            report_title=settings.report_title,
            company_name=settings.company_name,
            report_date=datetime.now().strftime("%B %d, %Y"),
            competitors=competitor_data,
            summary_stats=summary_stats
        )
        
        # Generate PDF
        pdf_filename = f"competitive_intelligence_{datetime.now().strftime('%Y%m%d')}.pdf"
        pdf_path = os.path.join(os.path.dirname(__file__), pdf_filename)
        
        try:
            # Create PDF with WeasyPrint
            html_doc = HTML(string=html_content)
            
            # Add custom CSS for better PDF rendering
            css = CSS(string='''
                @page {
                    size: A4;
                    margin: 2cm;
                }
                body {
                    font-size: 12px;
                }
                .header {
                    page-break-after: always;
                }
                .competitor-section {
                    page-break-inside: avoid;
                }
            ''')
            
            html_doc.write_pdf(pdf_path, stylesheets=[css])
            logger.info(f"PDF report generated: {pdf_path}")
            
        except Exception as e:
            logger.error(f"Error generating PDF: {e}")
            # Fallback: create empty PDF file
            pdf_path = None
        
        return html_content, pdf_path
        
    except Exception as e:
        logger.error(f"Error creating report: {e}")
        raise


def calculate_summary_stats(competitor_data):
    """Calculate summary statistics for the report"""
    if not competitor_data:
        return {
            'total_competitors': 0,
            'total_pages': 0,
            'total_insights': 0,
            'new_content_pages': 0
        }
    
    total_competitors = len(competitor_data)
    total_pages = 0
    total_insights = 0
    new_content_pages = 0
    
    for competitor in competitor_data:
        if competitor.get('pages'):
            total_pages += len(competitor['pages'])
            new_content_pages += len(competitor['pages'])
            
            for page in competitor['pages']:
                if page.get('insights'):
                    insights = page['insights']
                    # Count all types of insights
                    insight_count = 0
                    if hasattr(insights, 'product_updates') and insights.product_updates:
                        insight_count += len(insights.product_updates)
                    if hasattr(insights, 'pricing_changes') and insights.pricing_changes:
                        insight_count += len(insights.pricing_changes)
                    if hasattr(insights, 'strategic_shifts') and insights.strategic_shifts:
                        insight_count += len(insights.strategic_shifts)
                    
                    total_insights += insight_count
    
    return {
        'total_competitors': total_competitors,
        'total_pages': total_pages,
        'total_insights': total_insights,
        'new_content_pages': new_content_pages
    }


def create_sample_report():
    """Create a sample report for testing purposes"""
    sample_data = [
        {
            'name': 'CompetitorA',
            'pages': [
                {
                    'url': 'https://competitor-a.com/blog/new-feature',
                    'type': 'blog',
                    'insights': {
                        'product_updates': ['Launched new AI-powered dashboard', 'Improved mobile app performance'],
                        'pricing_changes': ['Introduced new enterprise tier at $999/month'],
                        'strategic_shifts': ['Hired 5 new engineers focused on AI'],
                        'summary': 'CompetitorA is focusing on AI features and enterprise expansion.',
                        'confidence_score': 0.85
                    }
                }
            ]
        },
        {
            'name': 'CompetitorB',
            'pages': [
                {
                    'url': 'https://competitor-b.com/pricing',
                    'type': 'pricing',
                    'insights': {
                        'product_updates': [],
                        'pricing_changes': ['Reduced starter plan price by 20%', 'Added annual billing discount'],
                        'strategic_shifts': [],
                        'summary': 'CompetitorB is making pricing more competitive.',
                        'confidence_score': 0.92
                    }
                }
            ]
        }
    ]
    
    return create_report(sample_data)


def validate_template():
    """Validate that the Jinja2 template can be rendered"""
    try:
        template_dir = os.path.join(os.path.dirname(__file__), 'templates')
        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template('weekly_report.html')
        
        # Test rendering with minimal data
        test_html = template.render(
            report_title="Test Report",
            company_name="Test Company",
            report_date="January 1, 2024",
            competitors=[],
            summary_stats={
                'total_competitors': 0,
                'total_pages': 0,
                'total_insights': 0,
                'new_content_pages': 0
            }
        )
        
        logger.info("Template validation successful")
        return True
        
    except Exception as e:
        logger.error(f"Template validation failed: {e}")
        return False