"""
Feature engineering utilities for property price prediction.

This module provides comprehensive feature engineering capabilities
including distance calculations, encoding, and feature transformations.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from haversine import haversine
from sklearn.preprocessing import LabelEncoder, StandardScaler, MinMaxScaler
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
import logging

logger = logging.getLogger(__name__)


class PropertyFeatureEngineer:
    """Feature engineering for property price prediction."""
    
    def __init__(self):
        """Initialize the feature engineer."""
        self.encoders = {}
        self.scalers = {}
        self.feature_columns = []
        self.target_column = 'total_price_naira'
        
        # Feature groups
        self.numeric_features = [
            'size_sqm', 'bedrooms', 'bathrooms', 'age_years',
            'distance_to_cbd_km', 'lga_median_price', 'price_per_bedroom',
            'size_per_bedroom', 'luxury_score', 'location_premium'
        ]
        
        self.categorical_features = [
            'city', 'lga', 'property_type', 'age_category', 'price_category'
        ]
        
        self.binary_features = [
            'has_parking', 'has_pool', 'has_gym', 'has_security', 'has_elevator'
        ]
        
        # All features
        self.all_features = self.numeric_features + self.categorical_features + self.binary_features
    
    def fit_transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Fit transformers and transform the data.
        
        Args:
            df: Input dataframe
            
        Returns:
            Transformed dataframe
        """
        logger.info("Fitting and transforming features...")
        
        # Create a copy to avoid modifying original data
        df_transformed = df.copy()
        
        # Ensure all required features exist
        self._validate_features(df_transformed)
        
        # Handle missing values
        df_transformed = self._handle_missing_values(df_transformed)
        
        # Encode categorical features
        df_transformed = self._encode_categorical_features(df_transformed, fit=True)
        
        # Scale numerical features
        df_transformed = self._scale_numerical_features(df_transformed, fit=True)
        
        # Create interaction features
        df_transformed = self._create_interaction_features(df_transformed)
        
        # Store feature columns
        self.feature_columns = [col for col in df_transformed.columns if col != self.target_column]
        
        logger.info(f"Feature engineering completed. Features: {len(self.feature_columns)}")
        return df_transformed
    
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transform data using fitted transformers.
        
        Args:
            df: Input dataframe
            
        Returns:
            Transformed dataframe
        """
        logger.info("Transforming features...")
        
        # Create a copy
        df_transformed = df.copy()
        
        # Handle missing values
        df_transformed = self._handle_missing_values(df_transformed)
        
        # Encode categorical features
        df_transformed = self._encode_categorical_features(df_transformed, fit=False)
        
        # Scale numerical features
        df_transformed = self._scale_numerical_features(df_transformed, fit=False)
        
        # Create interaction features
        df_transformed = self._create_interaction_features(df_transformed)
        
        return df_transformed
    
    def _validate_features(self, df: pd.DataFrame):
        """Validate that all required features exist."""
        missing_features = []
        
        for feature in self.all_features:
            if feature not in df.columns:
                missing_features.append(feature)
        
        if missing_features:
            raise ValueError(f"Missing required features: {missing_features}")
        
        if self.target_column not in df.columns:
            raise ValueError(f"Missing target column: {self.target_column}")
    
    def _handle_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """Handle missing values in the dataset."""
        logger.info("Handling missing values...")
        
        # For numerical features, use median
        for feature in self.numeric_features:
            if feature in df.columns and df[feature].isnull().any():
                median_value = df[feature].median()
                df[feature].fillna(median_value, inplace=True)
                logger.debug(f"Filled missing values in {feature} with median: {median_value}")
        
        # For categorical features, use mode
        for feature in self.categorical_features:
            if feature in df.columns and df[feature].isnull().any():
                mode_value = df[feature].mode()[0]
                df[feature].fillna(mode_value, inplace=True)
                logger.debug(f"Filled missing values in {feature} with mode: {mode_value}")
        
        # For binary features, use mode
        for feature in self.binary_features:
            if feature in df.columns and df[feature].isnull().any():
                mode_value = df[feature].mode()[0]
                df[feature].fillna(mode_value, inplace=True)
                logger.debug(f"Filled missing values in {feature} with mode: {mode_value}")
        
        return df
    
    def _encode_categorical_features(self, df: pd.DataFrame, fit: bool) -> pd.DataFrame:
        """Encode categorical features."""
        logger.info("Encoding categorical features...")
        
        for feature in self.categorical_features:
            if feature not in df.columns:
                continue
            
            if fit:
                # Fit and transform
                encoder = LabelEncoder()
                df[f'{feature}_encoded'] = encoder.fit_transform(df[feature].astype(str))
                self.encoders[feature] = encoder
                logger.debug(f"Fitted encoder for {feature}")
            else:
                # Transform only
                if feature in self.encoders:
                    encoder = self.encoders[feature]
                    # Handle unseen categories
                    unique_values = set(df[feature].astype(str).unique())
                    known_values = set(encoder.classes_)
                    
                    # Map unseen categories to 'unknown'
                    df[feature] = df[feature].astype(str)
                    df.loc[~df[feature].isin(known_values), feature] = 'unknown'
                    
                    # Add 'unknown' to encoder classes if not present
                    if 'unknown' not in known_values:
                        encoder.classes_ = np.append(encoder.classes_, 'unknown')
                    
                    df[f'{feature}_encoded'] = encoder.transform(df[feature])
                    logger.debug(f"Transformed {feature}")
                else:
                    logger.warning(f"No encoder found for {feature}")
                    df[f'{feature}_encoded'] = 0  # Default value
        
        return df
    
    def _scale_numerical_features(self, df: pd.DataFrame, fit: bool) -> pd.DataFrame:
        """Scale numerical features."""
        logger.info("Scaling numerical features...")
        
        for feature in self.numeric_features:
            if feature not in df.columns:
                continue
            
            if fit:
                # Fit and transform
                scaler = StandardScaler()
                df[f'{feature}_scaled'] = scaler.fit_transform(df[[feature]])
                self.scalers[feature] = scaler
                logger.debug(f"Fitted scaler for {feature}")
            else:
                # Transform only
                if feature in self.scalers:
                    scaler = self.scalers[feature]
                    df[f'{feature}_scaled'] = scaler.transform(df[[feature]])
                    logger.debug(f"Scaled {feature}")
                else:
                    logger.warning(f"No scaler found for {feature}")
                    df[f'{feature}_scaled'] = 0  # Default value
        
        return df
    
    def _create_interaction_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create interaction features."""
        logger.info("Creating interaction features...")
        
        # Size * Bedrooms interaction
        if 'size_sqm' in df.columns and 'bedrooms' in df.columns:
            df['size_bedroom_interaction'] = df['size_sqm'] * df['bedrooms']
        
        # Distance * Location premium
        if 'distance_to_cbd_km' in df.columns and 'location_premium' in df.columns:
            df['distance_premium_interaction'] = df['distance_to_cbd_km'] * df['location_premium']
        
        # Age * Luxury score
        if 'age_years' in df.columns and 'luxury_score' in df.columns:
            df['age_luxury_interaction'] = df['age_years'] * df['luxury_score']
        
        # Price per sqm * LGA median price
        if 'price_per_sqm' in df.columns and 'lga_median_price' in df.columns:
            df['price_lga_interaction'] = df['price_per_sqm'] * df['lga_median_price']
        
        # Bathroom to bedroom ratio
        if 'bathrooms' in df.columns and 'bedrooms' in df.columns:
            df['bathroom_bedroom_ratio'] = df['bathrooms'] / df['bedrooms']
            df['bathroom_bedroom_ratio'].fillna(1.0, inplace=True)  # Handle division by zero
        
        # Size per bathroom
        if 'size_sqm' in df.columns and 'bathrooms' in df.columns:
            df['size_per_bathroom'] = df['size_sqm'] / df['bathrooms']
            df['size_per_bathroom'].fillna(df['size_sqm'], inplace=True)  # Handle division by zero
        
        # Log transformations for skewed features
        if 'total_price_naira' in df.columns:
            df['log_price'] = np.log1p(df['total_price_naira'])
        
        if 'size_sqm' in df.columns:
            df['log_size'] = np.log1p(df['size_sqm'])
        
        if 'distance_to_cbd_km' in df.columns:
            df['log_distance'] = np.log1p(df['distance_to_cbd_km'])
        
        return df
    
    def get_feature_names(self) -> List[str]:
        """Get the names of engineered features."""
        return self.feature_columns
    
    def get_feature_importance_groups(self) -> Dict[str, List[str]]:
        """Get feature groups for importance analysis."""
        feature_groups = {
            'size_related': ['size_sqm_scaled', 'log_size', 'size_per_bedroom', 'size_per_bathroom'],
            'location_related': ['city_encoded', 'lga_encoded', 'distance_to_cbd_km_scaled', 'log_distance', 'location_premium'],
            'property_features': ['bedrooms_scaled', 'bathrooms_scaled', 'property_type_encoded', 'age_years_scaled'],
            'amenities': ['has_parking', 'has_pool', 'has_gym', 'has_security', 'has_elevator', 'luxury_score'],
            'price_indicators': ['lga_median_price_scaled', 'price_per_bedroom_scaled', 'price_lga_interaction'],
            'interactions': ['size_bedroom_interaction', 'distance_premium_interaction', 'age_luxury_interaction']
        }
        
        # Filter to only include features that actually exist
        available_features = set(self.feature_columns)
        filtered_groups = {}
        
        for group, features in feature_groups.items():
            existing_features = [f for f in features if f in available_features]
            if existing_features:
                filtered_groups[group] = existing_features
        
        return filtered_groups
    
    def create_preprocessing_pipeline(self) -> ColumnTransformer:
        """Create a scikit-learn preprocessing pipeline."""
        from sklearn.preprocessing import OneHotEncoder, StandardScaler
        from sklearn.compose import ColumnTransformer
        
        # Define preprocessing for different column types
        numeric_transformer = Pipeline(steps=[
            ('scaler', StandardScaler())
        ])
        
        categorical_transformer = Pipeline(steps=[
            ('onehot', OneHotEncoder(handle_unknown='ignore'))
        ])
        
        # Create column transformer
        preprocessor = ColumnTransformer(
            transformers=[
                ('num', numeric_transformer, self.numeric_features),
                ('cat', categorical_transformer, self.categorical_features)
            ],
            remainder='passthrough'  # Keep binary features as-is
        )
        
        return preprocessor
    
    def save_transformers(self, filepath: str):
        """Save fitted transformers."""
        import joblib
        
        transformers = {
            'encoders': self.encoders,
            'scalers': self.scalers,
            'feature_columns': self.feature_columns,
            'all_features': self.all_features
        }
        
        joblib.dump(transformers, filepath)
        logger.info(f"Transformers saved to {filepath}")
    
    def load_transformers(self, filepath: str):
        """Load fitted transformers."""
        import joblib
        
        transformers = joblib.load(filepath)
        self.encoders = transformers['encoders']
        self.scalers = transformers['scalers']
        self.feature_columns = transformers['feature_columns']
        self.all_features = transformers['all_features']
        
        logger.info(f"Transformers loaded from {filepath}")


