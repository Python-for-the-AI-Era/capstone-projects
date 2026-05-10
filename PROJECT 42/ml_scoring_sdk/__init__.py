"""
ML Scoring SDK

A comprehensive Python SDK for interacting with internal ML scoring APIs.

Features:
- Synchronous and asynchronous clients
- Automatic retry with exponential backoff
- Structured error handling
- Mock client for testing
- Type hints and Pydantic validation
"""

from .client import ScoringClient
from .async_client import AsyncScoringClient
from .mock_client import MockScoringClient
from .exceptions import (
    ScoringAPIError,
    RateLimitError,
    ModelNotFoundError,
    AuthenticationError,
    ValidationError,
    ServerError
)
from .models import (
    ScoringRequest,
    ScoringResponse,
    BatchScoringRequest,
    BatchScoringResponse,
    HealthResponse
)

__version__ = "1.0.0"
__author__ = "ML Team"
__email__ = "ml-team@company.com"

__all__ = [
    # Clients
    "ScoringClient",
    "AsyncScoringClient", 
    "MockScoringClient",
    
    # Exceptions
    "ScoringAPIError",
    "RateLimitError",
    "ModelNotFoundError",
    "AuthenticationError",
    "ValidationError",
    "ServerError",
    
    # Models
    "ScoringRequest",
    "ScoringResponse",
    "BatchScoringRequest",
    "BatchScoringResponse",
    "HealthResponse",
]
