#!/usr/bin/env python3
"""
Advanced usage examples for the ML Scoring SDK.

This script demonstrates advanced features including:
- Credit scoring workflow
- Fraud detection with concurrent processing
- Model monitoring and health checks
- Performance optimization techniques
- Error handling patterns
- Custom retry strategies
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any
from ml_scoring_sdk import (
    ScoringClient,
    AsyncScoringClient,
    MockScoringClient
)
from ml_scoring_sdk.models import (
    ScoringRequest, 
    ScoringResponse, 
    BatchScoringRequest,
    HealthResponse
)
from ml_scoring_sdk.exceptions import (
    RateLimitError,
    ModelNotFoundError,
    ValidationError,
    ServerError,
    NetworkError,
    TimeoutError
)


class CreditScoringWorkflow:
    """Complete credit scoring workflow example."""
    
    def __init__(self, api_url: str, api_key: str):
        self.client = ScoringClient(
            base_url=api_url,
            api_key=api_key,
            timeout=15,
            max_retries=3
        )
    
    def assess_applicant(self, applicant_data: Dict[str, Any]) -> Dict[str, Any]:
        """Assess a single credit applicant."""
        try:
            # Prepare features for the model
            features = {
                "age": applicant_data["age"],
                "annual_income": applicant_data["income"],
                "credit_score": applicant_data["credit_score"],
                "debt_to_income": applicant_data["debt_to_income"],
                "employment_length": applicant_data["employment_years"],
                "home_ownership": 1 if applicant_data["owns_home"] else 0,
                "loan_amount": applicant_data["requested_loan"],
                "loan_purpose": self._encode_loan_purpose(applicant_data["loan_purpose"])
            }
            
            # Get risk assessment
            result = self.client.score(features)
            
            # Interpret results
            risk_level = self._categorize_risk(result.score)
            decision = self._make_decision(result.score, applicant_data)
            
            return {
                "applicant_id": applicant_data["id"],
                "risk_score": result.score,
                "confidence": result.confidence,
                "risk_level": risk_level,
                "decision": decision,
                "explanation": result.explanation,
                "model_used": result.model_id,
                "assessment_timestamp": result.timestamp.isoformat()
            }
            
        except RateLimitError as e:
            return {"error": "Rate limit exceeded", "retry_after": 60}
        except ValidationError as e:
            return {"error": "Invalid applicant data", "details": str(e)}
        except Exception as e:
            return {"error": "Assessment failed", "details": str(e)}
    
    def batch_assess_applicants(self, applicants: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Assess multiple applicants in batch."""
        try:
            # Prepare batch request
            requests = []
            for applicant in applicants:
                features = {
                    "age": applicant["age"],
                    "annual_income": applicant["income"],
                    "credit_score": applicant["credit_score"],
                    "debt_to_income": applicant["debt_to_income"],
                    "employment_length": applicant["employment_years"],
                    "home_ownership": 1 if applicant["owns_home"] else 0,
                    "loan_amount": applicant["requested_loan"],
                    "loan_purpose": self._encode_loan_purpose(applicant["loan_purpose"])
                }
                requests.append(ScoringRequest(features=features))
            
            # Process batch
            batch_result = self.client.batch_score(requests)
            
            # Analyze batch results
            assessments = []
            for i, (applicant, response) in enumerate(zip(applicants, batch_result.responses)):
                assessment = {
                    "applicant_id": applicant["id"],
                    "risk_score": response.score,
                    "confidence": response.confidence,
                    "risk_level": self._categorize_risk(response.score),
                    "decision": self._make_decision(response.score, applicant)
                }
                assessments.append(assessment)
            
            # Batch summary
            risk_distribution = self._analyze_risk_distribution(assessments)
            
            return {
                "total_processed": batch_result.total_processed,
                "total_successful": batch_result.total_successful,
                "total_failed": batch_result.total_failed,
                "assessments": assessments,
                "risk_distribution": risk_distribution,
                "batch_timestamp": batch_result.timestamp.isoformat()
            }
            
        except Exception as e:
            return {"error": "Batch assessment failed", "details": str(e)}
    
    def _encode_loan_purpose(self, purpose: str) -> int:
        """Encode loan purpose as numeric value."""
        purpose_map = {
            "debt_consolidation": 1,
            "home_improvement": 2,
            "major_purchase": 3,
            "business": 4,
            "education": 5,
            "other": 6
        }
        return purpose_map.get(purpose.lower(), 6)
    
    def _categorize_risk(self, score: float) -> str:
        """Categorize risk level based on score."""
        if score < 0.2:
            return "Very Low"
        elif score < 0.4:
            return "Low"
        elif score < 0.6:
            return "Medium"
        elif score < 0.8:
            return "High"
        else:
            return "Very High"
    
    def _make_decision(self, score: float, applicant: Dict[str, Any]) -> str:
        """Make lending decision based on score and other factors."""
        if score < 0.3:
            return "Approve"
        elif score < 0.7:
            return "Manual Review"
        else:
            return "Decline"
    
    def _analyze_risk_distribution(self, assessments: List[Dict[str, Any]]) -> Dict[str, int]:
        """Analyze risk distribution across assessments."""
        distribution = {}
        for assessment in assessments:
            risk_level = assessment["risk_level"]
            distribution[risk_level] = distribution.get(risk_level, 0) + 1
        return distribution


