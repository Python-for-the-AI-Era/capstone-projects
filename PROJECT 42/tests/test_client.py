"""
Tests for the ML Scoring SDK synchronous client.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import httpx

from ml_scoring_sdk.client import ScoringClient
from ml_scoring_sdk.models import (
    ScoringRequest, 
    ScoringResponse, 
    BatchScoringRequest, 
    BatchScoringResponse,
    HealthResponse
)
from ml_scoring_sdk.exceptions import (
    RateLimitError,
    ModelNotFoundError,
    AuthenticationError,
    ValidationError,
    ServerError,
    NetworkError,
    TimeoutError,
    ScoringAPIError
)


@pytest.fixture
def client():
    """Create a test client instance."""
    return ScoringClient(
        base_url="https://api.example.com",
        api_key="test-api-key",
        timeout=5
    )


@pytest.fixture
def mock_response():
    """Create a mock HTTP response."""
    response = Mock(spec=httpx.Response)
    response.status_code = 200
    response.headers = {"Content-Type": "application/json"}
    response.json.return_value = {
        "score": 0.75,
        "confidence": 0.95,
        "model_id": "test-model",
        "timestamp": datetime.utcnow().isoformat(),
        "features": {"age": 25, "income": 50000.0}
    }
    response.content = b'{"score": 0.75}'
    return response


class TestScoringClientInit:
    """Test ScoringClient initialization."""
    
    def test_client_init_default(self):
        """Test client initialization with default parameters."""
        client = ScoringClient("https://api.example.com", "test-key")
        
        assert client.base_url == "https://api.example.com"
        assert client.api_key == "test-key"
        assert client.timeout == 10
        assert client.max_retries == 3
        assert client.retry_delay_min == 2.0
        assert client.retry_delay_max == 10.0
    
    def test_client_init_custom_params(self):
        """Test client initialization with custom parameters."""
        client = ScoringClient(
            base_url="https://api.example.com/",
            api_key="test-key",
            timeout=15,
            max_retries=5,
            retry_delay_min=1.0,
            retry_delay_max=20.0
        )
        
        assert client.base_url == "https://api.example.com"  # Trailing slash removed
        assert client.timeout == 15
        assert client.max_retries == 5
        assert client.retry_delay_min == 1.0
        assert client.retry_delay_max == 20.0
    
    def test_client_http_setup(self):
        """Test that HTTP client is properly configured."""
        client = ScoringClient("https://api.example.com", "test-key")
        
        assert client.client.base_url == "https://api.example.com"
        assert "X-API-Key" in client.client.headers
        assert client.client.headers["X-API-Key"] == "test-key"
        assert "User-Agent" in client.client.headers
        assert "ml-scoring-sdk/1.0.0" in client.client.headers["User-Agent"]


class TestScoringClientContextManager:
    """Test ScoringClient context manager support."""
    
    def test_context_manager(self):
        """Test using client as context manager."""
        with ScoringClient("https://api.example.com", "test-key") as client:
            assert isinstance(client, ScoringClient)
            assert client.base_url == "https://api.example.com"
    
    @patch('ml_scoring_sdk.client.httpx.Client')
    def test_context_manager_close(self, mock_client_class):
        """Test that context manager closes the client."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        with ScoringClient("https://api.example.com", "test-key") as client:
            pass
        
        mock_client.close.assert_called_once()
    
    def test_manual_close(self):
        """Test manual client closing."""
        with patch('ml_scoring_sdk.client.httpx.Client') as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            
            client = ScoringClient("https://api.example.com", "test-key")
            client.close()
            
            mock_client.close.assert_called_once()


