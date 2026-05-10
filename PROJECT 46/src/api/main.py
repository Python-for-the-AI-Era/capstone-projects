"""
FastAPI application for property price prediction.

This module provides a REST API for property price estimation with
confidence bounds and SHAP explanations.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from typing import List, Dict, Optional, Any
import numpy as np
import pandas as pd
import logging
from datetime import datetime
import asyncio
import joblib
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="PropEase Property Price Prediction API",
    description="AI-powered property price estimation for Nigerian real estate",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables for models
model_trainer = None
feature_engineer = None
model_loaded = False


# Pydantic models for API
class PropertyFeatures(BaseModel):
    """Property features for price prediction."""
    
    # Basic property information
    city: str = Field(..., description="City name (e.g., Lagos, Abuja, Port Harcourt)")
    lga: str = Field(..., description="Local Government Area")
    property_type: str = Field(..., description="Property type (Apartment, Duplex, etc.)")
    
    # Physical characteristics
    size_sqm: float = Field(..., gt=0, description="Property size in square meters")
    bedrooms: int = Field(..., ge=1, le=10, description="Number of bedrooms")
    bathrooms: int = Field(..., ge=1, le=10, description="Number of bathrooms")
    age_years: int = Field(..., ge=0, le=100, description="Property age in years")
    
    # Location
    latitude: float = Field(..., description="Property latitude")
    longitude: float = Field(..., description="Property longitude")
    
    # Amenities
    has_parking: bool = Field(default=False, description="Has parking space")
    has_pool: bool = Field(default=False, description="Has swimming pool")
    has_gym: bool = Field(default=False, description="Has gym")
    has_security: bool = Field(default=False, description="Has security system")
    has_elevator: bool = Field(default=False, description="Has elevator")
    
    @validator('city')
    def validate_city(cls, v):
        valid_cities = ['Lagos', 'Abuja', 'Port Harcourt', 'Kano', 'Ibadan', 'Enugu', 'Benin City', 'Warri']
        if v not in valid_cities:
            raise ValueError(f"City must be one of: {valid_cities}")
        return v
    
    @validator('property_type')
    def validate_property_type(cls, v):
        valid_types = ['Apartment', 'Duplex', 'Detached House', 'Terrace House', 'Bungalow', 'Penthouse', 'Studio']
        if v not in valid_types:
            raise ValueError(f"Property type must be one of: {valid_types}")
        return v


class PriceEstimate(BaseModel):
    """Price estimation result."""
    
    low: float = Field(..., description="Lower bound estimate (10th percentile)")
    mid: float = Field(..., description="Mid-point estimate (median)")
    high: float = Field(..., description="Upper bound estimate (90th percentile)")
    confidence_level: float = Field(default=0.8, description="Confidence level for bounds")
    
    # Explanations
    explanation: List[Dict[str, Any]] = Field(..., description="Top contributing features")
    feature_importance: Dict[str, float] = Field(..., description="Feature importance scores")
    
    # Metadata
    property_id: Optional[str] = Field(None, description="Property identifier")
    timestamp: str = Field(..., description="Prediction timestamp")
    model_version: str = Field(default="1.0.0", description="Model version")


class BatchEstimateRequest(BaseModel):
    """Batch price estimation request."""
    
    properties: List[PropertyFeatures] = Field(..., description="List of properties to estimate")
    batch_id: Optional[str] = Field(None, description="Batch identifier")


class BatchEstimateResponse(BaseModel):
    """Batch price estimation response."""
    
    batch_id: str = Field(..., description="Batch identifier")
    estimates: List[PriceEstimate] = Field(..., description="Price estimates")
    processing_time: float = Field(..., description="Processing time in seconds")
    timestamp: str = Field(..., description="Response timestamp")


class ModelInfo(BaseModel):
    """Model information response."""
    
    model_type: str = Field(..., description="Model type")
    version: str = Field(..., description="Model version")
    training_date: str = Field(..., description="Training date")
    feature_count: int = Field(..., description="Number of features")
    supported_cities: List[str] = Field(..., description="Supported cities")
    supported_property_types: List[str] = Field(..., description="Supported property types")
    performance_metrics: Dict[str, float] = Field(..., description="Model performance metrics")


# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize models on startup."""
    global model_trainer, feature_engineer, model_loaded
    
    try:
        # Load models
        models_dir = Path("models")
        if models_dir.exists():
            logger.info("Loading pre-trained models...")
            
            # Load feature engineer
            from ..utils.feature_engineering import PropertyFeatureEngineer
            feature_engineer = PropertyFeatureEngineer()
            if (models_dir / "transformers.pkl").exists():
                feature_engineer.load_transformers(models_dir / "transformers.pkl")
            
            # Load model trainer
            from ..models.train_model import PropertyPriceModelTrainer
            model_trainer = PropertyPriceModelTrainer()
            model_trainer.load_models(models_dir)
            
            model_loaded = True
            logger.info("Models loaded successfully")
        else:
            logger.warning("No pre-trained models found. Please train models first.")
    
    except Exception as e:
        logger.error(f"Failed to load models: {e}")
        model_loaded = False


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down API...")


