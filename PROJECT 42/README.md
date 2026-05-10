# ML Scoring SDK

A comprehensive Python SDK for interacting with ML scoring APIs, featuring both synchronous and asynchronous clients, automatic retry logic, structured error handling, and a mock client for testing.

## Features

- **Dual Client Support**: Both synchronous (`ScoringClient`) and asynchronous (`AsyncScoringClient`) clients
- **Automatic Retry**: Built-in retry logic with exponential backoff for 5xx errors using `tenacity`
- **Structured Error Handling**: Custom exception classes mapped to HTTP status codes
- **Type Safety**: Full type hints and Pydantic models for request/response validation
- **Mock Client**: `MockScoringClient` for testing without network calls
- **Context Manager Support**: Proper resource management with context managers
- **Comprehensive Logging**: Detailed request/response logging for debugging
- **Batch Processing**: Support for both single and batch scoring requests
- **Concurrent Processing**: Async client supports concurrent batch scoring

## Installation

```bash
pip install ml-scoring-sdk
```

For development with all optional dependencies:

```bash
pip install ml-scoring-sdk[dev,test,docs,examples]
```

## Quick Start

### Synchronous Client

```python
from ml_scoring_sdk import ScoringClient

# Initialize the client
client = ScoringClient(
    base_url="https://api.example.com",
    api_key="your-api-key",
    timeout=10
)

# Single scoring
features = {"age": 25, "income": 50000.0, "credit_score": 720}
result = client.score(features)
print(f"Score: {result.score}, Confidence: {result.confidence}")

# Batch scoring
features_list = [
    {"age": 25, "income": 50000.0, "credit_score": 720},
    {"age": 35, "income": 75000.0, "credit_score": 680}
]
batch_result = client.batch_score(features_list)
print(f"Processed: {batch_result.total_processed} items")

# Health check
health = client.health()
print(f"Service status: {health.status}")

# Model information
model_info = client.get_model_info("credit-risk-v2")
print(f"Model version: {model_info['version']}")
```

### Asynchronous Client

```python
import asyncio
from ml_scoring_sdk import AsyncScoringClient

async def main():
    # Initialize the async client
    client = AsyncScoringClient(
        base_url="https://api.example.com",
        api_key="your-api-key",
        timeout=10
    )
    
    try:
        # Single scoring
        features = {"age": 25, "income": 50000.0, "credit_score": 720}
        result = await client.score(features)
        print(f"Score: {result.score}, Confidence: {result.confidence}")
        
        # Concurrent batch scoring
        features_list = [
            {"age": 25, "income": 50000.0, "credit_score": 720},
            {"age": 35, "income": 75000.0, "credit_score": 680},
            {"age": 45, "income": 100000.0, "credit_score": 750}
        ]
        concurrent_results = await client.concurrent_batch_score(
            features_list, 
            max_concurrency=5
        )
        print(f"Concurrent results: {len(concurrent_results)} items")
        
    finally:
        await client.close()

# Run the async main function
asyncio.run(main())
```

### Using Context Managers

```python
# Synchronous context manager
with ScoringClient("https://api.example.com", "api-key") as client:
    result = client.score({"age": 25, "income": 50000.0})
    print(f"Score: {result.score}")

# Asynchronous context manager
async with AsyncScoringClient("https://api.example.com", "api-key") as client:
    result = await client.score({"age": 25, "income": 50000.0})
    print(f"Score: {result.score}")
```

## Mock Client for Testing

The `MockScoringClient` is perfect for unit testing and development without making actual API calls:

```python
from ml_scoring_sdk import MockScoringClient
from ml_scoring_sdk.models import ScoringResponse
from datetime import datetime

# Create mock client
mock_client = MockScoringClient(default_score=0.75)

# Configure specific responses
features = {"age": 25, "income": 50000.0}
response = ScoringResponse(
    score=0.85,
    confidence=0.95,
    model_id="test-model",
    timestamp=datetime.utcnow(),
    features=features
)

# Configure the mock to return this response for specific features
key = mock_client._get_request_key(features)
mock_client.configure_score_response(key, response)

# Use the mock client (works both sync and async)
result = mock_client.score(features)
print(f"Mock score: {result.score}")  # 0.85

# Async usage
async_result = await mock_client.async_score(features)
print(f"Async mock score: {async_result.score}")  # 0.85
```

