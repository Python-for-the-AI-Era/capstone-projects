"""
Tests for database repository.

This module tests database operations including CRUD operations,
session management, and error handling.
"""

from unittest.mock import Mock, patch, MagicMock
from typing import Any, Dict, List

import pytest
from sqlalchemy.orm import Session

from pipeline_pkg.storage.database import DatabaseRepository
from pipeline_pkg.models import PipelineData, EmailLog, APIResponse


class TestDatabaseRepository:
    """Test cases for DatabaseRepository."""
    
    def setup_method(self) -> None:
        """Setup test fixtures."""
        self.database_url = "sqlite:///:memory:"
        self.repo = DatabaseRepository(self.database_url)
    
    def teardown_method(self) -> None:
        """Cleanup after tests."""
        if self.repo:
            self.repo.close()
    
    def test_initialization(self) -> None:
        """Test DatabaseRepository initialization."""
        assert self.repo.database_url == self.database_url
        assert self.repo.engine is not None
        assert self.repo.SessionLocal is not None
    
    @patch("pipeline_pkg.storage.database.create_engine")
    @patch("pipeline_pkg.storage.database.sessionmaker")
    def test_initialization_sqlite_config(self, mock_sessionmaker: Mock, mock_create_engine: Mock) -> None:
        """Test initialization with SQLite-specific configuration."""
        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine
        mock_session_factory = Mock()
        mock_sessionmaker.return_value = mock_session_factory
        
        DatabaseRepository("sqlite:///test.db")
        
        mock_create_engine.assert_called_once_with(
            "sqlite:///test.db",
            poolclass=mock_create_engine.return_value.poolclass,
            connect_args={"check_same_thread": False},
        )
    
    @patch("pipeline_pkg.storage.database.create_engine")
    def test_initialization_postgresql_config(self, mock_create_engine: Mock) -> None:
        """Test initialization with PostgreSQL configuration."""
        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine
        
        DatabaseRepository("postgresql://user:pass@localhost/db")
        
        mock_create_engine.assert_called_once_with("postgresql://user:pass@localhost/db")
    
    def test_get_session_context_manager(self) -> None:
        """Test session context manager."""
        with self.repo.get_session() as session:
            assert isinstance(session, Session)
            # Session should be active
            assert session.is_active
    
    def test_get_session_cleanup_on_exception(self) -> None:
        """Test session cleanup on exception."""
        with patch.object(self.repo.SessionLocal, '__enter__') as mock_enter:
            mock_session = Mock()
            mock_enter.return_value = mock_session
            
            try:
                with self.repo.get_session() as session:
                    raise ValueError("Test exception")
            except ValueError:
                pass
            
            # Should have called rollback
            mock_session.rollback.assert_called_once()
            mock_session.close.assert_called_once()
    
    def test_save_pipeline_data(self) -> None:
        """Test saving pipeline data."""
        pipeline_data = PipelineData(
            source="test_api",
            data={"key": "value"},
        )
        
        record_id = self.repo.save_pipeline_data(pipeline_data)
        
        assert record_id is not None
        assert isinstance(record_id, int)
        assert record_id > 0
    
    def test_save_pipeline_data_with_processed_at(self) -> None:
        """Test saving pipeline data with processed timestamp."""
        from datetime import datetime
        
        pipeline_data = PipelineData(
            source="test_api",
            data={"key": "value"},
            processed_at=datetime.utcnow(),
        )
        
        record_id = self.repo.save_pipeline_data(pipeline_data)
        
        assert record_id is not None
        assert isinstance(record_id, int)
    
    def test_get_pipeline_data_all(self) -> None:
        """Test getting all pipeline data."""
        # Save some test data
        for i in range(3):
            pipeline_data = PipelineData(
                source=f"test_api_{i}",
                data={"id": i},
            )
            self.repo.save_pipeline_data(pipeline_data)
        
        # Get all data
        results = self.repo.get_pipeline_data()
        
        assert len(results) == 3
    
    def test_get_pipeline_data_by_source(self) -> None:
        """Test getting pipeline data by source."""
        # Save test data with different sources
        self.repo.save_pipeline_data(PipelineData(source="api1", data={}))
        self.repo.save_pipeline_data(PipelineData(source="api2", data={}))
        self.repo.save_pipeline_data(PipelineData(source="api1", data={}))
        
        # Get data by source
        results = self.repo.get_pipeline_data(source="api1")
        
        assert len(results) == 2
        for result in results:
            assert result.source == "api1"
    
    def test_get_pipeline_data_with_limit(self) -> None:
        """Test getting pipeline data with limit."""
        # Save test data
        for i in range(5):
            pipeline_data = PipelineData(
                source=f"test_api_{i}",
                data={"id": i},
            )
            self.repo.save_pipeline_data(pipeline_data)
        
        # Get data with limit
        results = self.repo.get_pipeline_data(limit=3)
        
        assert len(results) == 3
    
    def test_get_pipeline_data_with_offset(self) -> None:
        """Test getting pipeline data with offset."""
        # Save test data
        for i in range(5):
            pipeline_data = PipelineData(
                source=f"test_api_{i}",
                data={"id": i},
            )
            self.repo.save_pipeline_data(pipeline_data)
        
        # Get data with offset
        results = self.repo.get_pipeline_data(offset=2)
        
        assert len(results) == 3
    
    def test_save_email_log(self) -> None:
        """Test saving email log."""
        email_log = EmailLog(
            recipient="test@example.com",
            subject="Test Subject",
            status="sent",
        )
        
        record_id = self.repo.save_email_log(email_log)
        
        assert record_id is not None
        assert isinstance(record_id, int)
        assert record_id > 0
    
    def test_save_email_log_with_error(self) -> None:
        """Test saving email log with error."""
        email_log = EmailLog(
            recipient="test@example.com",
            subject="Test Subject",
            status="failed",
            error_message="Connection timeout",
        )
        
        record_id = self.repo.save_email_log(email_log)
        
        assert record_id is not None
        assert isinstance(record_id, int)
    
    def test_get_email_logs_all(self) -> None:
        """Test getting all email logs."""
        # Save test email logs
        for i in range(3):
            email_log = EmailLog(
                recipient=f"test{i}@example.com",
                subject=f"Subject {i}",
                status="sent",
            )
            self.repo.save_email_log(email_log)
        
        # Get all logs
        results = self.repo.get_email_logs()
        
        assert len(results) == 3
    
    def test_get_email_logs_by_recipient(self) -> None:
        """Test getting email logs by recipient."""
        # Save test email logs
        self.repo.save_email_log(EmailLog(recipient="user1@example.com", subject="Test", status="sent"))
        self.repo.save_email_log(EmailLog(recipient="user2@example.com", subject="Test", status="sent"))
        self.repo.save_email_log(EmailLog(recipient="user1@example.com", subject="Test", status="sent"))
        
        # Get logs by recipient
        results = self.repo.get_email_logs(recipient="user1@example.com")
        
        assert len(results) == 2
        for result in results:
            assert result.recipient == "user1@example.com"
    
    def test_get_email_logs_by_status(self) -> None:
        """Test getting email logs by status."""
        # Save test email logs
        self.repo.save_email_log(EmailLog(recipient="test@example.com", subject="Test", status="sent"))
        self.repo.save_email_log(EmailLog(recipient="test@example.com", subject="Test", status="failed"))
        self.repo.save_email_log(EmailLog(recipient="test@example.com", subject="Test", status="sent"))
        
        # Get logs by status
        results = self.repo.get_email_logs(status="sent")
        
        assert len(results) == 2
        for result in results:
            assert result.status == "sent"
    
    def test_save_api_response(self) -> None:
        """Test saving API response."""
        api_response = APIResponse(
            endpoint="/test",
            request_data={"param": "value"},
            response_data={"result": "success"},
            status_code=200,
            response_time=0.5,
        )
        
        record_id = self.repo.save_api_response(api_response)
        
        assert record_id is not None
        assert isinstance(record_id, int)
        assert record_id > 0
    
    def test_save_api_response_minimal(self) -> None:
        """Test saving API response with minimal data."""
        api_response = APIResponse(
            endpoint="/test",
            status_code=404,
            response_time=0.2,
        )
        
        record_id = self.repo.save_api_response(api_response)
        
        assert record_id is not None
        assert isinstance(record_id, int)
    
    def test_get_api_responses_all(self) -> None:
        """Test getting all API responses."""
        # Save test API responses
        for i in range(3):
            api_response = APIResponse(
                endpoint=f"/test{i}",
                status_code=200,
                response_time=0.1 * i,
            )
            self.repo.save_api_response(api_response)
        
        # Get all responses
        results = self.repo.get_api_responses()
        
        assert len(results) == 3
    
    def test_get_api_responses_by_endpoint(self) -> None:
        """Test getting API responses by endpoint."""
        # Save test API responses
        self.repo.save_api_response(APIResponse(endpoint="/users", status_code=200, response_time=0.1))
        self.repo.save_api_response(APIResponse(endpoint="/products", status_code=200, response_time=0.2))
        self.repo.save_api_response(APIResponse(endpoint="/users", status_code=404, response_time=0.3))
        
        # Get responses by endpoint
        results = self.repo.get_api_responses(endpoint="/users")
        
        assert len(results) == 2
        for result in results:
            assert result.endpoint == "/users"
    
    def test_get_api_responses_by_status_code(self) -> None:
        """Test getting API responses by status code."""
        # Save test API responses
        self.repo.save_api_response(APIResponse(endpoint="/test1", status_code=200, response_time=0.1))
        self.repo.save_api_response(APIResponse(endpoint="/test2", status_code=404, response_time=0.2))
        self.repo.save_api_response(APIResponse(endpoint="/test3", status_code=200, response_time=0.3))
        
        # Get responses by status code
        results = self.repo.get_api_responses(status_code=200)
        
        assert len(results) == 2
        for result in results:
            assert result.status_code == 200
    
    def test_get_statistics_empty(self) -> None:
        """Test getting statistics from empty database."""
        stats = self.repo.get_statistics()
        
        assert stats["pipeline_data_count"] == 0
        assert stats["email_count"] == 0
        assert stats["api_response_count"] == 0
        assert stats["successful_emails"] == 0
        assert stats["successful_api_calls"] == 0
        assert stats["email_success_rate"] == 0
        assert stats["api_success_rate"] == 0
    
    def test_get_statistics_with_data(self) -> None:
        """Test getting statistics with data."""
        # Save test data
        self.repo.save_pipeline_data(PipelineData(source="api1", data={}))
        self.repo.save_pipeline_data(PipelineData(source="api2", data={}))
        
        self.repo.save_email_log(EmailLog(recipient="test@example.com", subject="Test", status="sent"))
        self.repo.save_email_log(EmailLog(recipient="test@example.com", subject="Test", status="failed"))
        
        self.repo.save_api_response(APIResponse(endpoint="/test1", status_code=200, response_time=0.1))
        self.repo.save_api_response(APIResponse(endpoint="/test2", status_code=404, response_time=0.2))
        
        stats = self.repo.get_statistics()
        
        assert stats["pipeline_data_count"] == 2
        assert stats["email_count"] == 2
        assert stats["api_response_count"] == 2
        assert stats["successful_emails"] == 1
        assert stats["successful_api_calls"] == 1
        assert stats["email_success_rate"] == 50.0
        assert stats["api_success_rate"] == 50.0
    
    def test_close(self) -> None:
        """Test database connection cleanup."""
        # Should not raise an exception
        self.repo.close()
    
    @patch("pipeline_pkg.storage.database.SessionLocal")
    def test_save_pipeline_data_failure(self, mock_session_local: Mock) -> None:
        """Test saving pipeline data with database error."""
        mock_session = Mock()
        mock_session.commit.side_effect = Exception("Database error")
        mock_session_local.return_value = mock_session
        
        repo = DatabaseRepository(self.database_url)
        pipeline_data = PipelineData(source="test", data={})
        
        with pytest.raises(Exception, match="Database error"):
            repo.save_pipeline_data(pipeline_data)
        
        mock_session.rollback.assert_called_once()
    
    @patch("pipeline_pkg.storage.database.SessionLocal")
    def test_get_pipeline_data_failure(self, mock_session_local: Mock) -> None:
        """Test getting pipeline data with database error."""
        mock_session = Mock()
        mock_session.query.side_effect = Exception("Database error")
        mock_session_local.return_value = mock_session
        
        repo = DatabaseRepository(self.database_url)
        
        with pytest.raises(Exception, match="Database error"):
            repo.get_pipeline_data()
    
    def test_database_url_types(self) -> None:
        """Test initialization with different database URL types."""
        # SQLite
        repo_sqlite = DatabaseRepository("sqlite:///test.db")
        assert repo_sqlite.database_url == "sqlite:///test.db"
        repo_sqlite.close()
        
        # PostgreSQL
        repo_postgres = DatabaseRepository("postgresql://user:pass@localhost/db")
        assert repo_postgres.database_url == "postgresql://user:pass@localhost/db"
        repo_postgres.close()
        
        # MySQL
        repo_mysql = DatabaseRepository("mysql://user:pass@localhost/db")
        assert repo_mysql.database_url == "mysql://user:pass@localhost/db"
        repo_mysql.close()
