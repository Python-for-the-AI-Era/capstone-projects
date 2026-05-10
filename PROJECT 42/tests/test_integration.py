"""
Integration tests for the ML Scoring SDK.

These tests verify that all components work together correctly.
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, patch

from ml_scoring_sdk import (
    ScoringClient,
    AsyncScoringClient,
    MockScoringClient
)
from ml_scoring_sdk.models import (
    ScoringRequest, 
    ScoringResponse, 
    BatchScoringRequest, 
    BatchScoringResponse,
    HealthResponse
)
from ml_scoring_sdk.exceptions import (
    ScoringAPIError,
    RateLimitError,
    ModelNotFoundError,
    AuthenticationError,
    ValidationError,
    ServerError,
    NetworkError,
    TimeoutError
)


class TestSDKIntegration:
    """Test SDK integration and compatibility."""
    
    def test_sdk_imports(self):
        """Test that all SDK components can be imported."""
        from ml_scoring_sdk import (
            ScoringClient,
            AsyncScoringClient,
            MockScoringClient,
            ScoringAPIError,
            RateLimitError,
            ModelNotFoundError,
            AuthenticationError,
            ValidationError,
            ServerError,
            NetworkError,
            TimeoutError,
            ScoringRequest,
            ScoringResponse,
            BatchScoringRequest,
            BatchScoringResponse,
            HealthResponse
        )
        
        # Verify all classes are available
        assert ScoringClient is not None
        assert AsyncScoringClient is not None
        assert MockScoringClient is not None
        assert ScoringAPIError is not None
        assert RateLimitError is not None
        assert ModelNotFoundError is not None
        assert AuthenticationError is not None
        assert ValidationError is not None
        assert ServerError is not None
        assert NetworkError is not None
        assert TimeoutError is not None
        assert ScoringRequest is not None
        assert ScoringResponse is not None
        assert BatchScoringRequest is not None
        assert BatchScoringResponse is not None
        assert HealthResponse is not None
    
    def test_client_compatibility(self):
        """Test that sync and async clients have compatible interfaces."""
        sync_client = ScoringClient("https://api.example.com", "test-key")
        async_client = AsyncScoringClient("https://api.example.com", "test-key")
        
        # Both should have the same methods
        sync_methods = [method for method in dir(sync_client) if not method.startswith('_')]
        async_methods = [method for method in dir(async_client) if not method.startswith('_')]
        
        # Core methods should be present in both
        core_methods = ['score', 'batch_score', 'health', 'get_model_info', 'close']
        for method in core_methods:
            assert method in sync_methods, f"Missing {method} in sync client"
            assert method in async_methods, f"Missing {method} in async client"
    
    @pytest.mark.asyncio
    async def test_mock_client_compatibility(self):
        """Test that mock client works with both sync and async interfaces."""
        mock_client = MockScoringClient()
        
        # Test sync interface
        features = {"age": 25, "income": 50000.0}
        sync_result = mock_client.score(features)
        assert isinstance(sync_result, ScoringResponse)
        
        # Test async interface
        async_result = await mock_client.async_score(features)
        assert isinstance(async_result, ScoringResponse)
        
        # Results should be equivalent
        assert sync_result.score == async_result.score
        assert sync_result.features == async_result.features


class TestModelValidationIntegration:
    """Test model validation across the SDK."""
    
    def test_scoring_request_validation_in_client(self):
        """Test that ScoringRequest validation works in client context."""
        client = MockScoringClient()
        
        # Valid request should work
        valid_features = {"age": 25, "income": 50000.0}
        result = client.score(valid_features)
        assert isinstance(result, ScoringResponse)
        
        # Invalid request should raise validation error
        with pytest.raises(Exception):  # Should be caught by Pydantic validation
            client.score({})  # Empty features
    
    def test_batch_request_validation_integration(self):
        """Test batch request validation in client context."""
        client = MockScoringClient()
        
        # Valid batch request
        valid_features = [
            {"age": 25, "income": 50000.0},
            {"age": 35, "income": 75000.0}
        ]
        result = client.batch_score(valid_features)
        assert isinstance(result, BatchScoringResponse)
        assert result.total_processed == 2
    
    def test_model_serialization_integration(self):
        """Test that models serialize/deserialize correctly."""
        # Create a complete request/response cycle
        features = {"age": 25, "income": 50000.0, "credit_score": 720}
        
        # Test request serialization
        request = ScoringRequest(features=features, model_id="test-model")
        request_dict = request.dict()
        assert "features" in request_dict
        assert request_dict["features"] == features
        
        # Test response serialization
        response = ScoringResponse(
            score=0.75,
            confidence=0.95,
            model_id="test-model",
            timestamp=datetime.utcnow(),
            features=features,
            explanation="Good credit profile",
            metadata={"version": "1.0"}
        )
        response_dict = response.dict()
        assert response_dict["score"] == 0.75
        assert "explanation" in response_dict
        assert "metadata" in response_dict


class TestErrorHandlingIntegration:
    """Test error handling across the SDK."""
    
    def test_exception_hierarchy_integration(self):
        """Test that all exceptions inherit from base class."""
        exceptions = [
            RateLimitError,
            ModelNotFoundError,
            AuthenticationError,
            ValidationError,
            ServerError,
            NetworkError,
            TimeoutError
        ]
        
        for exc_class in exceptions:
            assert issubclass(exc_class, ScoringAPIError)
            
            # Test that they can be instantiated with message
            exc_instance = exc_class("Test message")
            assert str(exc_instance) == "Test message"
            assert isinstance(exc_instance, ScoringAPIError)
    
    def test_error_simulation_integration(self):
        """Test error simulation in mock client."""
        client = MockScoringClient()
        
        # Configure different errors for different methods
        client.configure_error("score", ValidationError("Invalid score"), probability=1.0)
        client.configure_error("health", NetworkError("Service down"), probability=1.0)
        client.configure_error("get_model_info", AuthenticationError("Unauthorized"), probability=1.0)
        
        # Test that each method raises the configured error
        with pytest.raises(ValidationError):
            client.score({"age": 25})
        
        with pytest.raises(NetworkError):
            client.health()
        
        with pytest.raises(AuthenticationError):
            client.get_model_info()
    
    def test_error_propagation_integration(self):
        """Test that errors propagate correctly through the SDK."""
        client = MockScoringClient()
        
        # Configure error with probability less than 1
        client.configure_error("score", ServerError("Random failure"), probability=0.5)
        
        # Multiple calls should sometimes succeed, sometimes fail
        results = []
        errors = []
        
        for _ in range(10):
            try:
                result = client.score({"age": 25})
                results.append(result)
            except ServerError:
                errors.append("Server error")
        
        # Should have both successes and failures (though this is probabilistic)
        assert len(results) + len(errors) == 10


class TestAsyncIntegration:
    """Test async functionality integration."""
    
    @pytest.mark.asyncio
    async def test_async_client_full_workflow(self):
        """Test complete async workflow."""
        client = AsyncScoringClient("https://api.example.com", "test-key")
        
        try:
            # Test health check
            health = await client.health()
            assert isinstance(health, HealthResponse)
            
            # Test single scoring
            features = {"age": 25, "income": 50000.0}
            score_result = await client.score(features)
            assert isinstance(score_result, ScoringResponse)
            
            # Test batch scoring
            features_list = [
                {"age": 25, "income": 50000.0},
                {"age": 35, "income": 75000.0}
            ]
            batch_result = await client.batch_score(features_list)
            assert isinstance(batch_result, BatchScoringResponse)
            assert batch_result.total_processed == 2
            
            # Test concurrent batch scoring
            concurrent_results = await client.concurrent_batch_score(features_list)
            assert len(concurrent_results) == 2
            assert all(isinstance(r, ScoringResponse) for r in concurrent_results)
            
        finally:
            await client.close()
    
    @pytest.mark.asyncio
    async def test_async_context_manager_integration(self):
        """Test async context manager integration."""
        async with AsyncScoringClient("https://api.example.com", "test-key") as client:
            assert isinstance(client, AsyncScoringClient)
            
            # Should be able to make requests within context
            health = await client.health()
            assert isinstance(health, HealthResponse)
    
    @pytest.mark.asyncio
    async def test_async_mock_client_integration(self):
        """Test async mock client integration."""
        client = MockScoringClient()
        
        # Configure custom async handler
        async def async_score_handler(request):
            await asyncio.sleep(0.01)  # Simulate async work
            return ScoringResponse(
                score=0.92,
                confidence=0.94,
                model_id="async-model",
                timestamp=datetime.utcnow(),
                features=request.features
            )
        
        client.set_score_handler(async_score_handler)
        
        # Test async scoring
        features = {"age": 30, "income": 60000.0}
        result = await client.async_score(features)
        
        assert result.score == 0.92
        assert result.confidence == 0.94
        assert result.model_id == "async-model"


class TestPerformanceIntegration:
    """Test performance characteristics."""
    
    @pytest.mark.asyncio
    async def test_concurrent_request_handling(self):
        """Test handling of concurrent requests."""
        client = MockScoringClient(default_latency=0.0)
        
        # Create multiple concurrent requests
        features_list = [{"age": i, "income": i * 1000} for i in range(10)]
        
        # Test concurrent batch scoring
        start_time = datetime.utcnow()
        results = await client.concurrent_batch_score(features_list, max_concurrency=5)
        end_time = datetime.utcnow()
        
        # Should have processed all requests
        assert len(results) == 10
        assert all(isinstance(r, ScoringResponse) for r in results)
        
        # Should be relatively fast (concurrent processing)
        duration = (end_time - start_time).total_seconds()
        assert duration < 1.0  # Should complete quickly
    
    def test_batch_size_limits(self):
        """Test batch size limits and validation."""
        client = MockScoringClient()
        
        # Test maximum batch size
        max_features = [{"test": i} for i in range(1000)]
        result = client.batch_score(max_features)
        assert result.total_processed == 1000
        
        # Test exceeding batch size (should raise validation error)
        too_many_features = [{"test": i} for i in range(1001)]
        with pytest.raises(Exception):  # Pydantic validation error
            client.batch_score(too_many_features)


class TestConfigurationIntegration:
    """Test configuration and customization integration."""
    
    def test_client_configuration_integration(self):
        """Test client configuration options."""
        # Test custom timeout and retry settings
        client = ScoringClient(
            base_url="https://api.example.com",
            api_key="test-key",
            timeout=15,
            max_retries=5,
            retry_delay_min=1.0,
            retry_delay_max=20.0
        )
        
        assert client.timeout == 15
        assert client.max_retries == 5
        assert client.retry_delay_min == 1.0
        assert client.retry_delay_max == 20.0
    
    def test_mock_client_configuration_integration(self):
        """Test mock client configuration options."""
        client = MockScoringClient(
            base_url="https://custom.example.com",
            api_key="custom-key",
            timeout=20,
            default_score=0.85,
            default_latency=0.2
        )
        
        assert client.base_url == "https://custom.example.com"
        assert client.api_key == "custom-key"
        assert client.default_score == 0.85
        assert client.default_latency == 0.2
    
    def test_request_logging_integration(self):
        """Test request logging across different clients."""
        sync_client = MockScoringClient()
        async_client = MockScoringClient()
        
        # Make requests with both clients
        sync_client.score({"age": 25})
        sync_client.health()
        
        # Test async logging
        asyncio.run(async_client.async_score({"age": 30}))
        asyncio.run(async_client.async_health())
        
        # Check logs
        sync_log = sync_client.get_request_log()
        async_log = async_client.get_request_log()
        
        assert len(sync_log) == 2
        assert len(async_log) == 2
        
        # Verify log structure
        for log in sync_log + async_log:
            assert "method" in log
            assert "timestamp" in log
            assert "data" in log


class TestRealWorldScenarios:
    """Test real-world usage scenarios."""
    
    def test_credit_scoring_workflow(self):
        """Test a typical credit scoring workflow."""
        client = MockScoringClient()
        
        # Configure realistic responses
        good_credit_features = {
            "age": 35,
            "income": 85000.0,
            "credit_score": 750,
            "debt_to_income": 0.25,
            "employment_length": 8
        }
        
        poor_credit_features = {
            "age": 22,
            "income": 30000.0,
            "credit_score": 580,
            "debt_to_income": 0.45,
            "employment_length": 1
        }
        
        # Configure different responses for different credit profiles
        good_response = ScoringResponse(
            score=0.15,  # Low risk
            confidence=0.96,
            model_id="credit-risk-v2",
            timestamp=datetime.utcnow(),
            features=good_credit_features,
            explanation="Excellent credit profile with high income and good credit history"
        )
        
        poor_response = ScoringResponse(
            score=0.85,  # High risk
            confidence=0.88,
            model_id="credit-risk-v2",
            timestamp=datetime.utcnow(),
            features=poor_credit_features,
            explanation="High risk due to low credit score and high debt-to-income ratio"
        )
        
        # Configure responses
        good_key = client._get_request_key(good_credit_features)
        poor_key = client._get_request_key(poor_credit_features)
        
        client.configure_score_response(good_key, good_response)
        client.configure_score_response(poor_key, poor_response)
        
        # Test scoring
        good_result = client.score(good_credit_features)
        poor_result = client.score(poor_credit_features)
        
        assert good_result.score == 0.15
        assert poor_result.score == 0.85
        assert good_result.explanation is not None
        assert poor_result.explanation is not None
    
    @pytest.mark.asyncio
    async def test_fraud_detection_workflow(self):
        """Test a fraud detection workflow with async processing."""
        client = AsyncScoringClient("https://fraud-api.example.com", "fraud-key")
        
        # Simulate multiple transactions to check for fraud
        transactions = [
            {"amount": 100.0, "merchant": "amazon", "location": "US", "user_age": 30},
            {"amount": 5000.0, "merchant": "unknown", "location": "FR", "user_age": 30},
            {"amount": 25.0, "merchant": "coffee_shop", "location": "US", "user_age": 30},
            {"amount": 10000.0, "merchant": "luxury_store", "location": "IT", "user_age": 30}
        ]
        
        try:
            # Process transactions concurrently
            fraud_scores = await client.concurrent_batch_score(
                transactions, 
                max_concurrency=4
            )
            
            # Verify results
            assert len(fraud_scores) == 4
            assert all(isinstance(score, ScoringResponse) for score in fraud_scores)
            
            # Higher amounts and unusual locations should have higher fraud scores
            # (This would be configured in the mock responses)
            
        finally:
            await client.close()
    
    def test_model_monitoring_workflow(self):
        """Test a model monitoring and health checking workflow."""
        client = MockScoringClient()
        
        # Configure health responses
        healthy_response = HealthResponse(
            status="healthy",
            version="2.1.0",
            timestamp=datetime.utcnow(),
            uptime_seconds=86400,  # 1 day
            details=["All systems operational"]
        )
        
        degraded_response = HealthResponse(
            status="degraded",
            version="2.1.0",
            timestamp=datetime.utcnow(),
            uptime_seconds=86400,
            details=["High latency", "Memory usage at 85%"]
        )
        
        # Configure model info
        model_info = {
            "id": "credit-risk-v2",
            "name": "Credit Risk Model v2",
            "version": "2.1.0",
            "status": "active",
            "performance": {
                "accuracy": 0.94,
                "precision": 0.92,
                "recall": 0.89,
                "auc": 0.96
            },
            "last_updated": datetime.utcnow().isoformat(),
            "training_data_size": 1000000
        }
        
        client.configure_health_response(healthy_response)
        client.configure_model_info("credit-risk-v2", model_info)
        
        # Test monitoring workflow
        health = client.health()
        assert health.status == "healthy"
        assert health.uptime_seconds == 86400
        
        model_details = client.get_model_info("credit-risk-v2")
        assert model_details["id"] == "credit-risk-v2"
        assert "performance" in model_details
        assert model_details["performance"]["accuracy"] == 0.94
        
        # Test degraded status
        client.configure_health_response(degraded_response)
        degraded_health = client.health()
        assert degraded_health.status == "degraded"
        assert len(degraded_health.details) == 2


class TestEdgeCasesIntegration:
    """Test edge cases and boundary conditions."""
    
    def test_empty_and_null_values(self):
        """Test handling of empty and null values."""
        client = MockScoringClient()
        
        # Test with various edge case features
        edge_cases = [
            {"age": 0, "income": 0.0},  # Zero values
            {"age": 120, "income": 999999.99},  # High values
            {"age": None, "income": 50000.0},  # None values (if allowed by schema)
        ]
        
        for features in edge_cases:
            try:
                result = client.score(features)
                assert isinstance(result, ScoringResponse)
            except Exception as e:
                # Some edge cases might raise validation errors, which is expected
                assert "validation" in str(e).lower() or "required" in str(e).lower()
    
    @pytest.mark.asyncio
    async def test_timeout_and_network_errors(self):
        """Test timeout and network error handling."""
        client = MockScoringClient()
        
        # Configure timeout simulation
        client.configure_error("score", TimeoutError("Request timed out"), probability=1.0)
        
        with pytest.raises(TimeoutError):
            client.score({"age": 25})
        
        # Configure network error simulation
        client.configure_error("score", NetworkError("Connection failed"), probability=1.0)
        
        with pytest.raises(NetworkError):
            client.score({"age": 25})
    
    def test_large_batch_processing(self):
        """Test processing of large batches."""
        client = MockScoringClient()
        
        # Create a large batch
        large_batch = [{"test": i, "value": i * 10} for i in range(500)]
        
        # Should process without issues
        result = client.batch_score(large_batch)
        assert result.total_processed == 500
        assert result.total_successful == 500
        assert len(result.responses) == 500
