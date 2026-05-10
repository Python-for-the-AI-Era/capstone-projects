# This Dockerfile reproduces the original dependency issue
FROM python:3.11-slim

WORKDIR /app

# Copy only requirements first to leverage Docker layer caching
COPY pyproject.toml .

# Install without the pinned versions to reproduce the issue
RUN pip install --upgrade pip && \
    pip install Scrapy>=2.11.0 beautifulsoup4>=4.12.0

COPY . .

# This will fail with the dependency issue
CMD ["scrapy", "crawl", "stanbic_spider"]
