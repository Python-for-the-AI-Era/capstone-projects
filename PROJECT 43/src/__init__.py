"""
CreditChek Model Drift Detection and Remediation System

This package provides tools for detecting, diagnosing, and remediating model drift
in credit default prediction models using PSI, SHAP, and automated retraining.
"""

__version__ = "1.0.0"
__author__ = "CreditChek Data Science Team"

from .data_generator import CreditDataGenerator
from .model_trainer import CreditModelTrainer
from .drift_detector import DriftDetector
from .model_registry import ModelRegistry
from .alerting import SlackNotifier

__all__ = [
    "CreditDataGenerator",
    "CreditModelTrainer", 
    "DriftDetector",
    "ModelRegistry",
    "SlackNotifier"
]
