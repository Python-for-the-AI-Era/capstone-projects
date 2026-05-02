"""
SOS API Integration with WebSocket Support
Handles real-time communication between safety system and Vaultryn backend
"""

import asyncio
import websockets
import json
import logging
import httpx
import uuid
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import aiofiles
import base64

from safety_system import SOSAlert

logger = logging.getLogger(__name__)


@dataclass
class APIConfig:
    """Configuration for SOS API"""
    base_url: str = "https://api.vaultryn.com"
    api_key: str = ""
    websocket_url: str = "wss://api.vaultryn.com/ws/sos"
    timeout_seconds: int = 30
    retry_attempts: int = 3
    retry_delay_seconds: float = 1.0
    
    # Endpoints
    sos_endpoint: str = "/v1/alerts/sos"
    status_endpoint: str = "/v1/alerts/status"
    upload_endpoint: str = "/v1/audio/upload"
    
    # WebSocket settings
    websocket_ping_interval: int = 20
    websocket_ping_timeout: int = 10
    max_message_size: int = 10 * 1024 * 1024  # 10MB


@dataclass
class SOSResponse:
    """Response from SOS API"""
    success: bool
    alert_id: str
    message: str
    timestamp: float
    response_code: int
    metadata: Optional[Dict[str, Any]] = None


