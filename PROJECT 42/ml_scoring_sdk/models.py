"""
Pydantic models for the ML Scoring SDK.

Provides data validation and serialization for API requests and responses.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field, validator


class ScoringRequest(BaseModel):
    """Request model for individual scoring."""
    
    features: Dict[str, float] = Field(
        ..., 
        description="Dictionary of feature names to values",
        min_items=1
    )
    model_id: Optional[str] = Field(
        None,
        description="Optional model identifier"
    )
    
    @validator('features')
    def validate_features(cls, v):
        """Validate that all feature values are numbers."""
        if not v:
            raise ValueError("Features dictionary cannot be empty")
        
        for key, value in v.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError("Feature names must be non-empty strings")
            
            if not isinstance(value, (int, float)):
                raise ValueError(f"Feature value for '{key}' must be a number")
        
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "features": {
                    "age": 25.0,
                    "income": 50000.0,
                    "credit_score": 720.0
                },
                "model_id": "credit_risk_v2"
            }
        }


class ScoringResponse(BaseModel):
    """Response model for individual scoring."""
    
    score: float = Field(
        ..., 
        ge=0.0, 
        le=1.0,
        description="Predicted score between 0 and 1"
    )
    model_version: str = Field(
        ..., 
        description="Version of the model that generated the score"
    )
    confidence: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Confidence score if available"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the score was generated"
    )
    processing_time_ms: Optional[int] = Field(
        None,
        ge=0,
        description="Processing time in milliseconds"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "score": 0.75,
                "model_version": "credit_risk_v2.1.0",
                "confidence": 0.92,
                "timestamp": "2024-01-15T10:30:00Z",
                "processing_time_ms": 45
            }
        }


class BatchScoringRequest(BaseModel):
    """Request model for batch scoring."""
    
    requests: List[ScoringRequest] = Field(
        ..., 
        min_items=1,
        max_items=1000,
        description="List of scoring requests"
    )
    
    @validator('requests')
    def validate_batch_size(cls, v):
        """Validate batch size limits."""
        if len(v) > 1000:
            raise ValueError("Batch size cannot exceed 1000 requests")
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "requests": [
                    {
                        "features": {"age": 25.0, "income": 50000.0},
                        "model_id": "credit_risk_v2"
                    },
                    {
                        "features": {"age": 35.0, "income": 75000.0},
                        "model_id": "credit_risk_v2"
                    }
                ]
            }
        }


class BatchScoringResponse(BaseModel):
    """Response model for batch scoring."""
    
    scores: List[ScoringResponse] = Field(
        ..., 
        description="List of scoring responses"
    )
    total_processed: int = Field(
        ..., 
        ge=0,
        description="Total number of requests processed"
    )
    failed_requests: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="List of failed requests with error details"
    )
    batch_processing_time_ms: Optional[int] = Field(
        None,
        ge=0,
        description="Total batch processing time in milliseconds"
    )
    
    @validator('scores')
    def validate_scores_length(cls, v, values):
        """Validate that scores length matches total processed."""
        if 'total_processed' in values and len(v) != values['total_processed']:
            raise ValueError("Scores length must match total_processed count")
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "scores": [
                    {
                        "score": 0.75,
                        "model_version": "credit_risk_v2.1.0",
                        "timestamp": "2024-01-15T10:30:00Z"
                    },
                    {
                        "score": 0.82,
                        "model_version": "credit_risk_v2.1.0",
                        "timestamp": "2024-01-15T10:30:01Z"
                    }
                ],
                "total_processed": 2,
                "batch_processing_time_ms": 89
            }
        }


class HealthResponse(BaseModel):
    """Response model for health check endpoint."""
    
    status: str = Field(
        ..., 
        description="Service status (healthy, unhealthy, degraded)"
    )
    version: str = Field(
        ..., 
        description="API version"
    )
    model_status: Dict[str, str] = Field(
        ..., 
        description="Status of available models"
    )
    uptime_seconds: int = Field(
        ..., 
        ge=0,
        description="Service uptime in seconds"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Health check timestamp"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "status": "healthy",
                "version": "1.2.3",
                "model_status": {
                    "credit_risk_v2": "available",
                    "fraud_detection_v1": "available"
                },
                "uptime_seconds": 86400,
                "timestamp": "2024-01-15T10:30:00Z"
            }
        }


class ErrorResponse(BaseModel):
    """Standard error response model."""
    
    error: str = Field(
        ..., 
        description="Error type"
    )
    message: str = Field(
        ..., 
        description="Human-readable error message"
    )
    details: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional error details"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Error timestamp"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "error": "ValidationError",
                "message": "Feature 'age' is required",
                "details": {
                    "missing_features": ["age"],
                    "invalid_features": ["income"]
                },
                "timestamp": "2024-01-15T10:30:00Z"
            }
        }
