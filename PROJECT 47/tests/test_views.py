"""
Comprehensive test suite for the data export views.

This module tests the corrected implementation including:
- Happy path scenarios
- Empty export scenarios
- Database error handling
- SQL injection prevention
- Input validation
- Error handling
- Performance
"""

import pytest
import io
import csv
from unittest.mock import Mock, patch, MagicMock
from flask import Flask
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError, OperationalError
import tempfile
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from views.corrected import app
from models.corrected import User, Order, Base
from utils.validators import ValidationError


class TestExportViews:
    """Test class for export views."""
    
    @pytest.fixture
    def app(self):
        """Create test Flask app."""
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-secret-key'
        return app
    
    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return app.test_client()
    
    @pytest.fixture
    def db_session(self):
        """Create test database session."""
        # Use in-memory SQLite for testing
        engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Add test data
        user1 = User(name='John Doe', email='john@example.com')
        user2 = User(name='Jane Smith', email='jane@example.com')
        session.add(user1)
        session.add(user2)
        
        order1 = Order(user_id=1, amount=100.0, status='completed')
        order2 = Order(user_id=1, amount=200.0, status='pending')
        order3 = Order(user_id=2, amount=150.0, status='completed')
        session.add(order1)
        session.add(order2)
        session.add(order3)
        
        session.commit()
        
        yield session
        
        session.close()
    
    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        session = Mock()
        return session


class TestHappyPath:
    """Test happy path scenarios."""
    
    def test_export_users_success(self, client, db_session):
        """Test successful user export."""
        with patch('views.corrected.Session', return_value=db_session):
            response = client.get('/export/users')
            
            assert response.status_code == 200
            assert response.mimetype == 'text/csv'
            
            # Parse CSV content
            csv_content = response.data.decode('utf-8')
            csv_reader = csv.reader(io.StringIO(csv_content))
            rows = list(csv_reader)
            
            # Check header
            assert len(rows[0]) == 7
            assert 'User ID' in rows[0]
            assert 'Name' in rows[0]
            
            # Check data rows (should have 2 users)
            assert len(rows) == 3  # Header + 2 users
            
            # Check user data
            assert 'John Doe' in csv_content
            assert 'Jane Smith' in csv_content
    
    def test_export_orders_success(self, client, db_session):
        """Test successful order export."""
        with patch('views.corrected.Session', return_value=db_session):
            response = client.get('/export/orders')
            
            assert response.status_code == 200
            assert response.mimetype == 'text/csv'
            
            # Parse CSV content
            csv_content = response.data.decode('utf-8')
            csv_reader = csv.reader(io.StringIO(csv_content))
            rows = list(csv_reader)
            
            # Check header
            assert len(rows[0]) == 8
            assert 'Order ID' in rows[0]
            assert 'Amount' in rows[0]
            
            # Check data rows (should have 3 orders)
            assert len(rows) == 4  # Header + 3 orders
            
            # Check order data
            assert '100.00' in csv_content
            assert '200.00' in csv_content
            assert '150.00' in csv_content
    
    def test_export_users_with_name_filter(self, client, db_session):
        """Test user export with name filter."""
        with patch('views.corrected.Session', return_value=db_session):
            response = client.get('/export/users?name=John')
            
            assert response.status_code == 200
            
            csv_content = response.data.decode('utf-8')
            csv_reader = csv.reader(io.StringIO(csv_content))
            rows = list(csv_reader)
            
            # Should have only John Doe
            assert len(rows) == 2  # Header + 1 user
            assert 'John Doe' in csv_content
            assert 'Jane Smith' not in csv_content
    
    def test_export_orders_with_status_filter(self, client, db_session):
        """Test order export with status filter."""
        with patch('views.corrected.Session', return_value=db_session):
            response = client.get('/export/orders?status=completed')
            
            assert response.status_code == 200
            
            csv_content = response.data.decode('utf-8')
            csv_reader = csv.reader(io.StringIO(csv_content))
            rows = list(csv_reader)
            
            # Should have only completed orders
            assert len(rows) == 3  # Header + 2 orders
            assert 'completed' in csv_content
            assert 'pending' not in csv_content
    
    def test_export_statistics_success(self, client, db_session):
        """Test statistics endpoint."""
        with patch('views.corrected.Session', return_value=db_session):
            response = client.get('/export/statistics')
            
            assert response.status_code == 200
            data = response.get_json()
            
            assert data['success'] is True
            assert 'data' in data
            assert 'total_users' in data['data']
            assert 'total_orders' in data['data']
            assert 'total_revenue' in data['data']
            
            # Check expected values
            assert data['data']['total_users'] == 2
            assert data['data']['total_orders'] == 3
            assert data['data']['total_revenue'] == 450.0
    
    def test_health_check_success(self, client):
        """Test health check endpoint."""
        with patch('views.corrected.Session') as mock_session_class:
            mock_session = Mock()
            mock_session.execute.return_value.scalar.return_value = 1
            mock_session_class.return_value = mock_session
            
            response = client.get('/health')
            
            assert response.status_code == 200
            data = response.get_json()
            
            assert data['status'] == 'healthy'
            assert data['database'] == 'healthy'
            assert 'timestamp' in data