# Helper functions
def load_models_if_needed():
    """Load models if not already loaded."""
    global model_trainer, feature_engineer, model_loaded
    
    if not model_loaded:
        raise HTTPException(
            status_code=503,
            detail="Models not loaded. Please train and load models first."
        )


def prepare_features(property_features: PropertyFeatures) -> pd.DataFrame:
    """Prepare features for prediction."""
    # Convert to DataFrame
    data = property_features.dict()
    df = pd.DataFrame([data])
    
    # Add calculated features
    from ..utils.feature_engineering import DistanceCalculator
    
    # Calculate distance to CBD
    df['distance_to_cbd_km'] = DistanceCalculator.calculate_distance_to_cbd(
        df['latitude'].iloc[0], 
        df['longitude'].iloc[0], 
        df['city'].iloc[0]
    )
    
    # Add other calculated features (simplified)
    df['lga_median_price'] = 500000  # Default, would be calculated from data
    df['price_per_bedroom'] = 0  # Placeholder
    df['size_per_bedroom'] = df['size_sqm'] / df['bedrooms']
    df['luxury_score'] = (
        df['has_pool'].astype(int) * 3 +
        df['has_gym'].astype(int) * 2 +
        df['has_elevator'].astype(int) * 2 +
        df['has_security'].astype(int) * 1 +
        df['has_parking'].astype(int) * 1
    )
    df['location_premium'] = np.exp(-df['distance_to_cbd_km'] / 10)
    
    # Add categorical features
    df['age_category'] = pd.cut(
        df['age_years'],
        bins=[0, 5, 10, 20, 50, 100],
        labels=['New', 'Modern', 'Established', 'Old', 'Very Old']
    )
    
    # Calculate price category (would need actual prices)
    df['price_category'] = 'Mid-range'  # Default
    
    return df


# API endpoints
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "PropEase Property Price Prediction API",
        "version": "1.0.0",
        "status": "active",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "models_loaded": model_loaded
    }


@app.get("/model/info", response_model=ModelInfo)
async def get_model_info():
    """Get model information."""
    load_models_if_needed()
    
    summary = model_trainer.get_model_summary()
    
    return ModelInfo(
        model_type=summary['model_type'],
        version=summary['training_history'].get('model_version', '1.0.0'),
        training_date=summary['training_history'].get('training_date', datetime.now().isoformat()),
        feature_count=summary['feature_count'],
        supported_cities=['Lagos', 'Abuja', 'Port Harcourt', 'Kano', 'Ibadan', 'Enugu', 'Benin City', 'Warri'],
        supported_property_types=['Apartment', 'Duplex', 'Detached House', 'Terrace House', 'Bungalow', 'Penthouse', 'Studio'],
        performance_metrics=summary['evaluation_metrics'].get('val', {})
    )


@app.post("/estimate", response_model=PriceEstimate)
async def estimate_price(property_features: PropertyFeatures):
    """
    Estimate property price with confidence bounds and explanations.
    
    Args:
        property_features: Property features for estimation
        
    Returns:
        Price estimate with confidence bounds and explanations
    """
    load_models_if_needed()
    
    start_time = datetime.now()
    
    try:
        # Prepare features
        df = prepare_features(property_features)
        
        # Transform features
        df_transformed = feature_engineer.transform(df)
        
        # Make prediction
        predictions = model_trainer.predict_with_confidence(df_transformed, return_shap=True)
        
        # Extract results
        low_price = float(predictions['low'][0])
        mid_price = float(predictions['mid'][0])
        high_price = float(predictions['high'][0])
        
        # Get SHAP explanations
        top_features = predictions['top_features'][0] if 'top_features' in predictions else []
        
        # Format explanations
        explanations = []
        for feature in top_features[:3]:  # Top 3 features
            explanations.append({
                'feature': feature['feature'],
                'contribution': feature['contribution'],
                'value': feature['value'],
                'impact': 'positive' if feature['contribution'] > 0 else 'negative'
            })
        
        # Get feature importance
        feature_importance = model_trainer.get_feature_importance()
        
        # Create response
        estimate = PriceEstimate(
            low=low_price,
            mid=mid_price,
            high=high_price,
            explanation=explanations,
            feature_importance=feature_importance,
            timestamp=datetime.now().isoformat()
        )
        
        processing_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"Price estimate completed in {processing_time:.3f}s")
        
        return estimate
    
    except Exception as e:
        logger.error(f"Error estimating price: {e}")
        raise HTTPException(status_code=500, detail=f"Error estimating price: {str(e)}")


