from typing import List, Dict, Optional
import httpx
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

class ScoringRequest(BaseModel):
    features: Dict[str, float]

class ScoringResponse(BaseModel):
    score: float
    model_version: str

class ScoringClient:
    def __init__(self, base_url: str, api_key: str, timeout: int = 10):
        self.client = httpx.Client(
            base_url=base_url,
            headers={"X-API-Key": api_key},
            timeout=timeout
        )

    # Task 3: Automatic Retry with Exponential Backoff
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def score(self, features: Dict[str, float]) -> ScoringResponse:
        response = self.client.post("/v1/score", json=features)
        return self._handle_response(response)

    def _handle_response(self, response: httpx.Response):
        # Task 4: Map status codes to Custom Exceptions
        if response.status_code == 429:
            raise RateLimitError("Too many requests")
        if response.status_code == 404:
            raise ModelNotFoundError("Model not found")
        response.raise_for_status()
        return ScoringResponse(**response.json())