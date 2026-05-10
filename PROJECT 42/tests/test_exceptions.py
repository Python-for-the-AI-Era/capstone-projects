"""
Tests for the ML Scoring SDK exceptions module.
"""

import pytest
from ml_scoring_sdk.exceptions import (
    ScoringAPIError,
    RateLimitError,
    ModelNotFoundError,
    AuthenticationError,
    ValidationError,
    ServerError,
    NetworkError,
    TimeoutError,
    STATUS_CODE_EXCEPTIONS,
    raise_exception_from_status_code
)


class TestScoringAPIError:
    """Test the base ScoringAPIError class."""
    
    def test_basic_error(self):
        """Test basic error creation."""
        error = ScoringAPIError("Test error")
        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.status_code is None
        assert error.response_data is None
    
    def test_error_with_details(self):
        """Test error creation with additional details."""
        response_data = {"error": "details", "code": 123}
        error = ScoringAPIError("Test error", status_code=400, response_data=response_data)
        assert error.message == "Test error"
        assert error.status_code == 400
        assert error.response_data == response_data


class TestSpecificExceptions:
    """Test specific exception classes."""
    
    def test_rate_limit_error(self):
        """Test RateLimitError."""
        error = RateLimitError("Rate limit exceeded")
        assert isinstance(error, ScoringAPIError)
        assert str(error) == "Rate limit exceeded"
    
    def test_model_not_found_error(self):
        """Test ModelNotFoundError."""
        error = ModelNotFoundError("Model not found")
        assert isinstance(error, ScoringAPIError)
        assert str(error) == "Model not found"
    
    def test_authentication_error(self):
        """Test AuthenticationError."""
        error = AuthenticationError("Authentication failed")
        assert isinstance(error, ScoringAPIError)
        assert str(error) == "Authentication failed"
    
    def test_validation_error(self):
        """Test ValidationError."""
        error = ValidationError("Invalid input")
        assert isinstance(error, ScoringAPIError)
        assert str(error) == "Invalid input"
    
    def test_server_error(self):
        """Test ServerError."""
        error = ServerError("Internal server error")
        assert isinstance(error, ScoringAPIError)
        assert str(error) == "Internal server error"
    
    def test_network_error(self):
        """Test NetworkError."""
        error = NetworkError("Network connection failed")
        assert isinstance(error, ScoringAPIError)
        assert str(error) == "Network connection failed"
    
    def test_timeout_error(self):
        """Test TimeoutError."""
        error = TimeoutError("Request timed out")
        assert isinstance(error, ScoringAPIError)
        assert str(error) == "Request timed out"


class TestStatusCodeMapping:
    """Test the status code to exception mapping."""
    
    def test_status_code_exceptions_mapping(self):
        """Test that all expected status codes are mapped."""
        expected_mappings = {
            400: ValidationError,
            401: AuthenticationError,
            404: ModelNotFoundError,
            429: RateLimitError,
            500: ServerError,
            502: ServerError,
            503: ServerError,
            504: ServerError,
        }
        
        for status_code, expected_exception in expected_mappings.items():
            assert STATUS_CODE_EXCEPTIONS[status_code] == expected_exception
    
    def test_raise_exception_from_status_code(self):
        """Test raising exceptions from status codes."""
        test_cases = [
            (400, ValidationError, "Bad request"),
            (401, AuthenticationError, "Unauthorized"),
            (404, ModelNotFoundError, "Not found"),
            (429, RateLimitError, "Rate limit exceeded"),
            (500, ServerError, "Internal server error"),
        ]
        
        for status_code, expected_exception, message in test_cases:
            with pytest.raises(expected_exception) as exc_info:
                raise_exception_from_status_code(status_code, message)
            
            assert str(exc_info.value) == message
            assert exc_info.value.status_code == status_code
    
    def test_raise_exception_unknown_status_code(self):
        """Test raising exception for unknown status code."""
        with pytest.raises(ScoringAPIError) as exc_info:
            raise_exception_from_status_code(418, "I'm a teapot")
        
        assert isinstance(exc_info.value, ScoringAPIError)
        assert exc_info.value.status_code == 418
        assert str(exc_info.value) == "I'm a teapot"
    
    def test_raise_exception_with_response_data(self):
        """Test raising exception with response data."""
        response_data = {"error": "Invalid field", "field": "email"}
        
        with pytest.raises(ValidationError) as exc_info:
            raise_exception_from_status_code(400, "Validation failed", response_data)
        
        assert exc_info.value.response_data == response_data
        assert exc_info.value.status_code == 400


class TestExceptionInheritance:
    """Test exception inheritance hierarchy."""
    
    def test_all_exceptions_inherit_from_base(self):
        """Test that all custom exceptions inherit from ScoringAPIError."""
        exceptions = [
            RateLimitError,
            ModelNotFoundError,
            AuthenticationError,
            ValidationError,
            ServerError,
            NetworkError,
            TimeoutError,
        ]
        
        for exception_class in exceptions:
            assert issubclass(exception_class, ScoringAPIError)
    
    def test_exception_chaining(self):
        """Test exception chaining works properly."""
        original_error = ValueError("Original error")
        
        try:
            raise NetworkError("Network failed") from original_error
        except NetworkError as e:
            assert e.__cause__ is original_error
            assert str(e) == "Network failed"