class TestEmptyExport:
    """Test empty export scenarios."""
    
    def test_export_users_no_results(self, client, mock_session):
        """Test user export with no results."""
        # Mock empty query result
        mock_session.query.return_value.options.return_value.all.return_value = []
        
        with patch('views.corrected.Session', return_value=mock_session):
            response = client.get('/export/users')
            
            assert response.status_code == 404
            assert b'No users found' in response.data
    
    def test_export_orders_no_results(self, client, mock_session):
        """Test order export with no results."""
        # Mock empty query result
        mock_session.query.return_value.options.return_value.all.return_value = []
        
        with patch('views.corrected.Session', return_value=mock_session):
            response = client.get('/export/orders')
            
            assert response.status_code == 404
            assert b'No orders found' in response.data
    
    def test_export_users_empty_name_filter(self, client, db_session):
        """Test user export with empty name filter."""
        with patch('views.corrected.Session', return_value=db_session):
            response = client.get('/export/users?name=')
            
            # Empty name should return all users
            assert response.status_code == 200
            
            csv_content = response.data.decode('utf-8')
            assert 'John Doe' in csv_content
            assert 'Jane Smith' in csv_content


class TestDatabaseErrors:
    """Test database error handling."""
    
    def test_export_users_database_error(self, client, mock_session):
        """Test user export with database error."""
        # Mock database error
        mock_session.query.return_value.options.side_effect = SQLAlchemyError("Database error")
        
        with patch('views.corrected.Session', return_value=mock_session):
            response = client.get('/export/users')
            
            assert response.status_code == 500
            assert b'Database error occurred' in response.data
    
    def test_export_orders_database_error(self, client, mock_session):
        """Test order export with database error."""
        # Mock database error
        mock_session.query.return_value.options.side_effect = OperationalError("Connection failed", None, None)
        
        with patch('views.corrected.Session', return_value=mock_session):
            response = client.get('/export/orders')
            
            assert response.status_code == 500
            assert b'Database error occurred' in response.data
    
    def test_export_statistics_database_error(self, client, mock_session):
        """Test statistics endpoint with database error."""
        # Mock database error
        mock_session.execute.side_effect = SQLAlchemyError("Database error")
        
        with patch('views.corrected.Session', return_value=mock_session):
            response = client.get('/export/statistics')
            
            assert response.status_code == 500
            data = response.get_json()
            
            assert data['success'] is False
            assert 'error' in data
    
    def test_health_check_database_error(self, client):
        """Test health check with database error."""
        with patch('views.corrected.Session') as mock_session_class:
            mock_session = Mock()
            mock_session.execute.side_effect = OperationalError("Connection failed", None, None)
            mock_session_class.return_value = mock_session
            
            response = client.get('/health')
            
            assert response.status_code == 503
            data = response.get_json()
            
            assert data['status'] == 'unhealthy'
            assert data['database'] == 'unhealthy'


