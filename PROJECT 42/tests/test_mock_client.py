"""
Tests for the ML Scoring SDK mock client.
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, patch

from ml_scoring_sdk.mock_client import MockScoringClient
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
    TimeoutError
)


@pytest.fixture
def mock_client():
    """Create a test mock client instance."""
    return MockScoringClient(
        base_url="http://mock-api.example.com",
        api_key="mock-api-key",
        timeout=10,
        default_score=0.75,
        default_latency=0.0
    )


class TestMockScoringClientInit:
    """Test MockScoringClient initialization."""
    
    def test_mock_client_init_default(self):
        """Test mock client initialization with default parameters."""
        client = MockScoringClient()
        
        assert client.base_url == "http://mock-api.example.com"
        assert client.api_key == "mock-api-key"
        assert client.timeout == 10
        assert client.default_score == 0.5
        assert client.default_latency == 0.1
    
    def test_mock_client_init_custom(self):
        """Test mock client initialization with custom parameters."""
        client = MockScoringClient(
            base_url="http://custom.example.com",
            api_key="custom-key",
            timeout=15,
            default_score=0.8,
            default_latency=0.5
        )
        
        assert client.base_url == "http://custom.example.com"
        assert client.api_key == "custom-key"
        assert client.timeout == 15
        assert client.default_score == 0.8
        assert client.default_latency == 0.5
    
    def test_mock_client_base_url_trimming(self):
        """Test that trailing slash is removed from base URL."""
        client = MockScoringClient(base_url="http://api.example.com/")
        
        assert client.base_url == "http://api.example.com"


class TestMockScoringClientContextManager:
    """Test MockScoringClient context manager support."""
    
    def test_sync_context_manager(self, mock_client):
        """Test using mock client as sync context manager."""
        with mock_client as client:
            assert isinstance(client, MockScoringClient)
            assert client.base_url == mock_client.base_url
    
    @pytest.mark.asyncio
    async def test_async_context_manager(self, mock_client):
        """Test using mock client as async context manager."""
        async with mock_client as client:
            assert isinstance(client, MockScoringClient)
            assert client.base_url == mock_client.base_url
    
    def test_manual_close(self, mock_client):
        """Test manual client closing."""
        mock_client.close()
        # Should not raise any exceptions
    
    @pytest.mark.asyncio
    async def test_manual_async_close(self, mock_client):
        """Test manual async client closing."""
        await mock_client.aclose()
        # Should not raise any exceptions


class TestMockScoringClientConfiguration:
    """Test mock client configuration methods."""
    
    def test_configure_score_response(self, mock_client):
        """Test configuring score responses."""
        features = {"age": 25, "income": 50000.0}
        response = ScoringResponse(
            score=0.85,
            confidence=0.90,
            model_id="test-model",
            timestamp=datetime.utcnow(),
            features=features
        )
        
        mock_client.configure_score_response("test_key", response, latency=0.2)
        
        assert "test_key" in mock_client._score_responses
        assert mock_client._score_responses["test_key"] == response
        assert "score_latency_test_key" in mock_client._error_config
        assert mock_client._error_config["score_latency_test_key"]["latency"] == 0.2
    
    def test_configure_batch_response(self, mock_client):
        """Test configuring batch responses."""
        responses = [
            ScoringResponse(
                score=0.75,
                confidence=0.95,
                model_id="test-model",
                timestamp=datetime.utcnow(),
                features={"age": 25}
            )
        ]
        batch_response = BatchScoringResponse(
            responses=responses,
            total_processed=1,
            total_successful=1,
            total_failed=0,
            timestamp=datetime.utcnow()
        )
        
        mock_client.configure_batch_response("batch_key", batch_response, latency=0.3)
        
        assert "batch_key" in mock_client._batch_responses
        assert mock_client._batch_responses["batch_key"] == batch_response
        assert "batch_latency_batch_key" in mock_client._error_config
        assert mock_client._error_config["batch_latency_batch_key"]["latency"] == 0.3
    
    def test_configure_health_response(self, mock_client):
        """Test configuring health response."""
        health_response = HealthResponse(
            status="healthy",
            version="1.0.0",
            timestamp=datetime.utcnow(),
            uptime_seconds=3600
        )
        
        mock_client.configure_health_response(health_response, latency=0.1)
        
        assert mock_client._health_response == health_response
        assert "health_latency" in mock_client._error_config
        assert mock_client._error_config["health_latency"]["latency"] == 0.1
    
    def test_configure_model_info(self, mock_client):
        """Test configuring model info."""
        model_info = {
            "id": "test-model",
            "name": "Test Model",
            "version": "1.0.0",
            "status": "active"
        }
        
        mock_client.configure_model_info("test-model", model_info, latency=0.15)
        
        assert "test-model" in mock_client._model_info
        assert mock_client._model_info["test-model"] == model_info
        assert "model_info_latency_test-model" in mock_client._error_config
        assert mock_client._error_config["model_info_latency_test-model"]["latency"] == 0.15
    
    def test_configure_error(self, mock_client):
        """Test configuring error simulation."""
        error = RateLimitError("Rate limit exceeded")
        
        mock_client.configure_error("score", error, probability=0.5, latency=0.2)
        
        assert "score" in mock_client._error_config
        assert mock_client._error_config["score"]["error"] == error
        assert mock_client._error_config["score"]["probability"] == 0.5
        assert mock_client._error_config["score"]["latency"] == 0.2
        assert "random" in mock_client._error_config["score"]
    
    def test_set_custom_handlers(self, mock_client):
        """Test setting custom handlers."""
        def custom_score_handler(request):
            return ScoringResponse(
                score=0.99,
                confidence=0.99,
                model_id="custom",
                timestamp=datetime.utcnow(),
                features=request.features
            )
        
        def custom_batch_handler(requests):
            return BatchScoringResponse(
                responses=[],
                total_processed=len(requests),
                total_successful=len(requests),
                total_failed=0,
                timestamp=datetime.utcnow()
            )
        
        def custom_health_handler():
            return HealthResponse(
                status="custom",
                version="2.0.0",
                timestamp=datetime.utcnow(),
                uptime_seconds=7200
            )
        
        mock_client.set_score_handler(custom_score_handler)
        mock_client.set_batch_handler(custom_batch_handler)
        mock_client.set_health_handler(custom_health_handler)
        
        assert mock_client._score_handler == custom_score_handler
        assert mock_client._batch_handler == custom_batch_handler
        assert mock_client._health_handler == custom_health_handler


class TestMockScoringClientScore:
    """Test the mock score methods."""
    
    def test_score_with_dict_sync(self, mock_client):
        """Test sync scoring with dictionary features."""
        features = {"age": 25, "income": 50000.0}
        
        result = mock_client.score(features)
        
        assert isinstance(result, ScoringResponse)
        assert result.score == mock_client.default_score
        assert result.confidence == 0.95
        assert result.features == features
        assert len(mock_client._request_log) == 1
        assert mock_client._request_log[0]["method"] == "score"
    
    @pytest.mark.asyncio
    async def test_score_with_dict_async(self, mock_client):
        """Test async scoring with dictionary features."""
        features = {"age": 25, "income": 50000.0}
        
        result = await mock_client.async_score(features)
        
        assert isinstance(result, ScoringResponse)
        assert result.score == mock_client.default_score
        assert result.confidence == 0.95
        assert result.features == features
    
    def test_score_with_request_object(self, mock_client):
        """Test scoring with ScoringRequest object."""
        features = {"age": 25, "income": 50000.0}
        request_obj = ScoringRequest(features=features)
        
        result = mock_client.score(request_obj)
        
        assert isinstance(result, ScoringResponse)
        assert result.score == mock_client.default_score
        assert result.features == features
    
    def test_score_with_configured_response(self, mock_client):
        """Test scoring with pre-configured response."""
        features = {"age": 25, "income": 50000.0}
        configured_response = ScoringResponse(
            score=0.95,
            confidence=0.99,
            model_id="configured-model",
            timestamp=datetime.utcnow(),
            features=features
        )
        
        # Configure response for these specific features
        key = mock_client._get_request_key(features)
        mock_client.configure_score_response(key, configured_response)
        
        result = mock_client.score(features)
        
        assert result.score == 0.95
        assert result.confidence == 0.99
        assert result.model_id == "configured-model"
    
    def test_score_with_custom_handler(self, mock_client):
        """Test scoring with custom handler."""
        features = {"age": 25, "income": 50000.0}
        
        def custom_handler(request):
            return ScoringResponse(
                score=0.88,
                confidence=0.92,
                model_id="custom-model",
                timestamp=datetime.utcnow(),
                features=request.features
            )
        
        mock_client.set_score_handler(custom_handler)
        
        result = mock_client.score(features)
        
        assert result.score == 0.88
        assert result.confidence == 0.92
        assert result.model_id == "custom-model"
    
    def test_score_with_error_simulation(self, mock_client):
        """Test scoring with error simulation."""
        features = {"age": 25, "income": 50000.0}
        error = ValidationError("Invalid features")
        
        mock_client.configure_error("score", error, probability=1.0)
        
        with pytest.raises(ValidationError) as exc_info:
            mock_client.score(features)
        
        assert str(exc_info.value) == "Invalid features"
    
    @pytest.mark.asyncio
    async def test_score_with_async_custom_handler(self, mock_client):
        """Test scoring with async custom handler."""
        features = {"age": 25, "income": 50000.0}
        
        async def async_custom_handler(request):
            await asyncio.sleep(0.01)  # Simulate async work
            return ScoringResponse(
                score=0.91,
                confidence=0.93,
                model_id="async-custom-model",
                timestamp=datetime.utcnow(),
                features=request.features
            )
        
        mock_client.set_score_handler(async_custom_handler)
        
        result = await mock_client.async_score(features)
        
        assert result.score == 0.91
        assert result.confidence == 0.93
        assert result.model_id == "async-custom-model"


class TestMockScoringClientBatchScore:
    """Test the mock batch score methods."""
    
    def test_batch_score_sync(self, mock_client):
        """Test sync batch scoring."""
        features_list = [
            {"age": 25, "income": 50000.0},
            {"age": 35, "income": 75000.0}
        ]
        
        result = mock_client.batch_score(features_list)
        
        assert isinstance(result, BatchScoringResponse)
        assert result.total_processed == 2
        assert result.total_successful == 2
        assert result.total_failed == 0
        assert len(result.responses) == 2
    
    @pytest.mark.asyncio
    async def test_batch_score_async(self, mock_client):
        """Test async batch scoring."""
        features_list = [
            {"age": 25, "income": 50000.0},
            {"age": 35, "income": 75000.0}
        ]
        
        result = await mock_client.async_batch_score(features_list)
        
        assert isinstance(result, BatchScoringResponse)
        assert result.total_processed == 2
        assert result.total_successful == 2
        assert result.total_failed == 0
        assert len(result.responses) == 2
    
    def test_batch_score_with_configured_response(self, mock_client):
        """Test batch scoring with pre-configured response."""
        features_list = [{"age": 25, "income": 50000.0}]
        configured_response = BatchScoringResponse(
            responses=[],
            total_processed=1,
            total_successful=1,
            total_failed=0,
            timestamp=datetime.utcnow()
        )
        
        mock_client.configure_batch_response("batch_1", configured_response)
        
        result = mock_client.batch_score(features_list)
        
        assert result.total_processed == 1
        assert result.total_successful == 1
    
    def test_batch_score_with_custom_handler(self, mock_client):
        """Test batch scoring with custom handler."""
        features_list = [{"age": 25, "income": 50000.0}]
        
        def custom_handler(requests):
            return BatchScoringResponse(
                responses=[],
                total_processed=len(requests),
                total_successful=len(requests),
                total_failed=0,
                timestamp=datetime.utcnow(),
                errors=[]
            )
        
        mock_client.set_batch_handler(custom_handler)
        
        result = mock_client.batch_score(features_list)
        
        assert result.total_processed == 1
        assert result.total_successful == 1
    
    def test_batch_score_with_error_simulation(self, mock_client):
        """Test batch scoring with error simulation."""
        features_list = [{"age": 25, "income": 50000.0}]
        error = ServerError("Server overloaded")
        
        mock_client.configure_error("batch_score", error, probability=1.0)
        
        with pytest.raises(ServerError) as exc_info:
            mock_client.batch_score(features_list)
        
        assert str(exc_info.value) == "Server overloaded"


class TestMockScoringClientHealth:
    """Test the mock health methods."""
    
    def test_health_sync(self, mock_client):
        """Test sync health check."""
        result = mock_client.health()
        
        assert isinstance(result, HealthResponse)
        assert result.status == "healthy"
        assert result.version == "1.0.0"
        assert result.uptime_seconds == 3600
        assert len(mock_client._request_log) == 1
        assert mock_client._request_log[0]["method"] == "health"
    
    @pytest.mark.asyncio
    async def test_health_async(self, mock_client):
        """Test async health check."""
        result = await mock_client.async_health()
        
        assert isinstance(result, HealthResponse)
        assert result.status == "healthy"
        assert result.version == "1.0.0"
        assert result.uptime_seconds == 3600
    
    def test_health_with_configured_response(self, mock_client):
        """Test health check with configured response."""
        configured_response = HealthResponse(
            status="degraded",
            version="2.0.0",
            timestamp=datetime.utcnow(),
            uptime_seconds=7200,
            details=["High latency", "Memory usage high"]
        )
        
        mock_client.configure_health_response(configured_response)
        
        result = mock_client.health()
        
        assert result.status == "degraded"
        assert result.version == "2.0.0"
        assert result.uptime_seconds == 7200
        assert len(result.details) == 2
    
    def test_health_with_custom_handler(self, mock_client):
        """Test health check with custom handler."""
        def custom_handler():
            return HealthResponse(
                status="custom",
                version="3.0.0",
                timestamp=datetime.utcnow(),
                uptime_seconds=10800
            )
        
        mock_client.set_health_handler(custom_handler)
        
        result = mock_client.health()
        
        assert result.status == "custom"
        assert result.version == "3.0.0"
        assert result.uptime_seconds == 10800
    
    def test_health_with_error_simulation(self, mock_client):
        """Test health check with error simulation."""
        error = NetworkError("Service unavailable")
        
        mock_client.configure_error("health", error, probability=1.0)
        
        with pytest.raises(NetworkError) as exc_info:
            mock_client.health()
        
        assert str(exc_info.value) == "Service unavailable"


class TestMockScoringClientModelInfo:
    """Test the mock model info methods."""
    
    def test_get_model_info_all_sync(self, mock_client):
        """Test sync getting info for all models."""
        result = mock_client.get_model_info()
        
        assert isinstance(result, dict)
        assert "models" in result
        assert len(result["models"]) == 1
        assert result["models"][0]["id"] == "mock-model"
    
    @pytest.mark.asyncio
    async def test_get_model_info_all_async(self, mock_client):
        """Test async getting info for all models."""
        result = await mock_client.async_get_model_info()
        
        assert isinstance(result, dict)
        assert "models" in result
        assert len(result["models"]) == 1
        assert result["models"][0]["id"] == "mock-model"
    
    def test_get_model_info_specific_sync(self, mock_client):
        """Test sync getting info for specific model."""
        model_info = {
            "id": "test-model",
            "name": "Test Model",
            "version": "1.0.0",
            "status": "active"
        }
        mock_client.configure_model_info("test-model", model_info)
        
        result = mock_client.get_model_info("test-model")
        
        assert isinstance(result, dict)
        assert result["id"] == "test-model"
        assert result["name"] == "Test Model"
    
    @pytest.mark.asyncio
    async def test_get_model_info_specific_async(self, mock_client):
        """Test async getting info for specific model."""
        model_info = {
            "id": "test-model",
            "name": "Test Model",
            "version": "1.0.0",
            "status": "active"
        }
        mock_client.configure_model_info("test-model", model_info)
        
        result = await mock_client.async_get_model_info("test-model")
        
        assert isinstance(result, dict)
        assert result["id"] == "test-model"
        assert result["name"] == "Test Model"
    
    def test_get_model_info_not_found(self, mock_client):
        """Test getting info for non-existent model."""
        with pytest.raises(ModelNotFoundError) as exc_info:
            mock_client.get_model_info("non-existent-model")
        
        assert "non-existent-model" in str(exc_info.value)
    
    def test_get_model_info_with_error_simulation(self, mock_client):
        """Test model info with error simulation."""
        error = AuthenticationError("Access denied")
        
        mock_client.configure_error("get_model_info", error, probability=1.0)
        
        with pytest.raises(AuthenticationError) as exc_info:
            mock_client.get_model_info()
        
        assert str(exc_info.value) == "Access denied"


class TestMockScoringClientUtilities:
    """Test mock client utility methods."""
    
    def test_get_request_key(self, mock_client):
        """Test request key generation."""
        features1 = {"age": 25, "income": 50000.0}
        features2 = {"income": 50000.0, "age": 25}  # Same but different order
        
        key1 = mock_client._get_request_key(features1)
        key2 = mock_client._get_request_key(features2)
        
        # Keys should be the same regardless of order
        assert key1 == key2
    
    def test_get_request_log(self, mock_client):
        """Test getting request log."""
        # Make some requests
        mock_client.score({"age": 25})
        mock_client.health()
        mock_client.get_model_info()
        
        log = mock_client.get_request_log()
        
        assert len(log) == 3
        assert log[0]["method"] == "score"
        assert log[1]["method"] == "health"
        assert log[2]["method"] == "get_model_info"
        
        # Check timestamp format
        for entry in log:
            assert "timestamp" in entry
            assert "data" in entry
    
    def test_clear_request_log(self, mock_client):
        """Test clearing request log."""
        # Make a request
        mock_client.score({"age": 25})
        assert len(mock_client._request_log) == 1
        
        # Clear log
        mock_client.clear_request_log()
        assert len(mock_client._request_log) == 0
    
    def test_reset(self, mock_client):
        """Test resetting mock client to defaults."""
        # Configure some responses and errors
        features = {"age": 25}
        response = ScoringResponse(
            score=0.95,
            confidence=0.99,
            model_id="test",
            timestamp=datetime.utcnow(),
            features=features
        )
        mock_client.configure_score_response("test", response)
        mock_client.configure_error("score", ValidationError("Test error"))
        
        # Verify configuration
        assert len(mock_client._score_responses) == 1
        assert len(mock_client._error_config) == 1
        
        # Reset
        mock_client.reset()
        
        # Verify reset
        assert len(mock_client._score_responses) == 0
        assert len(mock_client._batch_responses) == 0
        assert mock_client._health_response is None
        assert len(mock_client._model_info) == 0
        assert len(mock_client._error_config) == 0
        assert len(mock_client._request_log) == 0
        assert mock_client._score_handler is None
        assert mock_client._batch_handler is None
        assert mock_client._health_handler is None
    
    @pytest.mark.asyncio
    async def test_simulate_latency(self, mock_client):
        """Test latency simulation."""
        with patch('ml_scoring_sdk.mock_client.asyncio.sleep') as mock_sleep:
            await mock_client._simulate_latency("test_latency")
            mock_sleep.assert_called_once_with(mock_client.default_latency)
    
    def test_repr(self, mock_client):
        """Test string representation of mock client."""
        repr_str = repr(mock_client)
        assert "MockScoringClient" in repr_str
        assert mock_client.base_url in repr_str
        assert str(mock_client.default_score) in repr_str


class TestMockScoringClientErrorProbability:
    """Test error probability simulation."""
    
    def test_error_probability_zero(self, mock_client):
        """Test error simulation with zero probability."""
        features = {"age": 25, "income": 50000.0}
        error = ValidationError("Should not happen")
        
        mock_client.configure_error("score", error, probability=0.0)
        
        # Should not raise error
        result = mock_client.score(features)
        assert isinstance(result, ScoringResponse)
    
    def test_error_probability_partial(self, mock_client):
        """Test error simulation with partial probability."""
        features = {"age": 25, "income": 50000.0}
        error = ValidationError("Sometimes happens")
        
        # Set probability to 1.0 for deterministic testing
        mock_client.configure_error("score", error, probability=1.0)
        
        # Should always raise error
        with pytest.raises(ValidationError):
            mock_client.score(features)
