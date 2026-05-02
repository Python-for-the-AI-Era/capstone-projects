"""
Tests for HTTP client.

This module tests the HTTP client functionality including
retry logic, error handling, and response logging.
"""

import json
from unittest.mock import Mock, patch
from typing import Dict, Any

import pytest
import requests

from pipeline_pkg.clients.http import HTTPClient
from pipeline_pkg.models import APIResponse


class TestHTTPClient:
    """Test cases for HTTPClient."""
    
    def setup_method(self) -> None:
        """Setup test fixtures."""
        self.client = HTTPClient(
            base_url="https://api.example.com",
            api_key="test-key",
            timeout=10,
            max_retries=2,
            backoff_factor=0.1,
        )
    
    def teardown_method(self) -> None:
        """Cleanup after tests."""
        if self.client:
            self.client.close()
    
    def test_initialization(self) -> None:
        """Test HTTPClient initialization."""
        assert self.client.base_url == "https://api.example.com"
        assert self.client.api_key == "test-key"
        assert self.client.timeout == 10
        assert self.client.max_retries == 2
        assert self.client.backoff_factor == 0.1
        
        # Check default headers
        assert "Authorization" in self.client.session.headers
        assert self.client.session.headers["Authorization"] == "Bearer test-key"
        assert self.client.session.headers["Content-Type"] == "application/json"
    
    def test_build_url(self) -> None:
        """Test URL building."""
        # Test with leading slash
        url = self.client._build_url("/users")
        assert url == "https://api.example.com/users"
        
        # Test without leading slash
        url = self.client._build_url("products")
        assert url == "https://api.example.com/products"
        
        # Test with base URL ending in slash
        client = HTTPClient("https://api.example.com/", "test-key")
        url = client._build_url("/users")
        assert url == "https://api.example.com/users"
    
    @patch("pipeline_pkg.clients.http.requests.Session.get")
    def test_get_success(self, mock_get: Mock) -> None:
        """Test successful GET request."""
        # Mock response
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": 1, "name": "Test"}
        mock_response.text = '{"id": 1, "name": "Test"}'
        mock_get.return_value = mock_response
        
        # Make request
        data, api_response = self.client.get("/users")
        
        # Verify request
        mock_get.assert_called_once_with(
            "https://api.example.com/users",
            params=None,
            headers=None,
            timeout=10,
        )
        
        # Verify response
        assert data == {"id": 1, "name": "Test"}
        assert api_response.endpoint == "/users"
        assert api_response.status_code == 200
        assert api_response.response_data == {"id": 1, "name": "Test"}
        assert api_response.response_time > 0
    
    @patch("pipeline_pkg.clients.http.requests.Session.get")
    def test_get_with_params(self, mock_get: Mock) -> None:
        """Test GET request with parameters."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        mock_response.text = '{"results": []}'
        mock_get.return_value = mock_response
        
        params = {"page": 1, "limit": 10}
        data, api_response = self.client.get("/users", params=params)
        
        mock_get.assert_called_once_with(
            "https://api.example.com/users",
            params=params,
            headers=None,
            timeout=10,
        )
        
        assert api_response.request_data == params
    
    @patch("pipeline_pkg.clients.http.requests.Session.get")
    def test_get_with_headers(self, mock_get: Mock) -> None:
        """Test GET request with custom headers."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        mock_response.text = '{"results": []}'
        mock_get.return_value = mock_response
        
        headers = {"X-Custom-Header": "value"}
        data, api_response = self.client.get("/users", headers=headers)
        
        mock_get.assert_called_once_with(
            "https://api.example.com/users",
            params=None,
            headers=headers,
            timeout=10,
        )
    
    @patch("pipeline_pkg.clients.http.requests.Session.get")
    def test_get_api_error(self, mock_get: Mock) -> None:
        """Test GET request with API error."""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 404
        mock_response.json.return_value = {"error": "Not found"}
        mock_response.text = '{"error": "Not found"}'
        mock_get.return_value = mock_response
        
        data, api_response = self.client.get("/users")
        
        assert data == {"error": "Not found"}
        assert api_response.status_code == 404
        assert api_response.response_data == {"error": "Not found"}
    
    @patch("pipeline_pkg.clients.http.requests.Session.get")
    def test_get_invalid_json(self, mock_get: Mock) -> None:
        """Test GET request with invalid JSON response."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_response.text = "Invalid JSON response"
        mock_get.return_value = mock_response
        
        data, api_response = self.client.get("/users")
        
        assert data == {"error": "Invalid JSON response", "raw_content": "Invalid JSON response"}
        assert api_response.response_data == {"error": "Invalid JSON response", "raw_content": "Invalid JSON response"}
    
    @patch("pipeline_pkg.clients.http.requests.Session.get")
    def test_get_request_exception(self, mock_get: Mock) -> None:
        """Test GET request with request exception."""
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection failed")
        
        with pytest.raises(requests.exceptions.ConnectionError):
            self.client.get("/users")
    
    @patch("pipeline_pkg.clients.http.requests.Session.post")
    def test_post_success(self, mock_post: Mock) -> None:
        """Test successful POST request."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": 1, "created": True}
        mock_response.text = '{"id": 1, "created": True}'
        mock_post.return_value = mock_response
        
        json_data = {"name": "Test", "email": "test@example.com"}
        data, api_response = self.client.post("/users", json_data=json_data)
        
        mock_post.assert_called_once_with(
            "https://api.example.com/users",
            data=None,
            json=json_data,
            headers=None,
            timeout=10,
        )
        
        assert data == {"id": 1, "created": True}
        assert api_response.status_code == 201
        assert api_response.request_data == json_data
    
    @patch("pipeline_pkg.clients.http.requests.Session.post")
    def test_post_with_form_data(self, mock_post: Mock) -> None:
        """Test POST request with form data."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}
        mock_response.text = '{"success": True}'
        mock_post.return_value = mock_response
        
        form_data = {"username": "test", "password": "secret"}
        data, api_response = self.client.post("/login", data=form_data)
        
        mock_post.assert_called_once_with(
            "https://api.example.com/login",
            data=form_data,
            json=None,
            headers=None,
            timeout=10,
        )
        
        assert api_response.request_data == form_data
    
    @patch("pipeline_pkg.clients.http.requests.Session.post")
    def test_post_with_headers(self, mock_post: Mock) -> None:
        """Test POST request with custom headers."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}
        mock_response.text = '{"success": True}'
        mock_post.return_value = mock_response
        
        headers = {"Content-Type": "application/xml"}
        data, api_response = self.client.post("/users", headers=headers)
        
        mock_post.assert_called_once_with(
            "https://api.example.com/users",
            data=None,
            json=None,
            headers=headers,
            timeout=10,
        )
    
    def test_context_manager(self) -> None:
        """Test HTTPClient as context manager."""
        with HTTPClient("https://api.example.com", "test-key") as client:
            assert client.base_url == "https://api.example.com"
            assert client.api_key == "test-key"
    
    @patch("pipeline_pkg.clients.http.requests.Session.get")
    def test_retry_logic(self, mock_get: Mock) -> None:
        """Test retry logic on failures."""
        # First two calls fail, third succeeds
        mock_response_fail = Mock()
        mock_response_fail.ok = False
        mock_response_fail.status_code = 500
        
        mock_response_success = Mock()
        mock_response_success.ok = True
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {"success": True}
        mock_response_success.text = '{"success": True}'
        
        mock_get.side_effect = [
            mock_response_fail,
            mock_response_fail,
            mock_response_success,
        ]
        
        data, api_response = self.client.get("/users")
        
        # Should have been called 3 times (2 retries + 1 success)
        assert mock_get.call_count == 3
        assert data == {"success": True}
        assert api_response.status_code == 200
    
    @patch("pipeline_pkg.clients.http.requests.Session.get")
    def test_max_retries_exceeded(self, mock_get: Mock) -> None:
        """Test behavior when max retries are exceeded."""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 500
        mock_get.return_value = mock_response
        
        # All calls fail
        data, api_response = self.client.get("/users")
        
        # Should have been called 3 times (1 initial + 2 retries)
        assert mock_get.call_count == 3
        assert data == {"error": "Internal Server Error", "raw_content": ""}
        assert api_response.status_code == 500
