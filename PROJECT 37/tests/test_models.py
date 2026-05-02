"""
Tests for data models.

This module tests Pydantic models for validation and SQLAlchemy
models for database persistence.
"""

import pytest
from datetime import datetime
from typing import Dict, Any

from pipeline_pkg.models import (
    PipelineData,
    EmailLog,
    APIResponse,
    PipelineResult,
    PipelineDataDB,
    EmailLogDB,
    APIResponseDB,
)


class TestPipelineData:
    """Test cases for PipelineData model."""
    
    def test_valid_pipeline_data(self) -> None:
        """Test creating valid PipelineData."""
        data = PipelineData(
            source="test_api",
            data={"key": "value"},
        )
        
        assert data.source == "test_api"
        assert data.data == {"key": "value"}
        assert data.processed_at is None
        assert data.processing_version == "1.0"
    
    def test_pipeline_data_with_processed_at(self) -> None:
        """Test PipelineData with processed timestamp."""
        now = datetime.utcnow()
        data = PipelineData(
            source="test_api",
            data={"key": "value"},
            processed_at=now,
        )
        
        assert data.processed_at == now
    
    def test_invalid_empty_source(self) -> None:
        """Test PipelineData with empty source."""
        with pytest.raises(ValueError, match="Source cannot be empty"):
            PipelineData(source="", data={"key": "value"})
    
    def test_invalid_whitespace_source(self) -> None:
        """Test PipelineData with whitespace-only source."""
        with pytest.raises(ValueError, match="Source cannot be empty"):
            PipelineData(source="   ", data={"key": "value"})
    
    def test_source_normalization(self) -> None:
        """Test source is normalized to lowercase and stripped."""
        data = PipelineData(
            source="  TEST_API  ",
            data={"key": "value"},
        )
        
        assert data.source == "test_api"
    
    def test_invalid_data_type(self) -> None:
        """Test PipelineData with invalid data type."""
        with pytest.raises(ValueError, match="Data must be a dictionary"):
            PipelineData(source="test_api", data="invalid")  # type: ignore
    
    def test_empty_data_dict(self) -> None:
        """Test PipelineData with empty dictionary."""
        data = PipelineData(source="test_api", data={})
        assert data.data == {}


class TestEmailLog:
    """Test cases for EmailLog model."""
    
    def test_valid_email_log(self) -> None:
        """Test creating valid EmailLog."""
        log = EmailLog(
            recipient="test@example.com",
            subject="Test Subject",
            status="sent",
        )
        
        assert log.recipient == "test@example.com"
        assert log.subject == "Test Subject"
        assert log.status == "sent"
        assert log.error_message is None
        assert log.sent_at is None
    
    def test_email_log_with_error(self) -> None:
        """Test EmailLog with error message."""
        log = EmailLog(
            recipient="test@example.com",
            subject="Test Subject",
            status="failed",
            error_message="Connection timeout",
        )
        
        assert log.status == "failed"
        assert log.error_message == "Connection timeout"
    
    def test_invalid_email_address(self) -> None:
        """Test EmailLog with invalid email address."""
        with pytest.raises(ValueError, match="Invalid email address"):
            EmailLog(
                recipient="invalid-email",
                subject="Test Subject",
                status="sent",
            )
    
    def test_email_normalization(self) -> None:
        """Test email address is normalized to lowercase."""
        log = EmailLog(
            recipient="Test@EXAMPLE.COM",
            subject="Test Subject",
            status="sent",
        )
        
        assert log.recipient == "test@example.com"
    
    def test_invalid_status(self) -> None:
        """Test EmailLog with invalid status."""
        with pytest.raises(ValueError, match="Status must be one of"):
            EmailLog(
                recipient="test@example.com",
                subject="Test Subject",
                status="invalid",
            )
    
    def test_valid_statuses(self) -> None:
        """Test all valid statuses."""
        valid_statuses = ["sent", "failed", "pending"]
        
        for status in valid_statuses:
            log = EmailLog(
                recipient="test@example.com",
                subject="Test Subject",
                status=status,
            )
            assert log.status == status


