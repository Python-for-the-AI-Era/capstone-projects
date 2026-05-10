"""
WebSocket hub for real-time collaborative code editing.

This module manages WebSocket connections, Redis pub/sub broadcasting,
and real-time synchronization between multiple users.
"""

import asyncio
import json
import time
import uuid
from typing import Dict, List, Optional, Set, Any
from datetime import datetime
import redis.asyncio as redis
import structlog
from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from ..models.document import DocumentManager, Operation, CursorPosition
from ..ot.transform import OperationalTransformer, ConflictResolver

logger = structlog.get_logger()


class WebSocketMessage(BaseModel):
    """WebSocket message model."""
    
    type: str
    data: Dict[str, Any]
    timestamp: float = Field(default_factory=time.time)
    user_id: str
    session_id: str
    document_id: str


class OperationMessage(WebSocketMessage):
    """Operation message model."""
    
    type: str = "operation"
    operation: Dict[str, Any]
    
    @classmethod
    def create(cls, operation: Operation, user_id: str, session_id: str, document_id: str):
        """Create operation message."""
        return cls(
            operation=operation.to_dict(),
            user_id=user_id,
            session_id=session_id,
            document_id=document_id
        )


class CursorMessage(WebSocketMessage):
    """Cursor position message model."""
    
    type: str = "cursor"
    cursor: Dict[str, Any]
    
    @classmethod
    def create(cls, cursor: CursorPosition, user_id: str, session_id: str, document_id: str):
        """Create cursor message."""
        return cls(
            cursor=cursor.to_dict(),
            user_id=user_id,
            session_id=session_id,
            document_id=document_id
        )


class UserSession(BaseModel):
    """User session model."""
    
    user_id: str
    session_id: str
    websocket: WebSocket
    document_id: str
    user_name: str = ""
    user_color: str = "#007bff"
    connected_at: datetime = Field(default_factory=datetime.utcnow)
    last_activity: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        arbitrary_types_allowed = True