class TestScoringClientResponseHandling:
    """Test response handling methods."""
    
    def test_handle_response_success(self, client, mock_response):
        """Test handling successful response."""
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}
        
        result = client._handle_response(mock_response)
        
        assert result == {"status": "ok"}
    
    def test_handle_response_error_400(self, client, mock_response):
        """Test handling 400 error response."""
        mock_response.status_code = 400
        mock_response.json.return_value = {"message": "Bad request"}
        
        with pytest.raises(ValidationError) as exc_info:
            client._handle_response(mock_response)
        
        assert str(exc_info.value) == "Bad request"
        assert exc_info.value.status_code == 400
    
    def test_handle_response_error_401(self, client, mock_response):
        """Test handling 401 error response."""
        mock_response.status_code = 401
        mock_response.json.return_value = {"message": "Unauthorized"}
        
        with pytest.raises(AuthenticationError) as exc_info:
            client._handle_response(mock_response)
        
        assert str(exc_info.value) == "Unauthorized"
        assert exc_info.value.status_code == 401
    
    def test_handle_response_error_404(self, client, mock_response):
        """Test handling 404 error response."""
        mock_response.status_code = 404
        mock_response.json.return_value = {"message": "Not found"}
        
        with pytest.raises(ModelNotFoundError) as exc_info:
            client._handle_response(mock_response)
        
        assert str(exc_info.value) == "Not found"
        assert exc_info.value.status_code == 404
    
    def test_handle_response_error_429(self, client, mock_response):
        """Test handling 429 error response."""
        mock_response.status_code = 429
        mock_response.json.return_value = {"message": "Rate limit exceeded"}
        
        with pytest.raises(RateLimitError) as exc_info:
            client._handle_response(mock_response)
        
        assert str(exc_info.value) == "Rate limit exceeded"
        assert exc_info.value.status_code == 429
    
    def test_handle_response_error_500(self, client, mock_response):
        """Test handling 500 error response."""
        mock_response.status_code = 500
        mock_response.json.return_value = {"message": "Internal server error"}
        
        with pytest.raises(ServerError) as exc_info:
            client._handle_response(mock_response)
        
        assert str(exc_info.value) == "Internal server error"
        assert exc_info.value.status_code == 500
    
    def test_handle_response_invalid_json(self, client, mock_response):
        """Test handling response with invalid JSON."""
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.content = b"Invalid JSON"
        
        result = client._handle_response(mock_response)
        
        assert result == {}


