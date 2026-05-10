"""
Mock client for the ML Scoring SDK.

Provides a test double that accepts pre-configured responses without network calls.
Used for testing and development purposes.
"""

import logging
from typing import List, Dict, Optional, Union, Callable, Any
from datetime import datetime
import asyncio

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
    TimeoutError
)

logger = logging.getLogger(__name__)


class MockScoringClient:
    """
    Mock client for ML Scoring API testing.
    
    Features:
    - Pre-configured responses for different scenarios
    - Configurable delays and errors
    - Request logging and validation
    - Both sync and async interface compatibility
    """
    
    def __init__(
        self,
        base_url: str = "http://mock-api.example.com",
        api_key: str = "mock-api-key",
        timeout: int = 10,
        default_score: float = 0.5,
        default_latency: float = 0.1
    ):
        """
        Initialize the mock scoring client.
        
        Args:
            base_url: Mock base URL (for logging purposes)
            api_key: Mock API key (for logging purposes)
            timeout: Mock timeout (for logging purposes)
            default_score: Default score to return when no specific response configured
            default_latency: Default simulated latency in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.default_score = default_score
        self.default_latency = default_latency
        
        # Pre-configured responses
        self._score_responses: Dict[str, ScoringResponse] = {}
        self._batch_responses: Dict[str, BatchScoringResponse] = {}
        self._health_response: Optional[HealthResponse] = None
        self._model_info: Dict[str, Dict[str, Any]] = {}
        
        # Error simulation
        self._error_config: Dict[str, Dict[str, Any]] = {}
        
        # Request tracking
        self._request_log: List[Dict[str, Any]] = []
        
        # Custom handlers
        self._score_handler: Optional[Callable] = None
        self._batch_handler: Optional[Callable] = None
        self._health_handler: Optional[Callable] = None
        
        logger.info(f"Initialized MockScoringClient for {self.base_url}")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.aclose()
    
    def close(self):
        """Close the mock client."""
        logger.debug("MockScoringClient closed")
    
    async def aclose(self):
        """Async close the mock client."""
        logger.debug("MockScoringClient async closed")
    
    def configure_score_response(
        self, 
        key: str, 
        response: ScoringResponse,
        latency: Optional[float] = None
    ):
        """
        Configure a specific score response.
        
        Args:
            key: Key to identify this response (e.g., based on features)
            response: ScoringResponse to return
            latency: Optional simulated latency in seconds
        """
        self._score_responses[key] = response
        if latency is not None:
            self._error_config[f"score_latency_{key}"] = {"latency": latency}
    
    def configure_batch_response(
        self, 
        key: str, 
        response: BatchScoringResponse,
        latency: Optional[float] = None
    ):
        """
        Configure a specific batch response.
        
        Args:
            key: Key to identify this response
            response: BatchScoringResponse to return
            latency: Optional simulated latency in seconds
        """
        self._batch_responses[key] = response
        if latency is not None:
            self._error_config[f"batch_latency_{key}"] = {"latency": latency}
    
    def configure_health_response(
        self, 
        response: HealthResponse,
        latency: Optional[float] = None
    ):
        """
        Configure health check response.
        
        Args:
            response: HealthResponse to return
            latency: Optional simulated latency in seconds
        """
        self._health_response = response
        if latency is not None:
            self._error_config["health_latency"] = {"latency": latency}
    
    def configure_model_info(
        self, 
        model_id: str, 
        info: Dict[str, Any],
        latency: Optional[float] = None
    ):
        """
        Configure model info response.
        
        Args:
            model_id: Model ID
            info: Model information dictionary
            latency: Optional simulated latency in seconds
        """
        self._model_info[model_id] = info
        if latency is not None:
            self._error_config[f"model_info_latency_{model_id}"] = {"latency": latency}
    
    def configure_error(
        self, 
        method: str, 
        error: Exception,
        probability: float = 1.0,
        latency: Optional[float] = None
    ):
        """
        Configure error simulation.
        
        Args:
            method: Method name (e.g., 'score', 'batch_score', 'health')
            error: Exception to raise
            probability: Probability of raising this error (0.0-1.0)
            latency: Optional simulated latency before raising error
        """
        import random
        self._error_config[method] = {
            "error": error,
            "probability": probability,
            "latency": latency,
            "random": random.Random()
        }
    
    def set_score_handler(self, handler: Callable):
        """Set custom handler for score requests."""
        self._score_handler = handler
    
    def set_batch_handler(self, handler: Callable):
        """Set custom handler for batch requests."""
        self._batch_handler = handler
    
    def set_health_handler(self, handler: Callable):
        """Set custom handler for health requests."""
        self._health_handler = handler
    
    def _log_request(self, method: str, data: Dict[str, Any]):
        """Log request for debugging and testing."""
        request_info = {
            "method": method,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data
        }
        self._request_log.append(request_info)
        logger.debug(f"Mock request logged: {method}")
    
    def _get_request_key(self, features: Dict[str, float]) -> str:
        """Generate a key for feature-based response lookup."""
        # Sort features for consistent key generation
        sorted_features = sorted(features.items())
        return str(sorted_features)
    
    async def _simulate_latency(self, latency_key: Optional[str] = None):
        """Simulate network latency."""
        latency = self.default_latency
        
        if latency_key and latency_key in self._error_config:
            latency = self._error_config[latency_key]["latency"]
        
        if latency > 0:
            await asyncio.sleep(latency)
    
    def _check_error(self, method: str):
        """Check if we should simulate an error."""
        if method in self._error_config:
            config = self._error_config[method]
            if config["random"].random() < config["probability"]:
                raise config["error"]
    
    def score(self, features: Union[Dict[str, float], ScoringRequest]) -> ScoringResponse:
        """
        Mock score method (sync interface).
        
        Args:
            features: Feature dictionary or ScoringRequest object
            
        Returns:
            ScoringResponse object
        """
        return asyncio.run(self.async_score(features))
    
    async def async_score(self, features: Union[Dict[str, float], ScoringRequest]) -> ScoringResponse:
        """
        Mock score method (async interface).
        
        Args:
            features: Feature dictionary or ScoringRequest object
            
        Returns:
            ScoringResponse object
        """
        # Convert to ScoringRequest if needed
        if isinstance(features, dict):
            request_data = ScoringRequest(features=features)
        else:
            request_data = features
        
        self._log_request("score", {"features": request_data.features})
        
        # Check for custom handler
        if self._score_handler:
            result = self._score_handler(request_data)
            if asyncio.iscoroutine(result):
                return await result
            return result
        
        # Check for error simulation
        self._check_error("score")
        
        # Simulate latency
        await self._simulate_latency("score_latency")
        
        # Look for pre-configured response
        key = self._get_request_key(request_data.features)
        if key in self._score_responses:
            return self._score_responses[key]
        
        # Return default response
        return ScoringResponse(
            score=self.default_score,
            confidence=0.95,
            model_id="mock-model",
            timestamp=datetime.utcnow(),
            features=request_data.features
        )
    
    def batch_score(
        self, 
        feature_list: List[Union[Dict[str, float], ScoringRequest]]
    ) -> BatchScoringResponse:
        """
        Mock batch score method (sync interface).
        
        Args:
            feature_list: List of feature dictionaries or ScoringRequest objects
            
        Returns:
            BatchScoringResponse object
        """
        return asyncio.run(self.async_batch_score(feature_list))
    
    async def async_batch_score(
        self, 
        feature_list: List[Union[Dict[str, float], ScoringRequest]]
    ) -> BatchScoringResponse:
        """
        Mock batch score method (async interface).
        
        Args:
            feature_list: List of feature dictionaries or ScoringRequest objects
            
        Returns:
            BatchScoringResponse object
        """
        # Convert to ScoringRequest objects if needed
        requests = []
        for features in feature_list:
            if isinstance(features, dict):
                requests.append(ScoringRequest(features=features))
            else:
                requests.append(features)
        
        self._log_request("batch_score", {"requests": len(requests)})
        
        # Check for custom handler
        if self._batch_handler:
            result = self._batch_handler(requests)
            if asyncio.iscoroutine(result):
                return await result
            return result
        
        # Check for error simulation
        self._check_error("batch_score")
        
        # Simulate latency
        await self._simulate_latency("batch_latency")
        
        # Look for pre-configured response
        key = f"batch_{len(requests)}"
        if key in self._batch_responses:
            return self._batch_responses[key]
        
        # Generate default responses
        responses = []
        for request in requests:
            response = await self.async_score(request)
            responses.append(response)
        
        return BatchScoringResponse(
            responses=responses,
            total_processed=len(responses),
            total_successful=len(responses),
            total_failed=0,
            timestamp=datetime.utcnow()
        )
    
    def health(self) -> HealthResponse:
        """
        Mock health method (sync interface).
        
        Returns:
            HealthResponse object
        """
        return asyncio.run(self.async_health())
    
    async def async_health(self) -> HealthResponse:
        """
        Mock health method (async interface).
        
        Returns:
            HealthResponse object
        """
        self._log_request("health", {})
        
        # Check for custom handler
        if self._health_handler:
            result = self._health_handler()
            if asyncio.iscoroutine(result):
                return await result
            return result
        
        # Check for error simulation
        self._check_error("health")
        
        # Simulate latency
        await self._simulate_latency("health_latency")
        
        # Return configured or default response
        if self._health_response:
            return self._health_response
        
        return HealthResponse(
            status="healthy",
            version="1.0.0",
            timestamp=datetime.utcnow(),
            uptime_seconds=3600
        )
    
    def get_model_info(self, model_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Mock model info method (sync interface).
        
        Args:
            model_id: Optional specific model ID to query
            
        Returns:
            Dictionary with model information
        """
        return asyncio.run(self.async_get_model_info(model_id))
    
    async def async_get_model_info(self, model_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Mock model info method (async interface).
        
        Args:
            model_id: Optional specific model ID to query
            
        Returns:
            Dictionary with model information
        """
        self._log_request("get_model_info", {"model_id": model_id})
        
        # Check for error simulation
        self._check_error("get_model_info")
        
        # Simulate latency
        latency_key = f"model_info_latency_{model_id}" if model_id else None
        await self._simulate_latency(latency_key)
        
        # Return configured or default response
        if model_id and model_id in self._model_info:
            return self._model_info[model_id]
        
        if model_id:
            raise ModelNotFoundError(f"Model {model_id} not found")
        
        # Return list of available models
        return {
            "models": [
                {
                    "id": "mock-model",
                    "name": "Mock Model",
                    "version": "1.0.0",
                    "status": "active"
                }
            ]
        }
    
    def get_request_log(self) -> List[Dict[str, Any]]:
        """Get the log of all requests made to this mock client."""
        return self._request_log.copy()
    
    def clear_request_log(self):
        """Clear the request log."""
        self._request_log.clear()
    
    def reset(self):
        """Reset all configurations to defaults."""
        self._score_responses.clear()
        self._batch_responses.clear()
        self._health_response = None
        self._model_info.clear()
        self._error_config.clear()
        self._request_log.clear()
        self._score_handler = None
        self._batch_handler = None
        self._health_handler = None
        logger.debug("MockScoringClient reset to defaults")
    
    def __repr__(self) -> str:
        """String representation of the mock client."""
        return f"MockScoringClient(base_url='{self.base_url}', default_score={self.default_score})"