class TestAPIResponse:
    """Test cases for APIResponse model."""
    
    def test_valid_api_response(self) -> None:
        """Test creating valid APIResponse."""
        response = APIResponse(
            endpoint="/test",
            request_data={"param": "value"},
            response_data={"result": "success"},
            status_code=200,
            response_time=0.5,
        )
        
        assert response.endpoint == "/test"
        assert response.request_data == {"param": "value"}
        assert response.response_data == {"result": "success"}
        assert response.status_code == 200
        assert response.response_time == 0.5
    
    def test_minimal_api_response(self) -> None:
        """Test APIResponse with minimal required fields."""
        response = APIResponse(
            endpoint="/test",
            status_code=404,
            response_time=0.2,
        )
        
        assert response.endpoint == "/test"
        assert response.request_data is None
        assert response.response_data is None
        assert response.status_code == 404
        assert response.response_time == 0.2
    
    def test_invalid_status_code_too_low(self) -> None:
        """Test APIResponse with status code below 100."""
        with pytest.raises(ValueError, match="Status code must be between 100 and 599"):
            APIResponse(
                endpoint="/test",
                status_code=99,
                response_time=0.5,
            )
    
    def test_invalid_status_code_too_high(self) -> None:
        """Test APIResponse with status code above 599."""
        with pytest.raises(ValueError, match="Status code must be between 100 and 599"):
            APIResponse(
                endpoint="/test",
                status_code=600,
                response_time=0.5,
            )
    
    def test_negative_response_time(self) -> None:
        """Test APIResponse with negative response time."""
        with pytest.raises(ValueError, match="Response time cannot be negative"):
            APIResponse(
                endpoint="/test",
                status_code=200,
                response_time=-0.1,
            )


class TestPipelineResult:
    """Test cases for PipelineResult model."""
    
    def test_valid_pipeline_result(self) -> None:
        """Test creating valid PipelineResult."""
        result = PipelineResult(
            start_time="2023-01-01T00:00:00",
            status="completed",
        )
        
        assert result.start_time == "2023-01-01T00:00:00"
        assert result.status == "completed"
        assert result.end_time is None
        assert result.endpoints_processed == 0
        assert result.records_processed == 0
        assert result.emails_sent == 0
        assert result.pdfs_generated == 0
        assert result.errors == []
    
    def test_pipeline_result_with_data(self) -> None:
        """Test PipelineResult with execution data."""
        result = PipelineResult(
            start_time="2023-01-01T00:00:00",
            end_time="2023-01-01T01:00:00",
            endpoints_processed=5,
            records_processed=100,
            emails_sent=2,
            pdfs_generated=1,
            status="completed",
            errors=["Warning: Some data was skipped"],
        )
        
        assert result.end_time == "2023-01-01T01:00:00"
        assert result.endpoints_processed == 5
        assert result.records_processed == 100
        assert result.emails_sent == 2
        assert result.pdfs_generated == 1
        assert result.errors == ["Warning: Some data was skipped"]
    
    def test_invalid_status(self) -> None:
        """Test PipelineResult with invalid status."""
        with pytest.raises(ValueError, match="Status must be one of"):
            PipelineResult(
                start_time="2023-01-01T00:00:00",
                status="invalid",
            )
    
    def test_valid_statuses(self) -> None:
        """Test all valid statuses."""
        valid_statuses = ["running", "completed", "failed", "cancelled"]
        
        for status in valid_statuses:
            result = PipelineResult(
                start_time="2023-01-01T00:00:00",
                status=status,
            )
            assert result.status == status


class TestSQLAlchemyModels:
    """Test cases for SQLAlchemy database models."""
    
    def test_pipeline_data_db_creation(self) -> None:
        """Test PipelineDataDB creation."""
        data = PipelineDataDB(
            source="test_api",
            data='{"key": "value"}',
            processed=True,
        )
        
        assert data.source == "test_api"
        assert data.data == '{"key": "value"}'
        assert data.processed is True
        assert data.id is None  # Not saved to database yet
        assert data.created_at is None
        assert data.updated_at is None
    
    def test_email_log_db_creation(self) -> None:
        """Test EmailLogDB creation."""
        log = EmailLogDB(
            recipient="test@example.com",
            subject="Test Subject",
            status="sent",
        )
        
        assert log.recipient == "test@example.com"
        assert log.subject == "Test Subject"
        assert log.status == "sent"
        assert log.error_message is None
        assert log.id is None
        assert log.sent_at is None
    
    def test_api_response_db_creation(self) -> None:
        """Test APIResponseDB creation."""
        response = APIResponseDB(
            endpoint="/test",
            request_data='{"param": "value"}',
            response_data='{"result": "success"}',
            status_code=200,
            response_time=0.5,
        )
        
        assert response.endpoint == "/test"
        assert response.request_data == '{"param": "value"}'
        assert response.response_data == '{"result": "success"}'
        assert response.status_code == 200
        assert response.response_time == 0.5
        assert response.id is None
        assert response.created_at is None
