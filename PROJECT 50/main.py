"""
FastAPI Application for Real-Time Collaborative Code Editor
Integrates WebSocket, Redis, PostgreSQL, and Operational Transformation
"""

import asyncio
import logging
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn

# Import our custom modules
from document_model import DocumentManager, Operation, OperationType, create_insert_operation, create_delete_operation
from websocket_hub import ConnectionManager, handle_websocket_connection, initialize_connection_manager
from conflict_resolution import ConflictResolutionManager
from persistence import PersistenceManager, PersistenceConfig, initialize_persistence
from cursor_tracking import get_cursor_tracker, get_event_broadcaster, CursorPosition

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Pydantic models for API
class DocumentCreate(BaseModel):
    title: str = Field(default="", description="Document title")
    owner_id: str = Field(description="Document owner ID")
    is_public: bool = Field(default=False, description="Whether document is public")
    initial_content: str = Field(default="", description="Initial document content")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Document metadata")


class DocumentInfo(BaseModel):
    doc_id: str
    title: str
    owner_id: str
    is_public: bool
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any]
    current_users: int = Field(default=0, description="Number of active users")
    version: int = Field(default=0, description="Current document version")


class OperationRequest(BaseModel):
    type: str = Field(description="Operation type: insert, delete, or cursor")
    position: int = Field(description="Character position")
    char: str = Field(default="", description="Character to insert (for insert operations)")
    length: int = Field(default=1, description="Length of deletion (for delete operations)")
    user_id: str = Field(description="User ID")
    version: int = Field(description="Operation version")
    cursor_data: Optional[Dict[str, Any]] = Field(default=None, description="Cursor position data")


class CursorUpdate(BaseModel):
    user_id: str = Field(description="User ID")
    line: int = Field(description="Line number")
    column: int = Field(description="Column number")
    selection_start: Optional[int] = Field(default=None, description="Selection start position")
    selection_end: Optional[int] = Field(default=None, description="Selection end position")
    user_name: str = Field(default="", description="User display name")


class WebSocketMessage(BaseModel):
    type: str = Field(description="Message type")
    data: Dict[str, Any] = Field(description="Message data")


