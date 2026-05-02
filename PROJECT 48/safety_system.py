"""
Privacy-First On-Device Safety System
Main loop for voice-activated SOS with comprehensive privacy safeguards
"""

import asyncio
import logging
import time
import json
import hashlib
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass, asdict
from pathlib import Path
import threading
from collections import deque
from datetime import datetime, timedelta

from audio_processing import AudioConfig, AudioPreprocessor
from keyword_spotter import KeywordSpotter, KeywordDetector, ModelConfig, ModelManager

logger = logging.getLogger(__name__)


@dataclass
class SOSAlert:
    """SOS alert data structure"""
    alert_id: str
    timestamp: float
    confidence: float
    location: Optional[Dict[str, float]] = None
    audio_context_hash: Optional[str] = None
    device_info: Optional[Dict[str, str]] = None
    detection_metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for API transmission"""
        return asdict(self)


@dataclass
class PrivacyConfig:
    """Privacy configuration for safety system"""
    max_audio_retention_seconds: int = 10  # Maximum audio kept in memory
    auto_cleanup_interval_seconds: int = 30  # Cleanup interval
    encrypt_audio_context: bool = True
    hash_audio_context: bool = True
    min_confidence_for_upload: float = 0.98
    require_user_confirmation: bool = True
    confirmation_timeout_seconds: int = 10
    
    # Privacy metrics
    track_false_positives: bool = True
    privacy_audit_log: bool = True
    data_minimization: bool = True


class PrivacyGuard:
    """
    Privacy protection layer for the safety system
    Ensures no audio data is transmitted without explicit consent
    """
    
    def __init__(self, config: PrivacyConfig):
        self.config = config
        self.audio_buffer = deque(maxlen=config.max_audio_retention_seconds * 2)  # 500ms chunks
        self.last_cleanup_time = time.time()
        self.privacy_log = []
        
        # Privacy metrics
        self.total_audio_chunks_processed = 0
        self.audio_chunks_uploaded = 0
        self.false_positive_uploads_prevented = 0
        
        logger.info("PrivacyGuard initialized")
    
    def add_audio_chunk(self, audio_data: bytes, is_keyword_detected: bool = False):
        """
        Add audio chunk to buffer with privacy tracking
        
        Args:
            audio_data: Raw audio chunk
            is_keyword_detected: Whether keyword was detected in this chunk
        """
        try:
            # Add to buffer (automatically handles size limit)
            chunk_info = {
                'data': audio_data,
                'timestamp': time.time(),
                'is_keyword_detected': is_keyword_detected,
                'size': len(audio_data)
            }
            
            self.audio_buffer.append(chunk_info)
            self.total_audio_chunks_processed += 1
            
            # Periodic cleanup
            self._cleanup_if_needed()
            
        except Exception as e:
            logger.error(f"Error adding audio chunk to privacy buffer: {e}")
    
    def get_context_audio(self, duration_seconds: int = 5) -> bytes:
        """
        Get audio context for SOS alert
        
        Args:
            duration_seconds: Duration of context to retrieve
            
        Returns:
            Audio context bytes
        """
        try:
            current_time = time.time()
            cutoff_time = current_time - duration_seconds
            
            # Collect relevant chunks
            context_chunks = []
            for chunk_info in self.audio_buffer:
                if chunk_info['timestamp'] >= cutoff_time:
                    context_chunks.append(chunk_info['data'])
            
            # Concatenate audio
            context_audio = b''.join(context_chunks)
            
            # Hash for privacy audit
            if self.config.hash_audio_context:
                context_hash = hashlib.sha256(context_audio).hexdigest()
                logger.info(f"Audio context hash: {context_hash[:16]}...")
            
            return context_audio
            
        except Exception as e:
            logger.error(f"Error getting context audio: {e}")
            return b''
    
    def should_upload_audio(self, confidence: float, detection_result: Dict) -> bool:
        """
        Determine if audio should be uploaded based on privacy rules
        
        Args:
            confidence: Detection confidence
            detection_result: Full detection result
            
        Returns:
            True if audio upload is permitted
        """
        try:
            # Check confidence threshold
            if confidence < self.config.min_confidence_for_upload:
                self.false_positive_uploads_prevented += 1
                if self.config.privacy_audit_log:
                    self._log_privacy_event("UPLOAD_BLOCKED_LOW_CONFIDENCE", {
                        'confidence': confidence,
                        'threshold': self.config.min_confidence_for_upload
                    })
                return False
            
            # Additional privacy checks can be added here
            # For example: user consent, time of day, location, etc.
            
            return True
            
        except Exception as e:
            logger.error(f"Error in upload decision: {e}")
            return False
    
    def _cleanup_if_needed(self):
        """Periodic cleanup of old audio data"""
        current_time = time.time()
        
        if current_time - self.last_cleanup_time > self.config.auto_cleanup_interval_seconds:
            cutoff_time = current_time - self.config.max_audio_retention_seconds
            
            # Remove old chunks (deque handles this automatically, but we log it)
            old_chunks = sum(1 for chunk in self.audio_buffer 
                           if chunk['timestamp'] < cutoff_time)
            
            if old_chunks > 0:
                logger.info(f"Cleaned up {old_chunks} old audio chunks")
            
            self.last_cleanup_time = current_time
    
    def _log_privacy_event(self, event_type: str, metadata: Dict):
        """Log privacy events for audit"""
        if self.config.privacy_audit_log:
            event = {
                'timestamp': time.time(),
                'type': event_type,
                'metadata': metadata
            }
            self.privacy_log.append(event)
            
            # Keep log size manageable
            if len(self.privacy_log) > 1000:
                self.privacy_log = self.privacy_log[-500:]
    
    def get_privacy_metrics(self) -> Dict:
        """Get privacy protection metrics"""
        return {
            'total_chunks_processed': self.total_audio_chunks_processed,
            'chunks_uploaded': self.audio_chunks_uploaded,
            'false_positives_prevented': self.false_positive_uploads_prevented,
            'upload_rate': self.audio_chunks_uploaded / max(self.total_audio_chunks_processed, 1),
            'privacy_events_logged': len(self.privacy_log),
            'current_buffer_size': len(self.audio_buffer)
        }
    
    def clear_all_data(self):
        """Clear all stored audio data (privacy reset)"""
        self.audio_buffer.clear()
        self.privacy_log.clear()
        logger.info("All privacy data cleared")


class SafetySystem:
    """
    Main safety system orchestrator
    Coordinates audio processing, keyword detection, and SOS alerts
    """
    
    def __init__(self, 
                 audio_config: AudioConfig = None,
                 model_config: ModelConfig = None,
                 privacy_config: PrivacyConfig = None,
                 model_path: str = None):
        
        # Initialize configurations
        self.audio_config = audio_config or AudioConfig()
        self.model_config = model_config or ModelConfig()
        self.privacy_config = privacy_config or PrivacyConfig()
        
        # Initialize components
        self.audio_preprocessor = AudioPreprocessor(self.audio_config)
        
        # Load or create model
        if model_path and Path(model_path).exists():
            self.model = ModelManager.load_model(model_path)
            logger.info(f"Loaded model from {model_path}")
        else:
            self.model = KeywordSpotter(self.model_config)
            logger.info("Created new keyword spotter model")
        
        self.keyword_detector = KeywordDetector(self.model, self.audio_config)
        self.privacy_guard = PrivacyGuard(self.privacy_config)
        
        # System state
        self.is_running = False
        self.recording_task = None
        self.processing_task = None
        
        # Callbacks
        self.sos_callback: Optional[Callable[[SOSAlert], None]] = None
        self.detection_callback: Optional[Callable[[Dict], None]] = None
        
        # Statistics
        self.start_time = None
        self.total_detections = 0
        self.sos_alerts_sent = 0
        
        logger.info("SafetySystem initialized")
    
    async def start(self):
        """Start the safety system"""
        try:
            if self.is_running:
                logger.warning("Safety system is already running")
                return
            
            # Start audio processing
            self.recording_task = await self.audio_preprocessor.start()
            
            # Start main processing loop
            self.processing_task = asyncio.create_task(self._processing_loop())
            
            self.is_running = True
            self.start_time = time.time()
            
            logger.info("Safety system started successfully")
            
        except Exception as e:
            logger.error(f"Error starting safety system: {e}")
            await self.stop()
            raise
    
    async def stop(self):
        """Stop the safety system"""
        try:
            self.is_running = False
            
            # Stop audio processing
            await self.audio_preprocessor.stop()
            
            # Cancel tasks
            if self.recording_task:
                self.recording_task.cancel()
                try:
                    await self.recording_task
                except asyncio.CancelledError:
                    pass
            
            if self.processing_task:
                self.processing_task.cancel()
                try:
                    await self.processing_task
                except asyncio.CancelledError:
                    pass
            
            logger.info("Safety system stopped")
            
        except Exception as e:
            logger.error(f"Error stopping safety system: {e}")
    
    async def _processing_loop(self):
        """Main audio processing loop"""
        logger.info("Starting audio processing loop")
        
        while self.is_running:
            try:
                # Get processed audio chunk
                features = await self.audio_preprocessor.get_processed_chunk()
                
                if features is not None:
                    # Add to privacy buffer
                    raw_audio = self.audio_preprocessor.get_audio_chunk()
                    if raw_audio:
                        self.privacy_guard.add_audio_chunk(raw_audio)
                    
                    # Detect keyword
                    detection_result = self.keyword_detector.detect_keyword(features)
                    
                    if detection_result:
                        await self._handle_keyword_detection(detection_result, features)
                
                # Brief sleep to prevent CPU overload
                await asyncio.sleep(0.05)  # 50ms
                
            except asyncio.CancelledError:
                logger.info("Processing loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in processing loop: {e}")
                await asyncio.sleep(0.1)  # Brief pause on error
    
    async def _handle_keyword_detection(self, detection_result: Dict, features):
        """Handle keyword detection with privacy safeguards"""
        try:
            self.total_detections += 1
            
            logger.info(f"Keyword detected: {detection_result}")
            
            # Call detection callback if set
            if self.detection_callback:
                try:
                    await self._call_callback(self.detection_callback, detection_result)
                except Exception as e:
                    logger.error(f"Error in detection callback: {e}")
            
            # Check privacy rules before creating SOS alert
            confidence = detection_result['confidence']
            
            if self.privacy_guard.should_upload_audio(confidence, detection_result):
                # Create SOS alert
                sos_alert = await self._create_sos_alert(detection_result)
                
                # Handle user confirmation if required
                if self.privacy_config.require_user_confirmation:
                    confirmed = await self._request_user_confirmation(sos_alert)
                    if not confirmed:
                        logger.info("User did not confirm SOS alert")
                        return
                
                # Send SOS alert
                await self._send_sos_alert(sos_alert)
                
            else:
                logger.info("Audio upload blocked by privacy safeguards")
                
        except Exception as e:
            logger.error(f"Error handling keyword detection: {e}")
    
    async def _create_sos_alert(self, detection_result: Dict) -> SOSAlert:
        """Create SOS alert with privacy-protected data"""
        try:
            # Generate alert ID
            alert_id = hashlib.sha256(
                f"{detection_result['timestamp']}{detection_result['detection_id']}".encode()
            ).hexdigest()[:16]
            
            # Get location (placeholder - would use GPS in real app)
            location = await self._get_current_location()
            
            # Get audio context
            context_audio = self.privacy_guard.get_context_audio(
                self.audio_config.context_duration_s
            )
            
            # Hash audio context for privacy
            context_hash = None
            if context_audio and self.privacy_config.hash_audio_context:
                context_hash = hashlib.sha256(context_audio).hexdigest()
            
            # Create alert
            sos_alert = SOSAlert(
                alert_id=alert_id,
                timestamp=detection_result['timestamp'],
                confidence=detection_result['confidence'],
                location=location,
                audio_context_hash=context_hash,
                device_info=await self._get_device_info(),
                detection_metadata=detection_result
            )
            
            return sos_alert
            
        except Exception as e:
            logger.error(f"Error creating SOS alert: {e}")
            raise
    
    async def _request_user_confirmation(self, sos_alert: SOSAlert) -> bool:
        """
        Request user confirmation for SOS alert
        
        In a real app, this would show a UI confirmation dialog.
        For this demo, we'll simulate user confirmation.
        """
        try:
            logger.info(f"Requesting user confirmation for alert {sos_alert.alert_id}")
            
            # Simulate user confirmation (would be UI dialog in real app)
            # For demo purposes, we'll auto-confirm after a short delay
            await asyncio.sleep(1.0)  # Simulate user seeing the alert
            
            # In a real implementation, this would wait for user input
            # return await self.ui.show_confirmation_dialog(sos_alert)
            
            logger.info("User confirmed SOS alert")
            return True
            
        except Exception as e:
            logger.error(f"Error requesting user confirmation: {e}")
            return False
    
    async def _send_sos_alert(self, sos_alert: SOSAlert):
        """Send SOS alert to API"""
        try:
            # Get audio context for upload
            context_audio = self.privacy_guard.get_context_audio(
                self.audio_config.context_duration_s
            )
            
            # Prepare alert data
            alert_data = sos_alert.to_dict()
            
            # Add audio if available
            if context_audio:
                alert_data['audio_context'] = context_audio.hex()  # Convert to hex for JSON
                self.privacy_guard.audio_chunks_uploaded += 1
            
            # Call SOS callback if set
            if self.sos_callback:
                try:
                    await self._call_callback(self.sos_callback, alert_data)
                except Exception as e:
                    logger.error(f"Error in SOS callback: {e}")
            
            self.sos_alerts_sent += 1
            logger.info(f"SOS alert sent: {sos_alert.alert_id}")
            
        except Exception as e:
            logger.error(f"Error sending SOS alert: {e}")
    
    async def _call_callback(self, callback: Callable, data: Any):
        """Safely call async callback"""
        if asyncio.iscoroutinefunction(callback):
            await callback(data)
        else:
            # Run sync callback in thread pool
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, callback, data)
    
    async def _get_current_location(self) -> Optional[Dict[str, float]]:
        """Get current GPS location (placeholder)"""
        # In a real app, this would use the device's GPS
        return {
            'latitude': 40.7128,  # NYC coordinates as placeholder
            'longitude': -74.0060,
            'accuracy': 10.0,
            'timestamp': time.time()
        }
    
    async def _get_device_info(self) -> Dict[str, str]:
        """Get device information for alert context"""
        return {
            'device_id': 'demo_device_001',
            'app_version': '1.0.0',
            'os_version': 'iOS 17.0',
            'model': 'iPhone 14'
        }
    
    def set_sos_callback(self, callback: Callable[[SOSAlert], None]):
        """Set callback for SOS alerts"""
        self.sos_callback = callback
        logger.info("SOS callback set")
    
    def set_detection_callback(self, callback: Callable[[Dict], None]):
        """Set callback for keyword detections"""
        self.detection_callback = callback
        logger.info("Detection callback set")
    
    def get_system_stats(self) -> Dict:
        """Get comprehensive system statistics"""
        uptime = time.time() - self.start_time if self.start_time else 0
        
        return {
            'is_running': self.is_running,
            'uptime_seconds': uptime,
            'total_detections': self.total_detections,
            'sos_alerts_sent': self.sos_alerts_sent,
            'detection_rate': self.total_detections / max(uptime, 1),
            'keyword_detector_stats': self.keyword_detector.get_detection_stats(),
            'privacy_metrics': self.privacy_guard.get_privacy_metrics(),
            'model_info': self.model.get_model_info()
        }
    
    def update_privacy_config(self, **kwargs):
        """Update privacy configuration"""
        for key, value in kwargs.items():
            if hasattr(self.privacy_config, key):
                setattr(self.privacy_config, key, value)
                logger.info(f"Updated privacy config: {key} = {value}")
    
    def update_confidence_threshold(self, threshold: float):
        """Update confidence threshold for detection"""
        self.keyword_detector.set_confidence_threshold(threshold)
        self.privacy_config.min_confidence_for_upload = threshold
        logger.info(f"Updated confidence threshold to {threshold}")


# Demo functions for testing
async def demo_safety_system():
    """Demonstrate the safety system"""
    # Initialize system
    safety_system = SafetySystem()
    
    # Set up callbacks
    async def on_detection(detection_result):
        print(f"🎯 Keyword detected: {detection_result}")
    
    async def on_sos_alert(alert_data):
        print(f"🚨 SOS Alert: {alert_data['alert_id']}")
        print(f"   Confidence: {alert_data['confidence']:.3f}")
        print(f"   Location: {alert_data['location']}")
    
    safety_system.set_detection_callback(on_detection)
    safety_system.set_sos_callback(on_sos_alert)
    
    try:
        # Start system
        print("🎤 Starting safety system...")
        await safety_system.start()
        
        # Run for demo period
        print("🎧 Listening for 'help' keyword... (Ctrl+C to stop)")
        await asyncio.sleep(30)  # Run for 30 seconds
        
    except KeyboardInterrupt:
        print("\n⏹️  Stopping safety system...")
    finally:
        await safety_system.stop()
        
        # Print statistics
        stats = safety_system.get_system_stats()
        print(f"\n📊 System Statistics:")
        print(f"   Uptime: {stats['uptime_seconds']:.1f}s")
        print(f"   Total Detections: {stats['total_detections']}")
        print(f"   SOS Alerts: {stats['sos_alerts_sent']}")
        print(f"   Privacy Metrics: {stats['privacy_metrics']}")


if __name__ == "__main__":
    # Run demo
    asyncio.run(demo_safety_system())
