"""
WebSocket Hub with Redis Pub/Sub for Real-Time Collaborative Editing
Handles WebSocket connections and broadcasts operations across multiple servers
"""

import asyncio
import json
import logging
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import redis.asyncio as aioredis
from fastapi import WebSocket, WebSocketDisconnect
import uuid

from document_model import DocumentManager, Operation, OperationType

logger = logging.getLogger(__name__)


@dataclass
class ConnectionInfo:
    """Information about a WebSocket connection"""
    websocket: WebSocket
    user_id: str
    doc_id: str
    connected_at: datetime
    last_activity: datetime
    is_alive: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'user_id': self.user_id,
            'doc_id': self.doc_id,
            'connected_at': self.connected_at.isoformat(),
            'last_activity': self.last_activity.isoformat(),
            'is_alive': self.is_alive
        }


@dataclass
class BroadcastMessage:
    """Message to be broadcast to clients"""
    type: str  # 'operation', 'cursor', 'user_joined', 'user_left', 'error'
    doc_id: str
    user_id: str
    data: Dict[str, Any]
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'type': self.type,
            'doc_id': self.doc_id,
            'user_id': self.user_id,
            'data': self.data,
            'timestamp': self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BroadcastMessage':
        """Create from dictionary"""
        return cls(
            type=data.get('type', 'operation'),
            doc_id=data.get('doc_id', ''),
            user_id=data.get('user_id', ''),
            data=data.get('data', {}),
            timestamp=datetime.fromisoformat(data.get('timestamp', datetime.utcnow().isoformat()))
        )


class CursorRateLimiter:
    """Rate limiter for cursor updates (max 10fps)"""
    
    def __init__(self, max_updates_per_second: int = 10):
        self.max_updates_per_second = max_updates_per_second
        self.last_updates: Dict[str, float] = {}  # user_id -> timestamp
    
    def should_update(self, user_id: str) -> bool:
        """Check if cursor update should be sent"""
        current_time = asyncio.get_event_loop().time()
        last_update = self.last_updates.get(user_id, 0)
        
        if current_time - last_update >= (1.0 / self.max_updates_per_second):
            self.last_updates[user_id] = current_time
            return True
        
        return False


