"""
FastAPI Property Price Prediction API with SHAP Explanations
Serves property price predictions with explainable AI using SHAP values
"""

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
import numpy as np
import pandas as pd
import joblib
import shap
import logging
from datetime import datetime
import traceback

from model_training import PropertyPriceModel
from feature_engineering import NigerianRealEstateFeatures

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="PropEase Property Price Prediction API",
    description="AI-powered property price estimation with explainability",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://propease.com", "https://app.propease.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Load trained models
try:
    model = PropertyPriceModel()
    model.load_models("models/")
    logger.info("Models loaded successfully")
except Exception as e:
    logger.error(f"Failed to load models: {e}")
    model = None


class PropertyInput(BaseModel):
    """Input schema for property price prediction"""
    # Basic property information
    property_type: str = Field(..., description="Type of property (e.g., 'duplex', 'bungalow', 'flat')")
    bedrooms: int = Field(..., ge=1, le=10, description="Number of bedrooms")
    bathrooms: int = Field(..., ge=1, le=10, description="Number of bathrooms")
    total_rooms: int = Field(..., ge=1, le=20, description="Total number of rooms")
    parking_spaces: int = Field(..., ge=0, le=10, description="Number of parking spaces")
    square_meters: float = Field(..., gt=0, le=10000, description="Property size in square meters")
    year_built: int = Field(..., ge=1900, le=2024, description="Year property was built")
    
    # Location information
    address: str = Field(..., description="Full property address")
    city: str = Field(..., description="City (e.g., 'Lagos', 'Abuja', 'Port Harcourt')")
    state: str = Field(..., description="State (e.g., 'Lagos', 'Abuja', 'Rivers')")
    latitude: Optional[float] = Field(None, ge=-90, le=90, description="Property latitude")
    longitude: Optional[float] = Field(None, ge=-180, le=180, description="Property longitude")
    
    # Property features
    has_generator: bool = Field(False, description="Property has backup generator")
    has_borehole: bool = Field(False, description="Property has borehole")
    has_air_conditioning: bool = Field(False, description="Property has air conditioning")
    has_security_system: bool = Field(False, description="Property has security system")
    is_waterfront: bool = Field(False, description="Property is waterfront")
    is_corner_lot: bool = Field(False, description="Property is on a corner lot")
    
    # Market information
    days_on_market: int = Field(30, ge=1, le=365, description="Days property has been on market")
    price_change_percentage: float = Field(0.0, ge=-50, le=50, description="Price change percentage")
    competing_properties_count: int = Field(0, ge=0, le=50, description="Number of competing properties nearby")
    
    class Config:
        schema_extra = {
            "example": {
                "property_type": "duplex",
                "bedrooms": 4,
                "bathrooms": 3,
                "total_rooms": 8,
                "parking_spaces": 2,
                "square_meters": 250.0,
                "year_built": 2010,
                "address": "123 Victoria Island, Lagos, Nigeria",
                "city": "Lagos",
                "state": "Lagos",
                "latitude": 6.4550,
                "longitude": 3.3841,
                "has_generator": True,
                "has_borehole": False,
                "has_air_conditioning": True,
                "has_security_system": True,
                "is_waterfront": False,
                "is_corner_lot": False,
                "days_on_market": 45,
                "price_change_percentage": -5.0,
                "competing_properties_count": 3
            }
        }


class FeatureContribution(BaseModel):
    """Individual feature contribution for SHAP explanation"""
    feature: str = Field(..., description="Feature name")
    contribution: float = Field(..., description="SHAP contribution value")
    description: str = Field(..., description="Human-readable explanation of feature impact")


class PredictionResponse(BaseModel):
    """Response schema for property price prediction"""
    predicted_price: float = Field(..., description="Predicted property price in Naira")
    low_bound: float = Field(..., description="Lower bound of prediction (10th percentile)")
    mid_bound: float = Field(..., description="Mid-point prediction (50th percentile)")
    high_bound: float = Field(..., description="Upper bound of prediction (90th percentile)")
    confidence_interval: tuple[float, float] = Field(..., description="Confidence interval (low, high)")
    model_version: str = Field(..., description="Model version used for prediction")
    explanation: List[FeatureContribution] = Field(..., description="SHAP feature explanations")
    accuracy_metrics: Optional[Dict[str, float]] = Field(None, description="Model accuracy metrics")
    
    class Config:
        schema_extra = {
            "example": {
                "predicted_price": 45000000,
                "low_bound": 38000000,
                "mid_bound": 45000000,
                "high_bound": 52000000,
                "confidence_interval": [38000000, 52000000],
                "model_version": "xgboost_v1.0",
                "explanation": [
                    {
                        "feature": "distance_to_cbd",
                        "contribution": 8500000.0,
                        "description": "Property is 8.5km from Central Business District, reducing value by ₦8.5M"
                    },
                    {
                        "feature": "bedroom_count",
                        "contribution": 3200000.0,
                        "description": "4 bedrooms increase value by ₦3.2M"
                    },
                    {
                        "feature": "square_meters",
                        "contribution": 2100000.0,
                        "description": "250sqm adds ₦2.1M to property value"
                    }
                ]
            }
        }


