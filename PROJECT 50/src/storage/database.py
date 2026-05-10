"""
Database storage layer for collaborative code editor.

This module handles PostgreSQL persistence for documents, snapshots,
and metadata with proper connection pooling and transaction management.
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import asyncpg
import structlog

logger = structlog.get_logger()


class DatabaseManager:
    """
    Database manager for PostgreSQL operations.
    
    Handles connection pooling, transactions, and data persistence.
    """
    
    def __init__(self):
        """Initialize database manager."""
        self.pool: Optional[asyncpg.Pool] = None
        self.connection_string = (
            "postgresql://postgres:password@localhost:5432/codecollab"
        )
        logger.info("Database manager initialized")
    
    async def initialize(self):
        """Initialize database connection pool and create tables."""
        try:
            # Create connection pool
            self.pool = await asyncpg.create_pool(
                self.connection_string,
                min_size=5,
                max_size=20,
                command_timeout=60
            )
            
            # Create tables
            await self._create_tables()
            
            logger.info("Database initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize database", error=str(e))
            raise
    
    async def close(self):
        """Close database connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("Database connection pool closed")
    
    async def _create_tables(self):
        """Create database tables."""
        async with self.pool.acquire() as conn:
            # Documents table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    document_id UUID PRIMARY KEY,
                    title VARCHAR(200) NOT NULL,
                    language VARCHAR(50) DEFAULT 'python',
                    is_public BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
            
            # Document snapshots table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS document_snapshots (
                    id SERIAL PRIMARY KEY,
                    document_id UUID NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
                    content TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
            
            # Document metadata table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS document_metadata (
                    document_id UUID PRIMARY KEY REFERENCES documents(document_id) ON DELETE CASCADE,
                    title VARCHAR(200) NOT NULL,
                    language VARCHAR(50) DEFAULT 'python',
                    is_public BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
            
            # User sessions table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS user_sessions (
                    session_id UUID PRIMARY KEY,
                    document_id UUID NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
                    user_id VARCHAR(100) NOT NULL,
                    user_name VARCHAR(100),
                    user_color VARCHAR(7) DEFAULT '#007bff',
                    connected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    last_activity TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    is_active BOOLEAN DEFAULT TRUE
                )
            """)
            
            # Operation history table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS operation_history (
                    id SERIAL PRIMARY KEY,
                    document_id UUID NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
                    operation_id UUID NOT NULL,
                    operation_type VARCHAR(20) NOT NULL,
                    position INTEGER NOT NULL,
                    content TEXT,
                    length INTEGER,
                    attributes JSONB,
                    user_id VARCHAR(100) NOT NULL,
                    timestamp DOUBLE PRECISION NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
            
            # Create indexes
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_documents_created_at 
                ON documents(created_at)
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_document_snapshots_document_id 
                ON document_snapshots(document_id, created_at)
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_sessions_document_id 
                ON user_sessions(document_id, is_active)
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_operation_history_document_id 
                ON operation_history(document_id, timestamp)
            """)
            
            logger.info("Database tables created successfully")
    
    async def create_document_metadata(
        self, 
        document_id: str, 
        title: str, 
        language: str = "python", 
        is_public: bool = False
    ):
        """
        Create document metadata.
        
        Args:
            document_id: Document identifier
            title: Document title
            language: Programming language
            is_public: Whether document is public
        """
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO document_metadata (document_id, title, language, is_public)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (document_id) 
                DO UPDATE SET 
                    title = $2,
                    language = $3,
                    is_public = $4,
                    updated_at = NOW()
            """, document_id, title, language, is_public)
    
    async def get_document_metadata(self, document_id: str) -> Dict[str, Any]:
        """
        Get document metadata.
        
        Args:
            document_id: Document identifier
            
        Returns:
            Document metadata
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT title, language, is_public, created_at, updated_at
                FROM document_metadata
                WHERE document_id = $1
            """, document_id)
            
            if row:
                return {
                    'title': row['title'],
                    'language': row['language'],
                    'is_public': row['is_public'],
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at']
                }
            
            return {}
    
    async def store_document_snapshot(self, document_id: str, content: str, version: int):
        """
        Store document snapshot.
        
        Args:
            document_id: Document identifier
            content: Document content
            version: Document version
        """
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO document_snapshots (document_id, content, version)
                VALUES ($1, $2, $3)
            """, document_id, content, version)
    
    async def get_latest_snapshot(self, document_id: str) -> Optional[Dict[str, Any]]:
        """
        Get latest document snapshot.
        
        Args:
            document_id: Document identifier
            
        Returns:
            Latest snapshot or None
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT content, version, created_at
                FROM document_snapshots
                WHERE document_id = $1
                ORDER BY version DESC
                LIMIT 1
            """, document_id)
            
            if row:
                return {
                    'content': row['content'],
                    'version': row['version'],
                    'created_at': row['created_at']
                }
            
            return None
    
    async def store_operation(self, document_id: str, operation_data: Dict[str, Any]):
        """
        Store operation in history.
        
        Args:
            document_id: Document identifier
            operation_data: Operation data
        """
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO operation_history (
                    document_id, operation_id, operation_type, position, 
                    content, length, attributes, user_id, timestamp
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """, 
                document_id,
                operation_data['id'],
                operation_data['type'],
                operation_data['position'],
                operation_data.get('content'),
                operation_data.get('length'),
                json.dumps(operation_data.get('attributes', {})),
                operation_data['user_id'],
                operation_data['timestamp']
            )
    
    async def get_operation_history(
        self, 
        document_id: str, 
        limit: int = 1000,
        since_timestamp: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Get operation history for a document.
        
        Args:
            document_id: Document identifier
            limit: Maximum number of operations to return
            since_timestamp: Get operations since this timestamp
            
        Returns:
            List of operations
        """
        async with self.pool.acquire() as conn:
            query = """
                SELECT operation_id, operation_type, position, content, length, 
                       attributes, user_id, timestamp, created_at
                FROM operation_history
                WHERE document_id = $1
            """
            
            params = [document_id]
            
            if since_timestamp:
                query += " AND timestamp >= $2"
                params.append(since_timestamp)
            
            query += " ORDER BY timestamp DESC LIMIT $3"
            params.append(limit)
            
            rows = await conn.fetch(query, *params)
            
            return [
                {
                    'id': row['operation_id'],
                    'type': row['operation_type'],
                    'position': row['position'],
                    'content': row['content'],
                    'length': row['length'],
                    'attributes': json.loads(row['attributes']) if row['attributes'] else {},
                    'user_id': row['user_id'],
                    'timestamp': row['timestamp'],
                    'created_at': row['created_at']
                }
                for row in rows
            ]
    
    async def create_user_session(
        self, 
        session_id: str, 
        document_id: str, 
        user_id: str, 
        user_name: str = "",
        user_color: str = "#007bff"
    ):
        """
        Create user session.
        
        Args:
            session_id: Session identifier
            document_id: Document identifier
            user_id: User identifier
            user_name: User display name
            user_color: User cursor color
        """
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO user_sessions (
                    session_id, document_id, user_id, user_name, user_color
                )
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (session_id) 
                DO UPDATE SET 
                    last_activity = NOW(),
                    is_active = TRUE
            """, session_id, document_id, user_id, user_name, user_color)
    
    async def update_user_session_activity(self, session_id: str):
        """
        Update user session activity timestamp.
        
        Args:
            session_id: Session identifier
        """
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE user_sessions
                SET last_activity = NOW()
                WHERE session_id = $1
            """, session_id)
    
    async def deactivate_user_session(self, session_id: str):
        """
        Deactivate user session.
        
        Args:
            session_id: Session identifier
        """
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE user_sessions
                SET is_active = FALSE
                WHERE session_id = $1
            """, session_id)
    
    async def get_active_sessions(self, document_id: str) -> List[Dict[str, Any]]:
        """
        Get active user sessions for a document.
        
        Args:
            document_id: Document identifier
            
        Returns:
            List of active sessions
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT session_id, user_id, user_name, user_color, 
                       connected_at, last_activity
                FROM user_sessions
                WHERE document_id = $1 AND is_active = TRUE
                ORDER BY last_activity DESC
            """, document_id)
            
            return [
                {
                    'session_id': row['session_id'],
                    'user_id': row['user_id'],
                    'user_name': row['user_name'],
                    'user_color': row['user_color'],
                    'connected_at': row['connected_at'],
                    'last_activity': row['last_activity']
                }
                for row in rows
            ]
    
    async def cleanup_old_sessions(self, days: int = 7):
        """
        Clean up old user sessions.
        
        Args:
            days: Number of days to keep sessions
        """
        async with self.pool.acquire() as conn:
            await conn.execute("""
                DELETE FROM user_sessions
                WHERE last_activity < NOW() - INTERVAL '$1 days'
                OR is_active = FALSE
            """, days)
    
    async def cleanup_old_snapshots(self, days: int = 30):
        """
        Clean up old document snapshots.
        
        Args:
            days: Number of days to keep snapshots
        """
        async with self.pool.acquire() as conn:
            await conn.execute("""
                DELETE FROM document_snapshots
                WHERE created_at < NOW() - INTERVAL '$1 days'
            """, days)
    
    async def cleanup_old_operations(self, days: int = 7):
        """
        Clean up old operation history.
        
        Args:
            days: Number of days to keep operations
        """
        async with self.pool.acquire() as conn:
            await conn.execute("""
                DELETE FROM operation_history
                WHERE created_at < NOW() - INTERVAL '$1 days'
            """, days)
    
    async def get_system_stats(self) -> Dict[str, Any]:
        """
        Get system statistics.
        
        Returns:
            System statistics
        """
        async with self.pool.acquire() as conn:
            # Get document count
            doc_count = await conn.fetchval("SELECT COUNT(*) FROM documents")
            
            # Get snapshot count
            snapshot_count = await conn.fetchval("SELECT COUNT(*) FROM document_snapshots")
            
            # Get operation count
            operation_count = await conn.fetchval("SELECT COUNT(*) FROM operation_history")
            
            # Get active session count
            session_count = await conn.fetchval("SELECT COUNT(*) FROM user_sessions WHERE is_active = TRUE")
            
            # Get database size
            db_size = await conn.fetchval("SELECT pg_database_size(current_database())")
            
            return {
                'documents': doc_count,
                'snapshots': snapshot_count,
                'operations': operation_count,
                'active_sessions': session_count,
                'database_size_bytes': db_size
            }
    
    async def get_document_stats(self, document_id: str) -> Dict[str, Any]:
        """
        Get document statistics.
        
        Args:
            document_id: Document identifier
            
        Returns:
            Document statistics
        """
        async with self.pool.acquire() as conn:
            # Get snapshot count
            snapshot_count = await conn.fetchval(
                "SELECT COUNT(*) FROM document_snapshots WHERE document_id = $1",
                document_id
            )
            
            # Get operation count
            operation_count = await conn.fetchval(
                "SELECT COUNT(*) FROM operation_history WHERE document_id = $1",
                document_id
            )
            
            # Get active session count
            session_count = await conn.fetchval(
                "SELECT COUNT(*) FROM user_sessions WHERE document_id = $1 AND is_active = TRUE",
                document_id
            )
            
            return {
                'snapshot_count': snapshot_count,
                'operation_count': operation_count,
                'active_sessions': session_count
            }


class DocumentStorage:
    """
    High-level document storage interface.
    
    Provides a clean interface for document persistence operations.
    """
    
    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize document storage.
        
        Args:
            db_manager: Database manager instance
        """
        self.db_manager = db_manager
        logger.info("Document storage initialized")
    
    async def save_document(self, document_id: str, content: str, version: int, metadata: Dict[str, Any]):
        """
        Save document with metadata and snapshot.
        
        Args:
            document_id: Document identifier
            content: Document content
            version: Document version
            metadata: Document metadata
        """
        try:
            # Store metadata
            await self.db_manager.create_document_metadata(
                document_id=document_id,
                title=metadata.get('title', ''),
                language=metadata.get('language', 'python'),
                is_public=metadata.get('is_public', False)
            )
            
            # Store snapshot
            await self.db_manager.store_document_snapshot(document_id, content, version)
            
            logger.info("Document saved", document_id=document_id, version=version)
            
        except Exception as e:
            logger.error("Error saving document", document_id=document_id, error=str(e))
            raise
    
    async def load_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        """
        Load document from storage.
        
        Args:
            document_id: Document identifier
            
        Returns:
            Document data or None if not found
        """
        try:
            # Get latest snapshot
            snapshot = await self.db_manager.get_latest_snapshot(document_id)
            
            if not snapshot:
                return None
            
            # Get metadata
            metadata = await self.db_manager.get_document_metadata(document_id)
            
            return {
                'content': snapshot['content'],
                'version': snapshot['version'],
                'created_at': snapshot['created_at'],
                'metadata': metadata
            }
            
        except Exception as e:
            logger.error("Error loading document", document_id=document_id, error=str(e))
            raise
    
    async def save_operation(self, document_id: str, operation_data: Dict[str, Any]):
        """
        Save operation to history.
        
        Args:
            document_id: Document identifier
            operation_data: Operation data
        """
        try:
            await self.db_manager.store_operation(document_id, operation_data)
            logger.debug("Operation saved", document_id=document_id, operation_id=operation_data['id'])
            
        except Exception as e:
            logger.error("Error saving operation", document_id=document_id, error=str(e))
            raise
    
    async def get_operation_history(
        self, 
        document_id: str, 
        limit: int = 1000,
        since_timestamp: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Get operation history for a document.
        
        Args:
            document_id: Document identifier
            limit: Maximum number of operations
            since_timestamp: Get operations since this timestamp
            
        Returns:
            List of operations
        """
        try:
            return await self.db_manager.get_operation_history(document_id, limit, since_timestamp)
            
        except Exception as e:
            logger.error("Error getting operation history", document_id=document_id, error=str(e))
            raise
    
    async def cleanup_old_data(self, snapshot_days: int = 30, operation_days: int = 7, session_days: int = 7):
        """
        Clean up old data.
        
        Args:
            snapshot_days: Days to keep snapshots
            operation_days: Days to keep operations
            session_days: Days to keep sessions
        """
        try:
            await self.db_manager.cleanup_old_snapshots(snapshot_days)
            await self.db_manager.cleanup_old_operations(operation_days)
            await self.db_manager.cleanup_old_sessions(session_days)
            
            logger.info("Old data cleaned up", 
                       snapshot_days=snapshot_days,
                       operation_days=operation_days,
                       session_days=session_days)
            
        except Exception as e:
            logger.error("Error cleaning up old data", error=str(e))
            raise