class ConnectionManager:
    """
    Manages WebSocket connections and broadcasts messages
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.connections: Dict[str, ConnectionInfo] = {}  # connection_id -> ConnectionInfo
        self.doc_connections: Dict[str, Set[str]] = {}  # doc_id -> set of connection_ids
        self.user_connections: Dict[str, Set[str]] = {}  # user_id -> set of connection_ids
        self.redis_client: Optional[aioredis.Redis] = None
        self.redis_url = redis_url
        self.document_manager = DocumentManager()
        self.cursor_rate_limiter = CursorRateLimiter()
        self.message_handlers: Dict[str, callable] = {}
        
        logger.info("ConnectionManager initialized")
    
    async def initialize(self):
        """Initialize Redis connection and start background tasks"""
        try:
            self.redis_client = aioredis.from_url(self.redis_url)
            await self.redis_client.ping()
            logger.info("Connected to Redis")
            
            # Start Redis listener
            asyncio.create_task(self.redis_listener())
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def connect(self, websocket: WebSocket, doc_id: str, user_id: str) -> str:
        """
        Connect a new WebSocket client
        Returns connection ID
        """
        await websocket.accept()
        
        connection_id = str(uuid.uuid4())
        connection_info = ConnectionInfo(
            websocket=websocket,
            user_id=user_id,
            doc_id=doc_id,
            connected_at=datetime.utcnow(),
            last_activity=datetime.utcnow()
        )
        
        # Store connection
        self.connections[connection_id] = connection_info
        
        # Update indexes
        if doc_id not in self.doc_connections:
            self.doc_connections[doc_id] = set()
        self.doc_connections[doc_id].add(connection_id)
        
        if user_id not in self.user_connections:
            self.user_connections[user_id] = set()
        self.user_connections[user_id].add(connection_id)
        
        # Create document if it doesn't exist
        if not self.document_manager.get_document(doc_id):
            self.document_manager.create_document(doc_id)
        
        # Send current document state to new user
        await self.send_document_state(connection_id, doc_id)
        
        # Broadcast user joined
        await self.broadcast_user_joined(doc_id, user_id)
        
        logger.info(f"User {user_id} connected to document {doc_id}")
        
        return connection_id
    
    async def disconnect(self, connection_id: str):
        """Disconnect a WebSocket client"""
        connection_info = self.connections.get(connection_id)
        if not connection_info:
            return
        
        # Remove from indexes
        if connection_info.doc_id in self.doc_connections:
            self.doc_connections[connection_info.doc_id].discard(connection_id)
            if not self.doc_connections[connection_info.doc_id]:
                del self.doc_connections[connection_info.doc_id]
        
        if connection_info.user_id in self.user_connections:
            self.user_connections[connection_info.user_id].discard(connection_id)
            if not self.user_connections[connection_info.user_id]:
                del self.user_connections[connection_info.user_id]
        
        # Remove connection
        del self.connections[connection_id]
        
        # Broadcast user left
        await self.broadcast_user_left(connection_info.doc_id, connection_info.user_id)
        
        logger.info(f"User {connection_info.user_id} disconnected from document {connection_info.doc_id}")
    
    async def send_message(self, connection_id: str, message: Dict[str, Any]):
        """Send message to specific connection"""
        connection_info = self.connections.get(connection_id)
        if not connection_info or not connection_info.is_alive:
            return
        
        try:
            await connection_info.websocket.send_text(json.dumps(message))
            connection_info.last_activity = datetime.utcnow()
        except Exception as e:
            logger.error(f"Error sending message to {connection_id}: {e}")
            connection_info.is_alive = False
    
    async def broadcast_to_document(self, doc_id: str, message: Dict[str, Any], exclude_connection_id: str = None):
        """Broadcast message to all connections in a document"""
        connection_ids = self.doc_connections.get(doc_id, set()).copy()
        
        if exclude_connection_id:
            connection_ids.discard(exclude_connection_id)
        
        # Send to local connections
        for connection_id in connection_ids:
            await self.send_message(connection_id, message)
        
        # Publish to Redis for other servers
        await self.publish_to_redis(doc_id, message)
    
    async def publish_to_redis(self, doc_id: str, message: Dict[str, Any]):
        """Publish message to Redis for cross-server broadcasting"""
        if not self.redis_client:
            return
        
        try:
            channel = f"doc_{doc_id}"
            await self.redis_client.publish(channel, json.dumps(message))
        except Exception as e:
            logger.error(f"Error publishing to Redis: {e}")
    
    async def redis_listener(self):
        """Listen for Redis messages and broadcast to local connections"""
        if not self.redis_client:
            return
        
        pubsub = self.redis_client.pubsub()
        patterns = [f"doc_*"]
        await pubsub.psubscribe(*patterns)
        
        logger.info("Started Redis listener")
        
        while True:
            try:
                message = await pubsub.get_message(timeout=1.0)
                if message and message['type'] == 'pmessage':
                    channel = message['channel'].decode()
                    data = json.loads(message['data'])
                    
                    # Extract doc_id from channel
                    doc_id = channel.replace('doc_', '')
                    
                    # Broadcast to local connections (excluding original sender if present)
                    await self.broadcast_to_document(doc_id, data)
                    
            except Exception as e:
                logger.error(f"Error in Redis listener: {e}")
                await asyncio.sleep(1)
    
    async def handle_operation(self, connection_id: str, operation_data: Dict[str, Any]):
        """Handle text operation from client"""
        connection_info = self.connections.get(connection_id)
        if not connection_info:
            return
        
        try:
            # Parse operation
            operation = Operation.from_dict(operation_data)
            
            # Apply operation to document
            success = self.document_manager.apply_operation(connection_info.doc_id, operation)
            
            if success:
                # Broadcast operation to all clients
                message = BroadcastMessage(
                    type='operation',
                    doc_id=connection_info.doc_id,
                    user_id=connection_info.user_id,
                    data=operation.to_dict(),
                    timestamp=datetime.utcnow()
                )
                
                await self.broadcast_to_document(
                    connection_info.doc_id, 
                    message.to_dict(), 
                    exclude_connection_id=connection_id
                )
            else:
                # Send error
                error_message = BroadcastMessage(
                    type='error',
                    doc_id=connection_info.doc_id,
                    user_id=connection_info.user_id,
                    data={'error': 'Failed to apply operation'},
                    timestamp=datetime.utcnow()
                )
                await self.send_message(connection_id, error_message.to_dict())
                
        except Exception as e:
            logger.error(f"Error handling operation: {e}")
            
            # Send error to client
            error_message = BroadcastMessage(
                type='error',
                doc_id=connection_info.doc_id,
                user_id=connection_info.user_id,
                data={'error': str(e)},
                timestamp=datetime.utcnow()
            )
            await self.send_message(connection_id, error_message.to_dict())
    
    async def handle_cursor(self, connection_id: str, cursor_data: Dict[str, Any]):
        """Handle cursor position update"""
        connection_info = self.connections.get(connection_id)
        if not connection_info:
            return
        
        # Rate limit cursor updates
        if not self.cursor_rate_limiter.should_update(connection_info.user_id):
            return
        
        try:
            # Create cursor operation
            cursor_operation = Operation(
                type=OperationType.CURSOR,
                user_id=connection_info.user_id,
                cursor_data=cursor_data
            )
            
            # Apply to document
            self.document_manager.apply_operation(connection_info.doc_id, cursor_operation)
            
            # Broadcast cursor position
            message = BroadcastMessage(
                type='cursor',
                doc_id=connection_info.doc_id,
                user_id=connection_info.user_id,
                data=cursor_data,
                timestamp=datetime.utcnow()
            )
            
            await self.broadcast_to_document(
                connection_info.doc_id, 
                message.to_dict(), 
                exclude_connection_id=connection_id
            )
            
        except Exception as e:
            logger.error(f"Error handling cursor: {e}")
    
    async def send_document_state(self, connection_id: str, doc_id: str):
        """Send current document state to a client"""
        try:
            doc_info = self.document_manager.get_document_info(doc_id)
            if not doc_info:
                return
            
            message = BroadcastMessage(
                type='document_state',
                doc_id=doc_id,
                user_id='',
                data=doc_info,
                timestamp=datetime.utcnow()
            )
            
            await self.send_message(connection_id, message.to_dict())
            
        except Exception as e:
            logger.error(f"Error sending document state: {e}")
    
    async def broadcast_user_joined(self, doc_id: str, user_id: str):
        """Broadcast that a user joined"""
        message = BroadcastMessage(
            type='user_joined',
            doc_id=doc_id,
            user_id=user_id,
            data={'user_id': user_id},
            timestamp=datetime.utcnow()
        )
        
        await self.broadcast_to_document(doc_id, message.to_dict())
    
    async def broadcast_user_left(self, doc_id: str, user_id: str):
        """Broadcast that a user left"""
        message = BroadcastMessage(
            type='user_left',
            doc_id=doc_id,
            user_id=user_id,
            data={'user_id': user_id},
            timestamp=datetime.utcnow()
        )
        
        await self.broadcast_to_document(doc_id, message.to_dict())
    
    def get_document_users(self, doc_id: str) -> List[str]:
        """Get all users connected to a document"""
        connection_ids = self.doc_connections.get(doc_id, set())
        users = []
        
        for connection_id in connection_ids:
            connection_info = self.connections.get(connection_id)
            if connection_info and connection_info.is_alive:
                users.append(connection_info.user_id)
        
        return list(set(users))  # Remove duplicates
    
    def get_user_documents(self, user_id: str) -> List[str]:
        """Get all documents a user is connected to"""
        connection_ids = self.user_connections.get(user_id, set())
        documents = []
        
        for connection_id in connection_ids:
            connection_info = self.connections.get(connection_id)
            if connection_info and connection_info.is_alive:
                documents.append(connection_info.doc_id)
        
        return list(set(documents))  # Remove duplicates
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics"""
        active_connections = sum(1 for conn in self.connections.values() if conn.is_alive)
        
        return {
            'total_connections': len(self.connections),
            'active_connections': active_connections,
            'documents_with_connections': len(self.doc_connections),
            'connected_users': len(self.user_connections),
            'document_stats': {
                doc_id: len(connections) 
                for doc_id, connections in self.doc_connections.items()
            }
        }
    
    async def cleanup_stale_connections(self):
        """Clean up stale connections"""
        current_time = datetime.utcnow()
        stale_connections = []
        
        for connection_id, connection_info in self.connections.items():
            # Consider connection stale if no activity for 5 minutes
            if (current_time - connection_info.last_activity).seconds > 300:
                connection_info.is_alive = False
                stale_connections.append(connection_id)
        
        for connection_id in stale_connections:
            await self.disconnect(connection_id)
        
        if stale_connections:
            logger.info(f"Cleaned up {len(stale_connections)} stale connections")
    
    async def shutdown(self):
        """Shutdown the connection manager"""
        # Close all connections
        for connection_id in list(self.connections.keys()):
            await self.disconnect(connection_id)
        
        # Close Redis connection
        if self.redis_client:
            await self.redis_client.close()
        
        logger.info("ConnectionManager shutdown complete")