class BatchPredictionRequest(BaseModel):
    """Request schema for batch property predictions"""
    properties: List[PropertyInput] = Field(..., max_items=10, description="List of properties to predict")
    
    class Config:
        schema_extra = {
            "example": {
                "properties": [
                    {
                        "property_type": "bungalow",
                        "bedrooms": 3,
                        "square_meters": 180.0,
                        "city": "Abuja",
                        "latitude": 9.0579,
                        "longitude": 7.4951
                    }
                ]
            }
        }


class BatchPredictionResponse(BaseModel):
    """Response schema for batch predictions"""
    predictions: List[PredictionResponse] = Field(..., description="List of prediction results")
    total_processed: int = Field(..., description="Total number of properties processed")
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")
    
    class Config:
        schema_extra = {
            "example": {
                "predictions": [
                    {
                        "predicted_price": 35000000,
                        "low_bound": 30000000,
                        "mid_bound": 35000000,
                        "high_bound": 40000000,
                        "confidence_interval": [30000000, 40000000],
                        "model_version": "xgboost_v1.0"
                    }
                ],
                "total_processed": 1,
                "processing_time_ms": 150.0
            }
        }


class ErrorResponse(BaseModel):
    """Error response schema"""
    error: str = Field(..., description="Error description")
    detail: Optional[str] = Field(None, description="Detailed error information")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")
    
    class Config:
        schema_extra = {
            "example": {
                "error": "Model not loaded",
                "detail": "The prediction models are not available. Please try again later.",
                "timestamp": "2024-01-15T10:30:00Z"
            }
        }


def preprocess_input_data(property_input: PropertyInput) -> np.ndarray:
    """
    Convert input data to feature matrix for model prediction
    """
    try:
        feature_engineer = NigerianRealEstateFeatures()
        
        # Create dataframe from input
        input_dict = property_input.dict()
        df = pd.DataFrame([input_dict])
        
        # Engineer features
        df_engineered = feature_engineer.engineer_features(df)
        
        # Create feature matrix
        feature_matrix = feature_engineer.create_feature_matrix(df_engineered)
        
        return feature_matrix
        
    except Exception as e:
        logger.error(f"Error preprocessing input data: {e}")
        raise HTTPException(status_code=500, detail=f"Feature preprocessing failed: {str(e)}")


def generate_shap_explanation(features: np.ndarray, prediction: float, 
                        explainer: shap.TreeExplainer, top_k: int = 3) -> List[FeatureContribution]:
    """
    Generate SHAP explanations for prediction
    """
    try:
        # Calculate SHAP values
        shap_values = explainer.shap_values(features)
        feature_names = explainer.feature_names
        
        # Get top contributing features
        if len(shap_values[0]) != len(feature_names):
            logger.warning("SHAP values and feature names length mismatch")
            return []
        
        # Get absolute values and sort
        abs_shap = np.abs(shap_values[0])
        top_indices = np.argsort(abs_shap)[-top_k:]
        
        explanations = []
        feature_descriptions = {
            'property_age': 'Older properties generally worth less due to maintenance needs',
            'bedroom_count': 'Bedroom count is a primary driver of property value',
            'square_meters': 'Property size is fundamental to price calculation',
            'distance_to_cbd': 'Proximity to Central Business District affects property value',
            'lga_median_price': 'Local area prices establish baseline for property valuation',
            'has_generator': 'Generator adds value in areas with unreliable electricity',
            'distance_to_nearest_landmark': 'Proximity to landmarks like airports, malls increases accessibility value',
            'development_score': 'Development potential affects long-term value appreciation',
            'price_density_score': 'Price relative to area indicates market positioning',
        }
        
        for idx in reversed(top_indices):
            feature_name = feature_names[idx]
            contribution = float(shap_values[0][idx])
            description = feature_descriptions.get(feature_name, f"Feature {feature_name} impacts prediction")
            
            # Create human-readable explanation
            if contribution > 0:
                explanation = f"+₦{contribution:,.0f} because {description.lower()}"
            else:
                explanation = f"-₦{abs(contribution):,.0f} because {description.lower()}"
            
            explanations.append(FeatureContribution(
                feature=feature_name,
                contribution=contribution,
                description=explanation
            ))
        
        return explanations
        
    except Exception as e:
        logger.error(f"Error generating SHAP explanation: {e}")
        return []


