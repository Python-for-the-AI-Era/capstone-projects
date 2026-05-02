"""
XGBoost Property Price Prediction Model
Implements advanced ensemble modeling with quantile regression for confidence bounds
"""

import numpy as np
import pandas as pd
import xgboost as xgb
import joblib
import optuna
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_absolute_percentage_error, r2_score, mean_squared_error
from sklearn.preprocessing import StandardScaler, LabelEncoder
import logging
from typing import Dict, Any, Tuple, List
import warnings

logger = logging.getLogger(__name__)


class PropertyPriceModel:
    """
    Advanced XGBoost model for Nigerian real estate price prediction
    Implements quantile regression for confidence bounds
    """
    
    def __init__(self):
        self.model_mid = None
        self.model_low = None
        self.model_high = None
        self.scaler = StandardScaler()
        self.feature_columns = None
        self.feature_importance = None
        self.is_trained = False
        
        # Suppress warnings for cleaner output
        warnings.filterwarnings('ignore')
    
    def prepare_data(self, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """
        Prepare data for XGBoost training
        Handles categorical encoding and scaling
        """
        logger.info(f"Preparing data with shape: {df.shape}")
        
        # Create features and target
        feature_columns = [
            'property_age', 'bedroom_count', 'bathroom_count', 'total_rooms',
            'parking_spaces', 'distance_to_cbd', 'distance_to_nearest_landmark',
            'is_waterfront', 'is_corner_lot', 'lga_median_price',
            'neighborhood_price_per_sqm', 'price_density_score',
            'days_on_market', 'price_change_percentage', 'is_price_reduced',
            'competing_properties_count', 'has_generator', 'has_borehole',
            'has_air_conditioning', 'has_security_system', 'building_condition_score',
            'price_per_sqm', 'size_category', 'rental_yield_estimate',
            'appreciation_potential', 'development_score'
        ]
        
        # Handle missing values
        df_clean = df[feature_columns + ['price']].copy()
        
        # Fill missing values
        numeric_columns = df_clean.select_dtypes(include=[np.number]).columns
        for col in numeric_columns:
            df_clean[col] = df_clean[col].fillna(df_clean[col].median())
        
        categorical_columns = df_clean.select_dtypes(include=['object', 'category']).columns
        for col in categorical_columns:
            df_clean[col] = df_clean[col].fillna('unknown')
        
        # Encode categorical variables
        df_encoded = df_clean.copy()
        label_encoders = {}
        
        for col in ['size_category', 'building_condition_score']:
            if col in df_encoded.columns:
                le = LabelEncoder()
                df_encoded[col] = le.fit_transform(df_encoded[col])
                label_encoders[col] = le
        
        # Prepare features and target
        X = df_encoded[feature_columns].values
        y = df_encoded['price'].values
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        self.feature_columns = feature_columns
        logger.info(f"Data prepared successfully. Features: {len(feature_columns)}")
        
        return X_scaled, y
    
    def objective_quantile(self, y: np.ndarray, alpha: float) -> str:
        """
        Custom quantile objective for XGBoost
        """
        def quantile_loss(y_true, y_pred):
            # Quantile loss function
            delta = y_true - y_pred
            mask = delta >= 0
            return np.mean((alpha - mask) * delta - alpha * np.abs(delta))
        
        return quantile_loss
    
    def train_quantile_models(self, X: np.ndarray, y: np.ndarray, 
                         alpha_low: float = 0.1, alpha_high: float = 0.9,
                         cv_folds: int = 5) -> Dict[str, Any]:
        """
        Train two XGBoost models for quantile regression
        One for lower bound (10th percentile) and one for upper bound (90th percentile)
        """
        logger.info(f"Training quantile models with alpha_low={alpha_low}, alpha_high={alpha_high}")
        
        # Split data for validation
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        models = {}
        
        # Train lower bound model
        params_low = {
            'objective': f'reg:quantilelossalpha={alpha_low}',
            'eval_metric': 'mae',
            'learning_rate': 0.05,
            'max_depth': 7,
            'min_child_weight': 1,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'n_estimators': 200,
            'random_state': 42
        }
        
        model_low = xgb.XGBRegressor(**params_low)
        model_low.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            early_stopping_rounds=50,
            verbose=False
        )
        
        # Train upper bound model
        params_high = {
            'objective': f'reg:quantilelossalpha={alpha_high}',
            'eval_metric': 'mae',
            'learning_rate': 0.05,
            'max_depth': 7,
            'min_child_weight': 1,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'n_estimators': 200,
            'random_state': 42
        }
        
        model_high = xgb.XGBRegressor(**params_high)
        model_high.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            early_stopping_rounds=50,
            verbose=False
        )
        
        models['low'] = model_low
        models['high'] = model_high
        
        # Evaluate models
        for name, model in models.items():
            y_pred = model.predict(X_val)
            mae = mean_absolute_error(y_val, y_pred)
            
            logger.info(f"Model {name} - MAE: {mae:.2f}")
            
            # Cross-validation
            cv_scores = cross_val_score(
                model, X_train, y_train,
                cv=cv_folds,
                scoring='neg_mean_absolute_error',
                n_jobs=-1
            )
            
            logger.info(f"Model {name} - CV MAE: {-np.mean(cv_scores):.2f} (+/- {np.std(cv_scores):.2f})")
        
        return models
    
    def train_mean_model(self, X: np.ndarray, y: np.ndarray) -> xgb.XGBRegressor:
        """
        Train standard XGBoost model for median price prediction
        """
        logger.info("Training mean regression model")
        
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        params = {
            'objective': 'reg:squarederror',
            'eval_metric': 'mae',
            'learning_rate': 0.05,
            'max_depth': 7,
            'min_child_weight': 1,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'n_estimators': 200,
            'random_state': 42
        }
        
        model = xgb.XGBRegressor(**params)
        model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            early_stopping_rounds=50,
            verbose=False
        )
        
        # Evaluate
        y_pred = model.predict(X_val)
        mae = mean_absolute_error(y_val, y_pred)
        r2 = r2_score(y_val, y_pred)
        
        logger.info(f"Mean model - MAE: {mae:.2f}, R2: {r2:.3f}")
        
        return model
    
    def hyperparameter_optimization(self, X: np.ndarray, y: np.ndarray, 
                              n_trials: int = 50) -> Dict[str, Any]:
        """
        Optimize XGBoost hyperparameters using Optuna
        """
        logger.info(f"Starting hyperparameter optimization with {n_trials} trials")
        
        def objective(trial):
            # Define search space
            param = {
                'max_depth': trial.suggest_int('max_depth', 3, 10),
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
                'n_estimators': trial.suggest_int('n_estimators', 50, 300),
                'min_child_weight': trial.suggest_int('min_child_weight', 1, 10),
                'subsample': trial.suggest_float('subsample', 0.6, 1.0),
                'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
                'gamma': trial.suggest_float('gamma', 0, 5),
                'reg_alpha': trial.suggest_float('reg_alpha', 0, 1),
                'reg_lambda': trial.suggest_float('reg_lambda', 0, 1),
            }
            
            # Cross-validation
            cv_scores = cross_val_score(
                xgb.XGBRegressor(**param, random_state=trial.number),
                X, y, cv=3, scoring='neg_mean_absolute_error', n_jobs=-1
            )
            
            return np.mean(cv_scores)
        
        # Create study
        study = optuna.create_study(direction='minimize')
        study.optimize(objective, n_trials=n_trials)
        
        best_params = study.best_params
        best_score = study.best_value
        
        logger.info(f"Best parameters: {best_params}")
        logger.info(f"Best CV MAE: {best_score:.2f}")
        
        return {
            'best_params': best_params,
            'best_score': best_score,
            'n_trials': n_trials
        }
    
    def train(self, df: pd.DataFrame, optimize: bool = True, n_trials: int = 50) -> Dict[str, Any]:
        """
        Complete training pipeline
        """
        logger.info(f"Starting model training with {len(df)} samples")
        
        # Prepare data
        X, y = self.prepare_data(df)
        
        # Hyperparameter optimization
        best_params = {}
        if optimize:
            opt_result = self.hyperparameter_optimization(X, y, n_trials)
            best_params = opt_result['best_params']
            logger.info("Using optimized hyperparameters")
        else:
            # Default parameters
            best_params = {
                'max_depth': 7,
                'learning_rate': 0.05,
                'n_estimators': 200,
                'min_child_weight': 1,
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'gamma': 0,
                'reg_alpha': 0,
                'reg_lambda': 1,
            }
            logger.info("Using default hyperparameters")
        
        # Train quantile models
        quantile_models = self.train_quantile_models(X, y)
        self.model_low = quantile_models['low']
        self.model_high = quantile_models['high']
        
        # Train mean model
        self.model_mid = self.train_mean_model(X, y)
        
        # Calculate feature importance
        self.feature_importance = self._calculate_feature_importance()
        
        self.is_trained = True
        logger.info("Model training completed successfully")
        
        return {
            'models_trained': 3,
            'hyperparameters': best_params,
            'feature_importance': self.feature_importance
        }
    
    def _calculate_feature_importance(self) -> Dict[str, float]:
        """
        Calculate feature importance using mean model as reference
        """
        if not self.is_trained or not self.model_mid:
            return {}
        
        importance = self.model_mid.feature_importances_
        feature_names = self.feature_columns
        
        importance_dict = {}
        for name, score in zip(feature_names, importance):
            importance_dict[name] = float(score)
        
        # Sort by importance
        sorted_importance = dict(
            sorted(importance_dict.items(), key=lambda x: x[1], reverse=True)
        )
        
        return sorted_importance
    
    def predict(self, features: np.ndarray) -> Dict[str, Any]:
        """
        Make predictions with confidence bounds
        """
        if not self.is_trained:
            raise ValueError("Model must be trained before making predictions")
        
        # Scale features
        features_scaled = self.scaler.transform(features)
        
        # Predict with all models
        pred_low = self.model_low.predict(features_scaled)[0]
        pred_mid = self.model_mid.predict(features_scaled)[0]
        pred_high = self.model_high.predict(features_scaled)[0]
        
        # Inverse transform if needed (for quantile models)
        # Note: XGBoost outputs are already in original scale
        
        return {
            'predicted_price': pred_mid,
            'low_bound': pred_low,
            'high_bound': pred_high,
            'confidence_interval': (pred_low, pred_high),
            'model_version': 'xgboost_v1.0'
        }
    
    def save_models(self, model_dir: str = 'models') -> None:
        """
        Save all trained models
        """
        if not self.is_trained:
            raise ValueError("No models to save")
        
        import os
        os.makedirs(model_dir, exist_ok=True)
        
        # Save models
        joblib.dump(self.model_low, f"{model_dir}/xgboost_low.pkl")
        joblib.dump(self.model_mid, f"{model_dir}/xgboost_mid.pkl")
        joblib.dump(self.model_high, f"{model_dir}/xgboost_high.pkl")
        joblib.dump(self.scaler, f"{model_dir}/scaler.pkl")
        
        # Save feature importance
        import json
        with open(f"{model_dir}/feature_importance.json", 'w') as f:
            json.dump(self.feature_importance, f, indent=2)
        
        logger.info(f"Models saved to {model_dir}")
    
    def load_models(self, model_dir: str = 'models') -> None:
        """
        Load trained models
        """
        import os
        import json
        
        if not os.path.exists(model_dir):
            raise FileNotFoundError(f"Model directory {model_dir} not found")
        
        # Load models
        self.model_low = joblib.load(f"{model_dir}/xgboost_low.pkl")
        self.model_mid = joblib.load(f"{model_dir}/xgboost_mid.pkl")
        self.model_high = joblib.load(f"{model_dir}/xgboost_high.pkl")
        self.scaler = joblib.load(f"{model_dir}/scaler.pkl")
        
        # Load feature importance
        with open(f"{model_dir}/feature_importance.json", 'r') as f:
            self.feature_importance = json.load(f)
        
        self.is_trained = True
        logger.info(f"Models loaded from {model_dir}")
    
    def evaluate_model(self, X_test: np.ndarray, y_test: np.ndarray) -> Dict[str, float]:
        """
        Comprehensive model evaluation
        """
        if not self.is_trained:
            raise ValueError("Model must be trained before evaluation")
        
        # Scale test data
        X_test_scaled = self.scaler.transform(X_test)
        
        # Predictions
        y_pred_mid = self.model_mid.predict(X_test_scaled)
        y_pred_low = self.model_low.predict(X_test_scaled)
        y_pred_high = self.model_high.predict(X_test_scaled)
        
        # Metrics for mean model
        mae_mid = mean_absolute_error(y_test, y_pred_mid)
        mse_mid = mean_squared_error(y_test, y_pred_mid)
        r2_mid = r2_score(y_test, y_pred_mid)
        mape_mid = mean_absolute_percentage_error(y_test, y_pred_mid)
        
        # Metrics for quantile models
        mae_low = mean_absolute_error(y_test, y_pred_low)
        mae_high = mean_absolute_error(y_test, y_pred_high)
        
        # Calculate confidence interval accuracy
        within_interval = 0
        for i in range(len(y_test)):
            if y_pred_low[i] <= y_test[i] <= y_pred_high[i]:
                within_interval += 1
        
        interval_accuracy = within_interval / len(y_test)
        
        results = {
            'mae_mean': mae_mid,
            'mse_mean': mse_mid,
            'r2_mean': r2_mid,
            'mape_mean': mape_mid,
            'mae_low': mae_low,
            'mae_high': mae_high,
            'interval_accuracy': interval_accuracy,
            'samples': len(y_test)
        }
        
        logger.info(f"Model evaluation completed: {results}")
        return results