class TestScoringClientRequestMaking:
    """Test HTTP request making."""
    
    @patch('ml_scoring_sdk.client.httpx.Client')
    def test_make_request_success(self, mock_client_class, client):
        """Test successful request making."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "success"}
        mock_client.request.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        client.client = mock_client
        result = client._make_request("GET", "/test")
        
        mock_client.request.assert_called_once_with("GET", "/test")
        assert result == mock_response
    
    @patch('ml_scoring_sdk.client.httpx.Client')
    def test_make_request_timeout(self, mock_client_class, client):
        """Test request timeout handling."""
        mock_client = Mock()
        mock_client.request.side_effect = httpx.TimeoutException("Timeout")
        mock_client_class.return_value = mock_client
        
        client.client = mock_client
        
        with pytest.raises(TimeoutError) as exc_info:
            client._make_request("GET", "/test")
        
        assert "Request timeout" in str(exc_info.value)
    
    @patch('ml_scoring_sdk.client.httpx.Client')
    def test_make_request_network_error(self, mock_client_class, client):
        """Test network error handling."""
        mock_client = Mock()
        mock_client.request.side_effect = httpx.NetworkError("Connection failed")
        mock_client_class.return_value = mock_client
        
        client.client = mock_client
        
        with pytest.raises(NetworkError) as exc_info:
            client._make_request("GET", "/test")
        
        assert "Network error" in str(exc_info.value)
    
    @patch('ml_scoring_sdk.client.httpx.Client')
    def test_make_request_unexpected_error(self, mock_client_class, client):
        """Test unexpected error handling."""
        mock_client = Mock()
        mock_client.request.side_effect = Exception("Unexpected error")
        mock_client_class.return_value = mock_client
        
        client.client = mock_client
        
        with pytest.raises(ScoringAPIError) as exc_info:
            client._make_request("GET", "/test")
        
        assert "Unexpected error" in str(exc_info.value)


class TestScoringClientScore:
    """Test the score method."""
    
    @patch.object(ScoringClient, '_make_request')
    @patch.object(ScoringClient, '_handle_response')
    def test_score_with_dict(self, mock_handle, mock_request, client):
        """Test scoring with dictionary features."""
        features = {"age": 25, "income": 50000.0}
        mock_response_data = {
            "score": 0.75,
            "confidence": 0.95,
            "model_id": "test-model",
            "timestamp": datetime.utcnow().isoformat(),
            "features": features
        }
        mock_handle.return_value = mock_response_data
        
        result = client.score(features)
        
        assert isinstance(result, ScoringResponse)
        assert result.score == 0.75
        assert result.confidence == 0.95
        mock_request.assert_called_once()
    
    @patch.object(ScoringClient, '_make_request')
    @patch.object(ScoringClient, '_handle_response')
    def test_score_with_request_object(self, mock_handle, mock_request, client):
        """Test scoring with ScoringRequest object."""
        features = {"age": 25, "income": 50000.0}
        request_obj = ScoringRequest(features=features)
        mock_response_data = {
            "score": 0.75,
            "confidence": 0.95,
            "model_id": "test-model",
            "timestamp": datetime.utcnow().isoformat(),
            "features": features
        }
        mock_handle.return_value = mock_response_data
        
        result = client.score(request_obj)
        
        assert isinstance(result, ScoringResponse)
        assert result.score == 0.75
        mock_request.assert_called_once()
    
    @patch.object(ScoringClient, '_make_request')
    @patch.object(ScoringClient, '_handle_response')
    def test_score_request_parameters(self, mock_handle, mock_request, client):
        """Test that score method makes correct request."""
        features = {"age": 25, "income": 50000.0}
        mock_response_data = {
            "score": 0.75,
            "confidence": 0.95,
            "model_id": "test-model",
            "timestamp": datetime.utcnow().isoformat(),
            "features": features
        }
        mock_request.return_value = Mock()
        mock_handle.return_value = mock_response_data
        
        client.score(features)
        
        mock_request.assert_called_once_with(
            "POST",
            "/v1/score",
            json={"features": features}
        )


class TestScoringClientBatchScore:
    """Test the batch_score method."""
    
    @patch.object(ScoringClient, '_make_request')
    @patch.object(ScoringClient, '_handle_response')
    def test_batch_score_with_dicts(self, mock_handle, mock_request, client):
        """Test batch scoring with dictionary features."""
        features_list = [
            {"age": 25, "income": 50000.0},
            {"age": 35, "income": 75000.0}
        ]
        mock_response_data = {
            "responses": [
                {
                    "score": 0.75,
                    "confidence": 0.95,
                    "model_id": "test-model",
                    "timestamp": datetime.utcnow().isoformat(),
                    "features": features_list[0]
                },
                {
                    "score": 0.85,
                    "confidence": 0.90,
                    "model_id": "test-model",
                    "timestamp": datetime.utcnow().isoformat(),
                    "features": features_list[1]
                }
            ],
            "total_processed": 2,
            "total_successful": 2,
            "total_failed": 0,
            "timestamp": datetime.utcnow().isoformat()
        }
        mock_handle.return_value = mock_response_data
        
        result = client.batch_score(features_list)
        
        assert isinstance(result, BatchScoringResponse)
        assert result.total_processed == 2
        assert result.total_successful == 2
        assert len(result.responses) == 2
    
    @patch.object(ScoringClient, '_make_request')
    @patch.object(ScoringClient, '_handle_response')
    def test_batch_score_with_request_objects(self, mock_handle, mock_request, client):
        """Test batch scoring with ScoringRequest objects."""
        requests = [
            ScoringRequest(features={"age": 25, "income": 50000.0}),
            ScoringRequest(features={"age": 35, "income": 75000.0})
        ]
        mock_response_data = {
            "responses": [],
            "total_processed": 2,
            "total_successful": 2,
            "total_failed": 0,
            "timestamp": datetime.utcnow().isoformat()
        }
        mock_handle.return_value = mock_response_data
        
        result = client.batch_score(requests)
        
        assert isinstance(result, BatchScoringResponse)
        assert result.total_processed == 2
    
    @patch.object(ScoringClient, '_make_request')
    @patch.object(ScoringClient, '_handle_response')
    def test_batch_score_request_parameters(self, mock_handle, mock_request, client):
        """Test that batch_score method makes correct request."""
        features_list = [{"age": 25, "income": 50000.0}]
        mock_response_data = {
            "responses": [],
            "total_processed": 1,
            "total_successful": 1,
            "total_failed": 0,
            "timestamp": datetime.utcnow().isoformat()
        }
        mock_request.return_value = Mock()
        mock_handle.return_value = mock_response_data
        
        client.batch_score(features_list)
        
        # Check that the request was made with proper batch format
        call_args = mock_request.call_args
        assert call_args[0][0] == "POST"  # method
        assert call_args[0][1] == "/v1/batch-score"  # endpoint
        assert "requests" in call_args[1]["json"]


class TestScoringClientHealth:
    """Test the health method."""
    
    @patch.object(ScoringClient, '_make_request')
    @patch.object(ScoringClient, '_handle_response')
    def test_health_check(self, mock_handle, mock_request, client):
        """Test health check."""
        mock_response_data = {
            "status": "healthy",
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": 3600
        }
        mock_handle.return_value = mock_response_data
        
        result = client.health()
        
        assert isinstance(result, HealthResponse)
        assert result.status == "healthy"
        assert result.version == "1.0.0"
        assert result.uptime_seconds == 3600
        mock_request.assert_called_once_with("GET", "/v1/health")


class TestScoringClientModelInfo:
    """Test the get_model_info method."""
    
    @patch.object(ScoringClient, '_make_request')
    @patch.object(ScoringClient, '_handle_response')
    def test_get_model_info_all(self, mock_handle, mock_request, client):
        """Test getting info for all models."""
        mock_response_data = {
            "models": [
                {"id": "model1", "name": "Model 1", "version": "1.0"},
                {"id": "model2", "name": "Model 2", "version": "2.0"}
            ]
        }
        mock_handle.return_value = mock_response_data
        
        result = client.get_model_info()
        
        assert isinstance(result, dict)
        assert "models" in result
        assert len(result["models"]) == 2
        mock_request.assert_called_once_with("GET", "/v1/models")
    
    @patch.object(ScoringClient, '_make_request')
    @patch.object(ScoringClient, '_handle_response')
    def test_get_model_info_specific(self, mock_handle, mock_request, client):
        """Test getting info for a specific model."""
        mock_response_data = {
            "id": "model1",
            "name": "Model 1",
            "version": "1.0",
            "status": "active"
        }
        mock_handle.return_value = mock_response_data
        
        result = client.get_model_info("model1")
        
        assert isinstance(result, dict)
        assert result["id"] == "model1"
        mock_request.assert_called_once_with("GET", "/v1/models/model1")


class TestScoringClientRetry:
    """Test retry logic."""
    
    @patch.object(ScoringClient, '_make_request')
    @patch.object(ScoringClient, '_handle_response')
    def test_retry_on_server_error(self, mock_handle, mock_request, client):
        """Test that client retries on server errors."""
        from tenacity import RetryError
        
        # Configure _make_request to raise ServerError on first two calls
        mock_request.side_effect = [
            ServerError("Server error"),
            ServerError("Server error"),
            Mock(status_code=200)
        ]
        mock_response_data = {
            "score": 0.75,
            "confidence": 0.95,
            "model_id": "test-model",
            "timestamp": datetime.utcnow().isoformat(),
            "features": {"age": 25}
        }
        mock_handle.return_value = mock_response_data
        
        # This should succeed after retries
        result = client.score({"age": 25})
        
        assert isinstance(result, ScoringResponse)
        assert mock_request.call_count == 3  # Initial call + 2 retries
    
    @patch.object(ScoringClient, '_make_request')
    @patch.object(ScoringClient, '_handle_response')
    def test_retry_exhaustion(self, mock_handle, mock_request, client):
        """Test that retry eventually gives up."""
        # Configure _make_request to always raise ServerError
        mock_request.side_effect = ServerError("Persistent server error")
        
        # This should eventually raise RetryError after max retries
        from tenacity import RetryError
        with pytest.raises(RetryError):
            client.score({"age": 25})
        
        assert mock_request.call_count == 3  # Initial call + 2 retries


class TestScoringClientRepresentation:
    """Test client string representation."""
    
    def test_repr(self, client):
        """Test string representation of client."""
        repr_str = repr(client)
        assert "ScoringClient" in repr_str
        assert client.base_url in repr_str
        assert str(client.timeout) in repr_str
