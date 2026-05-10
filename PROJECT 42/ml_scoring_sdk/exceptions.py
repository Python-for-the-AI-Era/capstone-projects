"""
Custom exceptions for the ML Scoring SDK.

Provides structured error handling with specific exception types
for different API error scenarios.
"""

from typing import Optional, Dict, Any


class ScoringAPIError(Exception):
    """Base exception for all ML Scoring API errors."""
    
    def __init__(
        self, 
        message: str, 
        status_code: Optional[int] = None,
        response_data: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.response_data = response_data or {}
        super().__init__(self.message)
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(message='{self.message}', status_code={self.status_code})"


class AuthenticationError(ScoringAPIError):
    """Raised when API authentication fails (401)."""
    
    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(message, status_code=401, **kwargs)


class RateLimitError(ScoringAPIError):
    """Raised when API rate limit is exceeded (429)."""
    
    def __init__(
        self, 
        message: str = "Rate limit exceeded", 
        retry_after: Optional[int] = None,
        **kwargs
    ):
        self.retry_after = retry_after
        super().__init__(message, status_code=429, **kwargs)


class ModelNotFoundError(ScoringAPIError):
    """Raised when the requested model is not found (404)."""
    
    def __init__(self, message: str = "Model not found", **kwargs):
        super().__init__(message, status_code=404, **kwargs)


class ValidationError(ScoringAPIError):
    """Raised when request validation fails (400)."""
    
    def __init__(
        self, 
        message: str = "Validation failed", 
        validation_errors: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        self.validation_errors = validation_errors or {}
        super().__init__(message, status_code=400, **kwargs)


class ServerError(ScoringAPIError):
    """Raised when server error occurs (5xx)."""
    
    def __init__(
        self, 
        message: str = "Internal server error", 
        error_code: Optional[str] = None,
        **kwargs
    ):
        self.error_code = error_code
        super().__init__(message, status_code=500, **kwargs)


class NetworkError(ScoringAPIError):
    """Raised when network-related errors occur."""
    
    def __init__(self, message: str = "Network error", **kwargs):
        super().__init__(message, status_code=None, **kwargs)


class TimeoutError(ScoringAPIError):
    """Raised when request times out."""
    
    def __init__(self, message: str = "Request timeout", **kwargs):
        super().__init__(message, status_code=None, **kwargs)


# HTTP status code to exception mapping
STATUS_CODE_EXCEPTIONS = {
    400: ValidationError,
    401: AuthenticationError,
    404: ModelNotFoundError,
    429: RateLimitError,
    500: ServerError,
    502: ServerError,
    503: ServerError,
    504: ServerError,
}


def raise_exception_from_status_code(
    status_code: int, 
    message: str = "", 
    response_data: Optional[Dict[str, Any]] = None
) -> None:
    """Raise appropriate exception based on HTTP status code."""
    
    if status_code in STATUS_CODE_EXCEPTIONS:
        exception_class = STATUS_CODE_EXCEPTIONS[status_code]
        
        # Add specific details for certain status codes
        kwargs = {"response_data": response_data}
        
        if status_code == 429 and response_data:
            # Extract retry-after header if available
            retry_after = response_data.get("headers", {}).get("retry-after")
            if retry_after:
                kwargs["retry_after"] = int(retry_after)
        
        if status_code == 400 and response_data:
            # Extract validation errors if available
            kwargs["validation_errors"] = response_data.get("validation_errors", {})
        
        if status_code >= 500 and response_data:
            # Extract server error code if available
            kwargs["error_code"] = response_data.get("error_code")
        
        # Use provided message or default
        error_message = message or f"HTTP {status_code} error"
        
        raise exception_class(error_message, **kwargs)
    else:
        # For other status codes, raise generic ScoringAPIError
        raise ScoringAPIError(
            message or f"HTTP {status_code} error",
            status_code=status_code,
            response_data=response_data
        )
