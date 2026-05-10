"""
Document model for real-time collaborative code editor.

This module defines the document structure, operations, and state management
for the collaborative editing system with CRDT-like operational transformation.
"""

import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict, field
from enum import Enum
import redis.asyncio as redis
import asyncpg
from pydantic import BaseModel, Field
import structlog

logger = structlog.get_logger()


class OperationType(str, Enum):
    """Types of operations that can be applied to a document."""
    INSERT = "insert"
    DELETE = "delete"
    RETAIN = "retain"
    FORMAT = "format"


@dataclass
class Operation:
    """Represents a single operation on a document."""
    
    id: str
    type: OperationType
    position: int
    content: Optional[str] = None
    length: Optional[int] = None
    attributes: Optional[Dict[str, Any]] = None
    user_id: str = ""
    timestamp: float = field(default_factory=time.time)
    session_id: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert operation to dictionary."""
        return {
            'id': self.id,
            'type': self.type.value,
            'position': self.position,
            'content': self.content,
            'length': self.length,
            'attributes': self.attributes,
            'user_id': self.user_id,
            'timestamp': self.timestamp,
            'session_id': self.session_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Operation':
        """Create operation from dictionary."""
        return cls(
            id=data['id'],
            type=OperationType(data['type']),
            position=data['position'],
            content=data.get('content'),
            length=data.get('length'),
            attributes=data.get('attributes'),
            user_id=data.get('user_id', ''),
            timestamp=data.get('timestamp', time.time()),
            session_id=data.get('session_id', '')
        )


@dataclass
class CursorPosition:
    """Represents a user's cursor position in the document."""
    
    user_id: str
    session_id: str
    line: int
    column: int
    selection_start: Optional[int] = None
    selection_end: Optional[int] = None
    timestamp: float = field(default_factory=time.time)
    user_name: str = ""
    user_color: str = "#007bff"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert cursor to dictionary."""
        return {
            'user_id': self.user_id,
            'session_id': self.session_id,
            'line': self.line,
            'column': self.column,
            'selection_start': self.selection_start,
            'selection_end': self.selection_end,
            'timestamp': self.timestamp,
            'user_name': self.user_name,
            'user_color': self.user_color
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CursorPosition':
        """Create cursor from dictionary."""
        return cls(
            user_id=data['user_id'],
            session_id=data['session_id'],
            line=data['line'],
            column=data['column'],
            selection_start=data.get('selection_start'),
            selection_end=data.get('selection_end'),
            timestamp=data.get('timestamp', time.time()),
            user_name=data.get('user_name', ''),
            user_color=data.get('user_color', '#007bff')
        )


class DocumentState(BaseModel):
    """Represents the current state of a document."""
    
    document_id: str
    content: str = ""
    version: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_snapshot_at: Optional[datetime] = None
    active_users: List[str] = Field(default_factory=list)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class DocumentManager:
    """Manages document state, operations, and persistence."""
    
    def __init__(self, redis_client: redis.Redis, db_pool: asyncpg.Pool):
        """
        Initialize document manager.
        
        Args:
            redis_client: Redis client for real-time operations
            db_pool: PostgreSQL connection pool for persistence
        """
        self.redis = redis_client
        self.db_pool = db_pool
        self.documents: Dict[str, DocumentState] = {}
        self.operation_queues: Dict[str, asyncio.Queue] = {}
        self.cursor_positions: Dict[str, Dict[str, CursorPosition]] = {}
        
        logger.info("Document manager initialized")
    
    async def create_document(self, document_id: str, initial_content: str = "") -> DocumentState:
        """
        Create a new document.
        
        Args:
            document_id: Unique document identifier
            initial_content: Initial document content
            
        Returns:
            Created document state
        """
        document = DocumentState(
            document_id=document_id,
            content=initial_content,
            version=0
        )
        
        # Store in Redis for real-time access
        await self._store_document_in_redis(document)
        
        # Store in PostgreSQL for persistence
        await self._store_document_in_db(document)
        
        # Initialize operation queue
        self.operation_queues[document_id] = asyncio.Queue()
        
        self.documents[document_id] = document
        
        logger.info("Document created", document_id=document_id, version=document.version)
        return document
    
    async def get_document(self, document_id: str) -> Optional[DocumentState]:
        """
        Get document state.
        
        Args:
            document_id: Document identifier
            
        Returns:
            Document state or None if not found
        """
        # Check cache first
        if document_id in self.documents:
            return self.documents[document_id]
        
        # Try to load from Redis
        document = await self._load_document_from_redis(document_id)
        if document:
            self.documents[document_id] = document
            return document
        
        # Try to load from database
        document = await self._load_document_from_db(document_id)
        if document:
            self.documents[document_id] = document
            await self._store_document_in_redis(document)
            return document
        
        return None
    
    async def apply_operation(self, document_id: str, operation: Operation) -> bool:
        """
        Apply an operation to a document.
        
        Args:
            document_id: Document identifier
            operation: Operation to apply
            
        Returns:
            True if operation was applied successfully
        """
        document = await self.get_document(document_id)
        if not document:
            logger.error("Document not found", document_id=document_id)
            return False
        
        try:
            # Apply operation to document content
            new_content = await self._apply_operation_to_content(
                document.content, operation
            )
            
            if new_content is None:
                logger.error("Failed to apply operation", operation_id=operation.id)
                return False
            
            # Update document state
            document.content = new_content
            document.version += 1
            document.updated_at = datetime.utcnow()
            
            # Store updated document
            await self._store_document_in_redis(document)
            
            # Queue operation for broadcasting
            if document_id not in self.operation_queues:
                self.operation_queues[document_id] = asyncio.Queue()
            
            await self.operation_queues[document_id].put(operation)
            
            logger.info("Operation applied", 
                       document_id=document_id, 
                       operation_id=operation.id,
                       version=document.version)
            
            return True
            
        except Exception as e:
            logger.error("Error applying operation", 
                        document_id=document_id, 
                        operation_id=operation.id,
                        error=str(e))
            return False
    
    async def _apply_operation_to_content(self, content: str, operation: Operation) -> Optional[str]:
        """
        Apply operation to document content.
        
        Args:
            content: Current document content
            operation: Operation to apply
            
        Returns:
            New content or None if operation is invalid
        """
        try:
            if operation.type == OperationType.INSERT:
                if operation.position < 0 or operation.position > len(content):
                    return None
                return (
                    content[:operation.position] + 
                    operation.content + 
                    content[operation.position:]
                )
            
            elif operation.type == OperationType.DELETE:
                if operation.position < 0 or operation.position >= len(content):
                    return None
                delete_length = operation.length or 1
                end_position = min(operation.position + delete_length, len(content))
                return content[:operation.position] + content[end_position:]
            
            elif operation.type == OperationType.RETAIN:
                # Retain operation doesn't change content
                return content
            
            elif operation.type == OperationType.FORMAT:
                # Format operation doesn't change content in this simple implementation
                return content
            
            return content
            
        except Exception as e:
            logger.error("Error applying operation to content", error=str(e)
            return None
    
    async def get_operations_since(self, document_id: str, since_version: int) -> List[Operation]:
        """
        Get operations applied to document since a specific version.
        
        Args:
            document_id: Document identifier
            since_version: Version to get operations since
            
        Returns:
            List of operations
        """
        try:
            # Get operations from Redis
            operations_key = f"doc:{document_id}:operations"
            operations_data = await self.redis.lrange(operations_key, 0, -1)
            
            operations = []
            for op_data in operations_data:
                op_dict = json.loads(op_data)
                operation = Operation.from_dict(op_dict)
                
                # Filter by version (simplified - in practice, track version per operation)
                if operation.timestamp > (since_version * 1000):  # Simplified version check
                    operations.append(operation)
            
            return operations
            
        except Exception as e:
            logger.error("Error getting operations since version", 
                        document_id=document_id, 
                        since_version=since_version,
                        error=str(e))
            return []
    
    async def add_user(self, document_id: str, user_id: str, session_id: str):
        """
        Add a user to a document session.
        
        Args:
            document_id: Document identifier
            user_id: User identifier
            session_id: Session identifier
        """
        document = await self.get_document(document_id)
        if document and user_id not in document.active_users:
            document.active_users.append(user_id)
            await self._store_document_in_redis(document)
            
            # Initialize cursor positions for this session
            if document_id not in self.cursor_positions:
                self.cursor_positions[document_id] = {}
            
            logger.info("User added to document", 
                       document_id=document_id, 
                       user_id=user_id, 
                       session_id=session_id)
    
    async def remove_user(self, document_id: str, user_id: str, session_id: str):
        """
        Remove a user from a document session.
        
        Args:
            document_id: Document identifier
            user_id: User identifier
            session_id: Session identifier
        """
        document = await self.get_document(document_id)
        if document and user_id in document.active_users:
            document.active_users.remove(user_id)
            await self._store_document_in_redis(document)
            
            # Remove cursor positions
            if document_id in self.cursor_positions:
                self.cursor_positions[document_id].pop(session_id, None)
            
            logger.info("User removed from document", 
                       document_id=document_id, 
                       user_id=user_id, 
                       session_id=session_id)
    
    async def update_cursor_position(self, document_id: str, cursor: CursorPosition):
        """
        Update user's cursor position.
        
        Args:
            document_id: Document identifier
            cursor: Cursor position
        """
        if document_id not in self.cursor_positions:
            self.cursor_positions[document_id] = {}
        
        # Last-writer-wins for cursor positions
        self.cursor_positions[document_id][cursor.session_id] = cursor
        
        logger.debug("Cursor position updated", 
                    document_id=document_id,
                    user_id=cursor.user_id,
                    line=cursor.line,
                    column=cursor.column)
    
    async def get_cursor_positions(self, document_id: str) -> List[CursorPosition]:
        """
        Get all cursor positions for a document.
        
        Args:
            document_id: Document identifier
            
        Returns:
            List of cursor positions
        """
        if document_id not in self.cursor_positions:
            return []
        
        # Filter out old cursors (older than 5 seconds)
        current_time = time.time()
        cursors = []
        
        for cursor in self.cursor_positions[document_id].values():
            if current_time - cursor.timestamp < 5.0:  # 5 second timeout
                cursors.append(cursor)
        
        return cursors
    
    async def create_snapshot(self, document_id: str) -> bool:
        """
        Create a snapshot of the current document state.
        
        Args:
            document_id: Document identifier
            
        Returns:
            True if snapshot was created successfully
        """
        document = await self.get_document(document_id)
        if not document:
            return False
        
        try:
            # Store snapshot in database
            await self._store_document_snapshot(document)
            
            # Update last snapshot time
            document.last_snapshot_at = datetime.utcnow()
            await self._store_document_in_redis(document)
            
            # Clean up old operations (keep only recent ones)
            await self._cleanup_old_operations(document_id)
            
            logger.info("Snapshot created", 
                       document_id=document_id, 
                       version=document.version)
            
            return True
            
        except Exception as e:
            logger.error("Error creating snapshot", 
                        document_id=document_id,
                        error=str(e))
            return False
    
    async def get_pending_operations(self, document_id: str) -> List[Operation]:
        """
        Get pending operations for broadcasting.
        
        Args:
            document_id: Document identifier
            
        Returns:
            List of pending operations
        """
        if document_id not in self.operation_queues:
            return []
        
        operations = []
        queue = self.operation_queues[document_id]
        
        # Get all operations from queue
        while not queue.empty():
            try:
                operation = queue.get_nowait()
                operations.append(operation)
            except asyncio.QueueEmpty:
                break
        
        return operations
    
    async def _store_document_in_redis(self, document: DocumentState):
        """Store document state in Redis."""
        key = f"doc:{document.document_id}"
        data = document.json()
        await self.redis.set(key, data, ex=3600)  # 1 hour expiry
    
    async def _load_document_from_redis(self, document_id: str) -> Optional[DocumentState]:
        """Load document state from Redis."""
        key = f"doc:{document_id}"
        data = await self.redis.get(key)
        
        if data:
            return DocumentState.parse_raw(data)
        
        return None
    
    async def _store_document_in_db(self, document: DocumentState):
        """Store document state in PostgreSQL."""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO documents (document_id, content, version, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (document_id) 
                DO UPDATE SET 
                    content = $2,
                    version = $3,
                    updated_at = $5
            """, document.document_id, document.content, document.version,
                document.created_at, document.updated_at)
    
    async def _load_document_from_db(self, document_id: str) -> Optional[DocumentState]:
        """Load document state from PostgreSQL."""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT document_id, content, version, created_at, updated_at, last_snapshot_at
                FROM documents
                WHERE document_id = $1
            """, document_id)
            
            if row:
                return DocumentState(
                    document_id=row['document_id'],
                    content=row['content'],
                    version=row['version'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at'],
                    last_snapshot_at=row['last_snapshot_at']
                )
        
        return None
    
    async def _store_document_snapshot(self, document: DocumentState):
        """Store document snapshot in database."""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO document_snapshots (document_id, content, version, created_at)
                VALUES ($1, $2, $3, $4)
            """, document.document_id, document.content, document.version, datetime.utcnow())
    
    async def _cleanup_old_operations(self, document_id: str):
        """Clean up old operations from Redis."""
        operations_key = f"doc:{document_id}:operations"
        
        # Keep only last 1000 operations
        await self.redis.ltrim(operations_key, -1000, -1)
    
    async def get_document_stats(self, document_id: str) -> Dict[str, Any]:
        """
        Get document statistics.
        
        Args:
            document_id: Document identifier
            
        Returns:
            Document statistics
        """
        document = await self.get_document(document_id)
        if not document:
            return {}
        
        cursor_positions = await self.get_cursor_positions(document_id)
        
        return {
            'document_id': document_id,
            'version': document.version,
            'content_length': len(document.content),
            'active_users': len(document.active_users),
            'connected_cursors': len(cursor_positions),
            'last_updated': document.updated_at.isoformat(),
            'last_snapshot': document.last_snapshot_at.isoformat() if document.last_snapshot_at else None
        }
