"""
Generate synthetic Nigerian property dataset for price prediction.

This script creates realistic property data for Nigerian cities including
Lagos, Abuja, Port Harcourt, and other major cities with proper
geographic coordinates and price distributions.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import random
from typing import List, Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class NigerianPropertyDataGenerator:
    """Generate synthetic Nigerian property data."""
    
    def __init__(self, num_properties: int = 10000):
        """
        Initialize the data generator.
        
        Args:
            num_properties: Number of properties to generate
        """
        self.num_properties = num_properties
        
        # Nigerian cities with coordinates and median prices
        self.cities = {
            'Lagos': {
                'lat': 6.5244, 'lng': 3.3792,
                'median_price_per_sqm': 850000,  # Naira per sqm
                'cbd_lat': 6.6020, 'cbd_lng': 3.3474,  # Lagos Island CBD
                'price_multiplier': 1.0
            },
            'Abuja': {
                'lat': 9.0765, 'lng': 7.3986,
                'median_price_per_sqm': 650000,
                'cbd_lat': 9.0645, 'cbd_lng': 7.4865,  # Central Area
                'price_multiplier': 0.76
            },
            'Port Harcourt': {
                'lat': 4.8156, 'lng': 7.0498,
                'median_price_per_sqm': 450000,
                'cbd_lat': 4.8156, 'cbd_lng': 7.0498,  # City center
                'price_multiplier': 0.53
            },
            'Kano': {
                'lat': 11.9504, 'lng': 8.5154,
                'median_price_per_sqm': 350000,
                'cbd_lat': 11.9504, 'cbd_lng': 8.5154,  # City center
                'price_multiplier': 0.41
            },
            'Ibadan': {
                'lat': 7.3775, 'lng': 3.9470,
                'median_price_per_sqm': 280000,
                'cbd_lat': 7.3775, 'cbd_lng': 3.9470,  # City center
                'price_multiplier': 0.33
            },
            'Enugu': {
                'lat': 6.4419, 'lng': 7.5028,
                'median_price_per_sqm': 320000,
                'cbd_lat': 6.4419, 'cbd_lng': 7.5028,  # City center
                'price_multiplier': 0.38
            },
            'Benin City': {
                'lat': 6.3350, 'lng': 5.6037,
                'median_price_per_sqm': 250000,
                'cbd_lat': 6.3350, 'lng': 5.6037,  # City center
                'price_multiplier': 0.29
            },
            'Warri': {
                'lat': 5.5453, 'lng': 5.7579,
                'median_price_per_sqm': 380000,
                'cbd_lat': 5.5453, 'lng': 5.7579,  # City center
                'price_multiplier': 0.45
            }
        }
        
        # Property types with price multipliers
        self.property_types = {
            'Apartment': {'multiplier': 1.0, 'min_size': 45, 'max_size': 200},
            'Duplex': {'multiplier': 1.8, 'min_size': 120, 'max_size': 400},
            'Detached House': {'multiplier': 1.5, 'min_size': 100, 'max_size': 350},
            'Terrace House': {'multiplier': 1.2, 'min_size': 80, 'max_size': 250},
            'Bungalow': {'multiplier': 1.3, 'min_size': 90, 'max_size': 300},
            'Penthouse': {'multiplier': 2.2, 'min_size': 150, 'max_size': 500},
            'Studio': {'multiplier': 0.7, 'min_size': 25, 'max_size': 60}
        }
        
        # LGAs (Local Government Areas) with price variations
        self.lgas = {
            'Lagos': {
                'Ikoyi': 1.8, 'Victoria Island': 1.6, 'Lekki': 1.4,
                'Surulere': 1.1, 'Ikeja': 1.2, 'Agege': 0.8,
                'Mushin': 0.7, 'Badagry': 0.6, 'Ikorodu': 0.5
            },
            'Abuja': {
                'Asokoro': 1.7, 'Maitama': 1.5, 'Wuse': 1.3,
                'Garki': 1.1, 'Jabi': 1.0, 'Gwarimpa': 0.9,
                'Kubwa': 0.7, 'Nyanya': 0.6, 'Bwari': 0.5
            },
            'Port Harcourt': {
                'GRA': 1.6, 'Rumuola': 1.3, 'Diobu': 1.0,
                'Rumukwurushi': 0.9, 'Eleme': 0.8, 'Obio-Akpor': 0.7
            }
        }
    
    def generate_properties(self) -> pd.DataFrame:
        """
        Generate synthetic property data.
        
        Returns:
            DataFrame with property data
        """
        logger.info(f"Generating {self.num_properties} synthetic properties...")
        
        properties = []
        
        for i in range(self.num_properties):
            property_data = self._generate_single_property(i)
            properties.append(property_data)
        
        df = pd.DataFrame(properties)
        
        # Add calculated features
        df = self._add_calculated_features(df)
        
        logger.info(f"Generated {len(df)} properties with {len(df.columns)} features")
        return df
    
    def _generate_single_property(self, index: int) -> Dict:
        """Generate a single property record."""
        # Select city
        city = random.choice(list(self.cities.keys()))
        city_info = self.cities[city]
        
        # Select property type
        prop_type = random.choice(list(self.property_types.keys()))
        type_info = self.property_types[prop_type]
        
        # Generate coordinates around city center
        lat_offset = np.random.normal(0, 0.1)  # ~11km radius
        lng_offset = np.random.normal(0, 0.1)
        lat = city_info['lat'] + lat_offset
        lng = city_info['lng'] + lng_offset
        
        # Generate property features
        size_sqm = np.random.uniform(type_info['min_size'], type_info['max_size'])
        bedrooms = self._generate_bedrooms(prop_type, size_sqm)
        bathrooms = max(1, bedrooms - np.random.randint(0, 2))
        
        # Generate age (newer properties in premium areas)
        age_years = max(0, int(np.random.exponential(15)))  # Exponential distribution
        
        # Select LGA if available
        lga = self._select_lga(city)
        lga_multiplier = self.lgas.get(city, {}).get(lga, 1.0)
        
        # Calculate base price
        base_price_per_sqm = city_info['median_price_per_sqm']
        property_multiplier = type_info['multiplier']
        
        # Apply multipliers
        price_per_sqm = (
            base_price_per_sqm * 
            property_multiplier * 
            lga_multiplier * 
            np.random.uniform(0.7, 1.3)  # Random variation
        )
        
        # Apply age discount
        age_discount = 1.0 - (age_years * 0.01)  # 1% per year
        age_discount = max(0.4, age_discount)  # Minimum 40% of original value
        
        price_per_sqm *= age_discount
        
        # Calculate total price
        total_price = price_per_sqm * size_sqm
        
        # Add property features
        has_parking = random.random() < 0.7
        has_pool = random.random() < 0.15
        has_gym = random.random() < 0.2
        has_security = random.random() < 0.6
        has_elevator = random.random() < 0.3 if bedrooms > 2 else False
        
        # Generate listing date (last 3 years)
        days_ago = random.randint(0, 1095)  # 0-3 years
        listing_date = datetime.now() - timedelta(days=days_ago)
        
        return {
            'property_id': f'PROP_{index:06d}',
            'city': city,
            'lga': lga,
            'property_type': prop_type,
            'latitude': lat,
            'longitude': lng,
            'size_sqm': round(size_sqm, 1),
            'bedrooms': bedrooms,
            'bathrooms': bathrooms,
            'age_years': age_years,
            'price_per_sqm': round(price_per_sqm),
            'total_price_naira': round(total_price),
            'has_parking': has_parking,
            'has_pool': has_pool,
            'has_gym': has_gym,
            'has_security': has_security,
            'has_elevator': has_elevator,
            'listing_date': listing_date,
            'days_on_market': days_ago
        }
    
    def _generate_bedrooms(self, prop_type: str, size_sqm: float) -> int:
        """Generate realistic bedroom count based on property type and size."""
        if prop_type == 'Studio':
            return 1
        elif prop_type == 'Apartment':
            if size_sqm < 60:
                return 1
            elif size_sqm < 100:
                return random.choice([1, 2])
            elif size_sqm < 150:
                return random.choice([2, 3])
            else:
                return random.choice([3, 4])
        elif prop_type in ['Duplex', 'Detached House']:
            if size_sqm < 200:
                return random.choice([2, 3])
            elif size_sqm < 300:
                return random.choice([3, 4, 5])
            else:
                return random.choice([4, 5, 6])
        else:
            return max(1, int(size_sqm / 50))
    
    def _select_lga(self, city: str) -> str:
        """Select LGA for the given city."""
        if city in self.lgas:
            lgas = list(self.lgas[city].keys())
            return random.choice(lgas)
        return 'Central'
    
    def _add_calculated_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add calculated features to the dataset."""
        logger.info("Adding calculated features...")
        
        # Distance to CBD using Haversine formula
        df['distance_to_cbd_km'] = df.apply(self._calculate_distance_to_cbd, axis=1)
        
        # LGA median price
        df['lga_median_price'] = df.groupby(['city', 'lga'])['price_per_sqm'].transform('median')
        
        # Price per bedroom
        df['price_per_bedroom'] = df['total_price_naira'] / df['bedrooms']
        
        # Size to bedroom ratio
        df['size_per_bedroom'] = df['size_sqm'] / df['bedrooms']
        
        # Property age category
        df['age_category'] = pd.cut(
            df['age_years'],
            bins=[0, 5, 10, 20, 50, 100],
            labels=['New', 'Modern', 'Established', 'Old', 'Very Old']
        )
        
        # Luxury score based on features
        df['luxury_score'] = (
            df['has_pool'].astype(int) * 3 +
            df['has_gym'].astype(int) * 2 +
            df['has_elevator'].astype(int) * 2 +
            df['has_security'].astype(int) * 1 +
            df['has_parking'].astype(int) * 1
        )
        
        # Price category
        df['price_category'] = pd.cut(
            df['total_price_naira'],
            bins=[0, 5000000, 15000000, 30000000, 60000000, float('inf')],
            labels=['Budget', 'Mid-range', 'Upper-mid', 'Luxury', 'Ultra-luxury']
        )
        
        # Location premium (distance-based)
        df['location_premium'] = np.exp(-df['distance_to_cbd_km'] / 10)  # Decay with distance
        
        return df
    
    def _calculate_distance_to_cbd(self, row: pd.Series) -> float:
        """Calculate distance to CBD using Haversine formula."""
        from haversine import haversine
        
        city_info = self.cities[row['city']]
        cbd_coords = (city_info['cbd_lat'], city_info['cbd_lng'])
        property_coords = (row['latitude'], row['longitude'])
        
        distance_km = haversine(property_coords, cbd_coords)
        return round(distance_km, 2)
    
    def save_dataset(self, df: pd.DataFrame, filepath: str):
        """Save the dataset to CSV."""
        logger.info(f"Saving dataset to {filepath}")
        df.to_csv(filepath, index=False)
        logger.info(f"Dataset saved: {len(df)} properties, {len(df.columns)} columns")
    
    def get_data_summary(self, df: pd.DataFrame) -> Dict:
        """Get summary statistics of the dataset."""
        summary = {
            'total_properties': len(df),
            'cities': df['city'].nunique(),
            'property_types': df['property_type'].nunique(),
            'price_stats': {
                'mean_price': df['total_price_naira'].mean(),
                'median_price': df['total_price_naira'].median(),
                'min_price': df['total_price_naira'].min(),
                'max_price': df['total_price_naira'].max()
            },
            'size_stats': {
                'mean_size': df['size_sqm'].mean(),
                'median_size': df['size_sqm'].median(),
                'min_size': df['size_sqm'].min(),
                'max_size': df['size_sqm'].max()
            },
            'feature_correlations': {
                'price_size_corr': df['total_price_naira'].corr(df['size_sqm']),
                'price_bedroom_corr': df['total_price_naira'].corr(df['bedrooms']),
                'price_distance_corr': df['total_price_naira'].corr(df['distance_to_cbd_km'])
            }
        }
        return summary