@app.post("/estimate/batch", response_model=BatchEstimateResponse)
async def estimate_prices_batch(request: BatchEstimateRequest):
    """
    Estimate prices for multiple properties.
    
    Args:
        request: Batch estimation request
        
    Returns:
        Batch price estimates
    """
    load_models_if_needed()
    
    start_time = datetime.now()
    batch_id = request.batch_id or f"batch_{int(start_time.timestamp())}"
    
    try:
        estimates = []
        
        for i, property_features in enumerate(request.properties):
            # Prepare features
            df = prepare_features(property_features)
            
            # Transform features
            df_transformed = feature_engineer.transform(df)
            
            # Make prediction
            predictions = model_trainer.predict_with_confidence(df_transformed, return_shap=True)
            
            # Extract results
            low_price = float(predictions['low'][0])
            mid_price = float(predictions['mid'][0])
            high_price = float(predictions['high'][0])
            
            # Get SHAP explanations
            top_features = predictions['top_features'][0] if 'top_features' in predictions else []
            
            # Format explanations
            explanations = []
            for feature in top_features[:3]:  # Top 3 features
                explanations.append({
                    'feature': feature['feature'],
                    'contribution': feature['contribution'],
                    'value': feature['value'],
                    'impact': 'positive' if feature['contribution'] > 0 else 'negative'
                })
            
            # Get feature importance
            feature_importance = model_trainer.get_feature_importance()
            
            # Create estimate
            estimate = PriceEstimate(
                low=low_price,
                mid=mid_price,
                high=high_price,
                explanation=explanations,
                feature_importance=feature_importance,
                property_id=f"{batch_id}_{i}",
                timestamp=datetime.now().isoformat()
            )
            
            estimates.append(estimate)
        
        processing_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"Batch estimation completed for {len(request.properties)} properties in {processing_time:.3f}s")
        
        return BatchEstimateResponse(
            batch_id=batch_id,
            estimates=estimates,
            processing_time=processing_time,
            timestamp=datetime.now().isoformat()
        )
    
    except Exception as e:
        logger.error(f"Error in batch estimation: {e}")
        raise HTTPException(status_code=500, detail=f"Error in batch estimation: {str(e)}")


@app.get("/features/importance")
async def get_feature_importance():
    """Get global feature importance."""
    load_models_if_needed()
    
    try:
        importance = model_trainer.get_feature_importance()
        return {
            "feature_importance": importance,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting feature importance: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting feature importance: {str(e)}")


@app.get("/cities/supported")
async def get_supported_cities():
    """Get list of supported cities."""
    return {
        "cities": [
            {"name": "Lagos", "median_price_per_sqm": 850000},
            {"name": "Abuja", "median_price_per_sqm": 650000},
            {"name": "Port Harcourt", "median_price_per_sqm": 450000},
            {"name": "Kano", "median_price_per_sqm": 350000},
            {"name": "Ibadan", "median_price_per_sqm": 280000},
            {"name": "Enugu", "median_price_per_sqm": 320000},
            {"name": "Benin City", "median_price_per_sqm": 250000},
            {"name": "Warri", "median_price_per_sqm": 380000}
        ],
        "timestamp": datetime.now().isoformat()
    }


@app.get("/property/types")
async def get_property_types():
    """Get list of supported property types."""
    return {
        "property_types": [
            {"name": "Apartment", "description": "Self-contained housing unit"},
            {"name": "Duplex", "description": "Two-family house"},
            {"name": "Detached House", "description": "Single-family house"},
            {"name": "Terrace House", "description": "Row house"},
            {"name": "Bungalow", "description": "Single-story house"},
            {"name": "Penthouse", "description": "Top-floor luxury apartment"},
            {"name": "Studio", "description": "Single-room apartment"}
        ],
        "timestamp": datetime.now().isoformat()
    }


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    """Handle 404 errors."""
    return JSONResponse(
        status_code=404,
        content={"error": "Endpoint not found", "message": str(exc)}
    )


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    """Handle 500 errors."""
    logger.error(f"Internal server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "message": "An unexpected error occurred"}
    )


# Background task for model reloading
async def reload_models(background_tasks: BackgroundTasks):
    """Reload models in background."""
    background_tasks.add_task(load_models_if_needed)


# Development server startup
if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
