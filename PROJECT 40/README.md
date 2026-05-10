# Automated Competitive Intelligence Report System

A fully automated pipeline that scrapes competitor websites weekly, extracts key information using LLMs, and emails a formatted HTML report with PDF attachment.

## 🎯 Overview

This system monitors 5 competitor websites across three key areas:
- **Blog posts** - New features and product announcements
- **Pricing pages** - Price changes and new plans
- **Careers pages** - Hiring trends and strategic shifts

The system runs weekly via Celery Beat and delivers comprehensive intelligence reports to your growth team.

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Celery Beat   │───▶│   Task Queue     │───▶│  Workers         │
│   (Weekly)      │    │   (Redis)        │    │  (Scraping)      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Playwright    │───▶│   LangChain      │───▶│   Deduplication  │
│   Scraper       │    │   LLM Analysis   │    │   (Redis)        │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Jinja2        │───▶│   WeasyPrint     │───▶│   AWS SES        │
│   HTML Template │    │   PDF Generation │    │   Email Delivery │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

### 2. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your configuration
# - OpenAI API Key
# - AWS credentials
# - Email settings
# - Competitor URLs
```

### 3. Start Services

```bash
# Start Redis server
redis-server

# Start Celery worker
celery -A celery_app worker --loglevel=info

# Start Celery Beat scheduler
celery -A celery_app beat --loglevel=info
```

### 4. Run Tests

```bash
# Validate configuration
python main.py --validate-config

# Run all system tests
python main.py --test

# Generate sample report
python main.py --sample-report
```

## 📋 Configuration

### Environment Variables (.env)

```bash
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# AWS Configuration
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_REGION=us-east-1

# Email Configuration
EMAIL_FROM=ops@yourstartup.com
EMAIL_TO=growth@yourstartup.com,leadership@yourstartup.com

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
```

### Competitor Configuration

Edit `config.py` to update competitor URLs:

```python
competitors = [
    {
        "name": "CompetitorA",
        "blog_url": "https://competitor-a.com/blog",
        "pricing_url": "https://competitor-a.com/pricing",
        "careers_url": "https://competitor-a.com/careers"
    },
    # Add more competitors...
]
```

## 🔧 Components

### 1. Playwright Scraper (`scraper.py`)

- **Features**: Headless browser automation with realistic user behavior
- **Anti-detection**: Custom user agents, headers, and timing
- **Error handling**: Retry logic and graceful failure recovery
- **Content extraction**: Clean text extraction from HTML

### 2. LLM Intelligence Engine (`intelligence_engine.py`)

- **Model**: GPT-4o-mini for cost-effective analysis
- **Structured output**: Pydantic models for consistent insights
- **Prompt engineering**: Optimized for competitive intelligence
- **Error handling**: Fallback for failed analyses

### 3. Deduplication System (`deduplicator.py`)

- **Content hashing**: SHA-256 hashing of normalized content
- **Redis storage**: Efficient content change detection
- **TTL management**: Automatic cleanup of old hashes
- **Statistics**: Storage usage and performance metrics

### 4. Report Generation (`reporter.py`)

- **HTML templates**: Jinja2-based professional reports
- **PDF generation**: WeasyPrint for executive attachments
- **Responsive design**: Mobile-friendly email layouts
- **Statistics**: Executive summary with key metrics

### 5. Email Delivery (`delivery.py`)

- **AWS SES**: Reliable email delivery service
- **HTML + PDF**: Inline HTML with PDF attachment
- **Error handling**: Connection testing and retry logic
- **Multiple recipients**: Support for distribution lists

## 📊 Report Features

### HTML Email Report
- **Professional design**: Clean, branded layout
- **Executive summary**: Key statistics and metrics
- **Competitor sections**: Organized by company
- **Insight categories**: Product, pricing, and strategic changes
- **Source links**: Direct URLs to original content
- **Confidence scores**: LLM analysis reliability indicators

### PDF Attachment
- **Print-optimized**: Professional formatting for executives
- **Complete content**: Full report for archival purposes
- **Branding**: Company logo and consistent styling
- **Page breaks**: Proper section separation

## 🔄 Automation

### Celery Beat Schedule

```python
# Weekly report generation (every Monday at 9 AM)
'weekly-competitive-intelligence': {
    'task': 'tasks.run_weekly_intelligence_report',
    'schedule': crontab(hour=9, minute=0, day_of_week=1),
    'options': {'queue': 'intelligence'}
}
```

### Task Orchestration

1. **Scraping Phase**: Parallel scraping of all competitor pages
2. **Analysis Phase**: LLM processing of new content only
3. **Report Generation**: HTML and PDF creation
4. **Delivery Phase**: Email distribution to stakeholders

## 🧪 Testing

### System Tests

```bash
# Run complete test suite
python main.py --test