### Error Simulation with Mock Client

```python
from ml_scoring_sdk.exceptions import RateLimitError, ValidationError

# Configure error simulation
mock_client.configure_error("score", RateLimitError("Rate limit exceeded"), probability=0.5)
mock_client.configure_error("health", ValidationError("Service unavailable"), probability=1.0)

# This will randomly raise RateLimitError 50% of the time
try:
    result = mock_client.score({"age": 25})
    print(f"Success: {result.score}")
except RateLimitError as e:
    print(f"Rate limited: {e}")

# This will always raise ValidationError
try:
    mock_client.health()
except ValidationError as e:
    print(f"Health check failed: {e}")
```

## Error Handling

The SDK provides structured error handling with specific exception types:

```python
from ml_scoring_sdk import ScoringClient
from ml_scoring_sdk.exceptions import (
    RateLimitError,
    ModelNotFoundError,
    AuthenticationError,
    ValidationError,
    ServerError,
    NetworkError,
    TimeoutError
)

client = ScoringClient("https://api.example.com", "api-key")

try:
    result = client.score({"age": 25, "income": 50000.0})
except RateLimitError as e:
    print(f"Rate limit exceeded: {e}")
    # Implement backoff and retry logic
except AuthenticationError as e:
    print(f"Authentication failed: {e}")
    # Check API key configuration
except ModelNotFoundError as e:
    print(f"Model not found: {e}")
    # Verify model ID
except ValidationError as e:
    print(f"Invalid input: {e}")
    # Check input features
except ServerError as e:
    print(f"Server error: {e}")
    # SDK will automatically retry server errors
except NetworkError as e:
    print(f"Network error: {e}")
    # SDK will automatically retry network errors
except TimeoutError as e:
    print(f"Request timeout: {e}")
    # SDK will automatically retry timeouts
```

## Advanced Configuration

### Custom Retry Settings

```python
client = ScoringClient(
    base_url="https://api.example.com",
    api_key="your-api-key",
    timeout=15,
    max_retries=5,
    retry_delay_min=1.0,
    retry_delay_max=30.0
)
```

### Model-Specific Requests

```python
from ml_scoring_sdk.models import ScoringRequest

# Create a request with specific model and version
request = ScoringRequest(
    features={"age": 25, "income": 50000.0},
    model_id="credit-risk-v2",
    version="2.1"
)

result = client.score(request)
```

### Batch Requests with Model Specification

```python
from ml_scoring_sdk.models import ScoringRequest, BatchScoringRequest

# Create individual requests
requests = [
    ScoringRequest(features={"age": 25, "income": 50000.0}),
    ScoringRequest(features={"age": 35, "income": 75000.0})
]

# Create batch request
batch_request = BatchScoringRequest(
    requests=requests,
    model_id="credit-risk-v2",
    version="2.1"
)

result = client.batch_score(batch_request.requests)
```

## API Reference

### ScoringClient

The main synchronous client for interacting with ML scoring APIs.

#### Methods

- `score(features)`: Score a single set of features
- `batch_score(feature_list)`: Score multiple feature sets
- `health()`: Check API health status
- `get_model_info(model_id=None)`: Get model information

#### Parameters

- `base_url` (str): Base URL of the ML scoring API
- `api_key` (str): API key for authentication
- `timeout` (int, optional): Request timeout in seconds (default: 10)
- `max_retries` (int, optional): Maximum retry attempts (default: 3)
- `retry_delay_min` (float, optional): Minimum retry delay (default: 2.0)
- `retry_delay_max` (float, optional): Maximum retry delay (default: 10.0)

### AsyncScoringClient

The asynchronous version of the client with all the same methods plus:

- `concurrent_batch_score(feature_list, max_concurrency=10)`: Process multiple requests concurrently

