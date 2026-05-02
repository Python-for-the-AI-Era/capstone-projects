"""
Feature Engineering for Nigerian Real Estate Price Prediction
Implements geospatial calculations and property-specific features
"""

import numpy as np
import pandas as pd
from typing import Tuple, Optional
from dataclasses import dataclass
import requests
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import logging

logger = logging.getLogger(__name__)


@dataclass
class PropertyFeatures:
    """Data class for engineered property features"""
    # Basic property features
    property_age: float
    bedroom_count: int
    bathroom_count: int
    total_rooms: int
    parking_spaces: int
    
    # Location features
    latitude: float
    longitude: float
    distance_to_cbd: float  # Distance to Central Business District
    distance_to_nearest_landmark: float
    is_waterfront: bool
    is_corner_lot: bool
    
    # Neighborhood features
    lga_median_price: float  # Local Government Area median price
    neighborhood_price_per_sqm: float
    price_density_score: float  # Price per square meter relative to area
    
    # Market features
    days_on_market: int
    price_change_percentage: float
    is_price_reduced: bool
    competing_properties_count: int
    
    # Quality features
    has_generator: bool
    has_borehole: bool
    has_air_conditioning: bool
    has_security_system: bool
    building_condition_score: float  # 1-5 scale based on age and features
    
    # Size features
    price_per_sqm: float
    size_category: str  # 'small', 'medium', 'large', 'luxury'
    
    # Investment features
    rental_yield_estimate: float
    appreciation_potential: float
    development_score: float  # Potential for redevelopment/extension