class FraudDetectionSystem:
    """Fraud detection system with concurrent processing."""
    
    def __init__(self, api_url: str, api_key: str):
        self.client = AsyncScoringClient(
            base_url=api_url,
            api_key=api_key,
            timeout=10,
            max_retries=2
        )
    
    async def analyze_transactions(self, transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze multiple transactions for fraud concurrently."""
        try:
            # Convert transactions to feature dictionaries
            features_list = []
            for tx in transactions:
                features = {
                    "amount": tx["amount"],
                    "merchant_category": self._encode_merchant_category(tx["merchant"]["category"]),
                    "location_risk": tx["location"]["risk_score"],
                    "user_history_score": tx["user"]["history_score"],
                    "time_of_day": tx["timestamp"].hour,
                    "day_of_week": tx["timestamp"].weekday(),
                    "is_weekend": 1 if tx["timestamp"].weekday() >= 5 else 0,
                    "amount_vs_average": tx["amount"] / tx["user"]["avg_transaction_amount"],
                    "frequency_score": tx["user"]["transaction_frequency_score"]
                }
                features_list.append(features)
            
            # Process concurrently for speed
            start_time = time.time()
            results = await self.concurrent_batch_score(
                features_list, 
                max_concurrency=20
            )
            processing_time = time.time() - start_time
            
            # Analyze results
            fraud_alerts = []
            legitimate_transactions = []
            
            for i, (tx, result) in enumerate(zip(transactions, results)):
                transaction_result = {
                    "transaction_id": tx["id"],
                    "fraud_score": result.score,
                    "confidence": result.confidence,
                    "risk_factors": result.explanation,
                    "processing_timestamp": result.timestamp.isoformat()
                }
                
                if result.score > 0.8:  # High fraud probability
                    transaction_result["alert_level"] = "HIGH"
                    fraud_alerts.append(transaction_result)
                elif result.score > 0.6:  # Medium fraud probability
                    transaction_result["alert_level"] = "MEDIUM"
                    fraud_alerts.append(transaction_result)
                else:
                    transaction_result["alert_level"] = "LOW"
                    legitimate_transactions.append(transaction_result)
            
            # Generate summary
            summary = {
                "total_transactions": len(transactions),
                "processing_time_seconds": processing_time,
                "fraud_alerts": len(fraud_alerts),
                "legitimate_transactions": len(legitimate_transactions),
                "high_priority_alerts": len([a for a in fraud_alerts if a["alert_level"] == "HIGH"]),
                "medium_priority_alerts": len([a for a in fraud_alerts if a["alert_level"] == "MEDIUM"])
            }
            
            return {
                "summary": summary,
                "fraud_alerts": fraud_alerts,
                "legitimate_transactions": legitimate_transactions,
                "analysis_timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {"error": "Fraud analysis failed", "details": str(e)}
        finally:
            await self.client.close()
    
    async def concurrent_batch_score(self, features_list: List[Dict[str, Any]], max_concurrency: int) -> List[ScoringResponse]:
        """Concurrent batch scoring with rate limiting."""
        return await self.client.concurrent_batch_score(features_list, max_concurrency)
    
    def _encode_merchant_category(self, category: str) -> int:
        """Encode merchant category as numeric value."""
        category_map = {
            "retail": 1,
            "restaurant": 2,
            "gas": 3,
            "grocery": 4,
            "travel": 5,
            "entertainment": 6,
            "online": 7,
            "atm": 8,
            "other": 9
        }
        return category_map.get(category.lower(), 9)


class ModelMonitoringSystem:
    """Model performance and health monitoring system."""
    
    def __init__(self, api_url: str, api_key: str):
        self.client = ScoringClient(
            base_url=api_url,
            api_key=api_key,
            timeout=5,
            max_retries=1  # Quick retries for monitoring
        )
    
    def comprehensive_health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health and performance check."""
        health_report = {
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {}
        }
        
        # Service health
        try:
            health = self.client.health()
            health_report["checks"]["service"] = {
                "status": "healthy",
                "service_status": health.status,
                "version": health.version,
                "uptime_seconds": health.uptime_seconds,
                "details": health.details
            }
        except Exception as e:
            health_report["checks"]["service"] = {
                "status": "unhealthy",
                "error": str(e)
            }
        
        # Model information
        try:
            model_info = self.client.get_model_info()
            health_report["checks"]["models"] = {
                "status": "available",
                "model_count": len(model_info.get("models", [])),
                "models": model_info.get("models", [])
            }
        except Exception as e:
            health_report["checks"]["models"] = {
                "status": "unavailable",
                "error": str(e)
            }
        
        # Performance test
        try:
            performance_result = self._performance_test()
            health_report["checks"]["performance"] = performance_result
        except Exception as e:
            health_report["checks"]["performance"] = {
                "status": "failed",
                "error": str(e)
            }
        
        # Overall status
        all_healthy = all(
            check.get("status") == "healthy" or check.get("status") == "available"
            for check in health_report["checks"].values()
        )
        health_report["overall_status"] = "healthy" if all_healthy else "degraded"
        
        return health_report
    
    def _performance_test(self) -> Dict[str, Any]:
        """Run performance test with sample requests."""
        test_features = {"age": 30, "income": 60000.0, "credit_score": 700}
        
        # Measure response times
        response_times = []
        for _ in range(5):
            start_time = time.time()
            result = self.client.score(test_features)
            response_time = time.time() - start_time
            response_times.append(response_time)
        
        avg_response_time = sum(response_times) / len(response_times)
        max_response_time = max(response_times)
        min_response_time = min(response_times)
        
        # Determine performance status
        if avg_response_time < 0.5:
            status = "excellent"
        elif avg_response_time < 1.0:
            status = "good"
        elif avg_response_time < 2.0:
            status = "acceptable"
        else:
            status = "poor"
        
        return {
            "status": status,
            "avg_response_time_ms": avg_response_time * 1000,
            "max_response_time_ms": max_response_time * 1000,
            "min_response_time_ms": min_response_time * 1000,
            "sample_count": len(response_times)
        }


def error_handling_patterns():
    """Demonstrate advanced error handling patterns."""
    print("=== Advanced Error Handling Patterns ===")
    
    client = MockScoringClient()
    
    # Pattern 1: Exponential backoff for rate limits
    def handle_with_backoff(client, features, max_retries=3):
        """Handle requests with exponential backoff."""
        for attempt in range(max_retries):
            try:
                return client.score(features)
            except RateLimitError as e:
                if attempt == max_retries - 1:
                    raise
                wait_time = 2 ** attempt  # 1, 2, 4 seconds
                print(f"Rate limited, waiting {wait_time}s...")
                time.sleep(wait_time)
            except Exception as e:
                # Don't retry on non-rate-limit errors
                raise
    
    # Pattern 2: Circuit breaker pattern
    class CircuitBreaker:
        def __init__(self, failure_threshold=5, timeout=60):
            self.failure_threshold = failure_threshold
            self.timeout = timeout
            self.failure_count = 0
            self.last_failure_time = None
            self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        
        def call(self, func, *args, **kwargs):
            if self.state == "OPEN":
                if time.time() - self.last_failure_time > self.timeout:
                    self.state = "HALF_OPEN"
                else:
                    raise Exception("Circuit breaker is OPEN")
            
            try:
                result = func(*args, **kwargs)
                if self.state == "HALF_OPEN":
                    self.state = "CLOSED"
                    self.failure_count = 0
                return result
            except Exception as e:
                self.failure_count += 1
                self.last_failure_time = time.time()
                if self.failure_count >= self.failure_threshold:
                    self.state = "OPEN"
                raise
    
    # Pattern 3: Graceful degradation
    def graceful_scoring(client, features):
        """Attempt scoring with graceful degradation."""
        try:
            # Try primary model
            return client.score(features)
        except (ServerError, NetworkError, TimeoutError) as e:
            print(f"Primary model failed: {e}, trying fallback...")
            try:
                # Try fallback model (different model_id)
                fallback_request = ScoringRequest(
                    features=features, 
                    model_id="fallback-model"
                )
                return client.score(fallback_request)
            except Exception as e2:
                print(f"Fallback model also failed: {e2}, using default score")
                # Return a conservative default score
                return ScoringResponse(
                    score=0.5,  # Conservative default
                    confidence=0.5,  # Low confidence
                    model_id="default-fallback",
                    timestamp=datetime.utcnow(),
                    features=features,
                    explanation="Default score due to model unavailability"
                )
    
    # Test patterns
    features = {"age": 25, "income": 50000.0}
    
    # Configure some errors for testing
    client.configure_error("score", RateLimitError("Rate limited"), probability=0.7)
    
    print("Testing exponential backoff...")
    try:
        result = handle_with_backoff(client, features)
        print(f"Success after retries: {result.score:.3f}")
    except Exception as e:
        print(f"Failed after all retries: {e}")
    
    print("\nTesting circuit breaker...")
    circuit_breaker = CircuitBreaker(failure_threshold=2, timeout=2)
    
    # Configure persistent failures
    client.configure_error("score", ServerError("Persistent failure"), probability=1.0)
    
    for i in range(5):
        try:
            result = circuit_breaker.call(client.score, features)
            print(f"Circuit breaker call {i+1}: Success")
        except Exception as e:
            print(f"Circuit breaker call {i+1}: {e}")
    
    print("\nTesting graceful degradation...")
    # Reset client for graceful degradation test
    client.reset()
    client.configure_error("score", NetworkError("Network failure"), probability=0.5)
    
    try:
        result = graceful_scoring(client, features)
        print(f"Graceful degradation result: {result.score:.3f} ({result.model_id})")
    except Exception as e:
        print(f"Graceful degradation failed: {e}")


async def performance_optimization_example():
    """Demonstrate performance optimization techniques."""
    print("\n=== Performance Optimization Example ===")
    
    client = AsyncScoringClient("https://api.example.com", "api-key")
    
    try:
        # Generate test data
        features_list = [
            {"age": i + 20, "income": 40000 + i * 1000, "credit_score": 600 + i * 5}
            for i in range(100)
        ]
        
        # Test different concurrency levels
        concurrency_levels = [1, 5, 10, 20, 50]
        
        for concurrency in concurrency_levels:
            start_time = time.time()
            results = await client.concurrent_batch_score(
                features_list, 
                max_concurrency=concurrency
            )
            processing_time = time.time() - start_time
            
            print(f"Concurrency {concurrency:2d}: {processing_time:.2f}s "
                  f"({len(results)/processing_time:.1f} requests/sec)")
        
        # Batch vs concurrent comparison
        print("\nBatch vs Concurrent comparison:")
        
        # Batch processing
        start_time = time.time()
        batch_result = await client.batch_score(features_list)
        batch_time = time.time() - start_time
        
        # Concurrent processing
        start_time = time.time()
        concurrent_results = await client.concurrent_batch_score(features_list, max_concurrency=20)
        concurrent_time = time.time() - start_time
        
        print(f"Batch processing:     {batch_time:.2f}s")
        print(f"Concurrent processing: {concurrent_time:.2f}s")
        print(f"Speedup: {batch_time/concurrent_time:.2f}x")
        
    finally:
        await client.close()


def main():
    """Run all advanced examples."""
    print("ML Scoring SDK - Advanced Usage Examples")
    print("=" * 50)
    
    # Note: These examples use MockScoringClient for demonstration
    # In production, replace with actual API endpoints
    
    # Credit scoring workflow
    print("\n1. Credit Scoring Workflow")
    workflow = CreditScoringWorkflow("https://credit-api.example.com", "credit-key")
    
    # Mock the client for demonstration
    workflow.client = MockScoringClient(default_score=0.4)
    
    applicant = {
        "id": "app_001",
        "age": 35,
        "income": 75000.0,
        "credit_score": 720,
        "debt_to_income": 0.25,
        "employment_years": 8,
        "owns_home": True,
        "requested_loan": 25000.0,
        "loan_purpose": "home_improvement"
    }
    
    assessment = workflow.assess_applicant(applicant)
    print(f"Applicant assessment: {assessment['risk_level']} risk - {assessment['decision']}")
    
    # Error handling patterns
    error_handling_patterns()
    
    # Performance optimization (async)
    asyncio.run(performance_optimization_example())
    
    print("\n" + "=" * 50)
    print("Advanced examples completed!")


if __name__ == "__main__":
    main()
