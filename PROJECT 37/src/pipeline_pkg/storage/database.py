"""
Database repository for pipeline data persistence.

This module provides a clean repository pattern for database operations
with proper session management and error handling.
"""

from contextlib import contextmanager
from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import structlog

from ..models import PipelineDataDB, EmailLogDB, APIResponseDB, PipelineData, EmailLog, APIResponse


class DatabaseRepository:
    """
    Repository class for database operations.
    
    Provides a clean interface for CRUD operations with proper
    session management and error handling.
    """
    
    def __init__(self, database_url: str) -> None:
        """
        Initialize the database repository.
        
        Args:
            database_url: SQLAlchemy database URL
        """
        self.database_url = database_url
        self.logger = structlog.get_logger(__name__)
        
        # Create engine
        if database_url.startswith("sqlite"):
            # SQLite specific configuration
            engine_kwargs = {
                "poolclass": StaticPool,
                "connect_args": {"check_same_thread": False},
            }
        else:
            engine_kwargs = {}
        
        self.engine = create_engine(database_url, **engine_kwargs)
        
        # Create session factory
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        # Create tables
        self._create_tables()
        
        self.logger.info("Database repository initialized", database_url=database_url)
    
    def _create_tables(self) -> None:
        """Create database tables."""
        try:
            PipelineDataDB.__table__.create(self.engine, checkfirst=True)
            EmailLogDB.__table__.create(self.engine, checkfirst=True)
            APIResponseDB.__table__.create(self.engine, checkfirst=True)
            self.logger.info("Database tables created/verified")
        except Exception as e:
            self.logger.error("Failed to create database tables", error=str(e))
            raise
    
    @contextmanager
    def get_session(self):
        """Get a database session with proper cleanup."""
        session = self.SessionLocal()
        try:
            yield session
        except Exception as e:
            session.rollback()
            self.logger.error("Database session error", error=str(e))
            raise
        finally:
            session.close()
    
    def save_pipeline_data(self, pipeline_data: PipelineData) -> int:
        """
        Save pipeline data to database.
        
        Args:
            pipeline_data: Pipeline data model
            
        Returns:
            ID of the saved record
        """
        with self.get_session() as session:
            try:
                db_data = PipelineDataDB(
                    source=pipeline_data.source,
                    data=pipeline_data.data.json() if hasattr(pipeline_data.data, 'json') else str(pipeline_data.data),
                    processed=True,
                )
                session.add(db_data)
                session.commit()
                session.refresh(db_data)
                
                self.logger.info(
                    "Pipeline data saved",
                    source=pipeline_data.source,
                    record_id=db_data.id,
                )
                return db_data.id
                
            except Exception as e:
                session.rollback()
                self.logger.error(
                    "Failed to save pipeline data",
                    source=pipeline_data.source,
                    error=str(e),
                )
                raise
    
    def get_pipeline_data(
        self,
        source: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[PipelineDataDB]:
        """
        Get pipeline data from database.
        
        Args:
            source: Filter by source
            limit: Maximum number of records
            offset: Offset for pagination
            
        Returns:
            List of pipeline data records
        """
        with self.get_session() as session:
            try:
                query = session.query(PipelineDataDB)
                
                if source:
                    query = query.filter(PipelineDataDB.source == source)
                
                query = query.order_by(PipelineDataDB.created_at.desc())
                
                if limit:
                    query = query.limit(limit)
                
                if offset:
                    query = query.offset(offset)
                
                return query.all()
                
            except Exception as e:
                self.logger.error("Failed to get pipeline data", error=str(e))
                raise
    
    def save_email_log(self, email_log: EmailLog) -> int:
        """
        Save email log to database.
        
        Args:
            email_log: Email log model
            
        Returns:
            ID of the saved record
        """
        with self.get_session() as session:
            try:
                db_log = EmailLogDB(
                    recipient=email_log.recipient,
                    subject=email_log.subject,
                    status=email_log.status,
                    error_message=email_log.error_message,
                )
                session.add(db_log)
                session.commit()
                session.refresh(db_log)
                
                self.logger.info(
                    "Email log saved",
                    recipient=email_log.recipient,
                    status=email_log.status,
                    record_id=db_log.id,
                )
                return db_log.id
                
            except Exception as e:
                session.rollback()
                self.logger.error(
                    "Failed to save email log",
                    recipient=email_log.recipient,
                    error=str(e),
                )
                raise
    
    def save_api_response(self, api_response: APIResponse) -> int:
        """
        Save API response log to database.
        
        Args:
            api_response: API response model
            
        Returns:
            ID of the saved record
        """
        with self.get_session() as session:
            try:
                db_response = APIResponseDB(
                    endpoint=api_response.endpoint,
                    request_data=(
                        api_response.request_data.json()
                        if hasattr(api_response.request_data, 'json')
                        else str(api_response.request_data)
                    ),
                    response_data=(
                        api_response.response_data.json()
                        if hasattr(api_response.response_data, 'json')
                        else str(api_response.response_data)
                    ),
                    status_code=api_response.status_code,
                    response_time=api_response.response_time,
                )
                session.add(db_response)
                session.commit()
                session.refresh(db_response)
                
                self.logger.info(
                    "API response saved",
                    endpoint=api_response.endpoint,
                    status_code=api_response.status_code,
                    record_id=db_response.id,
                )
                return db_response.id
                
            except Exception as e:
                session.rollback()
                self.logger.error(
                    "Failed to save API response",
                    endpoint=api_response.endpoint,
                    error=str(e),
                )
                raise
    
    def get_email_logs(
        self,
        recipient: Optional[str] = None,
        status: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[EmailLogDB]:
        """
        Get email logs from database.
        
        Args:
            recipient: Filter by recipient
            status: Filter by status
            limit: Maximum number of records
            
        Returns:
            List of email log records
        """
        with self.get_session() as session:
            try:
                query = session.query(EmailLogDB)
                
                if recipient:
                    query = query.filter(EmailLogDB.recipient == recipient)
                
                if status:
                    query = query.filter(EmailLogDB.status == status)
                
                query = query.order_by(EmailLogDB.sent_at.desc())
                
                if limit:
                    query = query.limit(limit)
                
                return query.all()
                
            except Exception as e:
                self.logger.error("Failed to get email logs", error=str(e))
                raise
    
    def get_api_responses(
        self,
        endpoint: Optional[str] = None,
        status_code: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[APIResponseDB]:
        """
        Get API responses from database.
        
        Args:
            endpoint: Filter by endpoint
            status_code: Filter by status code
            limit: Maximum number of records
            
        Returns:
            List of API response records
        """
        with self.get_session() as session:
            try:
                query = session.query(APIResponseDB)
                
                if endpoint:
                    query = query.filter(APIResponseDB.endpoint == endpoint)
                
                if status_code:
                    query = query.filter(APIResponseDB.status_code == status_code)
                
                query = query.order_by(APIResponseDB.created_at.desc())
                
                if limit:
                    query = query.limit(limit)
                
                return query.all()
                
            except Exception as e:
                self.logger.error("Failed to get API responses", error=str(e))
                raise
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get database statistics.
        
        Returns:
            Dictionary with statistics
        """
        with self.get_session() as session:
            try:
                pipeline_count = session.query(PipelineDataDB).count()
                email_count = session.query(EmailLogDB).count()
                api_response_count = session.query(APIResponseDB).count()
                
                successful_emails = (
                    session.query(EmailLogDB).filter(EmailLogDB.status == "sent").count()
                )
                
                successful_api_calls = (
                    session.query(APIResponseDB)
                    .filter(APIResponseDB.status_code < 400)
                    .count()
                )
                
                stats = {
                    "pipeline_data_count": pipeline_count,
                    "email_count": email_count,
                    "api_response_count": api_response_count,
                    "successful_emails": successful_emails,
                    "successful_api_calls": successful_api_calls,
                    "email_success_rate": (
                        (successful_emails / email_count * 100) if email_count > 0 else 0
                    ),
                    "api_success_rate": (
                        (successful_api_calls / api_response_count * 100)
                        if api_response_count > 0
                        else 0
                    ),
                }
                
                return stats
                
            except Exception as e:
                self.logger.error("Failed to get statistics", error=str(e))
                raise
    
    def close(self) -> None:
        """Close database connections."""
        if self.engine:
            self.engine.dispose()
            self.logger.info("Database connections closed")
