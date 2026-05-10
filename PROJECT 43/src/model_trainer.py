"""
Credit Model Trainer for Loan Default Prediction

This module handles model training, evaluation, and persistence for the
credit default prediction model with support for model versioning
and performance tracking.
"""

import numpy as np
import pandas as pd
import joblib
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple, Optional, Any, List
import logging
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split, cross_val_score, GridSearchCV
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, classification_report, confusion_matrix,
    precision_recall_curve, roc_curve
)
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
import shap
import matplotlib.pyplot as plt
import seaborn as sns

logger = logging.getLogger(__name__)


class CreditModelTrainer:
    """
    Trainer for credit default prediction models.
    
    This class provides comprehensive model training capabilities including
    hyperparameter tuning, cross-validation, and detailed performance
    evaluation with SHAP explanations.
    """
    
    def __init__(self, model_path: str = "models/", random_state: int = 42):
        """
        Initialize the model trainer.
        
        Args:
            model_path: Directory to save trained models
            random_state: Random seed for reproducibility
        """
        self.model_path = Path(model_path)
        self.model_path.mkdir(parents=True, exist_ok=True)
        self.random_state = random_state
        self.model = None
        self.feature_names = None
        self.scaler = None
        self.training_history = []
        
    def prepare_data(
        self, 
        X: pd.DataFrame, 
        y: pd.Series,
        test_size: float = 0.2,
        validation_size: float = 0.2
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Prepare data for training with train/validation/test splits.
        
        Args:
            X: Feature DataFrame
            y: Target Series
            test_size: Proportion of data for test set
            validation_size: Proportion of training data for validation
            
        Returns:
            Tuple of (X_train, X_val, X_test, y_train, y_val, y_test)
        """
        logger.info(f"Preparing data with test_size={test_size}, validation_size={validation_size}")
        
        # Store feature names
        self.feature_names = X.columns.tolist()
        
        # First split: separate test set
        X_temp, X_test, y_temp, y_test = train_test_split(
            X, y, test_size=test_size, random_state=self.random_state, stratify=y
        )
        
        # Second split: separate train and validation
        X_train, X_val, y_train, y_val = train_test_split(
            X_temp, y_temp, test_size=validation_size, random_state=self.random_state, stratify=y_temp
        )
        
        logger.info(f"Data splits - Train: {X_train.shape}, Val: {X_val.shape}, Test: {X_test.shape}")
        logger.info(f"Default rates - Train: {y_train.mean():.3f}, Val: {y_val.mean():.3f}, Test: {y_test.mean():.3f}")
        
        return X_train, X_val, X_test, y_train, y_val, y_test
    
    def create_model_pipeline(self, model_type: str = "random_forest") -> Pipeline:
        """
        Create a modeling pipeline with preprocessing and model.
        
        Args:
            model_type: Type of model to use ('random_forest', 'gradient_boosting', 'logistic_regression')
            
        Returns:
            Scikit-learn Pipeline
        """
        # Define preprocessing
        preprocessor = StandardScaler()
        
        # Define model based on type
        if model_type == "random_forest":
            model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                min_samples_split=10,
                min_samples_leaf=5,
                random_state=self.random_state,
                n_jobs=-1
            )
        elif model_type == "gradient_boosting":
            model = GradientBoostingClassifier(
                n_estimators=100,
                learning_rate=0.1,
                max_depth=6,
                random_state=self.random_state
            )
        elif model_type == "logistic_regression":
            model = LogisticRegression(
                random_state=self.random_state,
                max_iter=1000,
                class_weight='balanced'
            )
        else:
            raise ValueError(f"Unknown model type: {model_type}")
        
        # Create pipeline
        pipeline = Pipeline([
            ('scaler', preprocessor),
            ('model', model)
        ])
        
        return pipeline
    
    def train_model(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
        model_type: str = "random_forest",
        hyperparameter_tuning: bool = False
    ) -> Dict[str, Any]:
        """
        Train the credit default model.
        
        Args:
            X_train: Training features
            y_train: Training targets
            X_val: Validation features
            y_val: Validation targets
            model_type: Type of model to train
            hyperparameter_tuning: Whether to perform hyperparameter tuning
            
        Returns:
            Dictionary containing training results and metrics
        """
        logger.info(f"Training {model_type} model with hyperparameter_tuning={hyperparameter_tuning}")
        
        # Create pipeline
        pipeline = self.create_model_pipeline(model_type)
        
        if hyperparameter_tuning:
            pipeline = self._hyperparameter_tuning(pipeline, X_train, y_train, model_type)
        else:
            # Fit the model directly
            pipeline.fit(X_train, y_train)
        
        # Store the trained model
        self.model = pipeline
        
        # Evaluate on validation set
        val_predictions = pipeline.predict(X_val)
        val_probabilities = pipeline.predict_proba(X_val)[:, 1]
        
        # Calculate metrics
        val_metrics = self._calculate_metrics(y_val, val_predictions, val_probabilities)
        
        # Cross-validation on training data
        cv_scores = cross_val_score(pipeline, X_train, y_train, cv=5, scoring='roc_auc')
        
        # Store training results
        training_results = {
            'model_type': model_type,
            'training_time': datetime.now().isoformat(),
            'validation_metrics': val_metrics,
            'cv_scores': {
                'mean': cv_scores.mean(),
                'std': cv_scores.std(),
                'scores': cv_scores.tolist()
            },
            'feature_names': self.feature_names
        }
        
        # Add to training history
        self.training_history.append(training_results)
        
        logger.info(f"Model trained successfully. Validation AUC: {val_metrics['roc_auc']:.4f}")
        logger.info(f"Cross-validation AUC: {cv_scores.mean():.4f} (+/- {cv_scores.std() * 2:.4f})")
        
        return training_results
    
    def _hyperparameter_tuning(
        self, 
        pipeline: Pipeline, 
        X_train: np.ndarray, 
        y_train: np.ndarray,
        model_type: str
    ) -> Pipeline:
        """Perform hyperparameter tuning using GridSearchCV."""
        
        # Define parameter grids for different models
        param_grids = {
            'random_forest': {
                'model__n_estimators': [50, 100, 200],
                'model__max_depth': [5, 10, 15, None],
                'model__min_samples_split': [5, 10, 20],
                'model__min_samples_leaf': [2, 5, 10]
            },
            'gradient_boosting': {
                'model__n_estimators': [50, 100, 200],
                'model__learning_rate': [0.01, 0.1, 0.2],
                'model__max_depth': [3, 6, 9],
                'model__subsample': [0.8, 1.0]
            },
            'logistic_regression': {
                'model__C': [0.1, 1.0, 10.0],
                'model__penalty': ['l1', 'l2'],
                'model__solver': ['liblinear', 'saga']
            }
        }
        
        param_grid = param_grids.get(model_type, param_grids['random_forest'])
        
        # Perform grid search
        grid_search = GridSearchCV(
            pipeline,
            param_grid,
            cv=3,
            scoring='roc_auc',
            n_jobs=-1,
            verbose=1
        )
        
        logger.info("Starting hyperparameter tuning...")
        grid_search.fit(X_train, y_train)
        
        # Update pipeline with best parameters
        pipeline = grid_search.best_estimator_
        
        logger.info(f"Best parameters: {grid_search.best_params_}")
        logger.info(f"Best cross-validation score: {grid_search.best_score_:.4f}")
        
        return pipeline
    
    def evaluate_model(
        self, 
        X_test: np.ndarray, 
        y_test: np.ndarray,
        save_plots: bool = True
    ) -> Dict[str, Any]:
        """
        Evaluate the trained model on test data.
        
        Args:
            X_test: Test features
            y_test: Test targets
            save_plots: Whether to save evaluation plots
            
        Returns:
            Dictionary containing evaluation metrics
        """
        if self.model is None:
            raise ValueError("Model must be trained before evaluation")
        
        logger.info("Evaluating model on test data")
        
        # Make predictions
        predictions = self.model.predict(X_test)
        probabilities = self.model.predict_proba(X_test)[:, 1]
        
        # Calculate metrics
        metrics = self._calculate_metrics(y_test, predictions, probabilities)
        
        # Generate detailed evaluation report
        evaluation_results = {
            'test_metrics': metrics,
            'classification_report': classification_report(y_test, predictions),
            'confusion_matrix': confusion_matrix(y_test, predictions).tolist(),
            'evaluation_time': datetime.now().isoformat()
        }
        
        # Generate SHAP explanations
        shap_results = self._generate_shap_explanations(X_test, save_plots)
        evaluation_results['shap_analysis'] = shap_results
        
        # Save evaluation plots
        if save_plots:
            self._save_evaluation_plots(X_test, y_test, predictions, probabilities)
        
        logger.info(f"Test evaluation completed. Test AUC: {metrics['roc_auc']:.4f}")
        
        return evaluation_results
    
    def _calculate_metrics(
        self, 
        y_true: np.ndarray, 
        y_pred: np.ndarray, 
        y_prob: np.ndarray
    ) -> Dict[str, float]:
        """Calculate comprehensive evaluation metrics."""
        return {
            'accuracy': accuracy_score(y_true, y_pred),
            'precision': precision_score(y_true, y_pred),
            'recall': recall_score(y_true, y_pred),
            'f1_score': f1_score(y_true, y_pred),
            'roc_auc': roc_auc_score(y_true, y_prob),
            'specificity': self._calculate_specificity(y_true, y_pred),
            'balanced_accuracy': (recall_score(y_true, y_pred) + self._calculate_specificity(y_true, y_pred)) / 2
        }
    
    def _calculate_specificity(self, y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """Calculate specificity (true negative rate)."""
        tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
        return tn / (tn + fp) if (tn + fp) > 0 else 0.0
    
    def _generate_shap_explanations(
        self, 
        X_test: np.ndarray, 
        save_plots: bool = True
    ) -> Dict[str, Any]:
        """Generate SHAP explanations for model interpretability."""
        logger.info("Generating SHAP explanations")
        
        # Get the model from pipeline
        model = self.model.named_steps['model']
        X_test_scaled = self.model.named_steps['scaler'].transform(X_test)
        
        # Create SHAP explainer
        if hasattr(model, 'feature_importances_'):
            # Tree-based models
            explainer = shap.TreeExplainer(model)
        else:
            # Linear models
            explainer = shap.LinearExplainer(model, X_test_scaled)
        
        # Calculate SHAP values
        shap_values = explainer.shap_values(X_test_scaled)
        
        # For binary classification, get SHAP values for positive class
        if isinstance(shap_values, list):
            shap_values = shap_values[1]
        
        # Calculate feature importance
        feature_importance = np.abs(shap_values).mean(axis=0)
        feature_importance_df = pd.DataFrame({
            'feature': self.feature_names,
            'importance': feature_importance
        }).sort_values('importance', ascending=False)
        
        shap_results = {
            'feature_importance': feature_importance_df.to_dict('records'),
            'shap_values_shape': shap_values.shape,
            'summary_stats': {
                'mean_abs_shap': np.mean(np.abs(shap_values)),
                'max_abs_shap': np.max(np.abs(shap_values)),
                'min_abs_shap': np.min(np.abs(shap_values))
            }
        }
        
        # Save SHAP plots
        if save_plots:
            self._save_shap_plots(shap_values, X_test_scaled)
        
        return shap_results
    
    def _save_shap_plots(self, shap_values: np.ndarray, X_test_scaled: np.ndarray):
        """Save SHAP visualization plots."""
        plots_dir = self.model_path / "plots"
        plots_dir.mkdir(exist_ok=True)
        
        # Summary plot
        plt.figure(figsize=(12, 8))
        shap.summary_plot(shap_values, X_test_scaled, feature_names=self.feature_names, show=False)
        plt.title("SHAP Summary Plot")
        plt.tight_layout()
        plt.savefig(plots_dir / "shap_summary.png", dpi=300, bbox_inches='tight')
        plt.close()
        
        # Feature importance plot
        feature_importance = np.abs(shap_values).mean(axis=0)
        importance_df = pd.DataFrame({
            'feature': self.feature_names,
            'importance': feature_importance
        }).sort_values('importance', ascending=False)
        
        plt.figure(figsize=(12, 8))
        sns.barplot(data=importance_df.head(10), x='importance', y='feature')
        plt.title('Top 10 Feature Importance (SHAP)')
        plt.xlabel('Mean |SHAP Value|')
        plt.tight_layout()
        plt.savefig(plots_dir / "shap_feature_importance.png", dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info("SHAP plots saved")
    
    def _save_evaluation_plots(
        self, 
        X_test: np.ndarray, 
        y_test: np.ndarray, 
        y_pred: np.ndarray, 
        y_prob: np.ndarray
    ):
        """Save evaluation plots."""
        plots_dir = self.model_path / "plots"
        plots_dir.mkdir(exist_ok=True)
        
        # ROC Curve
        fpr, tpr, _ = roc_curve(y_test, y_prob)
        plt.figure(figsize=(8, 6))
        plt.plot(fpr, tpr, label=f'ROC Curve (AUC = {roc_auc_score(y_test, y_prob):.3f})')
        plt.plot([0, 1], [0, 1], 'k--', label='Random')
        plt.xlabel('False Positive Rate')
        plt.ylabel('True Positive Rate')
        plt.title('ROC Curve')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(plots_dir / "roc_curve.png", dpi=300, bbox_inches='tight')
        plt.close()
        
        # Precision-Recall Curve
        precision, recall, _ = precision_recall_curve(y_test, y_prob)
        plt.figure(figsize=(8, 6))
        plt.plot(recall, precision, label=f'PR Curve (AUC = {np.trapz(precision, recall):.3f})')
        plt.xlabel('Recall')
        plt.ylabel('Precision')
        plt.title('Precision-Recall Curve')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(plots_dir / "pr_curve.png", dpi=300, bbox_inches='tight')
        plt.close()
        
        # Confusion Matrix
        cm = confusion_matrix(y_test, y_pred)
        plt.figure(figsize=(8, 6))
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', 
                   xticklabels=['No Default', 'Default'],
                   yticklabels=['No Default', 'Default'])
        plt.xlabel('Predicted')
        plt.ylabel('Actual')
        plt.title('Confusion Matrix')
        plt.tight_layout()
        plt.savefig(plots_dir / "confusion_matrix.png", dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info("Evaluation plots saved")
    
    def save_model(self, model_name: str, version: str = "1.0") -> str:
        """
        Save the trained model with versioning.
        
        Args:
            model_name: Name for the model
            version: Version string
            
        Returns:
            Path to saved model
        """
        if self.model is None:
            raise ValueError("Model must be trained before saving")
        
        # Create versioned model directory
        model_dir = self.model_path / f"{model_name}_v{version}"
        model_dir.mkdir(exist_ok=True)
        
        # Save model
        model_file = model_dir / "model.joblib"
        joblib.dump(self.model, model_file)
        
        # Save metadata
        metadata = {
            'model_name': model_name,
            'version': version,
            'feature_names': self.feature_names,
            'training_date': datetime.now().isoformat(),
            'training_history': self.training_history[-1] if self.training_history else None
        }
        
        metadata_file = model_dir / "metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"Model saved to {model_dir}")
        
        return str(model_dir)
    
    def load_model(self, model_path: str) -> Dict[str, Any]:
        """
        Load a saved model.
        
        Args:
            model_path: Path to the model directory
            
        Returns:
            Model metadata
        """
        model_dir = Path(model_path)
        
        # Load model
        model_file = model_dir / "model.joblib"
        self.model = joblib.load(model_file)
        
        # Load metadata
        metadata_file = model_dir / "metadata.json"
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
        
        # Set feature names
        self.feature_names = metadata['feature_names']
        
        logger.info(f"Model loaded from {model_dir}")
        
        return metadata
    
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Make probability predictions."""
        if self.model is None:
            raise ValueError("Model must be trained before prediction")
        
        return self.model.predict_proba(X)
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Make binary predictions."""
        if self.model is None:
            raise ValueError("Model must be trained before prediction")
        
        return self.model.predict(X)
    
    def get_feature_importance(self) -> pd.DataFrame:
        """Get feature importance from the trained model."""
        if self.model is None:
            raise ValueError("Model must be trained before getting feature importance")
        
        model = self.model.named_steps['model']
        
        if hasattr(model, 'feature_importances_'):
            # Tree-based models
            importance = model.feature_importances_
        elif hasattr(model, 'coef_'):
            # Linear models
            importance = np.abs(model.coef_[0])
        else:
            raise ValueError("Model does not support feature importance")
        
        importance_df = pd.DataFrame({
            'feature': self.feature_names,
            'importance': importance
        }).sort_values('importance', ascending=False)
        
        return importance_df
    
    def compare_models(
        self, 
        X_train: np.ndarray, 
        y_train: np.ndarray,
        X_val: np.ndarray, 
        y_val: np.ndarray
    ) -> pd.DataFrame:
        """
        Compare multiple model types.
        
        Args:
            X_train: Training features
            y_train: Training targets
            X_val: Validation features
            y_val: Validation targets
            
        Returns:
            DataFrame with comparison results
        """
        model_types = ['random_forest', 'gradient_boosting', 'logistic_regression']
        results = []
        
        for model_type in model_types:
            logger.info(f"Training {model_type} for comparison")
            
            # Train model
            training_results = self.train_model(
                X_train, y_train, X_val, y_val, 
                model_type=model_type, 
                hyperparameter_tuning=False
            )
            
            # Store results
            results.append({
                'model_type': model_type,
                'validation_auc': training_results['validation_metrics']['roc_auc'],
                'validation_f1': training_results['validation_metrics']['f1_score'],
                'cv_auc_mean': training_results['cv_scores']['mean'],
                'cv_auc_std': training_results['cv_scores']['std']
            })
        
        comparison_df = pd.DataFrame(results)
        comparison_df = comparison_df.sort_values('validation_auc', ascending=False)
        
        logger.info("Model comparison completed")
        
        return comparison_df
