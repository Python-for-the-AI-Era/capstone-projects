"""
Tests for core pipeline orchestrator.

This module tests the main Pipeline class including
workflow orchestration and service coordination.
"""

from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from typing import Any, Dict, List

import pytest

from pipeline_pkg.core.pipeline import Pipeline
from pipeline_pkg.models import PipelineData, PipelineResult


class TestPipeline:
    """Test cases for Pipeline."""
    
    def setup_method(self) -> None:
        """Setup test fixtures."""
        self.pipeline = Pipeline(
            database_url="sqlite:///:memory:",
            api_base_url="https://api.example.com",
            api_key="test-key",
            smtp_server="smtp.example.com",
            smtp_port=587,
            smtp_username="test@example.com",
            smtp_password="password123",
            output_dir="/tmp/test_output",
        )
    
    def teardown_method(self) -> None:
        """Cleanup after tests."""
        if self.pipeline:
            self.pipeline.cleanup()
    
    def test_initialization(self) -> None:
        """Test Pipeline initialization."""
        assert self.pipeline.db_repo is not None
        assert self.pipeline.http_client is not None
        assert self.pipeline.email_sender is not None
        assert self.pipeline.pdf_generator is not None
    
    def test_process_data_valid(self) -> None:
        """Test processing valid data."""
        raw_data = {
            "name": "  TEST NAME  ",
            "age": 25,
            "tags": ["  TAG1  ", "TAG2"],
            "active": True,
        }
        
        processed = self.pipeline.process_data(raw_data)
        
        assert processed["name"] == "test name"
        assert processed["age"] == 25
        assert processed["tags"] == ["tag1", "tag2"]
        assert processed["active"] is True
        assert "processed_at" in processed
        assert processed["processing_version"] == "1.0"
    
    def test_process_data_invalid_type(self) -> None:
        """Test processing invalid data type."""
        with pytest.raises(ValueError, match="Data must be a dictionary"):
            self.pipeline.process_data("invalid")  # type: ignore
    
    def test_process_data_empty_dict(self) -> None:
        """Test processing empty dictionary."""
        processed = self.pipeline.process_data({})
        
        assert "processed_at" in processed
        assert processed["processing_version"] == "1.0"
    
    @patch("pipeline_pkg.core.pipeline.HTTPClient.get")
    @patch("pipeline_pkg.core.pipeline.DatabaseRepository.save_api_response")
    @patch("pipeline_pkg.core.pipeline.DatabaseRepository.save_pipeline_data")
    def test_fetch_and_process_endpoint_success(
        self,
        mock_save_pipeline_data: Mock,
        mock_save_api_response: Mock,
        mock_get: Mock,
    ) -> None:
        """Test successful endpoint fetching and processing."""
        # Mock HTTP response
        raw_data = {"id": 1, "name": "Test"}
        api_response_mock = Mock()
        mock_get.return_value = (raw_data, api_response_mock)
        
        # Mock database saves
        mock_save_pipeline_data.return_value = 1
        mock_save_api_response.return_value = 1
        
        result = self.pipeline.fetch_and_process_endpoint("/users")
        
        assert result is not None
        assert "processed_at" in result
        assert result["processing_version"] == "1.0"
        mock_get.assert_called_once_with("/users", None)
        mock_save_api_response.assert_called_once_with(api_response_mock)
        mock_save_pipeline_data.assert_called_once()
    
    @patch("pipeline_pkg.core.pipeline.HTTPClient.get")
    def test_fetch_and_process_endpoint_no_data(self, mock_get: Mock) -> None:
        """Test endpoint fetching with no data."""
        mock_get.return_value = (None, Mock())
        
        result = self.pipeline.fetch_and_process_endpoint("/users")
        
        assert result is None
    
    @patch("pipeline_pkg.core.pipeline.HTTPClient.get")
    def test_fetch_and_process_endpoint_failure(self, mock_get: Mock) -> None:
        """Test endpoint fetching with failure."""
        mock_get.side_effect = Exception("API error")
        
        result = self.pipeline.fetch_and_process_endpoint("/users")
        
        assert result is None
    
    @patch("pipeline_pkg.core.pipeline.HTTPClient.get")
    @patch("pipeline_pkg.core.pipeline.DatabaseRepository.save_api_response")
    @patch("pipeline_pkg.core.pipeline.DatabaseRepository.save_pipeline_data")
    def test_fetch_and_process_endpoint_with_params(
        self,
        mock_save_pipeline_data: Mock,
        mock_save_api_response: Mock,
        mock_get: Mock,
    ) -> None:
        """Test endpoint fetching with parameters."""
        raw_data = {"id": 1, "name": "Test"}
        api_response_mock = Mock()
        mock_get.return_value = (raw_data, api_response_mock)
        mock_save_pipeline_data.return_value = 1
        mock_save_api_response.return_value = 1
        
        params = {"page": 1, "limit": 10}
        result = self.pipeline.fetch_and_process_endpoint("/users", params)
        
        assert result is not None
        mock_get.assert_called_once_with("/users", params)
    
    @patch("pipeline_pkg.core.pipeline.Pipeline.fetch_and_process_endpoint")
    @patch("pipeline_pkg.core.pipeline.PDFGenerator.generate_report")
    @patch("pipeline_pkg.core.pipeline.EmailSender.send_email")
    @patch("pipeline_pkg.core.pipeline.DatabaseRepository.save_email_log")
    def test_run_pipeline_success(
        self,
        mock_save_email_log: Mock,
        mock_send_email: Mock,
        mock_generate_report: Mock,
        mock_fetch_endpoint: Mock,
    ) -> None:
        """Test successful pipeline execution."""
        # Mock endpoint processing
        mock_fetch_endpoint.side_effect = [
            {"id": 1, "name": "User 1"},
            {"id": 2, "name": "Product 1"},
        ]
        
        # Mock PDF generation
        mock_pdf_path = Mock()
        mock_pdf_path.name = "report.pdf"
        mock_pdf_path.__str__ = Mock(return_value="/tmp/report.pdf")
        mock_generate_report.return_value = mock_pdf_path
        
        # Mock email sending
        mock_email_log = Mock()
        mock_email_log.status = "sent"
        mock_send_email.return_value = mock_email_log
        mock_save_email_log.return_value = 1
        
        # Run pipeline
        result = self.pipeline.run_pipeline(
            endpoints=["/users", "/products"],
            recipients=["admin@example.com"],
        )
        
        # Verify results
        assert result.status == "completed"
        assert result.endpoints_processed == 2
        assert result.records_processed == 2
        assert result.pdfs_generated == 1
        assert result.emails_sent == 1
        assert len(result.errors) == 0
        
        # Verify method calls
        assert mock_fetch_endpoint.call_count == 2
        mock_generate_report.assert_called_once()
        assert mock_send_email.call_count == 1
        mock_save_email_log.assert_called_once()
    
    @patch("pipeline_pkg.core.pipeline.Pipeline.fetch_and_process_endpoint")
    @patch("pipeline_pkg.core.pipeline.PDFGenerator.generate_report")
    @patch("pipeline_pkg.core.pipeline.EmailSender.send_email")
    def test_run_pipeline_partial_failure(
        self,
        mock_send_email: Mock,
        mock_generate_report: Mock,
        mock_fetch_endpoint: Mock,
    ) -> None:
        """Test pipeline execution with partial failures."""
        # Mock endpoint processing (one success, one failure)
        mock_fetch_endpoint.side_effect = [
            {"id": 1, "name": "User 1"},  # Success
            None,  # Failure
        ]
        
        # Mock PDF generation
        mock_pdf_path = Mock()
        mock_pdf_path.name = "report.pdf"
        mock_pdf_path.__str__ = Mock(return_value="/tmp/report.pdf")
        mock_generate_report.return_value = mock_pdf_path
        
        # Mock email sending
        mock_email_log = Mock()
        mock_email_log.status = "sent"
        mock_send_email.return_value = mock_email_log
        
        # Run pipeline
        result = self.pipeline.run_pipeline(
            endpoints=["/users", "/products"],
            recipients=["admin@example.com"],
        )
        
        # Verify results
        assert result.status == "completed_with_errors"
        assert result.endpoints_processed == 1
        assert result.records_processed == 1
        assert result.pdfs_generated == 1
        assert result.emails_sent == 1
        assert len(result.errors) == 1
        assert "Failed to process endpoint: /products" in result.errors[0]
    
    @patch("pipeline_pkg.core.pipeline.Pipeline.fetch_and_process_endpoint")
    def test_run_pipeline_no_data(self, mock_fetch_endpoint: Mock) -> None:
        """Test pipeline execution with no data."""
        # Mock endpoint processing (all failures)
        mock_fetch_endpoint.return_value = None
        
        # Run pipeline
        result = self.pipeline.run_pipeline(
            endpoints=["/users", "/products"],
            recipients=["admin@example.com"],
        )
        
        # Verify results
        assert result.status == "completed_with_errors"
        assert result.endpoints_processed == 0
        assert result.records_processed == 0
        assert result.pdfs_generated == 0
        assert result.emails_sent == 0
        assert len(result.errors) == 2
    
    @patch("pipeline_pkg.core.pipeline.Pipeline.fetch_and_process_endpoint")
    @patch("pipeline_pkg.core.pipeline.PDFGenerator.generate_report")
    @patch("pipeline_pkg.core.pipeline.EmailSender.send_email")
    @patch("pipeline_pkg.core.pipeline.DatabaseRepository.save_email_log")
    def test_run_pipeline_email_failure(
        self,
        mock_save_email_log: Mock,
        mock_send_email: Mock,
        mock_generate_report: Mock,
        mock_fetch_endpoint: Mock,
    ) -> None:
        """Test pipeline execution with email failure."""
        # Mock endpoint processing
        mock_fetch_endpoint.return_value = {"id": 1, "name": "User 1"}
        
        # Mock PDF generation
        mock_pdf_path = Mock()
        mock_pdf_path.name = "report.pdf"
        mock_pdf_path.__str__ = Mock(return_value="/tmp/report.pdf")
        mock_generate_report.return_value = mock_pdf_path
        
        # Mock email sending failure
        mock_email_log = Mock()
        mock_email_log.status = "failed"
        mock_email_log.error_message = "SMTP error"
        mock_send_email.return_value = mock_email_log
        mock_save_email_log.return_value = 1
        
        # Run pipeline
        result = self.pipeline.run_pipeline(
            endpoints=["/users"],
            recipients=["admin@example.com"],
        )
        
        # Verify results
        assert result.status == "completed_with_errors"
        assert result.endpoints_processed == 1
        assert result.records_processed == 1
        assert result.pdfs_generated == 1
        assert result.emails_sent == 0
        assert len(result.errors) == 1
        assert "Failed to send email to admin@example.com" in result.errors[0]
    
    @patch("pipeline_pkg.core.pipeline.Pipeline.fetch_and_process_endpoint")
    @patch("pipeline_pkg.core.pipeline.PDFGenerator.generate_report")
    def test_run_pipeline_pdf_failure(
        self,
        mock_generate_report: Mock,
        mock_fetch_endpoint: Mock,
    ) -> None:
        """Test pipeline execution with PDF generation failure."""
        # Mock endpoint processing
        mock_fetch_endpoint.return_value = {"id": 1, "name": "User 1"}
        
        # Mock PDF generation failure
        mock_generate_report.side_effect = Exception("PDF generation failed")
        
        # Run pipeline
        result = self.pipeline.run_pipeline(
            endpoints=["/users"],
            recipients=["admin@example.com"],
        )
        
        # Verify results
        assert result.status == "completed_with_errors"
        assert result.endpoints_processed == 1
        assert result.records_processed == 1
        assert result.pdfs_generated == 0
        assert result.emails_sent == 0
        assert len(result.errors) == 1
        assert "Failed to generate PDF" in result.errors[0]
    
    @patch("pipeline_pkg.core.pipeline.DatabaseRepository.get_statistics")
    def test_get_pipeline_statistics(self, mock_get_stats: Mock) -> None:
        """Test getting pipeline statistics."""
        mock_stats = {
            "pipeline_data_count": 10,
            "email_count": 5,
            "api_response_count": 15,
            "successful_emails": 4,
            "successful_api_calls": 12,
            "email_success_rate": 80.0,
            "api_success_rate": 80.0,
        }
        mock_get_stats.return_value = mock_stats
        
        stats = self.pipeline.get_pipeline_statistics()
        
        assert stats == mock_stats
        mock_get_stats.assert_called_once()
    
    @patch("pipeline_pkg.core.pipeline.DatabaseRepository.get_statistics")
    @patch("pipeline_pkg.core.pipeline.EmailSender.test_connection")
    def test_test_connections_success(
        self,
        mock_test_email: Mock,
        mock_get_stats: Mock,
    ) -> None:
        """Test successful connection testing."""
        mock_get_stats.return_value = {"test": "data"}  # Database success
        mock_test_email.return_value = True  # Email success
        
        connections = self.pipeline.test_connections()
        
        assert connections["database"] is True
        assert connections["email"] is True
    
    @patch("pipeline_pkg.core.pipeline.DatabaseRepository.get_statistics")
    @patch("pipeline_pkg.core.pipeline.EmailSender.test_connection")
    def test_test_connections_database_failure(
        self,
        mock_test_email: Mock,
        mock_get_stats: Mock,
    ) -> None:
        """Test connection testing with database failure."""
        mock_get_stats.side_effect = Exception("Database error")
        mock_test_email.return_value = True
        
        connections = self.pipeline.test_connections()
        
        assert connections["database"] is False
        assert connections["email"] is True
    
    @patch("pipeline_pkg.core.pipeline.DatabaseRepository.get_statistics")
    @patch("pipeline_pkg.core.pipeline.EmailSender.test_connection")
    def test_test_connections_email_failure(
        self,
        mock_test_email: Mock,
        mock_get_stats: Mock,
    ) -> None:
        """Test connection testing with email failure."""
        mock_get_stats.return_value = {"test": "data"}
        mock_test_email.return_value = False
        
        connections = self.pipeline.test_connections()
        
        assert connections["database"] is True
        assert connections["email"] is False
    
    def test_cleanup(self) -> None:
        """Test pipeline cleanup."""
        # Mock cleanup methods
        self.pipeline.http_client.close = Mock()
        self.pipeline.db_repo.close = Mock()
        
        self.pipeline.cleanup()
        
        self.pipeline.http_client.close.assert_called_once()
        self.pipeline.db_repo.close.assert_called_once()
    
    def test_context_manager(self) -> None:
        """Test Pipeline as context manager."""
        with patch.object(self.pipeline, 'cleanup') as mock_cleanup:
            with self.pipeline as pipeline:
                assert pipeline == self.pipeline
            mock_cleanup.assert_called_once()
    
    @patch("pipeline_pkg.core.pipeline.Pipeline.fetch_and_process_endpoint")
    def test_run_pipeline_with_params(
        self,
        mock_fetch_endpoint: Mock,
    ) -> None:
        """Test pipeline execution with parameters."""
        mock_fetch_endpoint.return_value = {"id": 1, "name": "User 1"}
        
        params = {"page": 1, "limit": 10}
        result = self.pipeline.run_pipeline(
            endpoints=["/users"],
            recipients=["admin@example.com"],
            params=params,
        )
        
        # Verify that params were passed to endpoint processing
        mock_fetch_endpoint.assert_called_once_with("/users", params)
    
    @patch("pipeline_pkg.core.pipeline.Pipeline.fetch_and_process_endpoint")
    @patch("pipeline_pkg.core.pipeline.PDFGenerator.generate_report")
    @patch("pipeline_pkg.core.pipeline.EmailSender.send_email")
    def test_run_pipeline_multiple_recipients(
        self,
        mock_send_email: Mock,
        mock_generate_report: Mock,
        mock_fetch_endpoint: Mock,
    ) -> None:
        """Test pipeline execution with multiple recipients."""
        mock_fetch_endpoint.return_value = {"id": 1, "name": "User 1"}
        
        mock_pdf_path = Mock()
        mock_pdf_path.name = "report.pdf"
        mock_pdf_path.__str__ = Mock(return_value="/tmp/report.pdf")
        mock_generate_report.return_value = mock_pdf_path
        
        mock_email_log = Mock()
        mock_email_log.status = "sent"
        mock_send_email.return_value = mock_email_log
        
        recipients = ["admin@example.com", "user@example.com"]
        result = self.pipeline.run_pipeline(
            endpoints=["/users"],
            recipients=recipients,
        )
        
        assert result.emails_sent == 2
        assert mock_send_email.call_count == 2
