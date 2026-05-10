"""
Tests for the ML Scoring SDK asynchronous client.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
import httpx

from ml_scoring_sdk.async_client import AsyncScoringClient
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
async def async_client():
    """Create a test async client instance."""
    return AsyncScoringClient(
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


class TestAsyncScoringClientInit:
    """Test AsyncScoringClient initialization."""
    
    def test_async_client_init_default(self):
        """Test async client initialization with default parameters."""
        client = AsyncScoringClient("https://api.example.com", "test-key")
        
        assert client.base_url == "https://api.example.com"
        assert client.api_key == "test-key"
        assert client.timeout == 10
        assert client.max_retries == 3
    
    def test_async_client_init_custom_params(self):
        """Test async client initialization with custom parameters."""
        client = AsyncScoringClient(
            base_url="https://api.example.com/",
            api_key="test-key",
            timeout=15,
            max_retries=5
        )
        
        assert client.base_url == "https://api.example.com"
        assert client.timeout == 15
        assert client.max_retries == 5
    
    def test_async_client_http_setup(self):
        """Test that async HTTP client is properly configured."""
        client = AsyncScoringClient("https://api.example.com", "test-key")
        
        assert client.client.base_url == "https://api.example.com"
        assert "X-API-Key" in client.client.headers
        assert client.client.headers["X-API-Key"] == "test-key"
        assert "User-Agent" in client.client.headers


class TestAsyncScoringClientContextManager:
    """Test AsyncScoringClient context manager support."""
    
    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        """Test using async client as context manager."""
        async with AsyncScoringClient("https://api.example.com", "test-key") as client:
            assert isinstance(client, AsyncScoringClient)
            assert client.base_url == "https://api.example.com"
    
    @patch('ml_scoring_sdk.async_client.httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_async_context_manager_close(self, mock_client_class):
        """Test that async context manager closes the client."""
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        
        async with AsyncScoringClient("https://api.example.com", "test-key") as client:
            pass
        
        mock_client.aclose.assert_called_once()
    
    @patch('ml_scoring_sdk.async_client.httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_manual_close(self, mock_client_class):
        """Test manual async client closing."""
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        
        client = AsyncScoringClient("https://api.example.com", "test-key")
        await client.close()
        
        mock_client.aclose.assert_called_once()


class TestAsyncScoringClientResponseHandling:
    """Test async response handling methods."""
    
    def test_handle_response_success(self, async_client, mock_response):
        """Test handling successful response."""
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}
        
        result = async_client._handle_response(mock_response)
        
        assert result == {"status": "ok"}
    
    def test_handle_response_error_400(self, async_client, mock_response):
        """Test handling 400 error response."""
        mock_response.status_code = 400
        mock_response.json.return_value = {"message": "Bad request"}
        
        with pytest.raises(ValidationError) as exc_info:
            async_client._handle_response(mock_response)
        
        assert str(exc_info.value) == "Bad request"
        assert exc_info.value.status_code == 400
    
    def test_handle_response_error_401(self, async_client, mock_response):
        """Test handling 401 error response."""
        mock_response.status_code = 401
        mock_response.json.return_value = {"message": "Unauthorized"}
        
        with pytest.raises(AuthenticationError) as exc_info:
            async_client._handle_response(mock_response)
        
        assert str(exc_info.value) == "Unauthorized"
        assert exc_info.value.status_code == 401
    
    def test_handle_response_error_404(self, async_client, mock_response):
        """Test handling 404 error response."""
        mock_response.status_code = 404
        mock_response.json.return_value = {"message": "Not found"}
        
        with pytest.raises(ModelNotFoundError) as exc_info:
            async_client._handle_response(mock_response)
        
        assert str(exc_info.value) == "Not found"
        assert exc_info.value.status_code == 404
    
    def test_handle_response_error_429(self, async_client, mock_response):
        """Test handling 429 error response."""
        mock_response.status_code = 429
        mock_response.json.return_value = {"message": "Rate limit exceeded"}
        
        with pytest.raises(RateLimitError) as exc_info:
            async_client._handle_response(mock_response)
        
        assert str(exc_info.value) == "Rate limit exceeded"
        assert exc_info.value.status_code == 429
    
    def test_handle_response_error_500(self, async_client, mock_response):
        """Test handling 500 error response."""
        mock_response.status_code = 500
        mock_response.json.return_value = {"message": "Internal server error"}
        
        with pytest.raises(ServerError) as exc_info:
            async_client._handle_response(mock_response)
        
        assert str(exc_info.value) == "Internal server error"
        assert exc_info.value.status_code == 500
    
    def test_handle_response_invalid_json(self, async_client, mock_response):
        """Test handling response with invalid JSON."""
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.content = b"Invalid JSON"
        
        result = async_client._handle_response(mock_response)
        
        assert result == {}


class TestAsyncScoringClientRequestMaking:
    """Test async HTTP request making."""
    
    @patch('ml_scoring_sdk.async_client.httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_make_request_success(self, mock_client_class, async_client):
        """Test successful async request making."""
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "success"}
        mock_client.request.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        async_client.client = mock_client
        result = await async_client._make_request("GET", "/test")
        
        mock_client.request.assert_called_once_with("GET", "/test")
        assert result == mock_response
    
    @patch('ml_scoring_sdk.async_client.httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_make_request_timeout(self, mock_client_class, async_client):
        """Test async request timeout handling."""
        mock_client = AsyncMock()
        mock_client.request.side_effect = httpx.TimeoutException("Timeout")
        mock_client_class.return_value = mock_client
        
        async_client.client = mock_client
        
        with pytest.raises(TimeoutError) as exc_info:
            await async_client._make_request("GET", "/test")
        
        assert "Request timeout" in str(exc_info.value)
    
    @patch('ml_scoring_sdk.async_client.httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_make_request_network_error(self, mock_client_class, async_client):
        """Test async network error handling."""
        mock_client = AsyncMock()
        mock_client.request.side_effect = httpx.NetworkError("Connection failed")
        mock_client_class.return_value = mock_client
        
        async_client.client = mock_client
        
        with pytest.raises(NetworkError) as exc_info:
            await async_client._make_request("GET", "/test")
        
        assert "Network error" in str(exc_info.value)
    
    @patch('ml_scoring_sdk.async_client.httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_make_request_unexpected_error(self, mock_client_class, async_client):
        """Test async unexpected error handling."""
        mock_client = AsyncMock()
        mock_client.request.side_effect = Exception("Unexpected error")
        mock_client_class.return_value = mock_client
        
        async_client.client = mock_client
        
        with pytest.raises(ScoringAPIError) as exc_info:
            await async_client._make_request("GET", "/test")
        
        assert "Unexpected error" in str(exc_info.value)


class TestAsyncScoringClientScore:
    """Test the async score method."""
    
    @patch.object(AsyncScoringClient, '_make_request')
    @patch.object(AsyncScoringClient, '_handle_response')
    @pytest.mark.asyncio
    async def test_async_score_with_dict(self, mock_handle, mock_request, async_client):
        """Test async scoring with dictionary features."""
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
        
        result = await async_client.score(features)
        
        assert isinstance(result, ScoringResponse)
        assert result.score == 0.75
        assert result.confidence == 0.95
        mock_request.assert_called_once()
    
    @patch.object(AsyncScoringClient, '_make_request')
    @patch.object(AsyncScoringClient, '_handle_response')
    @pytest.mark.asyncio
    async def test_async_score_with_request_object(self, mock_handle, mock_request, async_client):
        """Test async scoring with ScoringRequest object."""
        features = {"age": 25, "income": 50000.0}
        request_obj = ScoringRequest(features=features)
        mock_response_data = {
            "score": 0.75,
            "confidence": 0.95,
            "model_id": "test-model",
            "timestamp": datetime.utcnow().isoformat(),
            "features": features
        }
        mock_request.return_value = Mock()
        mock_handle.return_value = mock_response_data
        
        result = await async_client.score(request_obj)
        
        assert isinstance(result, ScoringResponse)
        assert result.score == 0.75
        mock_request.assert_called_once()
    
    @patch.object(AsyncScoringClient, '_make_request')
    @patch.object(AsyncScoringClient, '_handle_response')
    @pytest.mark.asyncio
    async def test_async_score_request_parameters(self, mock_handle, mock_request, async_client):
        """Test that async score method makes correct request."""
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
        
        await async_client.score(features)
        
        mock_request.assert_called_once_with(
            "POST",
            "/v1/score",
            json={"features": features}
        )


class TestAsyncScoringClientBatchScore:
    """Test the async batch_score method."""
    
    @patch.object(AsyncScoringClient, '_make_request')
    @patch.object(AsyncScoringClient, '_handle_response')
    @pytest.mark.asyncio
    async def test_async_batch_score_with_dicts(self, mock_handle, mock_request, async_client):
        """Test async batch scoring with dictionary features."""
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
        mock_request.return_value = Mock()
        mock_handle.return_value = mock_response_data
        
        result = await async_client.batch_score(features_list)
        
        assert isinstance(result, BatchScoringResponse)
        assert result.total_processed == 2
        assert result.total_successful == 2
        assert len(result.responses) == 2
    
    @patch.object(AsyncScoringClient, '_make_request')
    @patch.object(AsyncScoringClient, '_handle_response')
    @pytest.mark.asyncio
    async def test_async_batch_score_with_request_objects(self, mock_handle, mock_request, async_client):
        """Test async batch scoring with ScoringRequest objects."""
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
        mock_request.return_value = Mock()
        mock_handle.return_value = mock_response_data
        
        result = await async_client.batch_score(requests)
        
        assert isinstance(result, BatchScoringResponse)
        assert result.total_processed == 2


class TestAsyncScoringClientConcurrentBatchScore:
    """Test the async concurrent_batch_score method."""
    
    @patch.object(AsyncScoringClient, 'score')
    @pytest.mark.asyncio
    async def test_concurrent_batch_score(self, mock_score, async_client):
        """Test concurrent batch scoring."""
        features_list = [
            {"age": 25, "income": 50000.0},
            {"age": 35, "income": 75000.0},
            {"age": 45, "income": 100000.0}
        ]
        
        # Configure mock score to return different responses
        mock_responses = []
        for i, features in enumerate(features_list):
            response = ScoringResponse(
                score=0.7 + i * 0.1,
                confidence=0.95,
                model_id="test-model",
                timestamp=datetime.utcnow(),
                features=features
            )
            mock_responses.append(response)
        
        mock_score.side_effect = mock_responses
        
        result = await async_client.concurrent_batch_score(features_list, max_concurrency=2)
        
        assert len(result) == 3
        assert all(isinstance(r, ScoringResponse) for r in result)
        assert result[0].score == 0.7
        assert result[1].score == 0.8
        assert result[2].score == 0.9
        
        # Verify that score was called for each feature set
        assert mock_score.call_count == 3
    
    @patch.object(AsyncScoringClient, 'score')
    @pytest.mark.asyncio
    async def test_concurrent_batch_score_with_errors(self, mock_score, async_client):
        """Test concurrent batch scoring with errors."""
        features_list = [{"age": 25, "income": 50000.0}]
        
        # Configure mock score to raise an error
        mock_score.side_effect = ValidationError("Invalid input")
        
        with pytest.raises(ValidationError):
            await async_client.concurrent_batch_score(features_list)


class TestAsyncScoringClientHealth:
    """Test the async health method."""
    
    @patch.object(AsyncScoringClient, '_make_request')
    @patch.object(AsyncScoringClient, '_handle_response')
    @pytest.mark.asyncio
    async def test_async_health_check(self, mock_handle, mock_request, async_client):
        """Test async health check."""
        mock_response_data = {
            "status": "healthy",
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": 3600
        }
        mock_request.return_value = Mock()
        mock_handle.return_value = mock_response_data
        
        result = await async_client.health()
        
        assert isinstance(result, HealthResponse)
        assert result.status == "healthy"
        assert result.version == "1.0.0"
        assert result.uptime_seconds == 3600
        mock_request.assert_called_once_with("GET", "/v1/health")


class TestAsyncScoringClientModelInfo:
    """Test the async get_model_info method."""
    
    @patch.object(AsyncScoringClient, '_make_request')
    @patch.object(AsyncScoringClient, '_handle_response')
    @pytest.mark.asyncio
    async def test_async_get_model_info_all(self, mock_handle, mock_request, async_client):
        """Test async getting info for all models."""
        mock_response_data = {
            "models": [
                {"id": "model1", "name": "Model 1", "version": "1.0"},
                {"id": "model2", "name": "Model 2", "version": "2.0"}
            ]
        }
        mock_request.return_value = Mock()
        mock_handle.return_value = mock_response_data
        
        result = await async_client.get_model_info()
        
        assert isinstance(result, dict)
        assert "models" in result
        assert len(result["models"]) == 2
        mock_request.assert_called_once_with("GET", "/v1/models")
    
    @patch.object(AsyncScoringClient, '_make_request')
    @patch.object(AsyncScoringClient, '_handle_response')
    @pytest.mark.asyncio
    async def test_async_get_model_info_specific(self, mock_handle, mock_request, async_client):
        """Test async getting info for a specific model."""
        mock_response_data = {
            "id": "model1",
            "name": "Model 1",
            "version": "1.0",
            "status": "active"
        }
        mock_request.return_value = Mock()
        mock_handle.return_value = mock_response_data
        
        result = await async_client.get_model_info("model1")
        
        assert isinstance(result, dict)
        assert result["id"] == "model1"
        mock_request.assert_called_once_with("GET", "/v1/models/model1")


class TestAsyncScoringClientRetry:
    """Test async retry logic."""
    
    @patch.object(AsyncScoringClient, '_make_request')
    @patch.object(AsyncScoringClient, '_handle_response')
    @pytest.mark.asyncio
    async def test_async_retry_on_server_error(self, mock_handle, mock_request, async_client):
        """Test that async client retries on server errors."""
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
        result = await async_client.score({"age": 25})
        
        assert isinstance(result, ScoringResponse)
        assert mock_request.call_count == 3  # Initial call + 2 retries
    
    @patch.object(AsyncScoringClient, '_make_request')
    @patch.object(AsyncScoringClient, '_handle_response')
    @pytest.mark.asyncio
    async def test_async_retry_exhaustion(self, mock_handle, mock_request, async_client):
        """Test that async retry eventually gives up."""
        # Configure _make_request to always raise ServerError
        mock_request.side_effect = ServerError("Persistent server error")
        
        # This should eventually raise RetryError after max retries
        from tenacity import RetryError
        with pytest.raises(RetryError):
            await async_client.score({"age": 25})
        
        assert mock_request.call_count == 3  # Initial call + 2 retries


class TestAsyncScoringClientLatencySimulation:
    """Test async latency simulation."""
    
    @patch('ml_scoring_sdk.async_client.asyncio.sleep')
    @patch.object(AsyncScoringClient, '_make_request')
    @patch.object(AsyncScoringClient, '_handle_response')
    @pytest.mark.asyncio
    async def test_async_latency_simulation(self, mock_handle, mock_request, mock_sleep, async_client):
        """Test that async client simulates latency."""
        mock_response_data = {
            "score": 0.75,
            "confidence": 0.95,
            "model_id": "test-model",
            "timestamp": datetime.utcnow().isoformat(),
            "features": {"age": 25}
        }
        mock_request.return_value = Mock()
        mock_handle.return_value = mock_response_data
        
        await async_client._simulate_latency()
        
        mock_sleep.assert_called_once_with(async_client.default_latency)


class TestAsyncScoringClientRepresentation:
    """Test async client string representation."""
    
    def test_async_repr(self, async_client):
        """Test string representation of async client."""
        repr_str = repr(async_client)
        assert "AsyncScoringClient" in repr_str
        assert async_client.base_url in repr_str
        assert str(async_client.timeout) in repr_str
