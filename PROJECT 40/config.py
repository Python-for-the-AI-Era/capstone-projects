import os
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # OpenAI Configuration
    openai_api_key: str = ""
    
    # AWS Configuration
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"
    
    # Redis Configuration
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    
    # Email Configuration
    email_from: str = "ops@yourstartup.com"
    email_to: List[str] = ["growth@yourstartup.com"]
    
    # Competitor Configuration
    competitors: List[dict] = [
        {
            "name": "CompetitorA",
            "blog_url": "https://competitor-a.com/blog",
            "pricing_url": "https://competitor-a.com/pricing", 
            "careers_url": "https://competitor-a.com/careers"
        },
        {
            "name": "CompetitorB",
            "blog_url": "https://competitor-b.com/blog",
            "pricing_url": "https://competitor-b.com/pricing",
            "careers_url": "https://competitor-b.com/careers"
        },
        {
            "name": "CompetitorC", 
            "blog_url": "https://competitor-c.com/blog",
            "pricing_url": "https://competitor-c.com/pricing",
            "careers_url": "https://competitor-c.com/careers"
        },
        {
            "name": "CompetitorD",
            "blog_url": "https://competitor-d.com/blog", 
            "pricing_url": "https://competitor-d.com/pricing",
            "careers_url": "https://competitor-d.com/careers"
        },
        {
            "name": "CompetitorE",
            "blog_url": "https://competitor-e.com/blog",
            "pricing_url": "https://competitor-e.com/pricing", 
            "careers_url": "https://competitor-e.com/careers"
        }
    ]
    
    # Celery Configuration
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"
    
    # Report Configuration
    report_title: str = "Weekly Competitive Intelligence Report"
    company_name: str = "Your Startup"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
