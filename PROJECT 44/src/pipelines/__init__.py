"""
Data processing pipelines for Nigerian news crawler.

Includes validation, deduplication, storage, and monitoring pipelines
for processing crawled news articles.
"""

from .validation import ValidationPipeline
from .deduplication import DeduplicationPipeline
from .sqlite_storage import SQLiteStoragePipeline
from .postgresql_storage import PostgreSQLPipeline
from .monitoring import MonitoringPipeline

__all__ = [
    'ValidationPipeline',
    'DeduplicationPipeline',
    'SQLiteStoragePipeline',
    'PostgreSQLPipeline',
    'MonitoringPipeline'
]