### MockScoringClient

A mock client for testing with additional configuration methods:

- `configure_score_response(key, response, latency=None)`: Configure score response
- `configure_batch_response(key, response, latency=None)`: Configure batch response
- `configure_health_response(response, latency=None)`: Configure health response
- `configure_model_info(model_id, info, latency=None)`: Configure model info
- `configure_error(method, error, probability=1.0, latency=None)`: Configure error simulation
- `set_score_handler(handler)`: Set custom score handler
- `set_batch_handler(handler)`: Set custom batch handler
- `set_health_handler(handler)`: Set custom health handler

## Data Models

### ScoringRequest

```python
class ScoringRequest(BaseModel):
    features: Dict[str, float]  # Feature dictionary
    model_id: Optional[str] = None  # Specific model ID
    version: Optional[str] = None  # Model version
```

### ScoringResponse

```python
class ScoringResponse(BaseModel):
    score: float  # Prediction score (0.0 - 1.0)
    confidence: float  # Confidence score (0.0 - 1.0)
    model_id: str  # Model ID used
    timestamp: datetime  # Response timestamp
    features: Dict[str, float]  # Original features
    explanation: Optional[str] = None  # Score explanation
    metadata: Optional[Dict[str, Any]] = None  # Additional metadata
```

### BatchScoringResponse

```python
class BatchScoringResponse(BaseModel):
    responses: List[ScoringResponse]  # Individual responses
    total_processed: int  # Total items processed
    total_successful: int  # Successful predictions
    total_failed: int  # Failed predictions
    timestamp: datetime  # Response timestamp
    errors: Optional[List[str]] = None  # Error messages
```

### HealthResponse

```python
class HealthResponse(BaseModel):
    status: str  # Service status (healthy/unhealthy/degraded)
    version: str  # API version
    timestamp: datetime  # Response timestamp
    uptime_seconds: int  # Service uptime
    details: Optional[List[str]] = None  # Additional details
```

## Exception Hierarchy

```
ScoringAPIError (base exception)
├── RateLimitError (429)
├── ModelNotFoundError (404)
├── AuthenticationError (401)
├── ValidationError (400)
├── ServerError (5xx)
├── NetworkError (network issues)
└── TimeoutError (timeouts)
```

## Development

### Setting up for Development

```bash
# Clone the repository
git clone https://github.com/company/ml-scoring-sdk.git
cd ml-scoring-sdk

# Install in development mode
pip install -e ".[dev,test]"

# Install pre-commit hooks
pre-commit install
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=ml_scoring_sdk --cov-report=html

# Run specific test categories
pytest -m unit  # Unit tests only
pytest -m integration  # Integration tests only
pytest -m "not slow"  # Skip slow tests
```

### Code Quality

```bash
# Format code
black ml_scoring_sdk tests

# Sort imports
isort ml_scoring_sdk tests

# Lint code
flake8 ml_scoring_sdk tests

# Type checking
mypy ml_scoring_sdk
```

### Building Documentation

```bash
# Install documentation dependencies
pip install -e ".[docs]"

# Build documentation
cd docs
make html

# View documentation
open _build/html/index.html
```

## Examples

### Credit Scoring Example

```python
from ml_scoring_sdk import ScoringClient

def assess_credit_risk(applicant_data):
    """Assess credit risk for an applicant."""
    client = ScoringClient(
        base_url="https://credit-api.example.com",
        api_key="credit-api-key"
    )
    
    try:
        # Prepare features
        features = {
            "age": applicant_data["age"],
            "income": applicant_data["annual_income"],
            "credit_score": applicant_data["credit_score"],
            "debt_to_income": applicant_data["debt_to_income"],
            "employment_length": applicant_data["employment_years"]
        }
        
        # Get risk score
        result = client.score(features)
        
        # Interpret results
        if result.score < 0.3:
            risk_level = "Low"
        elif result.score < 0.7:
            risk_level = "Medium"
        else:
            risk_level = "High"
        
        return {
            "risk_score": result.score,
            "confidence": result.confidence,
            "risk_level": risk_level,
            "explanation": result.explanation
        }
        
    except Exception as e:
        return {"error": str(e)}

# Example usage
applicant = {
    "age": 35,
    "annual_income": 75000.0,
    "credit_score": 720,
    "debt_to_income": 0.25,
    "employment_years": 8
}

assessment = assess_credit_risk(applicant)
print(f"Risk assessment: {assessment}")
```