class NigerianRealEstateFeatures:
    """
    Feature engineering specifically for Nigerian real estate market
    Includes location-based features, market indicators, and property characteristics
    """
    
    def __init__(self):
        # Nigerian major cities coordinates (approximate)
        self.nigeria_cities = {
            'lagos': {'lat': 6.4550, 'lon': 3.3841, 'cbd_lat': 6.4531, 'cbd_lon': 3.3792},
            'abuja': {'lat': 9.0579, 'lon': 7.4951, 'cbd_lat': 9.0649, 'cbd_lon': 7.4898},
            'port_harcourt': {'lat': 4.8156, 'lon': 7.0498, 'cbd_lat': 4.8156, 'cbd_lon': 7.0498},
            'kano': {'lat': 11.9504, 'lon': 8.5112, 'cbd_lat': 11.9504, 'cbd_lon': 8.5112},
            'ibadan': {'lat': 7.3775, 'lon': 3.9470, 'cbd_lat': 7.3775, 'cbd_lon': 3.9470},
            'benin_city': {'lat': 6.6037, 'lon': 5.6315, 'cbd_lat': 6.6037, 'cbd_lon': 5.6315},
            'enugu': {'lat': 6.4419, 'lon': 7.5030, 'cbd_lat': 6.4419, 'cbd_lon': 7.5030},
        }
        
        # Major landmarks and their coordinates
        self.landmarks = {
            'lekki_phase_1': {'lat': 6.4429, 'lon': 3.5146},
            'victoria_island': {'lat': 6.4537, 'lon': 3.4253},
            'ikeja_city_mall': {'lat': 6.4341, 'lon': 3.4762},
            'murtala_muhammed_airport': {'lat': 6.5774, 'lon': 3.3212},
            'apapa_port': {'lat': 6.4550, 'lon': 3.3841},
            'tincan_island': {'lat': 6.4550, 'lon': 3.3841},
        }
        
        # LGA (Local Government Area) median prices by state
        self.lga_median_prices = {
            'lagos': {
                'ikeja': 45000000,  # Naira per square meter
                'lekki': 55000000,
                'surulere': 35000000,
                'ajah': 30000000,
                'agege': 28000000,
                'ikorodu': 25000000,
                'oshodi_isolo': 32000000,
                'epe': 29000000,
                'badagry': 27000000,
                'amuwo_odofin': 26000000,
                'ifako_ijaye': 24000000,
                'shomolu': 31000000,
                'munshin': 40000000,
                'alimosho': 38000000,
            },
            'abuja': {
                'maitama': 38000000,
                'bwar': 35000000,
                'gwarinpa': 42000000,
                'kuje': 40000000,
                'abaji': 32000000,
                'bwari': 36000000,
                'kwali': 34000000,
                'kuje': 41000000,
                'bwari': 36000000,
            },
            'rivers': {
                'port_harcourt': 28000000,
                'obio_akpor': 25000000,
                'ikwerre': 22000000,
                'ogba': 26000000,
                'oyigbo': 24000000,
                'etche': 23000000,
                'degema': 21000000,
            },
        }
    
    def haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate the great circle distance between two points on the earth (specified in decimal degrees)
        Returns distance in kilometers
        """
        # Convert decimal degrees to radians
        lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
        
        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
        c = 2 * np.arcsin2(np.sqrt(a))
        
        r = 6371.0  # Radius of earth in kilometers
        return r * c
    
    def geocode_address(self, address: str) -> Optional[Tuple[float, float]]:
        """
        Geocode Nigerian address using Nominatim
        Returns (latitude, longitude) or None if not found
        """
        try:
            geolocator = Nominatim(user_agent="PropEase_NG")
            location = geolocator.geocode(f"{address}, Nigeria")
            
            if location:
                return (location.latitude, location.longitude)
            return None
        except Exception as e:
            logger.error(f"Geocoding failed for address '{address}': {e}")
            return None
    
    def get_nearest_landmark_distance(self, lat: float, lon: float) -> Tuple[float, str]:
        """
        Find distance to nearest landmark
        Returns (distance_km, landmark_name)
        """
        min_distance = float('inf')
        nearest_landmark = None
        
        for landmark_name, landmark_coords in self.landmarks.items():
            distance = self.haversine_distance(
                lat, lon, landmark_coords['lat'], landmark_coords['lon']
            )
            
            if distance < min_distance:
                min_distance = distance
                nearest_landmark = landmark_name
        
        return min_distance, nearest_landmark or ("unknown", "")
    
    def get_lga_median_price(self, state: str, lga: str) -> float:
        """
        Get median price per square meter for LGA
        """
        return self.lga_median_prices.get(state, {}).get(lga, 30000000)  # Default fallback
    
    def calculate_property_age_score(self, age_years: float) -> float:
        """
        Calculate building condition score based on age
        Newer properties get higher scores
        """
        if age_years <= 5:
            return 5.0  # Excellent
        elif age_years <= 10:
            return 4.0  # Good
        elif age_years <= 20:
            return 3.0  # Fair
        elif age_years <= 30:
            return 2.0  # Poor
        else:
            return 1.0  # Very Poor
    
    def calculate_size_category(self, sqm: float) -> str:
        """
        Categorize property size based on Nigerian market standards
        """
        if sqm < 100:
            return 'small'
        elif sqm < 250:
            return 'medium'
        elif sqm < 500:
            return 'large'
        else:
            return 'luxury'
    
    def calculate_price_density_score(self, price: float, sqm: float, lga_median: float) -> float:
        """
        Calculate how expensive the property is relative to local area
        Higher score means more expensive relative to area median
        """
        if sqm <= 0:
            return 1.0
        
        price_per_sqm = price / sqm
        median_ratio = price_per_sqm / lga_median if lga_median > 0 else 1.0
        
        # Normalize to 0-1 scale (higher = more expensive)
        return min(median_ratio, 2.0)
    
    def calculate_rental_yield(self, price: float, sqm: float) -> float:
        """
        Estimate rental yield based on Nigerian market averages
        Annual rental yield = (monthly_rent * 12) / property_price
        """
        # Rough estimate based on property type and location
        # This would be refined with actual rental data
        monthly_rent_estimate = price * 0.008  # ~0.8% monthly rental rate
        annual_rent = monthly_rent_estimate * 12
        return (annual_rent / price) * 100 if price > 0 else 0
    
    def calculate_appreciation_potential(self, location_lat: float, location_lon: float, 
                                  property_age: float, size_category: str) -> float:
        """
        Calculate appreciation potential based on location and property characteristics
        """
        base_potential = 0.05  # 5% base annual appreciation
        
        # Location multiplier (prime areas appreciate faster)
        city_boosts = {
            'lagos': 1.2,  # Premium location
            'abuja': 1.1,  # Capital city
            'port_harcourt': 1.15,  # Oil & gas hub
        }
        
        # Find nearest city
        min_city_distance = float('inf')
        location_boost = 1.0
        
        for city, coords in self.nigeria_cities.items():
            distance = self.haversine_distance(
                location_lat, location_lon, coords['lat'], coords['lon']
            )
            if distance < min_city_distance:
                min_city_distance = distance
                location_boost = city_boosts.get(city, 1.0)
        
        # Property age factor
        age_factor = max(0.5, 1.0 - (property_age / 40))  # Older properties appreciate less
        
        # Size factor (medium sizes appreciate most)
        size_factors = {'small': 0.9, 'medium': 1.0, 'large': 1.1, 'luxury': 1.2}
        size_factor = size_factors.get(size_category, 1.0)
        
        return base_potential * location_boost * age_factor * size_factor
    
    def calculate_development_score(self, sqm: float, location_lat: float, location_lon: float) -> float:
        """
        Calculate development potential based on zoning and location
        """
        # Simplified scoring - in reality this would use zoning maps
        base_score = 0.5
        
        # Location factor (proximity to commercial areas)
        _, nearest_landmark = self.get_nearest_landmark_distance(location_lat, location_lon)
        if nearest_landmark and nearest_landmark[1] < 5:  # Within 5km of major landmark
            base_score += 0.3
        
        # Size factor (larger properties have more development potential)
        if sqm > 1000:
            base_score += 0.2
        elif sqm > 500:
            base_score += 0.1
        
        return min(base_score, 1.0)
    
    def engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Main feature engineering pipeline
        Takes raw property data and returns engineered features
        """
        logger.info(f"Starting feature engineering for {len(df)} properties")
        
        engineered_features = []
        
        for idx, row in df.iterrows():
            try:
                # Extract basic features
                property_age = 2024 - row.get('year_built', 2020)
                bedroom_count = row.get('bedrooms', 3)
                bathroom_count = row.get('bathrooms', 2)
                total_rooms = bedroom_count + bathroom_count + row.get('living_rooms', 1)
                parking_spaces = row.get('parking_spaces', 1)
                sqm = row.get('square_meters', 120)
                price = row.get('price', 50000000)
                
                # Get location features
                lat = row.get('latitude')
                lon = row.get('longitude')
                
                if lat is None or lon is None:
                    # Try to geocode address
                    address = f"{row.get('address', '')}, {row.get('city', '')}, Nigeria"
                    geocoded = self.geocode_address(address)
                    if geocoded:
                        lat, lon = geocoded
                    else:
                        lat, lon = self.nigeria_cities['lagos']['lat'], self.nigeria_cities['lagos']['lon']
                
                # Calculate distance features
                distance_to_cbd = self.haversine_distance(
                    lat, lon,
                    self.nigeria_cities['lagos']['cbd_lat'], 
                    self.nigeria_cities['lagos']['cbd_lon']
                )
                
                distance_to_landmark, nearest_landmark = self.get_nearest_landmark_distance(lat, lon)
                
                # Get LGA median price
                city = row.get('city', 'lagos').lower()
                lga = row.get('lga', 'ikeja').lower()
                lga_median_price = self.get_lga_median_price('lagos', lga)
                
                # Calculate engineered features
                features = PropertyFeatures(
                    property_age=property_age,
                    bedroom_count=bedroom_count,
                    bathroom_count=bathroom_count,
                    total_rooms=total_rooms,
                    parking_spaces=parking_spaces,
                    latitude=lat,
                    longitude=lon,
                    distance_to_cbd=distance_to_cbd,
                    distance_to_nearest_landmark=distance_to_landmark,
                    is_waterfront=row.get('is_waterfront', False),
                    is_corner_lot=row.get('is_corner_lot', False),
                    lga_median_price=lga_median_price,
                    neighborhood_price_per_sqm=lga_median_price,
                    price_density_score=self.calculate_price_density_score(price, sqm, lga_median_price),
                    days_on_market=row.get('days_on_market', 30),
                    price_change_percentage=row.get('price_change_percentage', 0),
                    is_price_reduced=row.get('price_change_percentage', 0) < 0,
                    competing_properties_count=row.get('competing_properties', 0),
                    has_generator=row.get('has_generator', False),
                    has_borehole=row.get('has_borehole', False),
                    has_air_conditioning=row.get('has_air_conditioning', False),
                    has_security_system=row.get('has_security_system', False),
                    building_condition_score=self.calculate_property_age_score(property_age),
                    price_per_sqm=price / sqm if sqm > 0 else 0,
                    size_category=self.calculate_size_category(sqm),
                    rental_yield_estimate=self.calculate_rental_yield(price, sqm),
                    appreciation_potential=self.calculate_appreciation_potential(
                        lat, lon, property_age, self.calculate_size_category(sqm)
                    ),
                    development_score=self.calculate_development_score(sqm, lat, lon)
                )
                
                engineered_features.append(features)
                
            except Exception as e:
                logger.error(f"Error engineering features for property {idx}: {e}")
                # Add a basic feature record even if engineering fails
                engineered_features.append(PropertyFeatures(
                    property_age=0, bedroom_count=3, bathroom_count=2, total_rooms=5,
                    parking_spaces=1, latitude=0, longitude=0, distance_to_cbd=50,
                    distance_to_nearest_landmark=50, is_waterfront=False, is_corner_lot=False,
                    lga_median_price=30000000, neighborhood_price_per_sqm=250000,
                    price_density_score=1.0, days_on_market=30, price_change_percentage=0,
                    is_price_reduced=False, competing_properties_count=0, has_generator=False,
                    has_borehole=False, has_air_conditioning=False, has_security_system=False,
                    building_condition_score=3.0, price_per_sqm=0, size_category='medium',
                    rental_yield_estimate=0, appreciation_potential=0.05, development_score=0.5
                ))
        
        logger.info(f"Successfully engineered features for {len(engineered_features)} properties")
        return pd.DataFrame([vars(f) for f in engineered_features])
    
    def create_feature_matrix(self, df: pd.DataFrame) -> np.ndarray:
        """
        Convert engineered features to numpy matrix for model training
        """
        feature_columns = [
            'property_age', 'bedroom_count', 'bathroom_count', 'total_rooms',
            'parking_spaces', 'latitude', 'longitude', 'distance_to_cbd',
            'distance_to_nearest_landmark', 'is_waterfront', 'is_corner_lot',
            'lga_median_price', 'neighborhood_price_per_sqm', 'price_density_score',
            'days_on_market', 'price_change_percentage', 'is_price_reduced',
            'competing_properties_count', 'has_generator', 'has_borehole',
            'has_air_conditioning', 'has_security_system', 'building_condition_score',
            'price_per_sqm', 'size_category', 'rental_yield_estimate',
            'appreciation_potential', 'development_score'
        ]
        
        # Ensure all features exist, fill missing with defaults
        for col in feature_columns:
            if col not in df.columns:
                df[col] = 0  # Default value
        
        feature_matrix = df[feature_columns].values
        logger.info(f"Created feature matrix with shape: {feature_matrix.shape}")
        
        return feature_matrix
    
    def get_feature_importance_hints(self) -> dict:
        """
        Return domain knowledge about feature importance for Nigerian real estate
        """
        return {
            'distance_to_cbd': {
                'importance': 'high',
                'reasoning': 'Proximity to Central Business District is the strongest price predictor in Nigerian cities'
            },
            'lga_median_price': {
                'importance': 'high',
                'reasoning': 'Local area median prices establish baseline for property valuation'
            },
            'property_age': {
                'importance': 'medium',
                'reasoning': 'Building condition affects value, newer properties generally worth more'
            },
            'bedroom_count': {
                'importance': 'medium',
                'reasoning': 'Bedroom count is a primary driver of property value'
            },
            'square_meters': {
                'importance': 'high',
                'reasoning': 'Property size is fundamental to price calculation'
            },
            'has_generator': {
                'importance': 'low',
                'reasoning': 'Generator adds value in areas with unreliable electricity'
            },
            'distance_to_landmark': {
                'importance': 'medium',
                'reasoning': 'Proximity to landmarks like airports, malls increases accessibility value'
            },
            'development_score': {
                'importance': 'low',
                'reasoning': 'Development potential affects long-term value appreciation'
            }
        }
