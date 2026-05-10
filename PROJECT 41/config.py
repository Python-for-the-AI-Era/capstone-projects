import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database Configuration
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/dropbox_nigeria"
    test_database_url: str = "postgresql+asyncpg://user:password@localhost:5432/dropbox_nigeria_test"
    
    # FastAPI Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    
    # Order Processing Configuration
    idempotency_window_seconds: int = 60
    max_concurrent_orders_per_user: int = 5
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