# Global instances
document_manager: Optional[DocumentManager] = None
conflict_manager: Optional[ConflictResolutionManager] = None
persistence_manager: Optional[PersistenceManager] = None
connection_manager: Optional[ConnectionManager] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting CodeCollab backend...")
    
    try:
        # Initialize persistence
        persistence_config = PersistenceConfig(
            postgres_dsn="postgresql://collab_user:collab_pass@localhost/collaborative_editor",
            redis_url="redis://localhost:6379",
            snapshot_interval_seconds=30,
            max_operations_in_memory=1000
        )
        
        await initialize_persistence(persistence_config)
        global persistence_manager
        persistence_manager = get_persistence_manager()
        
        # Initialize connection manager
        await initialize_connection_manager("redis://localhost:6379")
        global connection_manager
        from websocket_hub import connection_manager as cm
        connection_manager = cm
        
        # Initialize document and conflict managers
        global document_manager, conflict_manager
        document_manager = DocumentManager()
        conflict_manager = ConflictResolutionManager()
        
        logger.info("CodeCollab backend started successfully")
        
        yield
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise
    
    # Shutdown
    logger.info("Shutting down CodeCollab backend...")
    
    if persistence_manager:
        await persistence_manager.close()
    
    if connection_manager:
        await connection_manager.shutdown()
    
    logger.info("CodeCollab backend shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="CodeCollab API",
    description="Real-time collaborative code editor backend",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Dependency functions
def get_document_manager() -> DocumentManager:
    """Get document manager instance"""
    if document_manager is None:
        raise HTTPException(status_code=500, detail="Document manager not initialized")
    return document_manager


def get_conflict_manager() -> ConflictResolutionManager:
    """Get conflict manager instance"""
    if conflict_manager is None:
        raise HTTPException(status_code=500, detail="Conflict manager not initialized")
    return conflict_manager


def get_persistence_manager() -> PersistenceManager:
    """Get persistence manager instance"""
    if persistence_manager is None:
        raise HTTPException(status_code=500, detail="Persistence manager not initialized")
    return persistence_manager


# HTTP API endpoints
@app.post("/documents", response_model=DocumentInfo)
async def create_document(
    document: DocumentCreate,
    doc_manager: DocumentManager = Depends(get_document_manager),
    persist_manager: PersistenceManager = Depends(get_persistence_manager)
):
    """Create a new document"""
    try:
        # Create document in persistence layer
        success = await persist_manager.create_document(
            doc_id=document.title.replace(" ", "_").lower(),
            title=document.title,
            owner_id=document.owner_id,
            is_public=document.is_public,
            metadata=document.metadata
        )
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to create document")
        
        # Create document in memory
        doc_id = document.title.replace(" ", "_").lower()
        doc_state = doc_manager.create_document(doc_id, document.initial_content)
        
        # Start snapshot task
        await persist_manager.start_snapshot_task(doc_id, doc_manager.get_document)
        
        return DocumentInfo(
            doc_id=doc_id,
            title=document.title,
            owner_id=document.owner_id,
            is_public=document.is_public,
            created_at=doc_state.last_modified,
            updated_at=doc_state.last_modified,
            metadata=document.metadata,
            current_users=0,
            version=doc_state.version
        )
        
    except Exception as e:
        logger.error(f"Error creating document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents/{doc_id}", response_model=DocumentInfo)
async def get_document(
    doc_id: str,
    doc_manager: DocumentManager = Depends(get_document_manager),
    persist_manager: PersistenceManager = Depends(get_persistence_manager)
):
    """Get document information"""
    try:
        # Get document from persistence
        doc_info = await persist_manager.get_document_info(doc_id)
        if not doc_info:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Get current state
        doc_state = doc_manager.get_document(doc_id)
        if not doc_state:
            # Try to load from persistence
            doc_state = await persist_manager.get_document_state(doc_id)
            if doc_state:
                doc_manager.documents[doc_id] = doc_state
            else:
                raise HTTPException(status_code=404, detail="Document not found")
        
        # Get current users
        cursor_tracker = get_cursor_tracker()
        doc_tracker = cursor_tracker.get_tracker(doc_id)
        current_users = len(doc_tracker.get_all_cursors())
        
        return DocumentInfo(
            doc_id=doc_id,
            title=doc_info.get('title', doc_id),
            owner_id=doc_info.get('owner_id', ''),
            is_public=doc_info.get('is_public', False),
            created_at=datetime.fromisoformat(doc_info.get('created_at', datetime.utcnow().isoformat())),
            updated_at=datetime.fromisoformat(doc_info.get('updated_at', datetime.utcnow().isoformat())),
            metadata=doc_info.get('metadata', {}),
            current_users=current_users,
            version=doc_state.version
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document {doc_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents/{doc_id}/content")
async def get_document_content(
    doc_id: str,
    doc_manager: DocumentManager = Depends(get_document_manager),
    persist_manager: PersistenceManager = Depends(get_persistence_manager)
):
    """Get document content and state"""
    try:
        # Get document state
        doc_state = doc_manager.get_document(doc_id)
        if not doc_state:
            # Try to load from persistence
            doc_state = await persist_manager.get_document_state(doc_id)
            if doc_state:
                doc_manager.documents[doc_id] = doc_state
            else:
                raise HTTPException(status_code=404, detail="Document not found")
        
        # Get user cursors
        cursor_tracker = get_cursor_tracker()
        doc_tracker = cursor_tracker.get_tracker(doc_id)
        cursors = doc_tracker.get_all_cursors()
        
        return {
            'doc_id': doc_id,
            'content': doc_state.content,
            'version': doc_state.version,
            'user_cursors': [cursor.to_dict() for cursor in cursors],
            'last_modified': doc_state.last_modified.isoformat(),
            'operation_count': len(doc_state.operations)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document content {doc_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents/{doc_id}/operations")
async def get_document_operations(
    doc_id: str,
    since_version: Optional[int] = None,
    persist_manager: PersistenceManager = Depends(get_persistence_manager)
):
    """Get operations for a document"""
    try:
        if since_version is not None:
            # Get operations since version
            operations = await persist_manager.get_operations_since(doc_id, since_version)
        else:
            # Get recent operations
            doc_state = await persist_manager.get_document_state(doc_id)
            if doc_state:
                operations = doc_state.operations[-100:]  # Last 100 operations
            else:
                operations = []
        
        return {
            'doc_id': doc_id,
            'operations': [op.to_dict() for op in operations],
            'count': len(operations)
        }
        
    except Exception as e:
        logger.error(f"Error getting operations for {doc_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check all components
        status = {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'components': {
                'document_manager': document_manager is not None,
                'conflict_manager': conflict_manager is not None,
                'persistence_manager': persistence_manager is not None,
                'connection_manager': connection_manager is not None
            }
        }
        
        # Check if all components are initialized
        if not all(status['components'].values()):
            status['status'] = 'degraded'
        
        return status
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            'status': 'unhealthy',
            'timestamp': datetime.utcnow().isoformat(),
            'error': str(e)
        }


@app.get("/stats")
async def get_system_stats():
    """Get system statistics"""
    try:
        stats = {
            'timestamp': datetime.utcnow().isoformat(),
            'documents': {
                'total': len(document_manager.documents) if document_manager else 0,
                'active': len(connection_manager.doc_connections) if connection_manager else 0
            },
            'connections': connection_manager.get_connection_stats() if connection_manager else {},
            'cursors': get_cursor_tracker().get_global_statistics(),
            'conflicts': conflict_manager.get_conflict_report() if conflict_manager else {}
        }
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting system stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# WebSocket endpoints
@app.websocket("/ws/{doc_id}")
async def websocket_endpoint(websocket: WebSocket, doc_id: str):
    """WebSocket endpoint for real-time collaboration"""
    try:
        # Extract user info from query parameters
        user_id = websocket.query_params.get("user_id")
        user_name = websocket.query_params.get("user_name", "")
        
        if not user_id:
            await websocket.close(code=4001, reason="User ID required")
            return
        
        # Handle WebSocket connection
        await handle_websocket_connection(websocket, doc_id, user_id)
        
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for document {doc_id}")
    except Exception as e:
        logger.error(f"WebSocket error for document {doc_id}: {e}")
        await websocket.close(code=4000, reason=str(e))


# Helper functions for WebSocket message handling
async def handle_operation_message(doc_id: str, operation_data: Dict[str, Any], user_id: str):
    """Handle operation message from WebSocket"""
    try:
        # Parse operation
        op_type = operation_data.get('type')
        position = operation_data.get('position', 0)
        char = operation_data.get('char', '')
        length = operation_data.get('length', 1)
        version = operation_data.get('version', 0)
        
        # Create operation
        if op_type == 'insert':
            operation = create_insert_operation(position, char, user_id)
        elif op_type == 'delete':
            operation = create_delete_operation(position, length, user_id)
        elif op_type == 'cursor':
            # Handle cursor operation separately
            await handle_cursor_message(doc_id, operation_data, user_id)
            return
        else:
            logger.warning(f"Unknown operation type: {op_type}")
            return
        
        operation.version = version
        
        # Get current document state
        doc_state = document_manager.get_document(doc_id)
        if not doc_state:
            logger.warning(f"Document {doc_id} not found")
            return
        
        # Process with conflict resolution
        resolved_op, conflict = conflict_manager.process_operation(doc_id, operation, doc_state)
        
        if resolved_op:
            # Apply operation
            success = document_manager.apply_operation(doc_id, resolved_op)
            
            if success:
                # Save to persistence
                await persistence_manager.save_operation(doc_id, resolved_op)
                
                # Broadcast to all clients
                if connection_manager:
                    message = {
                        'type': 'operation',
                        'data': resolved_op.to_dict()
                    }
                    await connection_manager.broadcast_to_document(doc_id, message)
                
                logger.info(f"Applied operation {resolved_op.type} to document {doc_id}")
            else:
                logger.error(f"Failed to apply operation to document {doc_id}")
        else:
            logger.info(f"Operation discarded due to conflict resolution")
        
        # Log conflict if occurred
        if conflict:
            logger.info(f"Conflict resolved: {conflict.type.value} using {conflict.resolution_strategy}")
        
    except Exception as e:
        logger.error(f"Error handling operation message: {e}")


async def handle_cursor_message(doc_id: str, cursor_data: Dict[str, Any], user_id: str):
    """Handle cursor position message"""
    try:
        line = cursor_data.get('line', 0)
        column = cursor_data.get('column', 0)
        selection_start = cursor_data.get('selection_start')
        selection_end = cursor_data.get('selection_end')
        user_name = cursor_data.get('user_name', '')
        
        # Update cursor tracker
        cursor_tracker = get_cursor_tracker()
        doc_tracker = cursor_tracker.get_tracker(doc_id)
        
        should_broadcast = doc_tracker.update_cursor(
            user_id, line, column, selection_start, selection_end, user_name
        )
        
        if should_broadcast:
            # Broadcast cursor position
            cursor_info = doc_tracker.get_user_cursor(user_id)
            if cursor_info:
                message = {
                    'type': 'cursor',
                    'data': cursor_info.to_dict()
                }
                
                if connection_manager:
                    await connection_manager.broadcast_to_document(doc_id, message)
        
    except Exception as e:
        logger.error(f"Error handling cursor message: {e}")


# Custom WebSocket message handler (to be used in websocket_hub)
async def custom_websocket_handler(websocket: WebSocket, doc_id: str, user_id: str):
    """Custom WebSocket handler that integrates with our components"""
    try:
        # Connect to connection manager
        connection_id = await connection_manager.connect(websocket, doc_id, user_id)
        
        # Add user to cursor tracker
        cursor_tracker = get_cursor_tracker()
        doc_tracker = cursor_tracker.get_tracker(doc_id)
        doc_tracker.update_cursor(user_id, 0, 0, user_name=user_id)
        
        logger.info(f"User {user_id} connected to document {doc_id}")
        
        try:
            while True:
                # Receive message
                data = await websocket.receive_text()
                message = json.loads(data)
                
                message_type = message.get('type')
                
                if message_type == 'operation':
                    await handle_operation_message(doc_id, message.get('data', {}), user_id)
                elif message_type == 'cursor':
                    await handle_cursor_message(doc_id, message.get('data', {}), user_id)
                elif message_type == 'ping':
                    await websocket.send_text(json.dumps({'type': 'pong'}))
                else:
                    logger.warning(f"Unknown message type: {message_type}")
                    
        except WebSocketDisconnect:
            pass
        finally:
            # Disconnect
            await connection_manager.disconnect(connection_id)
            doc_tracker.remove_user(user_id)
            logger.info(f"User {user_id} disconnected from document {doc_id}")
            
    except Exception as e:
        logger.error(f"Error in WebSocket handler: {e}")
        await websocket.close(code=4000, reason=str(e))


# Override the default handler
if __name__ == "__main__":
    # This would normally be in a separate module, but for demo purposes
    import websocket_hub
    websocket_hub.handle_websocket_connection = custom_websocket_handler
    
    # Run the application
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )


if __name__ == "__main__":
    print("CodeCollab Backend Server")
    print("========================")
    print("Starting server on http://localhost:8000")
    print("WebSocket endpoint: ws://localhost:8000/ws/{doc_id}?user_id={user_id}")
    print("API Documentation: http://localhost:8000/docs")
    print("\nPress Ctrl+C to stop the server")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
