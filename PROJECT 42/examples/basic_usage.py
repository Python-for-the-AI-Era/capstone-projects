#!/usr/bin/env python3
"""
Basic usage examples for the ML Scoring SDK.

This script demonstrates the fundamental usage patterns of the SDK
including synchronous and asynchronous clients, error handling,
and the mock client for testing.
"""

import asyncio
from datetime import datetime
from ml_scoring_sdk import (
    ScoringClient,
    AsyncScoringClient,
    MockScoringClient
)
from ml_scoring_sdk.exceptions import (
    RateLimitError,
    ModelNotFoundError,
    ValidationError
)
from ml_scoring_sdk.models import ScoringResponse, HealthResponse


def basic_sync_example():
    """Basic synchronous client usage."""
    print("=== Basic Synchronous Example ===")
    
    # Initialize client (using mock for demo)
    client = MockScoringClient(
        base_url="https://api.example.com",
        api_key="demo-key",
        default_score=0.75
    )
    
    try:
        # Single scoring
        features = {"age": 25, "income": 50000.0, "credit_score": 720}
        result = client.score(features)
        
        print(f"Score: {result.score:.3f}")
        print(f"Confidence: {result.confidence:.3f}")
        print(f"Model: {result.model_id}")
        print(f"Features: {result.features}")
        
        # Batch scoring
        features_list = [
            {"age": 25, "income": 50000.0, "credit_score": 720},
            {"age": 35, "income": 75000.0, "credit_score": 680},
            {"age": 45, "income": 100000.0, "credit_score": 750}
        ]
        
        batch_result = client.batch_score(features_list)
        print(f"\nBatch Results:")
        print(f"Total processed: {batch_result.total_processed}")
        print(f"Successful: {batch_result.total_successful}")
        print(f"Failed: {batch_result.total_failed}")
        
        # Health check
        health = client.health()
        print(f"\nHealth Status: {health.status}")
        print(f"Version: {health.version}")
        print(f"Uptime: {health.uptime_seconds}s")
        
        # Model info
        model_info = client.get_model_info()
        print(f"\nAvailable Models: {len(model_info.get('models', []))}")
        
    except Exception as e:
        print(f"Error: {e}")


async def basic_async_example():
    """Basic asynchronous client usage."""
    print("\n=== Basic Asynchronous Example ===")
    
    client = AsyncScoringClient(
        base_url="https://api.example.com",
        api_key="demo-key"
    )
    
    try:
        # Single scoring
        features = {"age": 30, "income": 65000.0, "credit_score": 700}
        result = await client.score(features)
        
        print(f"Async Score: {result.score:.3f}")
        print(f"Confidence: {result.confidence:.3f}")
        
        # Concurrent batch scoring
        features_list = [
            {"age": 25, "income": 50000.0, "credit_score": 720},
            {"age": 35, "income": 75000.0, "credit_score": 680},
            {"age": 45, "income": 100000.0, "credit_score": 750},
            {"age": 55, "income": 120000.0, "credit_score": 780}
        ]
        
        concurrent_results = await client.concurrent_batch_score(
            features_list, 
            max_concurrency=2
        )
        
        print(f"\nConcurrent Results: {len(concurrent_results)} items")
        for i, result in enumerate(concurrent_results):
            print(f"  Item {i+1}: Score={result.score:.3f}, Confidence={result.confidence:.3f}")
        
        # Health check
        health = await client.health()
        print(f"\nAsync Health Status: {health.status}")
        
    except Exception as e:
        print(f"Async Error: {e}")
    finally:
        await client.close()


def context_manager_example():
    """Context manager usage example."""
    print("\n=== Context Manager Example ===")
    
    # Synchronous context manager
    with ScoringClient("https://api.example.com", "demo-key") as client:
        result = client.score({"age": 28, "income": 55000.0})
        print(f"Context Manager Score: {result.score:.3f}")
    
    # Asynchronous context manager
    async def async_context_example():
        async with AsyncScoringClient("https://api.example.com", "demo-key") as client:
            result = await client.score({"age": 32, "income": 70000.0})
            print(f"Async Context Manager Score: {result.score:.3f}")
    
    asyncio.run(async_context_example())