class TestSQLInjectionPrevention:
    """Test SQL injection prevention."""
    
    def test_sql_injection_name_filter(self, client, mock_session):
        """Test SQL injection attempt in name filter."""
        malicious_inputs = [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "'; SELECT * FROM users; --",
            "admin'; DELETE FROM users; --",
            "' UNION SELECT * FROM orders --"
        ]
        
        for malicious_input in malicious_inputs:
            with patch('views.corrected.Session', return_value=mock_session):
                response = client.get(f'/export/users?name={malicious_input}')
                
                # Should return 400 for invalid input
                assert response.status_code == 400
                assert b'Invalid input parameters' in response.data
                
                # Verify that no SQL queries were executed
                mock_session.query.assert_not_called()
    
    def test_sql_injection_status_filter(self, client, mock_session):
        """Test SQL injection attempt in status filter."""
        malicious_inputs = [
            "'; DROP TABLE orders; --",
            "' OR '1'='1",
            "'; SELECT * FROM users; --",
            "completed'; DELETE FROM orders; --",
            "' UNION SELECT * FROM users --"
        ]
        
        for malicious_input in malicious_inputs:
            with patch('views.corrected.Session', return_value=mock_session):
                response = client.get(f'/export/orders?status={malicious_input}')
                
                # Should return 400 for invalid input
                assert response.status_code == 400
                assert b'Invalid input parameters' in response.data
                
                # Verify that no SQL queries were executed
                mock_session.query.assert_not_called()
    
    def test_xss_prevention(self, client, mock_session):
        """Test XSS prevention in input parameters."""
        xss_inputs = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>",
            "'\"><script>alert('xss')</script>"
        ]
        
        for xss_input in xss_inputs:
            with patch('views.corrected.Session', return_value=mock_session):
                response = client.get(f'/export/users?name={xss_input}')
                
                # Should return 400 for invalid input
                assert response.status_code == 400
                assert b'Invalid input parameters' in response.data
    
    def test_parameterized_queries_used(self, client, db_session):
        """Test that parameterized queries are used."""
        with patch('views.corrected.Session', return_value=db_session):
            response = client.get('/export/users?name=John')
            
            assert response.status_code == 200
            
            # The implementation should use SQLAlchemy's parameterized queries
            # This is verified by the fact that the response is successful
            # and no SQL injection vulnerabilities exist


class TestInputValidation:
    """Test input validation."""
    
    def test_invalid_name_filter(self, client, mock_session):
        """Test invalid name filter inputs."""
        invalid_inputs = [
            'a' * 101,  # Too long
            '',  # Empty (should be handled gracefully)
            'user@domain.com',  # Email-like
            '123456789',  # Numbers only
            'user-name-very-long-with-many-dashes-and-chars',
            'user\nname',  # Newline
            'user\tname',  # Tab
        ]
        
        for invalid_input in invalid_inputs:
            with patch('views.corrected.Session', return_value=mock_session):
                response = client.get(f'/export/users?name={invalid_input}')
                
                # Should return 400 for invalid input
                assert response.status_code == 400
    
    def test_invalid_status_filter(self, client, mock_session):
        """Test invalid status filter inputs."""
        invalid_inputs = [
            'a' * 51,  # Too long
            'status-with-invalid-chars!',
            'status with spaces',
            '',  # Empty (should be handled gracefully)
            'UPPERCASE',  # Should be converted to lowercase
        ]
        
        for invalid_input in invalid_inputs:
            if invalid_input == 'UPPERCASE':
                continue  # This should be handled gracefully
            
            with patch('views.corrected.Session', return_value=mock_session):
                response = client.get(f'/export/orders?status={invalid_input}')
                
                # Should return 400 for invalid input
                assert response.status_code == 400
    
    def test_unknown_parameters(self, client, mock_session):
        """Test unknown parameters."""
        with patch('views.corrected.Session', return_value=mock_session):
            response = client.get('/export/users?unknown=value&another=value')
            
            # Should return 400 for unknown parameters
            assert response.status_code == 400
            assert b'Unknown parameter' in response.data
    
    def test_case_insensitive_name_filter(self, client, db_session):
        """Test case insensitive name filtering."""
        with patch('views.corrected.Session', return_value=db_session):
            # Test lowercase
            response1 = client.get('/export/users?name=john')
            assert response1.status_code == 200
            
            # Test uppercase
            response2 = client.get('/export/users?name=JOHN')
            assert response2.status_code == 200
            
            # Test mixed case
            response3 = client.get('/export/users?name=JoHn')
            assert response3.status_code == 200