# Individual component tests
python main.py --test-scraping     # Test Playwright scraping
python main.py --test-email        # Test AWS SES delivery
python main.py --test-template     # Test Jinja2 templates
python main.py --test-redis        # Test Redis deduplication
```

### Sample Report

```bash
# Generate sample report with mock data
python main.py --sample-report
```

### Manual Report

```bash
# Run full report manually
python main.py --run-report
```

## 📈 Performance & Scaling

### Optimization Features

- **Concurrent scraping**: Parallel processing of competitor pages
- **Content deduplication**: Only process new content
- **Efficient caching**: Redis-based content hashing
- **Retry logic**: Automatic recovery from failures
- **Resource management**: Proper cleanup of browser instances

### Scaling Considerations

- **Horizontal scaling**: Multiple Celery workers
- **Rate limiting**: Respectful scraping intervals
- **Memory management**: Efficient content processing
- **Error isolation**: Individual competitor failures don't affect others

## 🔒 Security & Privacy

### Data Protection

- **API keys**: Secure environment variable storage
- **Content hashing**: No sensitive content stored long-term
- **Email security**: AWS SES with verified domains
- **Access control**: Role-based email distribution

### Compliance

- **Terms of service**: Respectful scraping practices
- **Rate limiting**: Avoid overwhelming competitor servers
- **Data retention**: Configurable content cleanup policies
- **Privacy**: No personal data collection

## 🛠️ Troubleshooting

### Common Issues

**Scraping Failures**
```bash
# Check Playwright installation
playwright install --help

# Test individual URLs
python main.py --test-scraping
```

**Email Delivery Issues**
```bash
# Test AWS SES connection
python main.py --test-email

# Check AWS credentials
aws sts get-caller-identity
```

**Redis Connection Issues**
```bash
# Test Redis connection
python main.py --test-redis

# Check Redis server
redis-cli ping
```

### Logging

- **Celery logs**: Worker and scheduler activity
- **Application logs**: Detailed error messages
- **Performance metrics**: Task execution times
- **Error tracking**: Failed task notifications

## 📋 Maintenance

### Regular Tasks

- **Monitor Redis usage**: Clean up old content hashes
- **Update competitors**: Add/remove tracked companies
- **Review prompts**: Optimize LLM analysis accuracy
- **Check quotas**: Monitor AWS SES sending limits

### Monitoring

- **Task success rates**: Weekly report completion
- **Processing times**: End-to-end performance
- **Error rates**: Scraping and analysis failures
- **Resource usage**: Memory and CPU consumption

## 🚀 Deployment

### Production Setup

```bash
# Install production dependencies
pip install -r requirements.txt

# Configure production environment
export CELERY_BROKER_URL=redis://prod-redis:6379/0
export CELERY_RESULT_BACKEND=redis://prod-redis:6379/0

# Start production services
celery -A celery_app worker --loglevel=info --concurrency=4
celery -A celery_app beat --loglevel=info
```

### Docker Deployment

```dockerfile
# Dockerfile example
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    chromium \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Install Playwright
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy application code
COPY . .

# Start Celery worker
CMD ["celery", "-A", "celery_app", "worker", "--loglevel=info"]
```

## 📞 Support

### Getting Help

1. **Check logs**: Review Celery and application logs
2. **Run tests**: Execute the test suite for diagnostics
3. **Validate config**: Ensure all environment variables are set
4. **Check services**: Verify Redis and AWS connectivity

### Contributing

1. **Add tests**: Cover new functionality with tests
2. **Update docs**: Keep documentation current
3. **Follow patterns**: Maintain consistent code style
4. **Test thoroughly**: Validate all changes

---

This system provides your growth team with actionable competitive intelligence, automatically delivered every week. Stay ahead of market changes and competitor moves with minimal manual effort.
