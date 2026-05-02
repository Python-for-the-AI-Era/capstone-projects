"""
Pipeline Package - A refactored data processing pipeline.

This package provides a clean, modular approach to data processing
with proper separation of concerns and comprehensive testing.
"""

__version__ = "1.0.0"
__author__ = "Pipeline Team"

from .core.pipeline import Pipeline
from .models import PipelineData, EmailLog, APIResponse

__all__ = [
    "Pipeline",
    "PipelineData", 
    "EmailLog",
    "APIResponse"
]
