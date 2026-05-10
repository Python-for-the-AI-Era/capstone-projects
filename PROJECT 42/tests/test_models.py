"""
Tests for the ML Scoring SDK models module.
"""

import pytest
from datetime import datetime
from pydantic import ValidationError as PydanticValidationError

from ml_scoring_sdk.models import (
    ScoringRequest,
    ScoringResponse,
    BatchScoringRequest,
    BatchScoringResponse,
    HealthResponse,
    ErrorResponse
)


class TestScoringRequest:
    """Test the ScoringRequest model."""
    
    def test_valid_scoring_request(self):
        """Test creating a valid ScoringRequest."""
        features = {"age": 25, "income": 50000.0, "gender": "male"}
        request = ScoringRequest(features=features)
        
        assert request.features == features
        assert request.model_id is None
        assert request.version is None
    
    def test_scoring_request_with_model_id(self):
        """Test creating ScoringRequest with model_id."""
        features = {"age": 25, "income": 50000.0}
        request = ScoringRequest(
            features=features,
            model_id="credit-risk-v2",
            version="2.1"
        )
        
        assert request.features == features
        assert request.model_id == "credit-risk-v2"
        assert request.version == "2.1"
    
    def test_scoring_request_validation(self):
        """Test validation of ScoringRequest."""
        # Test empty features
        with pytest.raises(PydanticValidationError):
            ScoringRequest(features={})
        
        # Test non-dict features
        with pytest.raises(PydanticValidationError):
            ScoringRequest(features="invalid")
        
        # Test missing features
        with pytest.raises(PydanticValidationError):
            ScoringRequest()
    
    def test_scoring_request_serialization(self):
        """Test serialization of ScoringRequest."""
        features = {"age": 25, "income": 50000.0}
        request = ScoringRequest(features=features, model_id="test-model")
        
        data = request.dict()
        assert data["features"] == features
        assert data["model_id"] == "test-model"
        
        # Test exclude_unset
        data_unsets = request.dict(exclude_unset=True)
        assert "features" in data_unsets
        assert "model_id" in data_unsets
        assert "version" not in data_unsets
    
    def test_scoring_request_json(self):
        """Test JSON serialization of ScoringRequest."""
        features = {"age": 25, "income": 50000.0}
        request = ScoringRequest(features=features)
        
        json_str = request.json()
        assert "age" in json_str
        assert "income" in json_str


class TestScoringResponse:
    """Test the ScoringResponse model."""
    
    def test_valid_scoring_response(self):
        """Test creating a valid ScoringResponse."""
        features = {"age": 25, "income": 50000.0}
        response = ScoringResponse(
            score=0.75,
            confidence=0.95,
            model_id="test-model",
            timestamp=datetime.utcnow(),
            features=features
        )
        
        assert response.score == 0.75
        assert response.confidence == 0.95
        assert response.model_id == "test-model"
        assert response.features == features
        assert isinstance(response.timestamp, datetime)
    
    def test_scoring_response_validation(self):
        """Test validation of ScoringResponse."""
        features = {"age": 25, "income": 50000.0}
        
        # Test invalid score range
        with pytest.raises(PydanticValidationError):
            ScoringResponse(
                score=1.5,  # Invalid: > 1.0
                confidence=0.95,
                model_id="test",
                timestamp=datetime.utcnow(),
                features=features
            )
        
        # Test invalid confidence range
        with pytest.raises(PydanticValidationError):
            ScoringResponse(
                score=0.5,
                confidence=-0.1,  # Invalid: < 0
                model_id="test",
                timestamp=datetime.utcnow(),
                features=features
            )
    
    def test_scoring_response_optional_fields(self):
        """Test ScoringResponse with optional fields."""
        features = {"age": 25, "income": 50000.0}
        response = ScoringResponse(
            score=0.75,
            confidence=0.95,
            model_id="test-model",
            timestamp=datetime.utcnow(),
            features=features,
            explanation="High income indicates low risk",
            metadata={"version": "1.0", "region": "US"}
        )
        
        assert response.explanation == "High income indicates low risk"
        assert response.metadata == {"version": "1.0", "region": "US"}


class TestBatchScoringRequest:
    """Test the BatchScoringRequest model."""
    
    def test_valid_batch_request(self):
        """Test creating a valid BatchScoringRequest."""
        features_list = [
            {"age": 25, "income": 50000.0},
            {"age": 35, "income": 75000.0}
        ]
        requests = [ScoringRequest(features=f) for f in features_list]
        batch_request = BatchScoringRequest(requests=requests)
        
        assert len(batch_request.requests) == 2
        assert batch_request.model_id is None
        assert batch_request.version is None
    
    def test_batch_request_with_model_id(self):
        """Test BatchScoringRequest with model_id."""
        features_list = [{"age": 25, "income": 50000.0}]
        requests = [ScoringRequest(features=f) for f in features_list]
        batch_request = BatchScoringRequest(
            requests=requests,
            model_id="batch-model",
            version="1.0"
        )
        
        assert batch_request.model_id == "batch-model"
        assert batch_request.version == "1.0"
    
    def test_batch_request_validation(self):
        """Test validation of BatchScoringRequest."""
        # Test empty requests
        with pytest.raises(PydanticValidationError):
            BatchScoringRequest(requests=[])
        
        # Test too many requests
        with pytest.raises(PydanticValidationError):
            BatchScoringRequest(requests=[ScoringRequest(features={"test": 1})] * 1001)
    
    def test_batch_request_max_items(self):
        """Test batch request with maximum items."""
        requests = [ScoringRequest(features={"test": i}) for i in range(1000)]
        batch_request = BatchScoringRequest(requests=requests)
        assert len(batch_request.requests) == 1000


