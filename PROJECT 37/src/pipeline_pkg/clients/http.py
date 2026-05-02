"""
HTTP client for external API communication.

This module provides a robust HTTP client with retry logic,
timeout handling, and response logging.
"""

import json
import time
from typing import Any, Dict, Optional

import requests
import structlog
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from ..models import APIResponse


class HTTPClient:
    """
    A robust HTTP client with retry logic and comprehensive logging.
    """
    
    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: int = 30,
        max_retries: int = 3,
        backoff_factor: float = 1.0,
    ) -> None:
        """
        Initialize the HTTP client.
        
        Args:
            base_url: Base URL for API requests
            api_key: API key for authentication
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            backoff_factor: Backoff factor for retries
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.logger = structlog.get_logger(__name__)
        
        # Setup session with retry strategy
        self.session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT", "DELETE"],
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Set default headers
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Pipeline-Package/1.0",
        })
    
    def _build_url(self, endpoint: str) -> str:
        """Build full URL from endpoint."""
        return f"{self.base_url}/{endpoint.lstrip('/')}"
    
    def _log_response(
        self,
        endpoint: str,
        request_data: Optional[Dict[str, Any]],
        response: requests.Response,
        response_time: float,
    ) -> APIResponse:
        """Log API response and return APIResponse model."""
        try:
            response_data = response.json() if response.content else None
        except json.JSONDecodeError:
            response_data = {"raw_content": response.text}
        
        api_response = APIResponse(
            endpoint=endpoint,
            request_data=request_data,
            response_data=response_data,
            status_code=response.status_code,
            response_time=response_time,
        )
        
        # Log the response
        log_data = {
            "endpoint": endpoint,
            "status_code": response.status_code,
            "response_time": response_time,
            "success": response.ok,
        }
        
        if response.ok:
            self.logger.info("API request successful", **log_data)
        else:
            self.logger.warning("API request failed", **log_data)
        
        return api_response
    
    def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> tuple[Dict[str, Any], APIResponse]:
        """
        Make a GET request.
        
        Args:
            endpoint: API endpoint
            params: Query parameters
            headers: Additional headers
            
        Returns:
            Tuple of (response_data, api_response_log)
        """
        url = self._build_url(endpoint)
        request_headers = headers.copy() if headers else {}
        
        start_time = time.time()
        
        try:
            response = self.session.get(
                url,
                params=params,
                headers=request_headers,
                timeout=self.timeout,
            )
            response_time = time.time() - start_time
            
            # Log the response
            api_response = self._log_response(endpoint, params, response, response_time)
            
            # Return response data
            try:
                data = response.json()
            except json.JSONDecodeError:
                data = {"error": "Invalid JSON response", "raw_content": response.text}
            
            return data, api_response
            
        except requests.exceptions.RequestException as e:
            response_time = time.time() - start_time
            self.logger.error(
                "GET request failed",
                endpoint=endpoint,
                params=params,
                error=str(e),
                response_time=response_time,
            )
            
            # Create error response
            api_response = APIResponse(
                endpoint=endpoint,
                request_data=params,
                response_data=None,
                status_code=0,
                response_time=response_time,
            )
            
            raise
    
    def post(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> tuple[Dict[str, Any], APIResponse]:
        """
        Make a POST request.
        
        Args:
            endpoint: API endpoint
            data: Form data
            json_data: JSON data
            headers: Additional headers
            
        Returns:
            Tuple of (response_data, api_response_log)
        """
        url = self._build_url(endpoint)
        request_headers = headers.copy() if headers else {}
        
        start_time = time.time()
        
        try:
            response = self.session.post(
                url,
                data=data,
                json=json_data,
                headers=request_headers,
                timeout=self.timeout,
            )
            response_time = time.time() - start_time
            
            # Log the response
            api_response = self._log_response(
                endpoint, json_data or data, response, response_time
            )
            
            # Return response data
            try:
                response_data = response.json()
            except json.JSONDecodeError:
                response_data = {"error": "Invalid JSON response", "raw_content": response.text}
            
            return response_data, api_response
            
        except requests.exceptions.RequestException as e:
            response_time = time.time() - start_time
            self.logger.error(
                "POST request failed",
                endpoint=endpoint,
                data=data,
                json_data=json_data,
                error=str(e),
                response_time=response_time,
            )
            
            # Create error response
            api_response = APIResponse(
                endpoint=endpoint,
                request_data=json_data or data,
                response_data=None,
                status_code=0,
                response_time=response_time,
            )
            
            raise
    
    def close(self) -> None:
        """Close the HTTP session."""
        if self.session:
            self.session.close()
            self.logger.info("HTTP client session closed")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