class DistanceCalculator:
    """Calculate distances for property features."""
    
    # CBD coordinates for major Nigerian cities
    CBD_COORDINATES = {
        'Lagos': (6.6020, 3.3474),      # Lagos Island
        'Abuja': (9.0645, 7.4865),      # Central Area
        'Port Harcourt': (4.8156, 7.0498), # City Center
        'Kano': (11.9504, 8.5154),      # City Center
        'Ibadan': (7.3775, 3.9470),      # City Center
        'Enugu': (6.4419, 7.5028),       # City Center
        'Benin City': (6.3350, 5.6037),  # City Center
        'Warri': (5.5453, 5.7579),       # City Center
    }
    
    @staticmethod
    def calculate_distance_to_cbd(lat: float, lng: float, city: str) -> float:
        """
        Calculate distance to CBD using Haversine formula.
        
        Args:
            lat: Property latitude
            lng: Property longitude
            city: City name
            
        Returns:
            Distance in kilometers
        """
        if city not in DistanceCalculator.CBD_COORDINATES:
            return 0.0  # Default if city not found
        
        cbd_coords = DistanceCalculator.CBD_COORDINATES[city]
        property_coords = (lat, lng)
        
        distance_km = haversine(property_coords, cbd_coords)
        return round(distance_km, 2)
    
    @staticmethod
    def calculate_distance_between_points(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """
        Calculate distance between two points.
        
        Args:
            lat1, lng1: First point coordinates
            lat2, lng2: Second point coordinates
            
        Returns:
            Distance in kilometers
        """
        point1 = (lat1, lng1)
        point2 = (lat2, lng2)
        
        distance_km = haversine(point1, point2)
        return round(distance_km, 2)
    
    @staticmethod
    def batch_calculate_distances(df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate distances for a batch of properties.
        
        Args:
            df: DataFrame with latitude, longitude, and city columns
            
        Returns:
            DataFrame with distance_to_cbd_km column added
        """
        if all(col in df.columns for col in ['latitude', 'longitude', 'city']):
            df['distance_to_cbd_km'] = df.apply(
                lambda row: DistanceCalculator.calculate_distance_to_cbd(
                    row['latitude'], row['longitude'], row['city']
                ),
                axis=1
            )
        
        return df


def create_feature_matrix(df: pd.DataFrame, target_column: str = 'total_price_naira') -> Tuple[pd.DataFrame, pd.Series]:
    """
    Create feature matrix and target vector.
    
    Args:
        df: Input dataframe
        target_column: Name of target column
        
    Returns:
        Tuple of (features, target)
    """
    # Separate features and target
    features = df.drop(columns=[target_column])
    target = df[target_column]
    
    return features, target


def validate_features(features: pd.DataFrame, expected_features: List[str]) -> bool:
    """
    Validate that all expected features are present.
    
    Args:
        features: Feature dataframe
        expected_features: List of expected feature names
        
    Returns:
        True if all features are present, False otherwise
    """
    missing_features = set(expected_features) - set(features.columns)
    
    if missing_features:
        logger.error(f"Missing features: {missing_features}")
        return False
    
    return True