class SOSAPIManager:
    """
    Manages SOS API communication with WebSocket support
    Handles both REST API calls and real-time WebSocket connections
    """
    
    def __init__(self, config: APIConfig):
        self.config = config
        self.client = httpx.AsyncClient(timeout=config.timeout_seconds)
        self.websocket = None
        self.is_connected = False
        self.connection_callbacks = []
        
        # Statistics
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.connection_attempts = 0
        self.connection_time = 0.0
        
        logger.info("SOSAPIManager initialized")
    
    async def send_sos_alert(self, sos_alert: SOSAlert, audio_context: Optional[bytes] = None) -> SOSResponse:
        """
        Send SOS alert to Vaultryn API
        
        Args:
            sos_alert: SOS alert data
            audio_context: Optional audio context bytes
            
        Returns:
            API response
        """
        try:
            self.total_requests += 1
            
            # Prepare request data
            alert_data = sos_alert.to_dict()
            
            # Add audio context if provided
            files = {}
            data = {}
            
            if audio_context:
                # Convert audio to base64 for JSON transmission
                audio_b64 = base64.b64encode(audio_context).decode('utf-8')
                alert_data['audio_context_base64'] = audio_b64
                alert_data['audio_size'] = len(audio_context)
                alert_data['audio_format'] = 'wav'
            
            # Add API key
            headers = {
                'Authorization': f'Bearer {self.config.api_key}',
                'Content-Type': 'application/json',
                'X-Client-Version': '1.0.0',
                'X-Request-ID': str(uuid.uuid4())
            }
            
            # Make API request
            url = f"{self.config.base_url}{self.config.sos_endpoint}"
            
            logger.info(f"Sending SOS alert to {url}")
            
            response = await self._make_request_with_retry(
                'POST', 
                url, 
                json=alert_data, 
                headers=headers
            )
            
            if response.status_code == 200:
                self.successful_requests += 1
                response_data = response.json()
                
                sos_response = SOSResponse(
                    success=True,
                    alert_id=response_data.get('alert_id', sos_alert.alert_id),
                    message=response_data.get('message', 'SOS alert received'),
                    timestamp=response_data.get('timestamp', datetime.now().timestamp()),
                    response_code=response.status_code,
                    metadata=response_data.get('metadata')
                )
                
                logger.info(f"SOS alert sent successfully: {sos_response.alert_id}")
                return sos_response
            else:
                self.failed_requests += 1
                error_msg = f"API request failed: {response.status_code}"
                logger.error(f"{error_msg} - {response.text}")
                
                return SOSResponse(
                    success=False,
                    alert_id=sos_alert.alert_id,
                    message=error_msg,
                    timestamp=datetime.now().timestamp(),
                    response_code=response.status_code
                )
                
        except Exception as e:
            self.failed_requests += 1
            logger.error(f"Error sending SOS alert: {e}")
            
            return SOSResponse(
                success=False,
                alert_id=sos_alert.alert_id,
                message=f"Network error: {str(e)}",
                timestamp=datetime.now().timestamp(),
                response_code=0
            )
    
    async def upload_audio_file(self, audio_data: bytes, filename: str, 
                             alert_id: str) -> Dict[str, Any]:
        """
        Upload audio file separately if needed
        
        Args:
            audio_data: Raw audio bytes
            filename: Filename for upload
            alert_id: Associated alert ID
            
        Returns:
            Upload response
        """
        try:
            # Prepare multipart form data
            files = {
                'audio': (filename, audio_data, 'audio/wav')
            }
            
            data = {
                'alert_id': alert_id,
                'timestamp': datetime.now().isoformat()
            }
            
            headers = {
                'Authorization': f'Bearer {self.config.api_key}',
                'X-Request-ID': str(uuid.uuid4())
            }
            
            url = f"{self.config.base_url}{self.config.upload_endpoint}"
            
            logger.info(f"Uploading audio file: {filename} ({len(audio_data)} bytes)")
            
            response = await self._make_request_with_retry(
                'POST',
                url,
                files=files,
                data=data,
                headers=headers
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Audio upload successful: {result.get('upload_id')}")
                return result
            else:
                logger.error(f"Audio upload failed: {response.status_code}")
                return {'success': False, 'error': response.text}
                
        except Exception as e:
            logger.error(f"Error uploading audio file: {e}")
            return {'success': False, 'error': str(e)}
    
    async def get_alert_status(self, alert_id: str) -> Dict[str, Any]:
        """
        Get status of SOS alert
        
        Args:
            alert_id: Alert ID to check
            
        Returns:
            Alert status information
        """
        try:
            headers = {
                'Authorization': f'Bearer {self.config.api_key}',
                'X-Request-ID': str(uuid.uuid4())
            }
            
            url = f"{self.config.base_url}{self.config.status_endpoint}/{alert_id}"
            
            response = await self._make_request_with_retry('GET', url, headers=headers)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get alert status: {response.status_code}")
                return {'success': False, 'error': response.text}
                
        except Exception as e:
            logger.error(f"Error getting alert status: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _make_request_with_retry(self, method: str, url: str, **kwargs) -> httpx.Response:
        """
        Make HTTP request with retry logic
        
        Args:
            method: HTTP method
            url: Request URL
            **kwargs: Additional request parameters
            
        Returns:
            HTTP response
        """
        last_exception = None
        
        for attempt in range(self.config.retry_attempts):
            try:
                response = await self.client.request(method, url, **kwargs)
                return response
                
            except httpx.RequestError as e:
                last_exception = e
                logger.warning(f"Request attempt {attempt + 1} failed: {e}")
                
                if attempt < self.config.retry_attempts - 1:
                    await asyncio.sleep(self.config.retry_delay_seconds * (2 ** attempt))
                else:
                    raise
        
        # All attempts failed
        raise last_exception or Exception("All retry attempts failed")
    
    async def connect_websocket(self) -> bool:
        """
        Connect to WebSocket for real-time communication
        
        Returns:
            True if connection successful
        """
        try:
            self.connection_attempts += 1
            
            # Prepare WebSocket headers
            headers = {
                'Authorization': f'Bearer {self.config.api_key}',
                'X-Client-Version': '1.0.0'
            }
            
            logger.info(f"Connecting to WebSocket: {self.config.websocket_url}")
            
            # Connect with timeout
            self.websocket = await asyncio.wait_for(
                websockets.connect(
                    self.config.websocket_url,
                    extra_headers=headers,
                    ping_interval=self.config.websocket_ping_interval,
                    ping_timeout=self.config.websocket_ping_timeout,
                    max_size=self.config.max_message_size
                ),
                timeout=self.config.timeout_seconds
            )
            
            self.is_connected = True
            self.connection_time = datetime.now().timestamp()
            
            # Start message handler
            asyncio.create_task(self._websocket_message_handler())
            
            # Notify callbacks
            await self._notify_connection_callbacks(True)
            
            logger.info("WebSocket connection established")
            return True
            
        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            self.is_connected = False
            await self._notify_connection_callbacks(False)
            return False
    
    async def disconnect_websocket(self):
        """Disconnect from WebSocket"""
        try:
            if self.websocket:
                await self.websocket.close()
                self.websocket = None
            
            self.is_connected = False
            await self._notify_connection_callbacks(False)
            
            logger.info("WebSocket disconnected")
            
        except Exception as e:
            logger.error(f"Error disconnecting WebSocket: {e}")
    
    async def send_websocket_message(self, message: Dict[str, Any]) -> bool:
        """
        Send message through WebSocket
        
        Args:
            message: Message to send
            
        Returns:
            True if message sent successfully
        """
        try:
            if not self.is_connected or not self.websocket:
                logger.warning("WebSocket not connected")
                return False
            
            # Add timestamp and message ID
            message['timestamp'] = datetime.now().isoformat()
            message['message_id'] = str(uuid.uuid4())
            
            # Send message
            await self.websocket.send(json.dumps(message))
            
            logger.debug(f"WebSocket message sent: {message.get('type', 'unknown')}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending WebSocket message: {e}")
            return False
    
    async def _websocket_message_handler(self):
        """Handle incoming WebSocket messages"""
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    await self._handle_websocket_message(data)
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid WebSocket message format: {e}")
                except Exception as e:
                    logger.error(f"Error handling WebSocket message: {e}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.warning("WebSocket connection closed")
            self.is_connected = False
            await self._notify_connection_callbacks(False)
        except Exception as e:
            logger.error(f"WebSocket message handler error: {e}")
            self.is_connected = False
    
    async def _handle_websocket_message(self, data: Dict[str, Any]):
        """
        Handle incoming WebSocket message
        
        Args:
            data: Message data
        """
        message_type = data.get('type', 'unknown')
        
        if message_type == 'ping':
            # Respond to ping
            await self.send_websocket_message({'type': 'pong'})
            
        elif message_type == 'alert_update':
            # Handle alert status update
            alert_id = data.get('alert_id')
            status = data.get('status')
            logger.info(f"Alert update: {alert_id} -> {status}")
            
        elif message_type == 'emergency_response':
            # Handle emergency response
            logger.info(f"Emergency response received: {data}")
            
        else:
            logger.debug(f"Unknown WebSocket message type: {message_type}")
    
    def add_connection_callback(self, callback: Callable[[bool], None]):
        """
        Add callback for connection state changes
        
        Args:
            callback: Callback function that receives connection status
        """
        self.connection_callbacks.append(callback)
    
    async def _notify_connection_callbacks(self, connected: bool):
        """Notify all connection callbacks"""
        for callback in self.connection_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(connected)
                else:
                    # Run sync callback in thread pool
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, callback, connected)
            except Exception as e:
                logger.error(f"Error in connection callback: {e}")
    
    def get_api_stats(self) -> Dict[str, Any]:
        """Get API statistics"""
        return {
            'total_requests': self.total_requests,
            'successful_requests': self.successful_requests,
            'failed_requests': self.failed_requests,
            'success_rate': self.successful_requests / max(self.total_requests, 1),
            'websocket_connected': self.is_connected,
            'connection_attempts': self.connection_attempts,
            'connection_time': self.connection_time
        }
    
    async def cleanup(self):
        """Clean up resources"""
        try:
            await self.disconnect_websocket()
            await self.client.aclose()
            logger.info("SOSAPIManager cleaned up")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


class SOSWebSocketManager:
    """
    High-level WebSocket manager for SOS system
    Integrates with safety system for real-time communication
    """
    
    def __init__(self, api_manager: SOSAPIManager):
        self.api_manager = api_manager
        self.alert_status_callbacks = []
        self.emergency_callbacks = []
        
        # Register connection callback
        self.api_manager.add_connection_callback(self._on_connection_change)
        
        logger.info("SOSWebSocketManager initialized")
    
    def add_alert_status_callback(self, callback: Callable[[str, str], None]):
        """Add callback for alert status updates"""
        self.alert_status_callbacks.append(callback)
    
    def add_emergency_callback(self, callback: Callable[[Dict], None]):
        """Add callback for emergency responses"""
        self.emergency_callbacks.append(callback)
    
    async def _on_connection_change(self, connected: bool):
        """Handle WebSocket connection changes"""
        if connected:
            logger.info("WebSocket connected - ready for real-time updates")
        else:
            logger.warning("WebSocket disconnected - real-time updates unavailable")
    
    async def send_heartbeat(self):
        """Send heartbeat to maintain connection"""
        if self.api_manager.is_connected:
            await self.api_manager.send_websocket_message({
                'type': 'heartbeat',
                'timestamp': datetime.now().isoformat()
            })
    
    async def subscribe_alert_updates(self, alert_id: str):
        """Subscribe to updates for specific alert"""
        await self.api_manager.send_websocket_message({
            'type': 'subscribe_alert',
            'alert_id': alert_id
        })
    
    async def send_device_status(self, status: Dict[str, Any]):
        """Send device status update"""
        await self.api_manager.send_websocket_message({
            'type': 'device_status',
            'status': status
        })


# Integration with safety system
class SafetySystemAPI:
    """
    Integration layer between safety system and SOS API
    Handles all API communication for the safety system
    """
    
    def __init__(self, api_config: APIConfig):
        self.api_manager = SOSAPIManager(api_config)
        self.websocket_manager = SOSWebSocketManager(self.api_manager)
        
        # Statistics
        self.alerts_sent = 0
        self.alerts_confirmed = 0
        
        logger.info("SafetySystemAPI initialized")
    
    async def initialize(self):
        """Initialize API connections"""
        try:
            # Connect WebSocket
            websocket_connected = await self.api_manager.connect_websocket()
            
            if websocket_connected:
                logger.info("API initialization successful")
            else:
                logger.warning("WebSocket connection failed, using REST only")
            
            return True
            
        except Exception as e:
            logger.error(f"API initialization failed: {e}")
            return False
    
    async def send_sos_alert_with_audio(self, sos_alert: SOSAlert, 
                                      audio_context: bytes) -> SOSResponse:
        """
        Send SOS alert with audio context
        
        Args:
            sos_alert: SOS alert data
            audio_context: Audio context bytes
            
        Returns:
            API response
        """
        try:
            # Send SOS alert
            response = await self.api_manager.send_sos_alert(sos_alert, audio_context)
            
            if response.success:
                self.alerts_sent += 1
                
                # Subscribe to alert updates via WebSocket
                if self.api_manager.is_connected:
                    await self.websocket_manager.subscribe_alert_updates(response.alert_id)
                
                # Send device status
                await self.websocket_manager.send_device_status({
                    'alert_sent': True,
                    'alert_id': response.alert_id,
                    'timestamp': datetime.now().isoformat()
                })
            
            return response
            
        except Exception as e:
            logger.error(f"Error sending SOS alert with audio: {e}")
            raise
    
    async def send_sos_alert_only(self, sos_alert: SOSAlert) -> SOSResponse:
        """
        Send SOS alert without audio (for privacy-first mode)
        
        Args:
            sos_alert: SOS alert data
            
        Returns:
            API response
        """
        return await self.api_manager.send_sos_alert(sos_alert)
    
    def add_alert_status_callback(self, callback: Callable[[str, str], None]):
        """Add callback for alert status updates"""
        self.websocket_manager.add_alert_status_callback(callback)
    
    def add_emergency_callback(self, callback: Callable[[Dict], None]):
        """Add callback for emergency responses"""
        self.websocket_manager.add_emergency_callback(callback)
    
    async def start_heartbeat_loop(self):
        """Start periodic heartbeat to maintain connection"""
        while True:
            try:
                await self.websocket_manager.send_heartbeat()
                await asyncio.sleep(30)  # Send heartbeat every 30 seconds
            except Exception as e:
                logger.error(f"Error sending heartbeat: {e}")
                await asyncio.sleep(10)  # Brief pause on error
    
    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """Get comprehensive API statistics"""
        return {
            'api_stats': self.api_manager.get_api_stats(),
            'alerts_sent': self.alerts_sent,
            'alerts_confirmed': self.alerts_confirmed,
            'websocket_connected': self.api_manager.is_connected
        }
    
    async def cleanup(self):
        """Clean up API resources"""
        await self.api_manager.cleanup()


# Demo usage
async def demo_sos_api():
    """Demonstrate SOS API functionality"""
    # Initialize API
    config = APIConfig(api_key="demo_api_key")
    api = SafetySystemAPI(config)
    
    try:
        # Initialize connections
        await api.initialize()
        
        # Create test alert
        from safety_system import SOSAlert
        test_alert = SOSAlert(
            alert_id="test_001",
            timestamp=datetime.now().timestamp(),
            confidence=0.99,
            location={'latitude': 40.7128, 'longitude': -74.0060}
        )
        
        # Send alert
        print("📡 Sending SOS alert...")
        response = await api.send_sos_alert_only(test_alert)
        
        if response.success:
            print(f"✅ Alert sent: {response.alert_id}")
            print(f"   Message: {response.message}")
        else:
            print(f"❌ Alert failed: {response.message}")
        
        # Show statistics
        stats = api.get_comprehensive_stats()
        print(f"\n📊 API Statistics:")
        print(f"   Alerts Sent: {stats['alerts_sent']}")
        print(f"   WebSocket Connected: {stats['websocket_connected']}")
        
    except Exception as e:
        print(f"❌ Demo error: {e}")
    finally:
        await api.cleanup()


if __name__ == "__main__":
    # Run demo
    asyncio.run(demo_sos_api())
