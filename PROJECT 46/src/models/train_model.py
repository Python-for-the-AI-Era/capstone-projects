"""
Model training module for property price prediction.

This module implements XGBoost training with Optuna hyperparameter search,
quantile regression for confidence bounds, and comprehensive model evaluation.
"""

import numpy as np
import pandas as pd
import optuna
from typing import Dict, List, Tuple, Optional, Any
import logging
from datetime import datetime
import joblib
import json
from pathlib import Path

# ML models
import xgboost as xgb
import lightgbm as lgb
from sklearn.model_selection import train_test_split, cross_val_score, KFold
from sklearn.metrics import mean_absolute_percentage_error, r2_score, mean_squared_error, mean_absolute_error
from sklearn.preprocessing import StandardScaler

# SHAP for explainability
import shap

logger = logging.getLogger(__name__)


class PropertyPriceModelTrainer:
    """Train property price prediction models with hyperparameter optimization."""
    
    def __init__(self, random_state: int = 42):
        """
        Initialize the model trainer.
        
        Args:
            random_state: Random state for reproducibility
        """
        self.random_state = random_state
        self.best_xgb_model = None
        self.quantile_low_model = None
        self.quantile_high_model = None
        self.feature_names = None
        self.scaler = StandardScaler()
        self.training_history = {}
        self.shap_explainer = None
        
        # Model parameters
        self.xgb_params = None
        self.quantile_params = None
        
        # Evaluation metrics
        self.evaluation_results = {}
        
        logger.info(f"Model trainer initialized with random_state={random_state}")
    
    def train_xgboost_model(
        self, 
        X_train: pd.DataFrame, 
        y_train: pd.Series,
        X_val: pd.DataFrame = None,
        y_val: pd.Series = None,
        n_trials: int = 50,
        timeout: int = 3600
    ) -> xgb.XGBRegressor:
        """
        Train XGBoost model with Optuna hyperparameter optimization.
        
        Args:
            X_train: Training features
            y_train: Training target
            X_val: Validation features
            y_val: Validation target
            n_trials: Number of Optuna trials
            timeout: Timeout in seconds
            
        Returns:
            Trained XGBoost model
        """
        logger.info(f"Starting XGBoost training with {n_trials} trials...")
        
        # Store feature names
        self.feature_names = X_train.columns.tolist()
        
        # Create validation set if not provided
        if X_val is None or y_val is None:
            X_train, X_val, y_train, y_val = train_test_split(
                X_train, y_train, test_size=0.2, random_state=self.random_state
            )
        
        # Scale target variable for better training
        y_train_scaled = np.log1p(y_train)
        y_val_scaled = np.log1p(y_val)
        
        # Define objective function for Optuna
        def objective(trial):
            # Define hyperparameters
            params = {
                'n_estimators': trial.suggest_int('n_estimators', 100, 1000),
                'max_depth': trial.suggest_int('max_depth', 3, 10),
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
                'subsample': trial.suggest_float('subsample', 0.6, 1.0),
                'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
                'colsample_bylevel': trial.suggest_float('colsample_bylevel', 0.6, 1.0),
                'min_child_weight': trial.suggest_int('min_child_weight', 1, 10),
                'gamma': trial.suggest_float('gamma', 0, 5),
                'reg_alpha': trial.suggest_float('reg_alpha', 0, 5),
                'reg_lambda': trial.suggest_float('reg_lambda', 0, 5),
                'random_state': self.random_state,
                'n_jobs': -1,
                'objective': 'reg:squarederror',
                'eval_metric': 'rmse'
            }
            
            # Train model
            model = xgb.XGBRegressor(**params)
            model.fit(
                X_train, y_train_scaled,
                eval_set=[(X_val, y_val_scaled)],
                early_stopping_rounds=50,
                verbose=False
            )
            
            # Predict and evaluate
            y_pred_scaled = model.predict(X_val)
            y_pred = np.expm1(y_pred_scaled)  # Inverse transform
            
            # Calculate MAPE
            mape = mean_absolute_percentage_error(y_val, y_pred)
            
            return mape
        
        # Create Optuna study
        study = optuna.create_study(
            direction='minimize',
            sampler=optuna.samplers.TPESampler(seed=self.random_state)
        )
        
        # Optimize
        study.optimize(objective, n_trials=n_trials, timeout=timeout)
        
        # Get best parameters
        best_params = study.best_params
        best_params.update({
            'random_state': self.random_state,
            'n_jobs': -1,
            'objective': 'reg:squarederror',
            'eval_metric': 'rmse'
        })
        
        self.xgb_params = best_params
        
        # Train final model with best parameters
        self.best_xgb_model = xgb.XGBRegressor(**best_params)
        self.best_xgb_model.fit(
            X_train, y_train_scaled,
            eval_set=[(X_val, y_val_scaled)],
            early_stopping_rounds=50,
            verbose=False
        )
        
        # Evaluate model
        self._evaluate_model(self.best_xgb_model, X_train, y_train, X_val, y_val, 'XGBoost')
        
        # Store training history
        self.training_history['xgboost'] = {
            'best_params': best_params,
            'best_trial': study.best_trial.number,
            'best_value': study.best_value,
            'n_trials': len(study.trials),
            'study_name': study.study_name
        }
        
        logger.info(f"XGBoost training completed. Best MAPE: {study.best_value:.4f}")
        return self.best_xgb_model
    
    def train_quantile_models(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        low_quantile: float = 0.1,
        high_quantile: float = 0.9
    ) -> Tuple[lgb.LGBMRegressor, lgb.LGBMRegressor]:
        """
        Train quantile regression models for confidence bounds.
        
        Args:
            X_train: Training features
            y_train: Training target
            low_quantile: Lower quantile (default: 0.1)
            high_quantile: Upper quantile (default: 0.9)
            
        Returns:
            Tuple of (low_quantile_model, high_quantile_model)
        """
        logger.info(f"Training quantile models for {low_quantile} and {high_quantile} quantiles...")
        
        # Base parameters for quantile regression
        base_params = {
            'objective': 'quantile',
            'metric': 'quantile',
            'boosting_type': 'gbdt',
            'num_leaves': 31,
            'learning_rate': 0.05,
            'feature_fraction': 0.9,
            'bagging_fraction': 0.8,
            'bagging_freq': 5,
            'verbose': -1,
            'random_state': self.random_state,
            'n_estimators': 1000
        }
        
        # Train low quantile model
        low_params = base_params.copy()
        low_params['alpha'] = low_quantile
        
        self.quantile_low_model = lgb.LGBMRegressor(**low_params)
        self.quantile_low_model.fit(X_train, y_train)
        
        # Train high quantile model
        high_params = base_params.copy()
        high_params['alpha'] = high_quantile
        
        self.quantile_high_model = lgb.LGBMRegressor(**high_params)
        self.quantile_high_model.fit(X_train, y_train)
        
        # Store parameters
        self.quantile_params = {
            'low_quantile': low_quantile,
            'high_quantile': high_quantile,
            'low_params': low_params,
            'high_params': high_params
        }
        
        logger.info("Quantile models training completed")
        return self.quantile_low_model, self.quantile_high_model
    
    def _evaluate_model(
        self,
        model: Any,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame,
        y_val: pd.Series,
        model_name: str
    ):
        """Evaluate model performance."""
        logger.info(f"Evaluating {model_name} model...")
        
        # Make predictions
        if isinstance(model, xgb.XGBRegressor):
            # For XGBoost, we trained on log-transformed target
            y_train_pred_scaled = model.predict(X_train)
            y_val_pred_scaled = model.predict(X_val)
            
            y_train_pred = np.expm1(y_train_pred_scaled)
            y_val_pred = np.expm1(y_val_pred_scaled)
        else:
            y_train_pred = model.predict(X_train)
            y_val_pred = model.predict(X_val)
        
        # Calculate metrics
        train_metrics = self._calculate_metrics(y_train, y_train_pred, 'train')
        val_metrics = self._calculate_metrics(y_val, y_val_pred, 'val')
        
        # Store results
        self.evaluation_results[model_name] = {
            'train': train_metrics,
            'val': val_metrics
        }
        
        # Log results
        logger.info(f"{model_name} - Train MAPE: {train_metrics['mape']:.4f}, R2: {train_metrics['r2']:.4f}")
        logger.info(f"{model_name} - Val MAPE: {val_metrics['mape']:.4f}, R2: {val_metrics['r2']:.4f}")
    
    def _calculate_metrics(self, y_true: pd.Series, y_pred: np.ndarray, prefix: str) -> Dict[str, float]:
        """Calculate evaluation metrics."""
        metrics = {
            'mape': mean_absolute_percentage_error(y_true, y_pred),
            'r2': r2_score(y_true, y_pred),
            'mse': mean_squared_error(y_true, y_pred),
            'rmse': np.sqrt(mean_squared_error(y_true, y_pred)),
            'mae': mean_absolute_error(y_true, y_pred),
            'mean_price': np.mean(y_true),
            'mean_pred_price': np.mean(y_pred),
            'price_std': np.std(y_true)
        }
        
        # Add relative error metrics
        metrics['mean_abs_error_pct'] = np.mean(np.abs((y_true - y_pred) / y_true)) * 100
        
        return {f"{prefix}_{k}": v for k, v in metrics.items()}
    
    def create_shap_explainer(self, X_sample: pd.DataFrame = None):
        """Create SHAP explainer for model interpretability."""
        if self.best_xgb_model is None:
            raise ValueError("XGBoost model must be trained first")
        
        logger.info("Creating SHAP explainer...")
        
        # Use sample of training data for explainer
        if X_sample is None:
            # Use a subset of data for faster computation
            sample_size = min(1000, len(self.feature_names))
            X_sample = X_sample if X_sample is not None else pd.DataFrame(
                np.random.randn(sample_size, len(self.feature_names)),
                columns=self.feature_names
            )
        
        # Create explainer
        self.shap_explainer = shap.Explainer(self.best_xgb_model, X_sample)
        
        logger.info("SHAP explainer created successfully")
    
    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance from the trained model."""
        if self.best_xgb_model is None:
            raise ValueError("XGBoost model must be trained first")
        
        # Get feature importance
        importance = self.best_xgb_model.feature_importances_
        feature_importance = dict(zip(self.feature_names, importance))
        
        # Sort by importance
        sorted_importance = dict(
            sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)
        )
        
        return sorted_importance
    
    def predict_with_confidence(
        self,
        X: pd.DataFrame,
        return_shap: bool = True
    ) -> Dict[str, np.ndarray]:
        """
        Make predictions with confidence bounds and SHAP explanations.
        
        Args:
            X: Input features
            return_shap: Whether to return SHAP values
            
        Returns:
            Dictionary with predictions, confidence bounds, and SHAP values
        """
        if self.best_xgb_model is None:
            raise ValueError("Models must be trained first")
        
        logger.info(f"Making predictions for {len(X)} properties...")
        
        # Main prediction (XGBoost)
        pred_scaled = self.best_xgb_model.predict(X)
        pred_main = np.expm1(pred_scaled)
        
        # Confidence bounds (quantile models)
        pred_low = self.quantile_low_model.predict(X)
        pred_high = self.quantile_high_model.predict(X)
        
        # Ensure bounds are logical
        pred_low = np.minimum(pred_low, pred_main)
        pred_high = np.maximum(pred_high, pred_main)
        
        results = {
            'mid': pred_main,
            'low': pred_low,
            'high': pred_high
        }
        
        # Add SHAP explanations if requested
        if return_shap and self.shap_explainer is not None:
            shap_values = self.shap_explainer.shap_values(X)
            results['shap_values'] = shap_values
            
            # Get top 3 contributing features for each prediction
            top_features = self._get_top_shap_features(shap_values, X)
            results['top_features'] = top_features
        
        return results
    
    def _get_top_shap_features(
        self,
        shap_values: np.ndarray,
        X: pd.DataFrame,
        top_k: int = 3
    ) -> List[List[Dict[str, Any]]]:
        """Get top k contributing features for each prediction."""
        top_features_list = []
        
        for i in range(len(shap_values)):
            # Get absolute SHAP values for this prediction
            abs_shap_values = np.abs(shap_values[i])
            
            # Get indices of top k features
            top_indices = np.argsort(abs_shap_values)[-top_k:][::-1]
            
            # Create feature explanations
            top_features = []
            for idx in top_indices:
                feature_name = self.feature_names[idx]
                shap_value = shap_values[i][idx]
                feature_value = X.iloc[i][feature_name]
                
                top_features.append({
                    'feature': feature_name,
                    'contribution': float(shap_value),
                    'value': float(feature_value),
                    'abs_contribution': float(abs_shap_values[idx])
                })
            
            top_features_list.append(top_features)
        
        return top_features_list
    
    def save_models(self, directory: str):
        """Save all trained models and artifacts."""
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        
        # Save XGBoost model
        if self.best_xgb_model is not None:
            joblib.dump(self.best_xgb_model, directory / 'xgboost_model.pkl')
        
        # Save quantile models
        if self.quantile_low_model is not None:
            joblib.dump(self.quantile_low_model, directory / 'quantile_low_model.pkl')
        if self.quantile_high_model is not None:
            joblib.dump(self.quantile_high_model, directory / 'quantile_high_model.pkl')
        
        # Save SHAP explainer
        if self.shap_explainer is not None:
            joblib.dump(self.shap_explainer, directory / 'shap_explainer.pkl')
        
        # Save metadata
        metadata = {
            'feature_names': self.feature_names,
            'xgb_params': self.xgb_params,
            'quantile_params': self.quantile_params,
            'evaluation_results': self.evaluation_results,
            'training_history': self.training_history,
            'model_version': '1.0.0',
            'training_date': datetime.now().isoformat()
        }
        
        with open(directory / 'model_metadata.json', 'w') as f:
            json.dump(metadata, f, indent=2, default=str)
        
        logger.info(f"Models and artifacts saved to {directory}")
    
    def load_models(self, directory: str):
        """Load trained models and artifacts."""
        directory = Path(directory)
        
        # Load XGBoost model
        self.best_xgb_model = joblib.load(directory / 'xgboost_model.pkl')
        
        # Load quantile models
        self.quantile_low_model = joblib.load(directory / 'quantile_low_model.pkl')
        self.quantile_high_model = joblib.load(directory / 'quantile_high_model.pkl')
        
        # Load SHAP explainer
        if (directory / 'shap_explainer.pkl').exists():
            self.shap_explainer = joblib.load(directory / 'shap_explainer.pkl')
        
        # Load metadata
        with open(directory / 'model_metadata.json', 'r') as f:
            metadata = json.load(f)
        
        self.feature_names = metadata['feature_names']
        self.xgb_params = metadata['xgb_params']
        self.quantile_params = metadata['quantile_params']
        self.evaluation_results = metadata['evaluation_results']
        self.training_history = metadata['training_history']
        
        logger.info(f"Models and artifacts loaded from {directory}")
    
    def get_model_summary(self) -> Dict[str, Any]:
        """Get comprehensive model summary."""
        if self.best_xgb_model is None:
            return {"error": "Model not trained yet"}
        
        summary = {
            'model_type': 'XGBoost + LightGBM Quantile',
            'feature_count': len(self.feature_names),
            'training_samples': len(self.feature_names),
            'feature_importance': self.get_feature_importance(),
            'evaluation_metrics': self.evaluation_results,
            'hyperparameters': {
                'xgboost': self.xgb_params,
                'quantile': self.quantile_params
            },
            'training_history': self.training_history
        }
        
        return summary


def train_complete_pipeline(
    df: pd.DataFrame,
    target_column: str = 'total_price_naira',
    feature_columns: List[str] = None,
    n_trials: int = 50,
    random_state: int = 42
) -> PropertyPriceModelTrainer:
    """
    Train complete model pipeline.
    
    Args:
        df: Input dataframe
        target_column: Target column name
        feature_columns: List of feature columns
        n_trials: Number of Optuna trials
        random_state: Random state
        
    Returns:
        Trained model trainer
    """
    from ..utils.feature_engineering import PropertyFeatureEngineer
    
    logger.info("Starting complete model training pipeline...")
    
    # Initialize feature engineer
    feature_engineer = PropertyFeatureEngineer()
    
    # Prepare features
    if feature_columns is None:
        # Use all columns except target
        feature_columns = [col for col in df.columns if col != target_column]
    
    # Split features and target
    X = df[feature_columns].copy()
    y = df[target_column].copy()
    
    # Feature engineering
    X_transformed = feature_engineer.fit_transform(X)
    
    # Split data
    X_train, X_val, y_train, y_val = train_test_split(
        X_transformed, y, test_size=0.2, random_state=random_state
    )
    
    # Initialize trainer
    trainer = PropertyPriceModelTrainer(random_state=random_state)
    
    # Train XGBoost model
    trainer.train_xgboost_model(
        X_train, y_train, X_val, y_val, n_trials=n_trials
    )
    
    # Train quantile models
    trainer.train_quantile_models(X_train, y_train)
    
    # Create SHAP explainer
    trainer.create_shap_explainer(X_val.sample(min(1000, len(X_val))))
    
    logger.info("Complete model training pipeline finished")
    return trainer


def evaluate_model_performance(trainer: PropertyPriceModelTrainer, X_test: pd.DataFrame, y_test: pd.Series) -> Dict[str, float]:
    """
    Evaluate model performance on test set.
    
    Args:
        trainer: Trained model trainer
        X_test: Test features
        y_test: Test target
        
    Returns:
        Dictionary of evaluation metrics
    """
    logger.info("Evaluating model performance on test set...")
    
    # Make predictions
    predictions = trainer.predict_with_confidence(X_test, return_shap=False)
    
    # Calculate metrics for main prediction
    y_pred = predictions['mid']
    
    metrics = {
        'test_mape': mean_absolute_percentage_error(y_test, y_pred),
        'test_r2': r2_score(y_test, y_pred),
        'test_mse': mean_squared_error(y_test, y_pred),
        'test_rmse': np.sqrt(mean_squared_error(y_test, y_pred)),
        'test_mae': mean_absolute_error(y_test, y_pred)
    }
    
    # Calculate confidence interval coverage
    low_bound = predictions['low']
    high_bound = predictions['high']
    
    coverage = np.mean((y_test >= low_bound) & (y_test <= high_bound))
    metrics['confidence_coverage'] = coverage
    
    # Calculate average confidence interval width
    avg_width = np.mean(high_bound - low_bound)
    metrics['avg_confidence_width'] = avg_width
    metrics['avg_confidence_width_pct'] = avg_width / np.mean(y_test) * 100
    
    logger.info(f"Test MAPE: {metrics['test_mape']:.4f}, R2: {metrics['test_r2']:.4f}")
    logger.info(f"Confidence coverage: {metrics['confidence_coverage']:.4f}")
    
    return metrics