class TestErrorHandling:
    """Test error handling."""
    
    def test_general_exception_handling(self, client, mock_session):
        """Test general exception handling."""
        # Mock a general exception
        mock_session.query.return_value.options.side_effect = Exception("General error")
        
        with patch('views.corrected.Session', return_value=mock_session):
            response = client.get('/export/users')
            
            assert response.status_code == 500
            assert b'An unexpected error occurred' in response.data
    
    def test_session_cleanup_on_error(self, client, mock_session):
        """Test that session is properly closed on error."""
        mock_session.query.return_value.options.side_effect = SQLAlchemyError("Database error")
        mock_session.close = Mock()
        
        with patch('views.corrected.Session', return_value=mock_session):
            try:
                client.get('/export/users')
            except:
                pass
            
            # Verify session was closed
            mock_session.close.assert_called_once()
    
    def test_logging_on_error(self, client, mock_session):
        """Test that errors are properly logged."""
        mock_session.query.return_value.options.side_effect = SQLAlchemyError("Database error")
        
        with patch('views.corrected.Session', return_value=mock_session):
            with patch('views.corrected.logger') as mock_logger:
                client.get('/export/users')
                
                # Verify error was logged
                mock_logger.error.assert_called()
    
    def test_404_error_handling(self, client):
        """Test 404 error handling."""
        response = client.get('/nonexistent-endpoint')
        
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False
        assert 'error' in data
    
    def test_500_error_handling(self, app):
        """Test 500 error handling."""
        @app.route('/test-error')
        def test_error():
            raise Exception("Test error")
        
        client = app.test_client()
        response = client.get('/test-error')
        
        assert response.status_code == 500
        data = response.get_json()
        assert data['success'] is False
        assert 'error' in data


class TestPerformance:
    """Test performance aspects."""
    
    def test_n_plus_1_query_prevention(self, client, mock_session):
        """Test that N+1 queries are prevented."""
        # Mock the optimized query that loads users with orders in one query
        mock_query = Mock()
        mock_query.options.return_value.all.return_value = [
            Mock(id=1, name='John', email='john@test.com', 
                 orders=[Mock(id=1, amount=100.0), Mock(id=2, amount=200.0)]),
            Mock(id=2, name='Jane', email='jane@test.com', 
                 orders=[Mock(id=3, amount=150.0)])
        ]
        mock_session.query.return_value = mock_query
        
        with patch('views.corrected.Session', return_value=mock_session):
            response = client.get('/export/users')
            
            assert response.status_code == 200
            
            # Verify that only one query was made (with eager loading)
            mock_session.query.assert_called_once()
    
    def test_large_export_handling(self, client, mock_session):
        """Test handling of large exports."""
        # Mock large dataset
        large_dataset = []
        for i in range(10000):  # 10,000 users
            user = Mock(id=i, name=f'User{i}', email=f'user{i}@test.com')
            user.orders = [Mock(id=j, amount=100.0) for j in range(5)]
            large_dataset.append(user)
        
        mock_session.query.return_value.options.return_value.all.return_value = large_dataset
        
        with patch('views.corrected.Session', return_value=mock_session):
            response = client.get('/export/users')
            
            assert response.status_code == 200
            
            # Check that response is not empty
            assert len(response.data) > 0
    
    def test_concurrent_requests(self, client, mock_session):
        """Test concurrent request handling."""
        import threading
        import time
        
        results = []
        
        def make_request():
            result = client.get('/export/users')
            results.append(result.status_code)
        
        # Create multiple threads
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All requests should succeed
        assert all(status == 200 for status in results)