class TestBatchScoringResponse:
    """Test the BatchScoringResponse model."""
    
    def test_valid_batch_response(self):
        """Test creating a valid BatchScoringResponse."""
        features = {"age": 25, "income": 50000.0}
        responses = [
            ScoringResponse(
                score=0.75,
                confidence=0.95,
                model_id="test-model",
                timestamp=datetime.utcnow(),
                features=features
            )
        ]
        
        batch_response = BatchScoringResponse(
            responses=responses,
            total_processed=1,
            total_successful=1,
            total_failed=0,
            timestamp=datetime.utcnow()
        )
        
        assert len(batch_response.responses) == 1
        assert batch_response.total_processed == 1
        assert batch_response.total_successful == 1
        assert batch_response.total_failed == 0
    
    def test_batch_response_with_failures(self):
        """Test BatchScoringResponse with failures."""
        responses = []
        batch_response = BatchScoringResponse(
            responses=responses,
            total_processed=2,
            total_successful=1,
            total_failed=1,
            timestamp=datetime.utcnow(),
            errors=["Request 2 failed: Invalid input"]
        )
        
        assert batch_response.total_processed == 2
        assert batch_response.total_successful == 1
        assert batch_response.total_failed == 1
        assert len(batch_response.errors) == 1
    
    def test_batch_response_validation(self):
        """Test validation of BatchScoringResponse."""
        responses = []
        
        # Test negative counts
        with pytest.raises(PydanticValidationError):
            BatchScoringResponse(
                responses=responses,
                total_processed=-1,
                total_successful=0,
                total_failed=0,
                timestamp=datetime.utcnow()
            )


class TestHealthResponse:
    """Test the HealthResponse model."""
    
    def test_valid_health_response(self):
        """Test creating a valid HealthResponse."""
        response = HealthResponse(
            status="healthy",
            version="1.0.0",
            timestamp=datetime.utcnow(),
            uptime_seconds=3600
        )
        
        assert response.status == "healthy"
        assert response.version == "1.0.0"
        assert response.uptime_seconds == 3600
        assert isinstance(response.timestamp, datetime)
    
    def test_health_response_unhealthy(self):
        """Test HealthResponse with unhealthy status."""
        response = HealthResponse(
            status="unhealthy",
            version="1.0.0",
            timestamp=datetime.utcnow(),
            uptime_seconds=3600,
            details=["Database connection failed", "Cache service down"]
        )
        
        assert response.status == "unhealthy"
        assert len(response.details) == 2
        assert "Database connection failed" in response.details
    
    def test_health_response_validation(self):
        """Test validation of HealthResponse."""
        # Test invalid status
        with pytest.raises(PydanticValidationError):
            HealthResponse(
                status="invalid",  # Must be healthy/unhealthy/degraded
                version="1.0.0",
                timestamp=datetime.utcnow(),
                uptime_seconds=3600
            )
        
        # Test negative uptime
        with pytest.raises(PydanticValidationError):
            HealthResponse(
                status="healthy",
                version="1.0.0",
                timestamp=datetime.utcnow(),
                uptime_seconds=-1
            )


class TestErrorResponse:
    """Test the ErrorResponse model."""
    
    def test_valid_error_response(self):
        """Test creating a valid ErrorResponse."""
        response = ErrorResponse(
            message="Not found",
            error_code="MODEL_NOT_FOUND",
            status_code=404,
            timestamp=datetime.utcnow(),
            request_id="req-123"
        )
        
        assert response.message == "Not found"
        assert response.error_code == "MODEL_NOT_FOUND"
        assert response.status_code == 404
        assert response.request_id == "req-123"
    
    def test_error_response_with_details(self):
        """Test ErrorResponse with additional details."""
        response = ErrorResponse(
            message="Validation failed",
            error_code="VALIDATION_ERROR",
            status_code=400,
            timestamp=datetime.utcnow(),
            details={"field": "age", "error": "Must be positive"},
            suggestions=["Provide a valid age", "Check input format"]
        )
        
        assert response.details["field"] == "age"
        assert len(response.suggestions) == 2
    
    def test_error_response_validation(self):
        """Test validation of ErrorResponse."""
        # Test invalid status code
        with pytest.raises(PydanticValidationError):
            ErrorResponse(
                message="Error",
                error_code="TEST_ERROR",
                status_code=999,  # Invalid HTTP status code
                timestamp=datetime.utcnow()
            )


class TestModelExamples:
    """Test model examples and schema generation."""
    
    def test_model_schemas(self):
        """Test that all models have valid schemas."""
        models = [
            ScoringRequest,
            ScoringResponse,
            BatchScoringRequest,
            BatchScoringResponse,
            HealthResponse,
            ErrorResponse
        ]
        
        for model_class in models:
            schema = model_class.schema()
            assert isinstance(schema, dict)
            assert "title" in schema
            assert "properties" in schema
    
    def test_model_examples(self):
        """Test model examples are valid."""
        # Test ScoringRequest example
        request_example = ScoringRequest.schema().get("example", {})
        if request_example:
            request = ScoringRequest(**request_example)
            assert isinstance(request, ScoringRequest)
        
        # Test ScoringResponse example
        response_example = ScoringResponse.schema().get("example", {})
        if response_example:
            response = ScoringResponse(**response_example)
            assert isinstance(response, ScoringResponse)