# Convenience functions for training
def train_property_price_model(data_path: str, model_save_path: str = 'models', 
                           optimize: bool = True, n_trials: int = 50) -> PropertyPriceModel:
    """
    Train property price prediction model from data file
    """
    # Load data
    df = pd.read_csv(data_path)
    logger.info(f"Loaded data from {data_path}: {df.shape}")
    
    # Initialize and train model
    model = PropertyPriceModel()
    training_results = model.train(df, optimize=optimize, n_trials=n_trials)
    
    # Save models
    model.save_models(model_save_path)
    
    # Evaluate on holdout set
    from .feature_engineering import NigerianRealEstateFeatures
    feature_engineer = NigerianRealEstateFeatures()
    
    # Create engineered features
    df_engineered = feature_engineer.engineer_features(df)
    
    # Prepare final features
    feature_matrix = feature_engineer.create_feature_matrix(df_engineered)
    target = df_engineered['price'].values
    
    # Split for evaluation
    from sklearn.model_selection import train_test_split
    X_train, X_test, y_train, y_test = train_test_split(
        feature_matrix, target, test_size=0.2, random_state=42
    )
    
    # Evaluate final model
    evaluation_results = model.evaluate_model(X_test, y_test)
    
    logger.info("Training pipeline completed successfully")
    
    return {
        'model': model,
        'training_results': training_results,
        'evaluation_results': evaluation_results,
        'data_shape': df.shape,
        'feature_matrix_shape': feature_matrix.shape
    }


if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python model_training.py <data_file>")
        sys.exit(1)
    
    data_file = sys.argv[1]
    results = train_property_price_model(data_file)
    
    print("\n" + "="*50)
    print("TRAINING RESULTS")
    print("="*50)
    print(f"Data shape: {results['data_shape']}")
    print(f"Feature matrix shape: {results['feature_matrix_shape']}")
    print(f"Models trained: {results['training_results']['models_trained']}")
    print(f"Hyperparameters: {results['training_results']['hyperparameters']}")
    print(f"Evaluation MAE: {results['evaluation_results']['mae_mean']:.2f}")
    print(f"Evaluation R2: {results['evaluation_results']['r2_mean']:.3f}")
    print(f"Interval Accuracy: {results['evaluation_results']['interval_accuracy']:.2f}")
    print("="*50)