# Global connection manager instance
connection_manager = ConnectionManager()


# WebSocket handler functions
async def handle_websocket_connection(websocket: WebSocket, doc_id: str, user_id: str):
    """Handle WebSocket connection lifecycle"""
    connection_id = None
    
    try:
        # Connect
        connection_id = await connection_manager.connect(websocket, doc_id, user_id)
        
        # Handle messages
        while True:
            try:
                # Receive message
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                # Route message based on type
                message_type = message_data.get('type')
                
                if message_type == 'operation':
                    await connection_manager.handle_operation(connection_id, message_data.get('data', {}))
                elif message_type == 'cursor':
                    await connection_manager.handle_cursor(connection_id, message_data.get('data', {}))
                elif message_type == 'ping':
                    # Respond to ping
                    await websocket.send_text(json.dumps({'type': 'pong'}))
                else:
                    logger.warning(f"Unknown message type: {message_type}")
                    
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error handling message: {e}")
                break
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Error in WebSocket connection: {e}")
    finally:
        # Disconnect
        if connection_id:
            await connection_manager.disconnect(connection_id)


# Background tasks
async def start_background_tasks():
    """Start background maintenance tasks"""
    # Cleanup stale connections every 5 minutes
    while True:
        try:
            await connection_manager.cleanup_stale_connections()
            await asyncio.sleep(300)  # 5 minutes
        except Exception as e:
            logger.error(f"Error in cleanup task: {e}")
            await asyncio.sleep(60)


# Initialize connection manager
async def initialize_connection_manager(redis_url: str = "redis://localhost:6379"):
    """Initialize the global connection manager"""
    await connection_manager.initialize()
    asyncio.create_task(start_background_tasks())
    logger.info("Connection manager initialized and background tasks started")


# Example usage
if __name__ == "__main__":
    async def test_connection_manager():
        """Test the connection manager"""
        # Initialize
        await initialize_connection_manager()
        
        # Simulate some connections
        print(f"Connection stats: {connection_manager.get_connection_stats()}")
        
        # Wait a bit
        await asyncio.sleep(2)
        
        # Cleanup
        await connection_manager.shutdown()
    
    asyncio.run(test_connection_manager())
