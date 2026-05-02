"""
Data models for the pipeline package.

This module contains Pydantic models for data validation and SQLAlchemy
models for database persistence.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, validator
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class PipelineDataDB(Base):
    """SQLAlchemy model for pipeline data storage."""
    __tablename__ = "pipeline_data"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(255), nullable=False, index=True)
    data = Column(Text, nullable=False)
    processed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class EmailLogDB(Base):
    """SQLAlchemy model for email logging."""
    __tablename__ = "email_log"

    id = Column(Integer, primary_key=True, index=True)
    recipient = Column(String(255), nullable=False, index=True)
    subject = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, index=True)
    error_message = Column(Text, nullable=True)
    sent_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class APIResponseDB(Base):
    """SQLAlchemy model for API response logging."""
    __tablename__ = "api_response"

    id = Column(Integer, primary_key=True, index=True)
    endpoint = Column(String(255), nullable=False, index=True)
    request_data = Column(Text, nullable=True)
    response_data = Column(Text, nullable=True)
    status_code = Column(Integer, nullable=False)
    response_time = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# Pydantic models for data validation and serialization


class PipelineData(BaseModel):
    """Pydantic model for pipeline data validation."""
    source: str = Field(..., description="Source of the data")
    data: Dict[str, Any] = Field(..., description="Raw data payload")
    processed_at: Optional[datetime] = Field(None, description="Processing timestamp")
    processing_version: str = Field("1.0", description="Version of processing logic")

    @validator("source")
    def validate_source(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Source cannot be empty")
        return v.strip().lower()

    @validator("data")
    def validate_data(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(v, dict):
            raise ValueError("Data must be a dictionary")
        return v

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None,
        }


class EmailLog(BaseModel):
    """Pydantic model for email log entries."""
    recipient: str = Field(..., description="Email recipient")
    subject: str = Field(..., description="Email subject")
    status: str = Field(..., description="Email status (sent/failed)")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    sent_at: Optional[datetime] = Field(None, description="Timestamp when sent")

    @validator("recipient")
    def validate_recipient(cls, v: str) -> str:
        if "@" not in v:
            raise ValueError("Invalid email address")
        return v.lower()

    @validator("status")
    def validate_status(cls, v: str) -> str:
        allowed_statuses = {"sent", "failed", "pending"}
        if v not in allowed_statuses:
            raise ValueError(f"Status must be one of {allowed_statuses}")
        return v


class APIResponse(BaseModel):
    """Pydantic model for API response logging."""
    endpoint: str = Field(..., description="API endpoint called")
    request_data: Optional[Dict[str, Any]] = Field(None, description="Request payload")
    response_data: Optional[Dict[str, Any]] = Field(None, description="Response payload")
    status_code: int = Field(..., description="HTTP status code")
    response_time: float = Field(..., description="Response time in seconds")
    created_at: Optional[datetime] = Field(None, description="Timestamp of request")

    @validator("status_code")
    def validate_status_code(cls, v: int) -> int:
        if not 100 <= v <= 599:
            raise ValueError("Status code must be between 100 and 599")
        return v

    @validator("response_time")
    def validate_response_time(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Response time cannot be negative")
        return v


class PipelineResult(BaseModel):
    """Pydantic model for pipeline execution results."""
    start_time: str = Field(..., description="Pipeline start timestamp")
    end_time: Optional[str] = Field(None, description="Pipeline end timestamp")
    endpoints_processed: int = Field(0, description="Number of endpoints processed")
    records_processed: int = Field(0, description="Number of records processed")
    emails_sent: int = Field(0, description="Number of emails sent")
    pdfs_generated: int = Field(0, description="Number of PDFs generated")
    status: str = Field(..., description="Pipeline status")
    errors: list[str] = Field(default_factory=list, description="List of errors")

    @validator("status")
    def validate_status(cls, v: str) -> str:
        allowed_statuses = {"running", "completed", "failed", "cancelled"}
        if v not in allowed_statuses:
            raise ValueError(f"Status must be one of {allowed_statuses}")
        return v