@app.post("/predict", response_model=PredictionResponse, status_code=200)
async def predict_property_price(property_input: PropertyInput):
    """
    Predict property price with SHAP explanations
    """
    start_time = datetime.utcnow()
    
    try:
        if not model or not model.is_trained:
            raise HTTPException(
                status_code=503,
                detail="Prediction models not available. Please try again later."
            )
        
        # Preprocess input
        features = preprocess_input_data(property_input)
        
        # Make prediction
        prediction = model.predict(features)
        
        # Generate SHAP explanation
        explainer = shap.TreeExplainer(model.model_mid)
        explanations = generate_shap_explanation(features, prediction['predicted_price'], explainer)
        
        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        response = PredictionResponse(
            predicted_price=prediction['predicted_price'],
            low_bound=prediction['low_bound'],
            mid_bound=prediction['mid_bound'],
            high_bound=prediction['high_bound'],
            confidence_interval=prediction['confidence_interval'],
            model_version=prediction['model_version'],
            explanation=explanations,
            accuracy_metrics=model.feature_importance
        )
        
        logger.info(f"Prediction completed for property in {property_input.city}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in prediction: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Prediction failed: {str(e)}"
        )


@app.post("/predict/batch", response_model=BatchPredictionResponse, status_code=200)
async def predict_batch_properties(request: BatchPredictionRequest):
    """
    Predict multiple property prices with SHAP explanations
    """
    start_time = datetime.utcnow()
    
    try:
        if not model or not model.is_trained:
            raise HTTPException(
                status_code=503,
                detail="Prediction models not available. Please try again later."
            )
        
        predictions = []
        
        for property_input in request.properties:
            try:
                # Preprocess input
                features = preprocess_input_data(property_input)
                
                # Make prediction
                prediction = model.predict(features)
                
                # Generate SHAP explanation
                explainer = shap.TreeExplainer(model.model_mid)
                explanations = generate_shap_explanation(features, prediction['predicted_price'], explainer)
                
                predictions.append(PredictionResponse(
                    predicted_price=prediction['predicted_price'],
                    low_bound=prediction['low_bound'],
                    mid_bound=prediction['mid_bound'],
                    high_bound=prediction['high_bound'],
                    confidence_interval=prediction['confidence_interval'],
                    model_version=prediction['model_version'],
                    explanation=explanations
                ))
                
            except Exception as e:
                logger.error(f"Error predicting property: {e}")
                # Add error prediction
                predictions.append(PredictionResponse(
                    predicted_price=0,
                    low_bound=0,
                    mid_bound=0,
                    high_bound=0,
                    confidence_interval=[0, 0],
                    model_version="error",
                    explanation=[]
                ))
        
        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        response = BatchPredictionResponse(
            predictions=predictions,
            total_processed=len(request.properties),
            processing_time_ms=processing_time
        )
        
        logger.info(f"Batch prediction completed for {len(request.properties)} properties")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in batch prediction: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Batch prediction failed: {str(e)}"
        )


@app.get("/model/info", status_code=200)
async def get_model_info():
    """
    Get information about loaded models
    """
    try:
        if not model or not model.is_trained:
            raise HTTPException(
                status_code=503,
                detail="No models loaded"
            )
        
        return {
            "model_version": "xgboost_v1.0",
            "models_loaded": 3,
            "feature_count": len(model.feature_columns) if model.feature_columns else 0,
            "training_date": "2024-01-15",
            "hyperparameters": model.feature_importance,
            "performance_metrics": {
                "mae_mean": "N/A (Run evaluation)",
                "r2_mean": "N/A (Run evaluation)",
                "interval_accuracy": "N/A (Run evaluation)"
            },
            "feature_importance": model.feature_importance
        }
        
    except Exception as e:
        logger.error(f"Error getting model info: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get model info: {str(e)}"
        )


@app.get("/health", status_code=200)
async def health_check():
    """
    Health check endpoint
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "models_loaded": model.is_trained if model else False,
        "uptime": "healthy"
    }


@app.exception_handler(status_code=429)
async def rate_limit_exception_handler(request, exc):
    """Rate limit exception handler"""
    return JSONResponse(
        status_code=429,
        content={"error": "Rate limit exceeded", "detail": str(exc.detail)},
        headers={"Retry-After": "60"}
    )


@app.exception_handler(status_code=500)
async def general_exception_handler(request, exc):
    """General exception handler"""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": "An unexpected error occurred"},
        headers={"X-Error-ID": str(id(exc))}
    )


# Add rate limiting middleware
from slowapi import Request
from fastapi.concurrency import RateLimiter
import time

rate_limiter = RateLimiter(requests=100, window=60)  # 100 requests per minute

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Rate limiting middleware"""
    client_ip = request.client.host
    key = f"rate_limit:{client_ip}"
    
    # Check rate limit
    if not rate_limiter.test(key):
        logger.warning(f"Rate limit exceeded for IP: {client_ip}")
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please try again later."
        )
    
    response = await call_next(request)
    return response


# Apply rate limiting to prediction endpoints
for endpoint in [predict_property_price, predict_batch_properties]:
    app.middleware("http")(rate_limit_middleware)(endpoint)


if __name__ == "__main__":
    import uvicorn
    
    logger.info("Starting PropEase Property Price Prediction API")
    
    # Run with uvicorn for production
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        access_log=True
    )
