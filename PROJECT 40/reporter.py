from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

def create_report(competitor_data):
    env = Environment(loader=FileSystemLoader('templates'))
    template = env.get_template('weekly_report.html')
    
    html_out = template.render(
        date="May 2026",
        competitors=competitor_data # List of dicts with insights/URLs
    )
    
    # Save as PDF for executive attachment
    HTML(string=html_out).write_pdf("competitive_intel_weekly.pdf")
    return html_out