### Fraud Detection Example

```python
import asyncio
from ml_scoring_sdk import AsyncScoringClient

async def detect_fraud(transactions):
    """Detect fraud in multiple transactions concurrently."""
    client = AsyncScoringClient(
        base_url="https://fraud-api.example.com",
        api_key="fraud-api-key"
    )
    
    try:
        # Convert transactions to feature dictionaries
        features_list = []
        for tx in transactions:
            features = {
                "amount": tx["amount"],
                "merchant_category": tx["merchant"]["category"],
                "location_risk": tx["location"]["risk_score"],
                "user_history_score": tx["user"]["history_score"],
                "time_of_day": tx["timestamp"].hour,
                "day_of_week": tx["timestamp"].weekday()
            }
            features_list.append(features)
        
        # Process concurrently for speed
        results = await client.concurrent_batch_score(
            features_list, 
            max_concurrency=10
        )
        
        # Analyze results
        fraud_alerts = []
        for i, (tx, result) in enumerate(zip(transactions, results)):
            if result.score > 0.8:  # High fraud probability
                fraud_alerts.append({
                    "transaction_id": tx["id"],
                    "fraud_score": result.score,
                    "confidence": result.confidence,
                    "risk_factors": result.explanation
                })
        
        return fraud_alerts
        
    finally:
        await client.close()

# Example usage
transactions = [
    {
        "id": "tx_001",
        "amount": 1000.0,
        "merchant": {"category": "electronics"},
        "location": {"risk_score": 0.3},
        "user": {"history_score": 0.9},
        "timestamp": datetime.now()
    },
    # ... more transactions
]

fraud_alerts = await detect_fraud(transactions)
print(f"Found {len(fraud_alerts)} potential fraud cases")
```

### Model Monitoring Example

```python
from ml_scoring_sdk import ScoringClient
import time

def monitor_model_health():
    """Monitor ML model health and performance."""
    client = ScoringClient(
        base_url="https://model-api.example.com",
        api_key="monitoring-key"
    )
    
    while True:
        try:
            # Check service health
            health = client.health()
            print(f"Service status: {health.status}")
            print(f"Uptime: {health.uptime_seconds}s")
            
            if health.status != "healthy":
                print(f"Service issues: {health.details}")
            
            # Get model information
            model_info = client.get_model_info("production-model")
            print(f"Model version: {model_info['version']}")
            
            # Check model performance metrics
            if "performance" in model_info:
                perf = model_info["performance"]
                print(f"Accuracy: {perf['accuracy']:.3f}")
                print(f"Precision: {perf['precision']:.3f}")
                print(f"Recall: {perf['recall']:.3f}")
            
            # Wait before next check
            time.sleep(60)  # Check every minute
            
        except Exception as e:
            print(f"Monitoring error: {e}")
            time.sleep(30)  # Wait before retrying

# Run monitoring (in production, use proper scheduling)
# monitor_model_health()
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass (`pytest`)
6. Run code quality checks (`black`, `isort`, `flake8`, `mypy`)
7. Commit your changes (`git commit -m 'Add amazing feature'`)
8. Push to the branch (`git push origin feature/amazing-feature`)
9. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- Documentation: [https://ml-scoring-sdk.readthedocs.io/](https://ml-scoring-sdk.readthedocs.io/)
- Issues: [https://github.com/company/ml-scoring-sdk/issues](https://github.com/company/ml-scoring-sdk/issues)
- Discussions: [https://github.com/company/ml-scoring-sdk/discussions](https://github.com/company/ml-scoring-sdk/discussions)

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a list of changes and version history.