def main():
    """Main function to generate and save the dataset."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate Nigerian property dataset')
    parser.add_argument('--num-properties', type=int, default=10000, help='Number of properties to generate')
    parser.add_argument('--output', type=str, default='data/nigerian_properties.csv', help='Output file path')
    parser.add_argument('--seed', type=int, default=42, help='Random seed')
    
    args = parser.parse_args()
    
    # Set random seed
    np.random.seed(args.seed)
    random.seed(args.seed)
    
    # Create data directory
    import os
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    
    # Generate dataset
    generator = NigerianPropertyDataGenerator(args.num_properties)
    df = generator.generate_properties()
    
    # Save dataset
    generator.save_dataset(df, args.output)
    
    # Print summary
    summary = generator.get_data_summary(df)
    print("\n" + "="*50)
    print("DATASET SUMMARY")
    print("="*50)
    print(f"Total Properties: {summary['total_properties']:,}")
    print(f"Cities: {summary['cities']}")
    print(f"Property Types: {summary['property_types']}")
    print(f"\nPrice Statistics (Naira):")
    print(f"  Mean: ₦{summary['price_stats']['mean_price']:,.0f}")
    print(f"  Median: ₦{summary['price_stats']['median_price']:,.0f}")
    print(f"  Range: ₦{summary['price_stats']['min_price']:,.0f} - ₦{summary['price_stats']['max_price']:,.0f}")
    print(f"\nSize Statistics (sqm):")
    print(f"  Mean: {summary['size_stats']['mean_size']:.1f}")
    print(f"  Median: {summary['size_stats']['median_size']:.1f}")
    print(f"  Range: {summary['size_stats']['min_size']:.1f} - {summary['size_stats']['max_size']:.1f}")
    print(f"\nCorrelations:")
    print(f"  Price-Size: {summary['feature_correlations']['price_size_corr']:.3f}")
    print(f"  Price-Bedrooms: {summary['feature_correlations']['price_bedroom_corr']:.3f}")
    print(f"  Price-Distance: {summary['feature_correlations']['price_distance_corr']:.3f}")
    print("="*50)


if __name__ == '__main__':
    main()
