"""
FastAPI backend for real-time collaborative code editor.

This module provides REST API endpoints and WebSocket connections
for the CodeCollab collaborative editing platform.
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import redis.asyncio as redis
import asyncpg
import structlog

from ..models.document import DocumentManager, DocumentState, Operation, CursorPosition
from ..websocket.hub import WebSocketHub
from ..storage.database import DatabaseManager

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Initialize FastAPI app
app = FastAPI(
    title="CodeCollab API",
    description="Real-time collaborative code editor backend",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables
redis_client: Optional[redis.Redis] = None
document_manager: Optional[DocumentManager] = None
websocket_hub: Optional[WebSocketHub] = None
database_manager: Optional[DatabaseManager] = None

# Pydantic models
class CreateDocumentRequest(BaseModel):
    """Request model for creating a document."""
    
    title: str = Field(..., min_length=1, max_length=200)
    initial_content: str = Field(default="", max_length=100000)
    language: str = Field(default="python", regex="^[a-z]+$")
    is_public: bool = Field(default=False)

class DocumentResponse(BaseModel):
    """Response model for document data."""
    
    document_id: str
    title: str
    content: str
    version: int
    language: str
    is_public: bool
    created_at: datetime
    updated_at: datetime
    active_users: List[str]
    stats: Dict[str, Any]

class OperationRequest(BaseModel):
    """Request model for applying an operation."""
    
    operation_type: str = Field(..., regex="^(insert|delete|retain|format)$")
    position: int = Field(..., ge=0)
    content: Optional[str] = None
    length: Optional[int] = Field(None, ge=0)
    attributes: Optional[Dict[str, Any]] = None

class CursorRequest(BaseModel):
    """Request model for updating cursor position."""
    
    line: int = Field(..., ge=0)
    column: int = Field(..., ge=0)
    selection_start: Optional[int] = None
    selection_end: Optional[int] = None

class UserInfo(BaseModel):
    """User information model."""
    
    user_id: str
    user_name: str = Field(default="", max_length=50)
    user_color: str = Field(default="#007bff", regex="^#[0-9a-fA-F]{6}$")

class ConnectionRequest(BaseModel):
    """Request model for WebSocket connection."""
    
    document_id: str
    user_info: UserInfo

# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize application components."""
    global redis_client, document_manager, websocket_hub, database_manager
    
    try:
        # Initialize Redis client
        redis_client = redis.Redis(
            host="localhost",
            port=6379,
            db=0,
            decode_responses=True
        )
        
        # Test Redis connection
        await redis_client.ping()
        
        # Initialize database manager
        database_manager = DatabaseManager()
        await database_manager.initialize()
        
        # Initialize document manager
        document_manager = DocumentManager(redis_client, database_manager.pool)
        
        # Initialize WebSocket hub
        websocket_hub = WebSocketHub(redis_client, document_manager)
        
        # Start background tasks
        asyncio.create_task(cleanup_task())
        asyncio.create_task(snapshot_task())
        
        logger.info("CodeCollab API started successfully")
        
    except Exception as e:
        logger.error("Failed to start application", error=str(e))
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup application components."""
    global websocket_hub, database_manager, redis_client
    
    try:
        if websocket_hub:
            await websocket_hub.shutdown()
        
        if database_manager:
            await database_manager.close()
        
        if redis_client:
            await redis_client.close()
        
        logger.info("CodeCollab API shutdown complete")
        
    except Exception as e:
        logger.error("Error during shutdown", error=str(e))

# REST API endpoints
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "CodeCollab API",
        "version": "1.0.0",
        "status": "active",
        "docs": "/docs",
        "websocket": "/ws/{document_id}"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Check Redis connection
        await redis_client.ping()
        
        # Check database connection
        async with database_manager.pool.acquire() as conn:
            await conn.execute("SELECT 1")
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                "redis": "healthy",
                "database": "healthy"
            }
        }
        
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }
        )

@app.post("/documents", response_model=DocumentResponse)
async def create_document(request: CreateDocumentRequest):
    """
    Create a new document.
    
    Args:
        request: Document creation request
        
    Returns:
        Created document information
    """
    try:
        # Generate document ID
        document_id = str(uuid.uuid4())
        
        # Create document
        document = await document_manager.create_document(
            document_id=document_id,
            initial_content=request.initial_content
        )
        
        # Store document metadata
        await database_manager.create_document_metadata(
            document_id=document_id,
            title=request.title,
            language=request.language,
            is_public=request.is_public
        )
        
        # Get document stats
        stats = await document_manager.get_document_stats(document_id)
        
        return DocumentResponse(
            document_id=document.document_id,
            title=request.title,
            content=document.content,
            version=document.version,
            language=request.language,
            is_public=request.is_public,
            created_at=document.created_at,
            updated_at=document.updated_at,
            active_users=document.active_users,
            stats=stats
        )
        
    except Exception as e:
        logger.error("Error creating document", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: str):
    """
    Get document information.
    
    Args:
        document_id: Document identifier
        
    Returns:
        Document information
    """
    try:
        # Get document
        document = await document_manager.get_document(document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Get document metadata
        metadata = await database_manager.get_document_metadata(document_id)
        
        # Get document stats
        stats = await document_manager.get_document_stats(document_id)
        
        return DocumentResponse(
            document_id=document.document_id,
            title=metadata.get('title', ''),
            content=document.content,
            version=document.version,
            language=metadata.get('language', 'python'),
            is_public=metadata.get('is_public', False),
            created_at=document.created_at,
            updated_at=document.updated_at,
            active_users=document.active_users,
            stats=stats
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting document", document_id=document_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/documents/{document_id}/operations")
async def apply_operation(document_id: str, request: OperationRequest, user_info: UserInfo):
    """
    Apply an operation to a document.
    
    Args:
        document_id: Document identifier
        request: Operation request
        user_info: User information
        
    Returns:
        Operation result
    """
    try:
        # Create operation
        operation = Operation(
            id=str(uuid.uuid4()),
            type=request.operation_type,
            position=request.position,
            content=request.content,
            length=request.length,
            attributes=request.attributes,
            user_id=user_info.user_id,
            session_id="",  # Will be set by WebSocket hub
        )
        
        # Apply operation
        success = await document_manager.apply_operation(document_id, operation)
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to apply operation")
        
        return {
            "success": True,
            "operation_id": operation.id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error applying operation", document_id=document_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/documents/{document_id}/operations")
async def get_operations(document_id: str, since_version: Optional[int] = None):
    """
    Get operations applied to a document.
    
    Args:
        document_id: Document identifier
        since_version: Get operations since this version
        
    Returns:
        List of operations
    """
    try:
        operations = await document_manager.get_operations_since(document_id, since_version or 0)
        
        return {
            "operations": [op.to_dict() for op in operations],
            "count": len(operations)
        }
        
    except Exception as e:
        logger.error("Error getting operations", document_id=document_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/documents/{document_id}/cursors")
async def get_cursors(document_id: str):
    """
    Get cursor positions for a document.
    
    Args:
        document_id: Document identifier
        
    Returns:
        List of cursor positions
    """
    try:
        cursors = await document_manager.get_cursor_positions(document_id)
        
        return {
            "cursors": [cursor.to_dict() for cursor in cursors],
            "count": len(cursors)
        }
        
    except Exception as e:
        logger.error("Error getting cursors", document_id=document_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/documents/{document_id}/stats")
async def get_document_stats(document_id: str):
    """
    Get document statistics.
    
    Args:
        document_id: Document identifier
        
    Returns:
        Document statistics
    """
    try:
        stats = await document_manager.get_document_stats(document_id)
        return stats
        
    except Exception as e:
        logger.error("Error getting document stats", document_id=document_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stats")
async def get_system_stats():
    """
    Get system statistics.
    
    Returns:
        System statistics
    """
    try:
        # Get connection stats from WebSocket hub
        connection_stats = await websocket_hub.get_connection_stats()
        
        # Get database stats
        db_stats = await database_manager.get_system_stats()
        
        # Get Redis stats
        redis_info = await redis_client.info()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "connections": connection_stats,
            "database": db_stats,
            "redis": {
                "used_memory": redis_info.get('used_memory'),
                "connected_clients": redis_info.get('connected_clients'),
                "total_commands_processed": redis_info.get('total_commands_processed')
            }
        }
        
    except Exception as e:
        logger.error("Error getting system stats", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

# WebSocket endpoints
@app.websocket("/ws/{document_id}")
async def websocket_endpoint(websocket: WebSocket, document_id: str):
    """
    WebSocket endpoint for real-time collaboration.
    
    Args:
        websocket: WebSocket connection
        document_id: Document identifier
    """
    try:
        # Accept WebSocket connection
        await websocket.accept()
        
        # Wait for initial message with user info
        initial_message = await websocket.receive_text()
        message_data = json.loads(initial_message)
        
        if message_data.get("type") != "connect":
            await websocket.close(code=4000, reason="Expected connect message")
            return
        
        connection_request = ConnectionRequest(**message_data.get("data", {}))
        
        # Connect user to document
        result = await websocket_hub.connect_user(
            websocket=websocket,
            user_id=connection_request.user_info.user_id,
            session_id=str(uuid.uuid4()),
            document_id=document_id,
            user_name=connection_request.user_info.user_name,
            user_color=connection_request.user_info.user_color
        )
        
        if not result.get("success"):
            await websocket.close(code=4004, reason=result.get("error", "Connection failed"))
            return
        
        # Send initial state
        await websocket.send_text(json.dumps({
            "type": "connected",
            "data": {
                "document": result["document"],
                "active_users": result["active_users"]
            }
        }))
        
        # Handle WebSocket messages
        while True:
            try:
                # Receive message
                message = await websocket.receive_text()
                message_data = json.loads(message)
                
                # Handle message
                result = await websocket_hub.handle_message(
                    session_id=connection_request.user_info.user_id,  # Temporary session ID
                    message=message_data
                )
                
                # Send response
                await websocket.send_text(json.dumps({
                    "type": "response",
                    "data": result
                }))
                
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error("Error handling WebSocket message", error=str(e))
                break
        
        # Disconnect user
        await websocket_hub.disconnect_user(connection_request.user_info.user_id)
        
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected", document_id=document_id)
    except Exception as e:
        logger.error("WebSocket error", document_id=document_id, error=str(e))
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except:
            pass

# Background tasks
async def cleanup_task():
    """Background task for cleanup operations."""
    while True:
        try:
            # Clean up inactive connections
            await websocket_hub.cleanup_inactive_connections(timeout_minutes=30)
            
            # Clean up old operations in transformer
            # (This would be implemented in the transformer)
            
            # Sleep for 5 minutes
            await asyncio.sleep(300)
            
        except Exception as e:
            logger.error("Error in cleanup task", error=str(e))
            await asyncio.sleep(60)

async def snapshot_task():
    """Background task for document snapshots."""
    while True:
        try:
            # Get all active documents
            connection_stats = await websocket_hub.get_connection_stats()
            active_documents = connection_stats.get("documents", {})
            
            # Create snapshots for active documents
            for document_id in active_documents:
                await document_manager.create_snapshot(document_id)
            
            # Sleep for 30 seconds
            await asyncio.sleep(30)
            
        except Exception as e:
            logger.error("Error in snapshot task", error=str(e))
            await asyncio.sleep(60)

# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    """Handle 404 errors."""
    return JSONResponse(
        status_code=404,
        content={"error": "Not found", "message": str(exc)}
    )

@app.exception_handler(500)
async def internal_error_handler(request, exc):
    """Handle 500 errors."""
    logger.error("Internal server error", error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "message": "An unexpected error occurred"}
    )

# Utility functions
def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    return app

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
