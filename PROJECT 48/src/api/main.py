"""
FastAPI backend for voice-activated safety alert system.

This module provides the API endpoints, WebSocket connections, and SOS alert
functionality for the voice-activated safety system.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import asyncio
import json
import logging
import base64
import io
import wave
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import uuid
from collections import deque
import structlog

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
    title="Voice-Activated Safety Alert System",
    description="Real-time voice-activated SOS alert system for Vaultryn",
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

# Global state
class ConnectionState:
    """Manage WebSocket connections and system state."""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_sessions: Dict[str, Dict[str, Any]] = {}
        self.alert_history: deque = deque(maxlen=1000)
        self.detection_stats = {
            'total_detections': 0,
            'false_positives': 0,
            'confirmed_alerts': 0,
            'last_detection': None
        }
    
    def add_connection(self, user_id: str, websocket: WebSocket):
        """Add WebSocket connection."""
        self.active_connections[user_id] = websocket
        self.user_sessions[user_id] = {
            'connected_at': datetime.utcnow(),
            'last_activity': datetime.utcnow(),
            'location': None,
            'device_info': None
        }
        logger.info("WebSocket connection added", user_id=user_id)
    
    def remove_connection(self, user_id: str):
        """Remove WebSocket connection."""
        if user_id in self.active_connections:
            del self.active_connections[user_id]
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]
        logger.info("WebSocket connection removed", user_id=user_id)
    
    def update_user_location(self, user_id: str, location: Dict[str, float]):
        """Update user location."""
        if user_id in self.user_sessions:
            self.user_sessions[user_id]['location'] = location
            self.user_sessions[user_id]['last_activity'] = datetime.utcnow()
    
    def add_alert(self, alert: Dict[str, Any]):
        """Add alert to history."""
        alert['timestamp'] = datetime.utcnow().isoformat()
        alert['id'] = str(uuid.uuid4())
        self.alert_history.append(alert)
        self.detection_stats['total_detections'] += 1
        self.detection_stats['last_detection'] = alert['timestamp']
        logger.info("Alert added", alert_id=alert['id'], user_id=alert.get('user_id'))

# Global connection manager
connection_manager = ConnectionState()

# Pydantic models
class Location(BaseModel):
    """Location information."""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    accuracy: Optional[float] = Field(None, ge=0)
    altitude: Optional[float] = None
    heading: Optional[float] = Field(None, ge=0, lt=360)

class DeviceInfo(BaseModel):
    """Device information."""
    device_id: str
    platform: str  # ios, android, web
    app_version: str
    os_version: Optional[str] = None
    model: Optional[str] = None

class AudioData(BaseModel):
    """Audio data for processing."""
    audio_data: str  # Base64 encoded audio
    sample_rate: int = 16000
    format: str = "wav"
    duration: float = Field(..., gt=0, le=10.0)  # Max 10 seconds

class DetectionResult(BaseModel):
    """Keyword detection result."""
    detected: bool
    confidence: float = Field(..., ge=0, le=1)
    timestamp: datetime
    audio_snippet: Optional[str] = None  # Base64 encoded
    location: Optional[Location] = None

class SOSAlert(BaseModel):
    """SOS alert data."""
    user_id: str
    location: Location
    detection_confidence: float
    audio_context: str  # Base64 encoded 5-second context
    device_info: DeviceInfo
    timestamp: datetime
    emergency_type: str = "general"
    additional_info: Optional[Dict[str, Any]] = None

class AlertConfirmation(BaseModel):
    """Alert confirmation data."""
    alert_id: str
    confirmed: bool
    user_id: str
    timestamp: datetime
    notes: Optional[str] = None

class SystemStatus(BaseModel):
    """System status information."""
    active_connections: int
    total_detections: int
    false_positives: int
    confirmed_alerts: int
    uptime: str
    last_detection: Optional[str] = None

# API Endpoints
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Voice-Activated Safety Alert System",
        "version": "1.0.0",
        "status": "active",
        "endpoints": {
            "docs": "/docs",
            "websocket": "/ws/{user_id}",
            "detect": "/api/detect",
            "sos": "/api/alerts/sos",
            "confirm": "/api/alerts/{alert_id}/confirm",
            "status": "/api/status"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "active_connections": len(connection_manager.active_connections),
        "uptime": "active"
    }

@app.get("/api/status", response_model=SystemStatus)
async def get_system_status():
    """Get system status."""
    return SystemStatus(
        active_connections=len(connection_manager.active_connections),
        total_detections=connection_manager.detection_stats['total_detections'],
        false_positives=connection_manager.detection_stats['false_positives'],
        confirmed_alerts=connection_manager.detection_stats['confirmed_alerts'],
        uptime="active",  # Would calculate actual uptime
        last_detection=connection_manager.detection_stats['last_detection']
    )

@app.post("/api/detect")
async def process_audio_detection(result: DetectionResult):
    """
    Process keyword detection result from on-device processing.
    
    This endpoint receives detection results from the mobile app
    after on-device processing to maintain privacy.
    """
    try:
        # Log detection
        logger.info(
            "Detection received",
            detected=result.detected,
            confidence=result.confidence,
            timestamp=result.timestamp.isoformat()
        )
        
        # Update statistics
        if result.detected:
            connection_manager.detection_stats['total_detections'] += 1
            connection_manager.detection_stats['last_detection'] = result.timestamp.isoformat()
        
        # If keyword detected, prepare for potential SOS
        if result.detected and result.confidence >= 0.8:
            # Broadcast detection to all connected clients
            await broadcast_detection(result)
            
            # Return confirmation
            return {
                "success": True,
                "detected": True,
                "confidence": result.confidence,
                "message": "High confidence detection received",
                "next_step": "Awaiting SOS confirmation"
            }
        else:
            return {
                "success": True,
                "detected": False,
                "confidence": result.confidence,
                "message": "No significant detection"
            }
    
    except Exception as e:
        logger.error("Error processing detection", error=str(e))
        raise HTTPException(status_code=500, detail="Error processing detection")

@app.post("/api/alerts/sos")
async def create_sos_alert(alert: SOSAlert, background_tasks: BackgroundTasks):
    """
    Create SOS alert with location and audio context.
    
    This endpoint is called only after explicit user confirmation
    to maintain privacy.
    """
    try:
        # Add alert to history
        alert_data = alert.dict()
        connection_manager.add_alert(alert_data)
        
        # Log alert
        logger.info(
            "SOS alert created",
            alert_id=alert_data['id'],
            user_id=alert.user_id,
            confidence=alert.detection_confidence,
            location=f"{alert.location.latitude},{alert.location.longitude}"
        )
        
        # Process alert in background
        background_tasks.add_task(process_sos_alert, alert_data)
        
        # Broadcast to all connected clients
        await broadcast_alert(alert_data)
        
        return {
            "success": True,
            "alert_id": alert_data['id'],
            "message": "SOS alert created successfully",
            "timestamp": alert_data['timestamp']
        }
    
    except Exception as e:
        logger.error("Error creating SOS alert", error=str(e))
        raise HTTPException(status_code=500, detail="Error creating SOS alert")

@app.post("/api/alerts/{alert_id}/confirm")
async def confirm_alert(alert_id: str, confirmation: AlertConfirmation):
    """Confirm or cancel an alert."""
    try:
        # Find alert in history
        alert_found = None
        for alert in connection_manager.alert_history:
            if alert.get('id') == alert_id:
                alert_found = alert
                break
        
        if not alert_found:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        # Update alert status
        alert_found['confirmed'] = confirmation.confirmed
        alert_found['confirmation_timestamp'] = confirmation.timestamp.isoformat()
        alert_found['notes'] = confirmation.notes
        
        # Update statistics
        if confirmation.confirmed:
            connection_manager.detection_stats['confirmed_alerts'] += 1
        else:
            connection_manager.detection_stats['false_positives'] += 1
        
        # Log confirmation
        logger.info(
            "Alert confirmation received",
            alert_id=alert_id,
            confirmed=confirmation.confirmed,
            user_id=confirmation.user_id
        )
        
        # Broadcast confirmation
        await broadcast_confirmation(alert_id, confirmation.confirmed)
        
        return {
            "success": True,
            "alert_id": alert_id,
            "confirmed": confirmation.confirmed,
            "message": "Alert confirmation processed"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error confirming alert", error=str(e))
        raise HTTPException(status_code=500, detail="Error confirming alert")

@app.get("/api/alerts")
async def get_alerts(limit: int = 50, offset: int = 0):
    """Get alert history."""
    try:
        alerts = list(connection_manager.alert_history)
        alerts.reverse()  # Most recent first
        
        paginated_alerts = alerts[offset:offset + limit]
        
        return {
            "success": True,
            "alerts": paginated_alerts,
            "total": len(alerts),
            "limit": limit,
            "offset": offset
        }
    
    except Exception as e:
        logger.error("Error getting alerts", error=str(e))
        raise HTTPException(status_code=500, detail="Error getting alerts")

# WebSocket endpoints
@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """WebSocket endpoint for real-time communication."""
    await websocket.accept()
    
    # Add connection
    connection_manager.add_connection(user_id, websocket)
    
    try:
        while True:
            # Receive message
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Handle different message types
            message_type = message.get('type')
            
            if message_type == 'ping':
                await websocket.send_text(json.dumps({"type": "pong"}))
            
            elif message_type == 'location':
                location_data = message.get('location', {})
                location = Location(**location_data)
                connection_manager.update_user_location(user_id, location.dict())
                
                await websocket.send_text(json.dumps({
                    "type": "location_updated",
                    "timestamp": datetime.utcnow().isoformat()
                }))
            
            elif message_type == 'device_info':
                device_info = DeviceInfo(**message.get('device_info', {}))
                if user_id in connection_manager.user_sessions:
                    connection_manager.user_sessions[user_id]['device_info'] = device_info.dict()
                
                await websocket.send_text(json.dumps({
                    "type": "device_info_updated",
                    "timestamp": datetime.utcnow().isoformat()
                }))
            
            else:
                logger.warning("Unknown message type", type=message_type, user_id=user_id)
    
    except WebSocketDisconnect:
        connection_manager.remove_connection(user_id)
        logger.info("WebSocket disconnected", user_id=user_id)
    
    except Exception as e:
        logger.error("WebSocket error", error=str(e), user_id=user_id)
        connection_manager.remove_connection(user_id)

# Background tasks
async def process_sos_alert(alert: Dict[str, Any]):
    """Process SOS alert in background."""
    try:
        logger.info("Processing SOS alert", alert_id=alert['id'])
        
        # Here you would:
        # 1. Contact emergency services
        # 2. Notify emergency contacts
        # 3. Send push notifications
        # 4. Log to external systems
        # 5. Update databases
        
        # Simulate processing time
        await asyncio.sleep(1)
        
        logger.info("SOS alert processed", alert_id=alert['id'])
    
    except Exception as e:
        logger.error("Error processing SOS alert", error=str(e), alert_id=alert['id'])

# Broadcasting functions
async def broadcast_detection(detection: DetectionResult):
    """Broadcast detection to all connected clients."""
    message = {
        "type": "detection",
        "data": detection.dict(),
        "timestamp": datetime.utcnow().isoformat()
    }
    
    disconnected = []
    for user_id, websocket in connection_manager.active_connections.items():
        try:
            await websocket.send_text(json.dumps(message))
        except:
            disconnected.append(user_id)
    
    # Remove disconnected clients
    for user_id in disconnected:
        connection_manager.remove_connection(user_id)

async def broadcast_alert(alert: Dict[str, Any]):
    """Broadcast alert to all connected clients."""
    message = {
        "type": "alert",
        "data": alert,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    disconnected = []
    for user_id, websocket in connection_manager.active_connections.items():
        try:
            await websocket.send_text(json.dumps(message))
        except:
            disconnected.append(user_id)
    
    # Remove disconnected clients
    for user_id in disconnected:
        connection_manager.remove_connection(user_id)

async def broadcast_confirmation(alert_id: str, confirmed: bool):
    """Broadcast alert confirmation to all connected clients."""
    message = {
        "type": "confirmation",
        "data": {
            "alert_id": alert_id,
            "confirmed": confirmed
        },
        "timestamp": datetime.utcnow().isoformat()
    }
    
    disconnected = []
    for user_id, websocket in connection_manager.active_connections.items():
        try:
            await websocket.send_text(json.dumps(message))
        except:
            disconnected.append(user_id)
    
    # Remove disconnected clients
    for user_id in disconnected:
        connection_manager.remove_connection(user_id)

# Utility functions
def decode_audio_from_base64(audio_data: str, sample_rate: int = 16000) -> np.ndarray:
    """Decode base64 encoded audio data."""
    try:
        # Decode base64
        audio_bytes = base64.b64decode(audio_data)
        
        # Read WAV file from bytes
        with io.BytesIO(audio_bytes) as wav_buffer:
            with wave.open(wav_buffer, 'rb') as wav_file:
                frames = wav_file.readframes(-1)
                audio_data = np.frombuffer(frames, dtype=np.int16)
                
                # Convert to float
                audio_data = audio_data.astype(np.float32) / 32768.0
                
                return audio_data
    
    except Exception as e:
        logger.error("Error decoding audio", error=str(e))
        raise

def encode_audio_to_base64(audio_data: np.ndarray, sample_rate: int = 16000) -> str:
    """Encode audio data to base64."""
    try:
        # Convert to int16
        audio_int16 = (audio_data * 32767).astype(np.int16)
        
        # Create WAV file in memory
        with io.BytesIO() as wav_buffer:
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(audio_int16.tobytes())
            
            # Encode to base64
            wav_bytes = wav_buffer.getvalue()
            return base64.b64encode(wav_bytes).decode('utf-8')
    
    except Exception as e:
        logger.error("Error encoding audio", error=str(e))
        raise

# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    """Handle 404 errors."""
    return JSONResponse(
        status_code=404,
        content={"error": "Endpoint not found", "message": str(exc)}
    )

@app.exception_handler(500)
async def internal_error_handler(request, exc):
    """Handle 500 errors."""
    logger.error("Internal server error", error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "message": "An unexpected error occurred"}
    )

# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    logger.info("Voice-Activated Safety Alert System starting up")
    
    # Create necessary directories
    Path("logs").mkdir(exist_ok=True)
    Path("data/audio").mkdir(exist_ok=True)
    
    logger.info("Application startup completed")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Voice-Activated Safety Alert System shutting down")
    
    # Close all WebSocket connections
    for user_id in list(connection_manager.active_connections.keys()):
        connection_manager.remove_connection(user_id)
    
    logger.info("Application shutdown completed")

# Development server
if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