def error_handling_example():
    """Error handling examples."""
    print("\n=== Error Handling Example ===")
    
    client = MockScoringClient()
    
    # Configure error simulation
    client.configure_error("score", RateLimitError("Rate limit exceeded"), probability=0.3)
    client.configure_error("health", ValidationError("Service unavailable"), probability=1.0)
    
    # Try scoring with potential rate limit
    for i in range(5):
        try:
            result = client.score({"age": 25, "income": 50000.0})
            print(f"Attempt {i+1}: Success - Score: {result.score:.3f}")
        except RateLimitError as e:
            print(f"Attempt {i+1}: Rate limited - {e}")
        except Exception as e:
            print(f"Attempt {i+1}: Other error - {e}")
    
    # Health check that always fails
    try:
        client.health()
    except ValidationError as e:
        print(f"Health check failed as expected: {e}")


def mock_client_configuration_example():
    """Mock client configuration examples."""
    print("\n=== Mock Client Configuration Example ===")
    
    client = MockScoringClient(default_score=0.6)
    
    # Configure specific responses
    good_credit_features = {"age": 35, "income": 85000.0, "credit_score": 750}
    poor_credit_features = {"age": 22, "income": 30000.0, "credit_score": 580}
    
    # Create custom responses
    good_response = ScoringResponse(
        score=0.15,  # Low risk
        confidence=0.96,
        model_id="credit-risk-v2",
        timestamp=datetime.utcnow(),
        features=good_credit_features,
        explanation="Excellent credit profile"
    )
    
    poor_response = ScoringResponse(
        score=0.85,  # High risk
        confidence=0.88,
        model_id="credit-risk-v2",
        timestamp=datetime.utcnow(),
        features=poor_credit_features,
        explanation="High risk profile"
    )
    
    # Configure responses
    good_key = client._get_request_key(good_credit_features)
    poor_key = client._get_request_key(poor_credit_features)
    
    client.configure_score_response(good_key, good_response)
    client.configure_score_response(poor_key, poor_response)
    
    # Test configured responses
    good_result = client.score(good_credit_features)
    poor_result = client.score(poor_credit_features)
    
    print(f"Good Credit - Score: {good_result.score:.3f}, Explanation: {good_result.explanation}")
    print(f"Poor Credit - Score: {poor_result.score:.3f}, Explanation: {poor_result.explanation}")
    
    # Show request log
    log = client.get_request_log()
    print(f"\nRequest Log: {len(log)} requests made")
    for entry in log:
        print(f"  {entry['method']} at {entry['timestamp']}")


def custom_handler_example():
    """Custom handler example for mock client."""
    print("\n=== Custom Handler Example ===")
    
    client = MockScoringClient()
    
    # Define custom score handler
    def custom_score_handler(request):
        # Implement custom scoring logic
        age = request.features.get("age", 0)
        income = request.features.get("income", 0)
        
        # Simple custom scoring formula
        if age < 25:
            base_score = 0.7
        elif age < 40:
            base_score = 0.5
        else:
            base_score = 0.3
        
        # Adjust for income
        if income > 80000:
            base_score -= 0.2
        elif income < 40000:
            base_score += 0.2
        
        return ScoringResponse(
            score=max(0.0, min(1.0, base_score)),
            confidence=0.85,
            model_id="custom-model",
            timestamp=datetime.utcnow(),
            features=request.features,
            explanation=f"Custom score based on age ({age}) and income (${income})"
        )
    
    # Set custom handler
    client.set_score_handler(custom_score_handler)
    
    # Test custom handler
    test_cases = [
        {"age": 22, "income": 35000.0},
        {"age": 35, "income": 75000.0},
        {"age": 50, "income": 90000.0}
    ]
    
    for features in test_cases:
        result = client.score(features)
        print(f"Age: {features['age']}, Income: ${features['income']:,}")
        print(f"  Score: {result.score:.3f}")
        print(f"  Explanation: {result.explanation}")


def main():
    """Run all examples."""
    print("ML Scoring SDK - Basic Usage Examples")
    print("=" * 50)
    
    # Run synchronous example
    basic_sync_example()
    
    # Run asynchronous example
    asyncio.run(basic_async_example())
    
    # Run context manager example
    context_manager_example()
    
    # Run error handling example
    error_handling_example()
    
    # Run mock client configuration example
    mock_client_configuration_example()
    
    # Run custom handler example
    custom_handler_example()
    
    print("\n" + "=" * 50)
    print("All examples completed successfully!")


if __name__ == "__main__":
    main()