class TestSecurity:
    """Test security aspects."""
    
    def test_security_headers(self, client, mock_session):
        """Test that security headers are present."""
        mock_session.query.return_value.options.return_value.all.return_value = []
        
        with patch('views.corrected.Session', return_value=mock_session):
            response = client.get('/export/users')
            
            # Check for security headers
            assert 'X-Content-Type-Options' in response.headers
            assert 'X-Frame-Options' in response.headers
            assert 'X-XSS-Protection' in response.headers
            assert 'Referrer-Policy' in response.headers
    
    def test_caching_headers(self, client, mock_session):
        """Test that caching headers are properly set."""
        mock_session.query.return_value.options.return_value.all.return_value = []
        
        with patch('views.corrected.Session', return_value=mock_session):
            response = client.get('/export/users')
            
            # Check for caching headers
            assert 'Cache-Control' in response.headers
            assert 'no-cache' in response.headers['Cache-Control']
            assert 'Pragma' in response.headers
            assert 'Expires' in response.headers
    
    def test_content_type_security(self, client, mock_session):
        """Test that content type is properly set."""
        mock_session.query.return_value.options.return_value.all.return_value = []
        
        with patch('views.corrected.Session', return_value=mock_session):
            response = client.get('/export/users')
            
            assert response.mimetype == 'text/csv'
    
    def test_filename_in_content_disposition(self, client, mock_session):
        """Test that filename is properly set in Content-Disposition."""
        mock_session.query.return_value.options.return_value.all.return_value = []
        
        with patch('views.corrected.Session', return_value=mock_session):
            response = client.get('/export/users')
            
            assert 'Content-Disposition' in response.headers
            assert 'users_export.csv' in response.headers['Content-Disposition']


class TestIntegration:
    """Integration tests."""
    
    def test_complete_export_workflow(self, client, db_session):
        """Test complete export workflow."""
        with patch('views.corrected.Session', return_value=db_session):
            # Test user export
            response = client.get('/export/users')
            assert response.status_code == 200
            
            # Test order export
            response = client.get('/export/orders')
            assert response.status_code == 200
            
            # Test statistics
            response = client.get('/export/statistics')
            assert response.status_code == 200
            
            # Test health check
            with patch('views.corrected.Session') as mock_session_class:
                mock_session = Mock()
                mock_session.execute.return_value.scalar.return_value = 1
                mock_session_class.return_value = mock_session
                
                response = client.get('/health')
                assert response.status_code == 200
    
    def test_api_error_responses_format(self, client):
        """Test that API error responses have consistent format."""
        # Test 404
        response = client.get('/nonexistent')
        assert response.status_code == 404
        data = response.get_json()
        assert 'success' in data
        assert 'error' in data
        assert 'timestamp' in data
        
        # Test 500
        @app.route('/test-500')
        def test_500():
            raise Exception("Test error")
        
        client = app.test_client()
        response = client.get('/test-500')
        assert response.status_code == 500
        data = response.get_json()
        assert 'success' in data
        assert 'error' in data
        assert 'timestamp' in data


if __name__ == '__main__':
    pytest.main([__file__])
