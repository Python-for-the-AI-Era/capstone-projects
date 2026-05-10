"""
Credit Data Generator for Model Drift Detection

This module generates synthetic credit data that simulates realistic scenarios
including concept drift and data drift over time.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Tuple, Dict, List, Optional
import logging
from sklearn.datasets import make_classification
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


class CreditDataGenerator:
    """
    Generates synthetic credit data with controlled drift patterns.
    
    This class creates realistic credit application data that can be used
    to test model drift detection algorithms. It supports various types of
    drift including gradual, sudden, and recurring patterns.
    """
    
    def __init__(self, random_state: int = 42):
        """
        Initialize the data generator.
        
        Args:
            random_state: Random seed for reproducibility
        """
        self.random_state = random_state
        np.random.seed(random_state)
        self.feature_names = [
            'credit_score', 'annual_income', 'debt_to_income_ratio', 
            'employment_length', 'loan_amount', 'loan_term',
            'home_ownership', 'purpose', 'num_credit_lines',
            'credit_history_length', 'recent_inquiries', 'derogatory_marks'
        ]
        
    def generate_training_data(
        self, 
        n_samples: int = 10000,
        target_default_rate: float = 0.15
    ) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Generate training data with stable characteristics.
        
        Args:
            n_samples: Number of samples to generate
            target_default_rate: Target default rate for the dataset
            
        Returns:
            Tuple of (features DataFrame, target Series)
        """
        logger.info(f"Generating {n_samples} training samples with {target_default_rate:.2%} default rate")
        
        # Generate base features
        X, y = self._generate_base_features(n_samples, target_default_rate)
        
        # Create DataFrame with proper feature names
        df = pd.DataFrame(X, columns=self.feature_names)
        
        # Add realistic correlations and constraints
        df = self._add_realistic_constraints(df)
        
        # Create target series
        target = pd.Series(y, name='default')
        
        logger.info(f"Generated training data: {df.shape}")
        logger.info(f"Actual default rate: {target.mean():.2%}")
        
        return df, target
    
    def generate_production_data(
        self,
        n_samples: int = 1000,
        start_date: datetime = None,
        drift_type: str = "gradual",
        drift_magnitude: float = 0.3,
        external_events: Optional[List[Dict]] = None
    ) -> Tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
        """
        Generate production data with drift patterns.
        
        Args:
            n_samples: Number of samples to generate
            start_date: Start date for data generation
            drift_type: Type of drift ('gradual', 'sudden', 'recurring', 'seasonal')
            drift_magnitude: Magnitude of drift (0.0 to 1.0)
            external_events: List of external events that affect data distribution
            
        Returns:
            Tuple of (features DataFrame, target Series, metadata DataFrame)
        """
        if start_date is None:
            start_date = datetime.now() - timedelta(days=90)
            
        logger.info(f"Generating {n_samples} production samples with {drift_type} drift")
        
        # Generate base data
        X, y = self._generate_base_features(n_samples, 0.15)
        df = pd.DataFrame(X, columns=self.feature_names)
        
        # Apply drift patterns
        df = self._apply_drift_patterns(df, drift_type, drift_magnitude, start_date, n_samples)
        
        # Apply external events
        if external_events:
            df = self._apply_external_events(df, external_events, start_date)
        
        # Add realistic constraints
        df = self._add_realistic_constraints(df)
        
        # Create timestamps and metadata
        timestamps = self._generate_timestamps(start_date, n_samples)
        metadata = pd.DataFrame({
            'application_date': timestamps,
            'application_id': [f"APP_{i:06d}" for i in range(n_samples)],
            'drift_applied': [drift_type] * n_samples
        })
        
        # Adjust target based on drift
        y = self._adjust_target_for_drift(y, drift_type, drift_magnitude, df)
        target = pd.Series(y, name='default')
        
        logger.info(f"Generated production data: {df.shape}")
        logger.info(f"Production default rate: {target.mean():.2%}")
        
        return df, target, metadata
    
    def _generate_base_features(self, n_samples: int, default_rate: float) -> Tuple[np.ndarray, np.ndarray]:
        """Generate base features using sklearn's make_classification."""
        # Create correlated features with realistic distributions
        X, y = make_classification(
            n_samples=n_samples,
            n_features=12,
            n_informative=10,
            n_redundant=2,
            n_clusters_per_class=2,
            weights=[1 - default_rate, default_rate],
            flip_y=0.01,
            random_state=self.random_state
        )
        
        # Scale features to realistic ranges
        X = self._scale_features_to_realistic_ranges(X)
        
        return X, y
    
    def _scale_features_to_realistic_ranges(self, X: np.ndarray) -> np.ndarray:
        """Scale features to realistic credit data ranges."""
        # Define realistic ranges for each feature
        feature_ranges = {
            0: (300, 850),      # credit_score
            1: (20000, 200000), # annual_income
            2: (0.0, 0.8),      # debt_to_income_ratio
            3: (0, 40),         # employment_length
            4: (1000, 50000),   # loan_amount
            5: (12, 360),       # loan_term
            6: (0, 3),          # home_ownership
            7: (0, 6),          # purpose
            8: (1, 20),         # num_credit_lines
            9: (1, 30),         # credit_history_length
            10: (0, 10),        # recent_inquiries
            11: (0, 10)         # derogatory_marks
        }
        
        X_scaled = np.zeros_like(X)
        
        for i in range(X.shape[1]):
            min_val, max_val = feature_ranges[i]
            # Normalize to [0, 1] then scale to target range
            X_norm = (X[:, i] - X[:, i].min()) / (X[:, i].max() - X[:, i].min())
            X_scaled[:, i] = X_norm * (max_val - min_val) + min_val
        
        return X_scaled
    
    def _add_realistic_constraints(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add realistic constraints and correlations to the data."""
        # Credit score and derogatory marks correlation
        df.loc[df['derogatory_marks'] > 5, 'credit_score'] = np.maximum(
            df.loc[df['derogatory_marks'] > 5, 'credit_score'] - 50, 300
        )
        
        # Income and loan amount correlation
        max_loan_ratio = 0.5  # Maximum loan amount as ratio of income
        max_loan = df['annual_income'] * max_loan_ratio / 12 * df['loan_term'] / 12
        df['loan_amount'] = np.minimum(df['loan_amount'], max_loan)
        
        # Debt-to-income ratio constraint
        monthly_payment = df['loan_amount'] * 0.005  # Rough monthly payment estimate
        monthly_income = df['annual_income'] / 12
        total_monthly_debt = monthly_payment + (monthly_income * df['debt_to_income_ratio'])
        df['debt_to_income_ratio'] = np.minimum(total_monthly_debt / monthly_income, 0.8)
        
        # Employment length and age correlation (if we had age)
        df.loc[df['employment_length'] > 30, 'employment_length'] = 30
        
        # Ensure credit score is within valid range
        df['credit_score'] = np.clip(df['credit_score'], 300, 850)
        
        return df
    
    def _apply_drift_patterns(
        self, 
        df: pd.DataFrame, 
        drift_type: str, 
        drift_magnitude: float,
        start_date: datetime,
        n_samples: int
    ) -> pd.DataFrame:
        """Apply different drift patterns to the data."""
        if drift_type == "gradual":
            return self._apply_gradual_drift(df, drift_magnitude, n_samples)
        elif drift_type == "sudden":
            return self._apply_sudden_drift(df, drift_magnitude, n_samples)
        elif drift_type == "recurring":
            return self._apply_recurring_drift(df, drift_magnitude, n_samples)
        elif drift_type == "seasonal":
            return self._apply_seasonal_drift(df, drift_magnitude, start_date, n_samples)
        else:
            return df
    
    def _apply_gradual_drift(self, df: pd.DataFrame, drift_magnitude: float, n_samples: int) -> pd.DataFrame:
        """Apply gradual drift over time."""
        # Gradual increase in loan amounts and decrease in credit scores
        for i in range(n_samples):
            progress = i / n_samples
            drift_factor = 1 + (drift_magnitude * progress)
            
            # Increase loan amounts
            df.loc[i, 'loan_amount'] *= drift_factor
            
            # Decrease credit scores slightly
            df.loc[i, 'credit_score'] *= (2 - drift_factor)
            df.loc[i, 'credit_score'] = np.maximum(df.loc[i, 'credit_score'], 300)
        
        return df
    
    def _apply_sudden_drift(self, df: pd.DataFrame, drift_magnitude: float, n_samples: int) -> pd.DataFrame:
        """Apply sudden drift at a specific point."""
        # Sudden change happens at 60% through the data
        change_point = int(n_samples * 0.6)
        
        # Before change point: normal distribution
        # After change point: shifted distribution
        for i in range(change_point, n_samples):
            # Increase debt-to-income ratio
            df.loc[i, 'debt_to_income_ratio'] *= (1 + drift_magnitude)
            df.loc[i, 'debt_to_income_ratio'] = np.minimum(df.loc[i, 'debt_to_income_ratio'], 0.8)
            
            # Increase loan amounts
            df.loc[i, 'loan_amount'] *= (1 + drift_magnitude * 0.5)
            
            # Change loan purpose distribution (more high-risk purposes)
            df.loc[i, 'purpose'] = np.random.choice([4, 5, 6], p=[0.3, 0.4, 0.3])
        
        return df
    
    def _apply_recurring_drift(self, df: pd.DataFrame, drift_magnitude: float, n_samples: int) -> pd.DataFrame:
        """Apply recurring drift patterns."""
        # Recurring drift every 100 samples
        cycle_length = 100
        
        for i in range(n_samples):
            cycle_position = i % cycle_length
            if cycle_position < 20:  # Drift period
                drift_factor = 1 + drift_magnitude
                
                # Increase risk factors during drift period
                df.loc[i, 'debt_to_income_ratio'] *= drift_factor
                df.loc[i, 'recent_inquiries'] *= drift_factor
                df.loc[i, 'derogatory_marks'] = min(df.loc[i, 'derogatory_marks'] + 1, 10)
        
        return df
    
    def _apply_seasonal_drift(
        self, 
        df: pd.DataFrame, 
        drift_magnitude: float,
        start_date: datetime,
        n_samples: int
    ) -> pd.DataFrame:
        """Apply seasonal drift patterns."""
        for i in range(n_samples):
            # Calculate day of year for seasonal pattern
            current_date = start_date + timedelta(days=i)
            day_of_year = current_date.timetuple().tm_yday
            
            # Seasonal factor (higher risk in winter months)
            seasonal_factor = 1 + drift_magnitude * 0.3 * np.sin(2 * np.pi * day_of_year / 365)
            
            if seasonal_factor > 1.1:  # High risk season
                df.loc[i, 'debt_to_income_ratio'] *= seasonal_factor
                df.loc[i, 'loan_amount'] *= seasonal_factor
                df.loc[i, 'purpose'] = np.random.choice([4, 5, 6], p=[0.2, 0.3, 0.5])
        
        return df
    
    def _apply_external_events(
        self, 
        df: pd.DataFrame, 
        external_events: List[Dict],
        start_date: datetime
    ) -> pd.DataFrame:
        """Apply external events that affect data distribution."""
        for event in external_events:
            event_date = event['date']
            event_impact = event['impact']
            affected_features = event.get('features', ['loan_amount', 'debt_to_income_ratio'])
            
            # Find samples around the event date
            for i in range(len(df)):
                sample_date = start_date + timedelta(days=i)
                days_since_event = (sample_date - event_date).days
                
                if 0 <= days_since_event <= event.get('duration_days', 30):
                    # Apply event impact
                    for feature in affected_features:
                        if feature in df.columns:
                            df.loc[i, feature] *= (1 + event_impact)
        
        return df
    
    def _generate_timestamps(self, start_date: datetime, n_samples: int) -> List[datetime]:
        """Generate timestamps for production data."""
        timestamps = []
        current_date = start_date
        
        for i in range(n_samples):
            # Add some randomness to timestamps (multiple applications per day)
            days_to_add = i // 10  # ~10 applications per day
            hours_to_add = np.random.randint(0, 24)
            minutes_to_add = np.random.randint(0, 60)
            
            timestamp = current_date + timedelta(
                days=days_to_add,
                hours=hours_to_add,
                minutes=minutes_to_add
            )
            timestamps.append(timestamp)
        
        return timestamps
    
    def _adjust_target_for_drift(
        self, 
        y: np.ndarray, 
        drift_type: str, 
        drift_magnitude: float,
        df: pd.DataFrame
    ) -> np.ndarray:
        """Adjust target variable based on drift patterns."""
        y_adjusted = y.copy()
        
        if drift_type == "gradual":
            # Gradual increase in default rate
            for i in range(len(y)):
                progress = i / len(y)
                if np.random.random() < drift_magnitude * progress:
                    y_adjusted[i] = 1 - y_adjusted[i]  # Flip the label
                    
        elif drift_type == "sudden":
            # Sudden increase in default rate after change point
            change_point = int(len(y) * 0.6)
            for i in range(change_point, len(y)):
                if np.random.random() < drift_magnitude * 0.3:
                    y_adjusted[i] = 1 - y_adjusted[i]
                    
        elif drift_type == "recurring":
            # Recurring increases in default rate
            cycle_length = 100
            for i in range(len(y)):
                cycle_position = i % cycle_length
                if cycle_position < 20:  # High risk period
                    if np.random.random() < drift_magnitude * 0.4:
                        y_adjusted[i] = 1 - y_adjusted[i]
        
        # Additional adjustments based on feature values
        # Higher debt-to-income ratio increases default probability
        high_dti_mask = df['debt_to_income_ratio'] > 0.5
        y_adjusted[high_dti_mask] = np.where(
            np.random.random(len(high_dti_mask)) < 0.3,
            1 - y_adjusted[high_dti_mask],
            y_adjusted[high_dti_mask]
        )
        
        # Lower credit score increases default probability
        low_credit_mask = df['credit_score'] < 600
        y_adjusted[low_credit_mask] = np.where(
            np.random.random(len(low_credit_mask)) < 0.25,
            1 - y_adjusted[low_credit_mask],
            y_adjusted[low_credit_mask]
        )
        
        return y_adjusted
    
    def create_external_events(self) -> List[Dict]:
        """Create predefined external events for testing."""
        today = datetime.now()
        
        events = [
            {
                'date': today - timedelta(days=60),
                'name': 'Economic Recession Start',
                'impact': 0.3,
                'duration_days': 45,
                'features': ['debt_to_income_ratio', 'credit_score', 'loan_amount'],
                'description': 'Economic downturn increases loan applications and risk'
            },
            {
                'date': today - timedelta(days=30),
                'name': 'New Loan Product Launch',
                'impact': 0.2,
                'duration_days': 15,
                'features': ['loan_amount', 'purpose'],
                'description': 'Launch of high-value loan product changes application patterns'
            },
            {
                'date': today - timedelta(days=10),
                'name': 'Marketing Campaign',
                'impact': 0.15,
                'duration_days:': 7,
                'features': ['annual_income', 'employment_length'],
                'description': 'Targeted marketing campaign changes applicant demographics'
            }
        ]
        
        return events
    
    def get_feature_descriptions(self) -> Dict[str, str]:
        """Get descriptions of all features."""
        return {
            'credit_score': 'Applicant credit score (300-850)',
            'annual_income': 'Annual income in USD',
            'debt_to_income_ratio': 'Total debt payments as percentage of income',
            'employment_length': 'Years at current employment',
            'loan_amount': 'Requested loan amount in USD',
            'loan_term': 'Loan term in months',
            'home_ownership': 'Home ownership status (0=rent, 1=own, 2=mortgage, 3=other)',
            'purpose': 'Loan purpose category (0=debt_consolidation, 1=home_improvement, 2=major_purchase, 3=business, 4=education, 5=other, 6=auto)',
            'num_credit_lines': 'Number of active credit lines',
            'credit_history_length': 'Length of credit history in years',
            'recent_inquiries': 'Number of credit inquiries in last 6 months',
            'derogatory_marks': 'Number of derogatory marks on credit report'
        }