class WebSocketHub:
    """
    WebSocket hub for managing collaborative editing sessions.
    
    Handles connection management, message broadcasting, and real-time synchronization.
    """
    
    def __init__(self, redis_client: redis.Redis, document_manager: DocumentManager):
        """
        Initialize WebSocket hub.
        
        Args:
            redis_client: Redis client for pub/sub
            document_manager: Document manager instance
        """
        self.redis = redis_client
        self.document_manager = document_manager
        self.transformer = OperationalTransformer()
        self.conflict_resolver = ConflictResolver(self.transformer)
        
        # Connection management
        self.connections: Dict[str, UserSession] = {}  # session_id -> UserSession
        self.document_connections: Dict[str, Set[str]] = {}  # document_id -> set of session_ids
        
        # Pub/Sub subscribers
        self.pubsub_tasks: Dict[str, asyncio.Task] = {}
        self.cursor_broadcast_tasks: Dict[str, asyncio.Task] = {}
        
        # Rate limiting
        self.message_rate_limits: Dict[str, List[float]] = {}
        self.cursor_rate_limits: Dict[str, List[float]] = {}
        
        logger.info("WebSocket hub initialized")
    
    async def connect_user(
        self, 
        websocket: WebSocket, 
        user_id: str, 
        session_id: str, 
        document_id: str,
        user_name: str = "",
        user_color: str = "#007bff"
    ) -> Dict[str, Any]:
        """
        Connect a user to a document session.
        
        Args:
            websocket: WebSocket connection
            user_id: User identifier
            session_id: Session identifier
            document_id: Document identifier
            user_name: User display name
            user_color: User cursor color
            
        Returns:
            Connection result
        """
        try:
            # Check if document exists
            document = await self.document_manager.get_document(document_id)
            if not document:
                await websocket.close(code=4004, reason="Document not found")
                return {"success": False, "error": "Document not found"}
            
            # Create user session
            session = UserSession(
                user_id=user_id,
                session_id=session_id,
                websocket=websocket,
                document_id=document_id,
                user_name=user_name,
                user_color=user_color
            )
            
            # Store connection
            self.connections[session_id] = session
            
            # Add to document connections
            if document_id not in self.document_connections:
                self.document_connections[document_id] = set()
                # Start pub/sub subscriber for this document
                await self._start_document_subscriber(document_id)
                # Start cursor broadcaster for this document
                await self._start_cursor_broadcaster(document_id)
            
            self.document_connections[document_id].add(session_id)
            
            # Add user to document
            await self.document_manager.add_user(document_id, user_id, session_id)
            
            # Start rate limiting tracking
            self.message_rate_limits[session_id] = []
            self.cursor_rate_limits[session_id] = []
            
            logger.info("User connected", 
                       user_id=user_id, 
                       session_id=session_id, 
                       document_id=document_id)
            
            return {
                "success": True,
                "document": document.dict(),
                "active_users": len(self.document_connections[document_id])
            }
            
        except Exception as e:
            logger.error("Error connecting user", 
                        user_id=user_id,
                        session_id=session_id,
                        document_id=document_id,
                        error=str(e))
            await websocket.close(code=1011, reason="Internal server error")
            return {"success": False, "error": str(e)}
    
    async def disconnect_user(self, session_id: str):
        """
        Disconnect a user from the hub.
        
        Args:
            session_id: Session identifier
        """
        if session_id not in self.connections:
            return
        
        session = self.connections[session_id]
        document_id = session.document_id
        user_id = session.user_id
        
        try:
            # Remove from connections
            del self.connections[session_id]
            
            # Remove from document connections
            if document_id in self.document_connections:
                self.document_connections[document_id].discard(session_id)
                
                # Stop pub/sub subscriber if no more connections
                if not self.document_connections[document_id]:
                    await self._stop_document_subscriber(document_id)
                    await self._stop_cursor_broadcaster(document_id)
                    del self.document_connections[document_id]
            
            # Remove user from document
            await self.document_manager.remove_user(document_id, user_id, session_id)
            
            # Clean up rate limiting
            if session_id in self.message_rate_limits:
                del self.message_rate_limits[session_id]
            if session_id in self.cursor_rate_limits:
                del self.cursor_rate_limits[session_id]
            
            logger.info("User disconnected", 
                       user_id=user_id,
                       session_id=session_id,
                       document_id=document_id)
            
        except Exception as e:
            logger.error("Error disconnecting user", 
                        session_id=session_id,
                        error=str(e))
    
    async def handle_message(self, session_id: str, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle incoming WebSocket message.
        
        Args:
            session_id: Session identifier
            message: Message data
            
        Returns:
            Message handling result
        """
        try:
            if session_id not in self.connections:
                return {"success": False, "error": "Session not found"}
            
            session = self.connections[session_id]
            
            # Validate message structure
            if "type" not in message:
                return {"success": False, "error": "Missing message type"}
            
            message_type = message["type"]
            
            if message_type == "operation":
                return await self._handle_operation_message(session, message)
            elif message_type == "cursor":
                return await self._handle_cursor_message(session, message)
            elif message_type == "ping":
                return await self._handle_ping_message(session, message)
            else:
                return {"success": False, "error": f"Unknown message type: {message_type}"}
                
        except Exception as e:
            logger.error("Error handling message", 
                        session_id=session_id,
                        message_type=message.get("type"),
                        error=str(e))
            return {"success": False, "error": str(e)}
    
    async def _handle_operation_message(self, session: UserSession, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle operation message."""
        try:
            # Rate limiting check
            if not self._check_rate_limit(session.session_id, self.message_rate_limits, max_per_second=10):
                return {"success": False, "error": "Rate limit exceeded"}
            
            # Parse operation
            operation_data = message.get("operation", {})
            operation = Operation.from_dict(operation_data)
            
            # Set operation metadata
            operation.user_id = session.user_id
            operation.session_id = session.session_id
            
            # Get concurrent operations
            document_id = session.document_id
            concurrent_operations = await self._get_concurrent_operations(document_id, operation)
            
            # Transform operation against concurrent operations
            transform_result = await self.transformer.transform_operation(
                operation, concurrent_operations, ""
            )
            
            if not transform_result.success:
                return {"success": False, "error": transform_result.error_message}
            
            # Apply operation to document
            success = await self.document_manager.apply_operation(document_id, transform_result.operation)
            
            if not success:
                return {"success": False, "error": "Failed to apply operation"}
            
            # Add to transformer history
            self.transformer.add_operation_to_history(document_id, transform_result.operation)
            
            # Broadcast to other users
            await self._broadcast_operation(document_id, transform_result.operation, session.session_id)
            
            # Update last activity
            session.last_activity = datetime.utcnow()
            
            logger.debug("Operation handled", 
                        operation_id=operation.id,
                        user_id=session.user_id,
                        document_id=document_id,
                        transformed=transform_result.transformed)
            
            return {"success": True, "transformed": transform_result.transformed}
            
        except Exception as e:
            logger.error("Error handling operation message", 
                        session_id=session.session_id,
                        error=str(e))
            return {"success": False, "error": str(e)}
    
    async def _handle_cursor_message(self, session: UserSession, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle cursor position message."""
        try:
            # Rate limiting check
            if not self._check_rate_limit(session.session_id, self.cursor_rate_limits, max_per_second=10):
                return {"success": False, "error": "Rate limit exceeded"}
            
            # Parse cursor position
            cursor_data = message.get("cursor", {})
            cursor = CursorPosition.from_dict(cursor_data)
            
            # Set cursor metadata
            cursor.user_id = session.user_id
            cursor.session_id = session.session_id
            cursor.user_name = session.user_name
            cursor.user_color = session.user_color
            
            # Get recent operations for transformation
            document_id = session.document_id
            recent_operations = self.transformer.get_operation_history(document_id, since_timestamp=time.time() - 5.0)
            
            # Transform cursor position
            transformed_cursor = await self.transformer.transform_cursor_position(cursor, recent_operations)
            
            # Update cursor position
            await self.document_manager.update_cursor_position(document_id, transformed_cursor)
            
            # Broadcast to other users (handled by cursor broadcaster)
            
            # Update last activity
            session.last_activity = datetime.utcnow()
            
            return {"success": True}
            
        except Exception as e:
            logger.error("Error handling cursor message", 
                        session_id=session.session_id,
                        error=str(e))
            return {"success": False, "error": str(e)}
    
    async def _handle_ping_message(self, session: UserSession, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle ping message."""
        # Update last activity
        session.last_activity = datetime.utcnow()
        
        return {"success": True, "pong": True}
    
    async def _broadcast_operation(self, document_id: str, operation: Operation, exclude_session_id: str):
        """
        Broadcast operation to all users in a document.
        
        Args:
            document_id: Document identifier
            operation: Operation to broadcast
            exclude_session_id: Session to exclude from broadcast
        """
        try:
            # Create message
            message = OperationMessage.create(operation, operation.user_id, operation.session_id, document_id)
            
            # Publish to Redis pub/sub
            channel = f"doc:{document_id}:operations"
            await self.redis.publish(channel, message.json())
            
            logger.debug("Operation broadcasted", 
                        document_id=document_id,
                        operation_id=operation.id,
                        exclude_session=exclude_session_id)
            
        except Exception as e:
            logger.error("Error broadcasting operation", 
                        document_id=document_id,
                        operation_id=operation.id,
                        error=str(e))
    
    async def _broadcast_cursor(self, document_id: str, cursor: CursorPosition, exclude_session_id: str):
        """
        Broadcast cursor position to all users in a document.
        
        Args:
            document_id: Document identifier
            cursor: Cursor position to broadcast
            exclude_session_id: Session to exclude from broadcast
        """
        try:
            # Create message
            message = CursorMessage.create(cursor, cursor.user_id, cursor.session_id, document_id)
            
            # Publish to Redis pub/sub
            channel = f"doc:{document_id}:cursors"
            await self.redis.publish(channel, message.json())
            
            logger.debug("Cursor broadcasted", 
                        document_id=document_id,
                        user_id=cursor.user_id,
                        exclude_session=exclude_session_id)
            
        except Exception as e:
            logger.error("Error broadcasting cursor", 
                        document_id=document_id,
                        user_id=cursor.user_id,
                        error=str(e))
    
    async def _start_document_subscriber(self, document_id: str):
        """
        Start Redis pub/sub subscriber for a document.
        
        Args:
            document_id: Document identifier
        """
        if document_id in self.pubsub_tasks:
            return
        
        task = asyncio.create_task(self._document_subscriber_loop(document_id))
        self.pubsub_tasks[document_id] = task
        
        logger.info("Document subscriber started", document_id=document_id)
    
    async def _stop_document_subscriber(self, document_id: str):
        """
        Stop Redis pub/sub subscriber for a document.
        
        Args:
            document_id: Document identifier
        """
        if document_id in self.pubsub_tasks:
            task = self.pubsub_tasks[document_id]
            task.cancel()
            del self.pubsub_tasks[document_id]
            
            logger.info("Document subscriber stopped", document_id=document_id)
    
    async def _document_subscriber_loop(self, document_id: str):
        """
        Redis pub/sub subscriber loop for a document.
        
        Args:
            document_id: Document identifier
        """
        pubsub = self.redis.pubsub()
        channel = f"doc:{document_id}:operations"
        
        try:
            await pubsub.subscribe(channel)
            
            while True:
                try:
                    message = await pubsub.get_message(timeout=1.0)
                    if message is None:
                        continue
                    
                    # Parse message
                    data = json.loads(message['data'])
                    message_type = data.get('type')
                    
                    if message_type == 'operation':
                        await self._handle_broadcasted_operation(document_id, data)
                    
                except Exception as e:
                    logger.error("Error in subscriber loop", 
                                document_id=document_id,
                                error=str(e))
                    await asyncio.sleep(1.0)  # Brief pause before retrying
                    
        except asyncio.CancelledError:
            logger.info("Subscriber loop cancelled", document_id=document_id)
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
    
    async def _handle_broadcasted_operation(self, document_id: str, message_data: Dict[str, Any]):
        """
        Handle broadcasted operation message.
        
        Args:
            document_id: Document identifier
            message_data: Message data
        """
        try:
            exclude_session_id = message_data.get('session_id')
            
            # Send to all connected users in the document
            if document_id in self.document_connections:
                for session_id in self.document_connections[document_id]:
                    if session_id != exclude_session_id and session_id in self.connections:
                        session = self.connections[session_id]
                        try:
                            await session.websocket.send_text(json.dumps(message_data))
                        except Exception as e:
                            logger.warning("Failed to send operation to user", 
                                        session_id=session_id,
                                        error=str(e))
                            # Connection might be dead, consider cleanup
                            await self.disconnect_user(session_id)
            
        except Exception as e:
            logger.error("Error handling broadcasted operation", 
                        document_id=document_id,
                        error=str(e))
    
    async def _start_cursor_broadcaster(self, document_id: str):
        """
        Start cursor broadcaster for a document.
        
        Args:
            document_id: Document identifier
        """
        if document_id in self.cursor_broadcast_tasks:
            return
        
        task = asyncio.create_task(self._cursor_broadcaster_loop(document_id))
        self.cursor_broadcast_tasks[document_id] = task
        
        logger.info("Cursor broadcaster started", document_id=document_id)
    
    async def _stop_cursor_broadcaster(self, document_id: str):
        """
        Stop cursor broadcaster for a document.
        
        Args:
            document_id: Document identifier
        """
        if document_id in self.cursor_broadcast_tasks:
            task = self.cursor_broadcast_tasks[document_id]
            task.cancel()
            del self.cursor_broadcast_tasks[document_id]
            
            logger.info("Cursor broadcaster stopped", document_id=document_id)
    
    async def _cursor_broadcaster_loop(self, document_id: str):
        """
        Cursor broadcaster loop for a document.
        
        Args:
            document_id: Document identifier
        """
        try:
            while True:
                try:
                    # Get current cursor positions
                    cursors = await self.document_manager.get_cursor_positions(document_id)
                    
                    if cursors:
                        # Broadcast cursor positions
                        for cursor in cursors:
                            await self._broadcast_cursor(document_id, cursor, cursor.session_id)
                    
                    # Wait before next broadcast (10fps = 100ms)
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    logger.error("Error in cursor broadcaster loop", 
                                document_id=document_id,
                                error=str(e))
                    await asyncio.sleep(1.0)  # Brief pause before retrying
                    
        except asyncio.CancelledError:
            logger.info("Cursor broadcaster loop cancelled", document_id=document_id)
    
    async def _get_concurrent_operations(self, document_id: str, current_operation: Operation) -> List[Operation]:
        """
        Get concurrent operations for transformation.
        
        Args:
            document_id: Document identifier
            current_operation: Current operation
            
        Returns:
            List of concurrent operations
        """
        try:
            # Get recent operations from transformer history
            recent_operations = self.transformer.get_operation_history(document_id)
            
            # Filter operations that happened within the last second
            current_time = time.time()
            concurrent_operations = [
                op for op in recent_operations 
                if abs(op.timestamp - current_operation.timestamp) < 1.0
                and op.id != current_operation.id
            ]
            
            return concurrent_operations
            
        except Exception as e:
            logger.error("Error getting concurrent operations", 
                        document_id=document_id,
                        error=str(e))
            return []
    
    def _check_rate_limit(self, session_id: str, rate_limits: Dict[str, List[float]], max_per_second: int = 10) -> bool:
        """
        Check if session is within rate limits.
        
        Args:
            session_id: Session identifier
            rate_limits: Rate limit tracking
            max_per_second: Maximum messages per second
            
        Returns:
            True if within rate limits
        """
        current_time = time.time()
        
        if session_id not in rate_limits:
            rate_limits[session_id] = []
        
        # Clean up old entries (older than 1 second)
        rate_limits[session_id] = [
            timestamp for timestamp in rate_limits[session_id]
            if current_time - timestamp < 1.0
        ]
        
        # Check rate limit
        if len(rate_limits[session_id]) >= max_per_second:
            return False
        
        # Add current timestamp
        rate_limits[session_id].append(current_time)
        return True
    
    async def get_connection_stats(self) -> Dict[str, Any]:
        """
        Get connection statistics.
        
        Returns:
            Connection statistics
        """
        try:
            stats = {
                'total_connections': len(self.connections),
                'active_documents': len(self.document_connections),
                'pubsub_subscribers': len(self.pubsub_tasks),
                'cursor_broadcasters': len(self.cursor_broadcast_tasks),
                'documents': {}
            }
            
            for document_id, session_ids in self.document_connections.items():
                document_stats = await self.document_manager.get_document_stats(document_id)
                stats['documents'][document_id] = {
                    'connected_users': len(session_ids),
                    'stats': document_stats
                }
            
            return stats
            
        except Exception as e:
            logger.error("Error getting connection stats", error=str(e))
            return {}
    
    async def cleanup_inactive_connections(self, timeout_minutes: int = 30):
        """
        Clean up inactive connections.
        
        Args:
            timeout_minutes: Inactivity timeout in minutes
        """
        try:
            current_time = datetime.utcnow()
            timeout = timedelta(minutes=timeout_minutes)
            
            inactive_sessions = []
            
            for session_id, session in list(self.connections.items()):
                if current_time - session.last_activity > timeout:
                    inactive_sessions.append(session_id)
            
            for session_id in inactive_sessions:
                await self.disconnect_user(session_id)
            
            if inactive_sessions:
                logger.info("Cleaned up inactive connections", 
                           count=len(inactive_sessions),
                           timeout_minutes=timeout_minutes)
            
        except Exception as e:
            logger.error("Error cleaning up inactive connections", error=str(e))
    
    async def shutdown(self):
        """Shutdown the WebSocket hub."""
        try:
            # Disconnect all users
            for session_id in list(self.connections.keys()):
                await self.disconnect_user(session_id)
            
            # Stop all pub/sub tasks
            for document_id in list(self.pubsub_tasks.keys()):
                await self._stop_document_subscriber(document_id)
            
            # Stop all cursor broadcasters
            for document_id in list(self.cursor_broadcast_tasks.keys()):
                await self._stop_cursor_broadcaster(document_id)
            
            logger.info("WebSocket hub shutdown complete")
            
        except Exception as e:
            logger.error("Error during shutdown", error=str(e))
