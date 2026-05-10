"""
Asynchronous client for the ML Scoring SDK.

Provides a clean async interface for interacting with the ML scoring API
with automatic retry, error handling, and type safety.
"""

import asyncio
import logging
from typing import List, Dict, Optional, Union
from datetime import datetime

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .models import (
    ScoringRequest, 
    ScoringResponse, 
    BatchScoringRequest, 
    BatchScoringResponse, 
    HealthResponse
)
from .exceptions import (
    ScoringAPIError,
    RateLimitError,
    ModelNotFoundError,
    AuthenticationError,
    ValidationError,
    ServerError,
    NetworkError,
    TimeoutError,
    STATUS_CODE_EXCEPTIONS
)

logger = logging.getLogger(__name__)


class AsyncScoringClient:
    """
    Asynchronous client for ML Scoring API.
    
    Features:
    - Automatic retry with exponential backoff
    - Structured error handling
    - Type validation with Pydantic
    - Request/response logging
    - Async context manager support
    """
    
    def __init__(
        self, 
        base_url: str, 
        api_key: str, 
        timeout: int = 10,
        max_retries: int = 3,
        retry_delay_multiplier: float = 1.0,
        retry_delay_min: float = 2.0,
        retry_delay_max: float = 10.0
    ):
        """
        Initialize the async scoring client.
        
        Args:
            base_url: Base URL of the ML scoring API
            api_key: API key for authentication
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            retry_delay_multiplier: Multiplier for exponential backoff
            retry_delay_min: Minimum delay between retries
            retry_delay_max: Maximum delay between retries
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay_multiplier = retry_delay_multiplier
        self.retry_delay_min = retry_delay_min
        self.retry_delay_max = retry_delay_max
        
        # Initialize HTTP client
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "X-API-Key": self.api_key,
                "User-Agent": "ml-scoring-sdk/1.0.0",
                "Content-Type": "application/json"
            },
            timeout=httpx.Timeout(timeout)
        )
        
        logger.info(f"Initialized AsyncScoringClient for {self.base_url}")
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
        logger.debug("AsyncScoringClient closed")
    
    def _handle_response(self, response: httpx.Response) -> Dict[str, any]:
        """
        Handle HTTP response and raise appropriate exceptions.
        
        Args:
            response: HTTP response object
            
        Returns:
            Response data as dictionary
            
        Raises:
            ScoringAPIError: For API errors
            NetworkError: For network-related errors
        """
        try:
            response_data = response.json() if response.content else {}
        except Exception:
            response_data = {}
        
        # Add response headers to response data for error handling
        if hasattr(response, 'headers'):
            response_data['headers'] = dict(response.headers)
        
        if response.status_code >= 400:
            from .exceptions import raise_exception_from_status_code
            raise_exception_from_status_code(
                response.status_code,
                response_data.get('message', f"HTTP {response.status_code}"),
                response_data
            )
        
        return response_data
    
    async def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        **kwargs
    ) -> httpx.Response:
        """
        Make HTTP request with error handling.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            **kwargs: Additional arguments for httpx
            
        Returns:
            HTTP response object
            
        Raises:
            NetworkError: For network-related errors
            TimeoutError: For timeout errors
        """
        try:
            response = await self.client.request(method, endpoint, **kwargs)
            return response
        except httpx.TimeoutException as e:
            logger.error(f"Request timeout: {e}")
            raise TimeoutError(f"Request timeout after {self.timeout}s") from e
        except httpx.NetworkError as e:
            logger.error(f"Network error: {e}")
            raise NetworkError(f"Network error: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error during request: {e}")
            raise ScoringAPIError(f"Unexpected error: {e}") from e
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((ServerError, NetworkError, TimeoutError)),
        before_sleep=lambda retry_state: logger.warning(
            f"Retrying request (attempt {retry_state.attempt_number}/3) "
            f"after {retry_state.next_action.sleep} seconds..."
        )
    )
    async def score(self, features: Union[Dict[str, float], ScoringRequest]) -> ScoringResponse:
        """
        Score a single set of features asynchronously.
        
        Args:
            features: Feature dictionary or ScoringRequest object
            
        Returns:
            ScoringResponse object with prediction results
            
        Raises:
            ValidationError: If features are invalid
            ModelNotFoundError: If model is not found
            RateLimitError: If rate limit is exceeded
            AuthenticationError: If authentication fails
            ServerError: If server error occurs
        """
        # Convert to ScoringRequest if needed
        if isinstance(features, dict):
            request_data = ScoringRequest(features=features)
        else:
            request_data = features
        
        logger.debug(f"Async scoring request: {request_data.features}")
        
        # Make request
        response = await self._make_request(
            "POST", 
            "/v1/score",
            json=request_data.dict(exclude_unset=True)
        )
        
        # Handle response
        response_data = self._handle_response(response)
        
        # Parse response
        scoring_response = ScoringResponse(**response_data)
        
        logger.debug(f"Async scoring response: score={scoring_response.score}")
        
        return scoring_response
    
    async def batch_score(
        self, 
        feature_list: List[Union[Dict[str, float], ScoringRequest]]
    ) -> BatchScoringResponse:
        """
        Score multiple feature sets in a single request asynchronously.
        
        Args:
            feature_list: List of feature dictionaries or ScoringRequest objects
            
        Returns:
            BatchScoringResponse with all results
            
        Raises:
            ValidationError: If any features are invalid
            ModelNotFoundError: If model is not found
            RateLimitError: If rate limit is exceeded
            AuthenticationError: If authentication fails
            ServerError: If server error occurs
        """
        # Convert to ScoringRequest objects if needed
        requests = []
        for features in feature_list:
            if isinstance(features, dict):
                requests.append(ScoringRequest(features=features))
            else:
                requests.append(features)
        
        batch_request = BatchScoringRequest(requests=requests)
        
        logger.debug(f"Async batch scoring request: {len(requests)} items")
        
        # Make request
        response = await self._make_request(
            "POST",
            "/v1/batch-score",
            json=batch_request.dict()
        )
        
        # Handle response
        response_data = self._handle_response(response)
        
        # Parse response
        batch_response = BatchScoringResponse(**response_data)
        
        logger.debug(f"Async batch scoring response: {batch_response.total_processed} items processed")
        
        return batch_response
    
    async def concurrent_batch_score(
        self, 
        feature_list: List[Union[Dict[str, float], ScoringRequest]],
        max_concurrency: int = 10
    ) -> List[ScoringResponse]:
        """
        Score multiple feature sets concurrently using individual requests.
        
        This method is useful when you want to process multiple scoring requests
        in parallel but maintain individual request/response semantics.
        
        Args:
            feature_list: List of feature dictionaries or ScoringRequest objects
            max_concurrency: Maximum number of concurrent requests
            
        Returns:
            List of ScoringResponse objects
            
        Raises:
            ValidationError: If any features are invalid
            ModelNotFoundError: If model is not found
            RateLimitError: If rate limit is exceeded
            AuthenticationError: If authentication fails
            ServerError: If server error occurs
        """
        logger.debug(f"Concurrent batch scoring request: {len(feature_list)} items, max_concurrency={max_concurrency}")
        
        # Create semaphore to limit concurrency
        semaphore = asyncio.Semaphore(max_concurrency)
        
        async def score_single(features):
            async with semaphore:
                return await self.score(features)
        
        # Execute all requests concurrently
        tasks = [score_single(features) for features in feature_list]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions in responses
        results = []
        for i, response in enumerate(responses):
            if isinstance(response, Exception):
                logger.error(f"Error in concurrent request {i}: {response}")
                raise response
            results.append(response)
        
        logger.debug(f"Concurrent batch scoring completed: {len(results)} responses")
        
        return results
    
    async def health(self) -> HealthResponse:
        """
        Check the health of the ML scoring service asynchronously.
        
        Returns:
            HealthResponse with service status
            
        Raises:
            NetworkError: If service is unreachable
            ServerError: If service is unhealthy
        """
        logger.debug("Async health check request")
        
        # Make request
        response = await self._make_request("GET", "/v1/health")
        
        # Handle response
        response_data = self._handle_response(response)
        
        # Parse response
        health_response = HealthResponse(**response_data)
        
        logger.debug(f"Async health check response: status={health_response.status}")
        
        return health_response
    
    async def get_model_info(self, model_id: Optional[str] = None) -> Dict[str, any]:
        """
        Get information about available models or a specific model asynchronously.
        
        Args:
            model_id: Optional specific model ID to query
            
        Returns:
            Dictionary with model information
            
        Raises:
            ModelNotFoundError: If model is not found
            AuthenticationError: If authentication fails
            ServerError: If server error occurs
        """
        endpoint = "/v1/models"
        if model_id:
            endpoint = f"/v1/models/{model_id}"
        
        logger.debug(f"Async model info request: {endpoint}")
        
        # Make request
        response = await self._make_request("GET", endpoint)
        
        # Handle response
        response_data = self._handle_response(response)
        
        return response_data
    
    def __repr__(self) -> str:
        """String representation of the client."""
        return f"AsyncScoringClient(base_url='{self.base_url}', timeout={self.timeout})"
