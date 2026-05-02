"""
Mobile API Integration Layer for Vaultryn Voice-Activated Safety System
Provides mobile-friendly interfaces and platform-specific optimizations
"""

import asyncio
import logging
import json
import platform
import sys
from typing import Dict, Any, Optional, Callable, Union
from dataclasses import dataclass, asdict
from pathlib import Path
import threading
from datetime import datetime

from safety_system import SafetySystem, SOSAlert, AudioConfig, PrivacyConfig
from sos_api import SafetySystemAPI, APIConfig

logger = logging.getLogger(__name__)


@dataclass
class MobileConfig:
    """Mobile-specific configuration"""
    platform: str  # 'ios', 'android', 'web'
    app_version: str = "1.0.0"
    device_id: str = ""
    permission_check_interval: int = 30  # seconds
    
    # Battery optimization
    battery_saver_mode: bool = False
    adaptive_sampling: bool = True
    low_battery_threshold: float = 0.2  # 20%
    
    # UI integration
    show_notifications: bool = True
    vibration_on_detection: bool = True
    sound_on_detection: bool = True
    
    # Privacy settings
    gdpr_compliance: bool = True
    data_retention_days: int = 7
    require_explicit_consent: bool = True


class PermissionManager:
    """
    Mobile permission management for microphone and location access
    """
    
    def __init__(self, config: MobileConfig):
        self.config = config
        self.microphone_permission = False
        self.location_permission = False
        self.notification_permission = False
        
        logger.info(f"PermissionManager initialized for {config.platform}")
    
    async def check_permissions(self) -> Dict[str, bool]:
        """
        Check all required permissions
        
        Returns:
            Dictionary of permission status
        """
        permissions = {
            'microphone': await self._check_microphone_permission(),
            'location': await self._check_location_permission(),
            'notifications': await self._check_notification_permission()
        }
        
        self.microphone_permission = permissions['microphone']
        self.location_permission = permissions['location']
        self.notification_permission = permissions['notifications']
        
        logger.info(f"Permission check: {permissions}")
        return permissions
    
    async def _check_microphone_permission(self) -> bool:
        """Check microphone permission (platform-specific)"""
        if self.config.platform == 'ios':
            # iOS implementation would use AVAudioSession
            return self._simulate_permission_check('microphone')
        elif self.config.platform == 'android':
            # Android implementation would use ActivityCompat
            return self._simulate_permission_check('microphone')
        else:
            # Web implementation would use navigator.permissions
            return self._simulate_permission_check('microphone')
    
    async def _check_location_permission(self) -> bool:
        """Check location permission (platform-specific)"""
        return self._simulate_permission_check('location')
    
    async def _check_notification_permission(self) -> bool:
        """Check notification permission (platform-specific)"""
        return self._simulate_permission_check('notifications')
    
    def _simulate_permission_check(self, permission_type: str) -> bool:
        """Simulate permission check for demo purposes"""
        # In real implementation, this would check actual permissions
        # For demo, we'll simulate granted permissions
        return True
    
    async def request_permission(self, permission_type: str) -> bool:
        """
        Request specific permission from user
        
        Args:
            permission_type: Type of permission to request
            
        Returns:
            True if permission granted
        """
        logger.info(f"Requesting {permission_type} permission")
        
        # In real implementation, this would show OS permission dialog
        # For demo, we'll simulate user granting permission
        return True
    
    def get_permission_status(self) -> Dict[str, bool]:
        """Get current permission status"""
        return {
            'microphone': self.microphone_permission,
            'location': self.location_permission,
            'notifications': self.notification_permission
        }


class BatteryManager:
    """
    Battery optimization and power management for mobile devices
    """
    
    def __init__(self, config: MobileConfig):
        self.config = config
        self.battery_level = 1.0  # 100%
        self.is_charging = False
        self.power_saver_mode = False
        
        logger.info("BatteryManager initialized")
    
    async def start_monitoring(self):
        """Start battery level monitoring"""
        while True:
            await self._update_battery_status()
            await asyncio.sleep(self.config.permission_check_interval)
    
    async def _update_battery_status(self):
        """Update battery status (platform-specific)"""
        # In real implementation, this would check actual battery status
        # For demo, we'll simulate battery drain
        if not self.is_charging:
            self.battery_level = max(0.0, self.battery_level - 0.01)
        
        # Check if we should enable power saver mode
        if self.battery_level < self.config.low_battery_threshold:
            self.power_saver_mode = True
            logger.warning(f"Low battery ({self.battery_level:.1%}) - enabling power saver")
        else:
            self.power_saver_mode = False
    
    def get_battery_status(self) -> Dict[str, Any]:
        """Get current battery status"""
        return {
            'level': self.battery_level,
            'is_charging': self.is_charging,
            'power_saver_mode': self.power_saver_mode,
            'estimated_time_remaining': self._estimate_time_remaining()
        }
    
    def _estimate_time_remaining(self) -> float:
        """Estimate remaining battery time in hours"""
        if self.is_charging:
            return float('inf')
        
        if self.power_saver_mode:
            drain_rate = 0.005  # Slower drain in power saver
        else:
            drain_rate = 0.02  # Normal drain rate
        
        return self.battery_level / max(drain_rate, 0.001)


class NotificationManager:
    """
    Mobile notification management
    """
    
    def __init__(self, config: MobileConfig):
        self.config = config
        self.notification_queue = []
        
        logger.info("NotificationManager initialized")
    
    async def show_notification(self, title: str, body: str, 
                              notification_type: str = "info") -> bool:
        """
        Show mobile notification
        
        Args:
            title: Notification title
            body: Notification body
            notification_type: Type of notification
            
        Returns:
            True if notification shown successfully
        """
        if not self.config.show_notifications:
            return False
        
        try:
            notification_data = {
                'title': title,
                'body': body,
                'type': notification_type,
                'timestamp': datetime.now().isoformat(),
                'vibration': self.config.vibration_on_detection,
                'sound': self.config.sound_on_detection
            }
            
            # Platform-specific notification implementation
            if self.config.platform == 'ios':
                success = await self._show_ios_notification(notification_data)
            elif self.config.platform == 'android':
                success = await self._show_android_notification(notification_data)
            else:
                success = await self._show_web_notification(notification_data)
            
            if success:
                logger.info(f"Notification shown: {title}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error showing notification: {e}")
            return False
    
    async def _show_ios_notification(self, data: Dict) -> bool:
        """Show iOS notification (would use UserNotifications framework)"""
        logger.info(f"iOS Notification: {data['title']} - {data['body']}")
        return True
    
    async def _show_android_notification(self, data: Dict) -> bool:
        """Show Android notification (would use NotificationManager)"""
        logger.info(f"Android Notification: {data['title']} - {data['body']}")
        return True
    
    async def _show_web_notification(self, data: Dict) -> bool:
        """Show web notification (would use Notification API)"""
        logger.info(f"Web Notification: {data['title']} - {data['body']}")
        return True
    
    async def show_sos_confirmation_dialog(self, alert_data: Dict) -> bool:
        """
        Show SOS confirmation dialog
        
        Args:
            alert_data: Alert data to show
            
        Returns:
            True if user confirms SOS
        """
        logger.info("Showing SOS confirmation dialog")
        
        # In real implementation, this would show a native dialog
        # For demo, we'll simulate user confirmation after 3 seconds
        await asyncio.sleep(3)
        
        # Show notification about the detection
        await self.show_notification(
            "Help Detected",
            "Say 'Confirm SOS' to send alert or 'Cancel' to dismiss",
            "sos_confirmation"
        )
        
        # Simulate user confirmation (in real app, this would wait for user input)
        return True


class MobileSafetySystem:
    """
    Mobile-optimized safety system with platform-specific features
    """
    
    def __init__(self, mobile_config: MobileConfig, 
                 audio_config: AudioConfig = None,
                 api_config: APIConfig = None):
        self.mobile_config = mobile_config
        self.audio_config = audio_config or AudioConfig()
        self.api_config = api_config or APIConfig()
        
        # Initialize core systems
        self.safety_system = SafetySystem(self.audio_config)
        self.api_system = SafetySystemAPI(self.api_config)
        
        # Initialize mobile components
        self.permission_manager = PermissionManager(mobile_config)
        self.battery_manager = BatteryManager(mobile_config)
        self.notification_manager = NotificationManager(mobile_config)
        
        # System state
        self.is_initialized = False
        self.is_active = False
        self.background_tasks = []
        
        # Callbacks for mobile integration
        self.detection_callbacks = []
        self.sos_callbacks = []
        self.error_callbacks = []
        
        logger.info(f"MobileSafetySystem initialized for {mobile_config.platform}")
    
    async def initialize(self) -> bool:
        """
        Initialize the mobile safety system
        
        Returns:
            True if initialization successful
        """
        try:
            logger.info("Initializing mobile safety system...")
            
            # Check permissions
            permissions = await self.permission_manager.check_permissions()
            
            if not all(permissions.values()):
                logger.error("Required permissions not granted")
                await self._handle_permission_denied(permissions)
                return False
            
            # Initialize API connections
            api_initialized = await self.api_system.initialize()
            if not api_initialized:
                logger.warning("API initialization failed, continuing in offline mode")
            
            # Set up callbacks
            self._setup_callbacks()
            
            # Start background monitoring
            await self._start_background_monitoring()
            
            self.is_initialized = True
            logger.info("Mobile safety system initialized successfully")
            
            return True
            
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            await self._handle_error("initialization", str(e))
            return False
    
    async def start_monitoring(self) -> bool:
        """
        Start voice monitoring
        
        Returns:
            True if monitoring started successfully
        """
        if not self.is_initialized:
            logger.error("System not initialized")
            return False
        
        try:
            # Check battery level
            battery_status = self.battery_manager.get_battery_status()
            if battery_status['power_saver_mode']:
                logger.info("Power saver mode active - using reduced monitoring")
                # Could implement reduced monitoring here
            
            # Start safety system
            await self.safety_system.start()
            
            self.is_active = True
            logger.info("Voice monitoring started")
            
            # Show notification
            await self.notification_manager.show_notification(
                "Vaultryn Active",
                "Voice monitoring is now active. Say 'Help' in an emergency.",
                "system_active"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to start monitoring: {e}")
            await self._handle_error("start_monitoring", str(e))
            return False
    
    async def stop_monitoring(self):
        """Stop voice monitoring"""
        try:
            await self.safety_system.stop()
            self.is_active = False
            
            logger.info("Voice monitoring stopped")
            
            # Show notification
            await self.notification_manager.show_notification(
                "Vaultryn Inactive",
                "Voice monitoring has been stopped.",
                "system_inactive"
            )
            
        except Exception as e:
            logger.error(f"Error stopping monitoring: {e}")
    
    def _setup_callbacks(self):
        """Set up callbacks for safety system events"""
        # Detection callback
        async def on_detection(detection_result):
            await self._handle_keyword_detection(detection_result)
        
        self.safety_system.set_detection_callback(on_detection)
        
        # SOS callback
        async def on_sos_alert(alert_data):
            await self._handle_sos_alert(alert_data)
        
        self.safety_system.set_sos_callback(on_sos_alert)
    
    async def _handle_keyword_detection(self, detection_result):
        """Handle keyword detection"""
        logger.info(f"Keyword detected: {detection_result['confidence']:.3f}")
        
        # Show immediate feedback
        await self.notification_manager.show_notification(
            "Help Detected",
            "Processing your request...",
            "detection"
        )
        
        # Call mobile callbacks
        for callback in self.detection_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(detection_result)
                else:
                    # Run sync callback in thread pool
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, callback, detection_result)
            except Exception as e:
                logger.error(f"Error in detection callback: {e}")
    
    async def _handle_sos_alert(self, alert_data):
        """Handle SOS alert"""
        logger.info(f"SOS alert: {alert_data.get('alert_id', 'unknown')}")
        
        # Show confirmation dialog
        confirmed = await self.notification_manager.show_sos_confirmation_dialog(alert_data)
        
        if confirmed:
            # Send alert via API
            from safety_system import SOSAlert
            
            # Recreate SOS alert from data
            sos_alert = SOSAlert(
                alert_id=alert_data.get('alert_id', ''),
                timestamp=alert_data.get('timestamp', 0),
                confidence=alert_data.get('confidence', 0),
                location=alert_data.get('location'),
                device_info=alert_data.get('device_info')
            )
            
            # Get audio context if available
            audio_context = self.safety_system.privacy_guard.get_context_audio()
            
            response = await self.api_system.send_sos_alert_with_audio(sos_alert, audio_context)
            
            if response.success:
                await self.notification_manager.show_notification(
                    "SOS Alert Sent",
                    f"Alert {response.alert_id} has been sent to emergency services.",
                    "sos_sent"
                )
            else:
                await self.notification_manager.show_notification(
                    "SOS Failed",
                    "Failed to send alert. Please try again.",
                    "sos_failed"
                )
        
        # Call mobile callbacks
        for callback in self.sos_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(alert_data, confirmed)
                else:
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, callback, alert_data, confirmed)
            except Exception as e:
                logger.error(f"Error in SOS callback: {e}")
    
    async def _start_background_monitoring(self):
        """Start background monitoring tasks"""
        # Battery monitoring
        battery_task = asyncio.create_task(self.battery_manager.start_monitoring())
        self.background_tasks.append(battery_task)
        
        # API heartbeat
        heartbeat_task = asyncio.create_task(self.api_system.start_heartbeat_loop())
        self.background_tasks.append(heartbeat_task)
        
        logger.info("Background monitoring started")
    
    async def _handle_permission_denied(self, permissions: Dict[str, bool]):
        """Handle denied permissions"""
        missing_permissions = [p for p, granted in permissions.items() if not granted]
        
        await self.notification_manager.show_notification(
            "Permissions Required",
            f"Please grant {', '.join(missing_permissions)} permissions to use Vaultryn.",
            "permission_denied"
        )
    
    async def _handle_error(self, error_type: str, error_message: str):
        """Handle system errors"""
        logger.error(f"System error ({error_type}): {error_message}")
        
        await self.notification_manager.show_notification(
            "System Error",
            f"An error occurred: {error_type}",
            "error"
        )
        
        # Call error callbacks
        for callback in self.error_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(error_type, error_message)
                else:
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, callback, error_type, error_message)
            except Exception as e:
                logger.error(f"Error in error callback: {e}")
    
    def add_detection_callback(self, callback: Callable):
        """Add callback for keyword detection"""
        self.detection_callbacks.append(callback)
    
    def add_sos_callback(self, callback: Callable):
        """Add callback for SOS alerts"""
        self.sos_callbacks.append(callback)
    
    def add_error_callback(self, callback: Callable):
        """Add callback for system errors"""
        self.error_callbacks.append(callback)
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        return {
            'initialized': self.is_initialized,
            'active': self.is_active,
            'platform': self.mobile_config.platform,
            'app_version': self.mobile_config.app_version,
            'permissions': self.permission_manager.get_permission_status(),
            'battery': self.battery_manager.get_battery_status(),
            'safety_system': self.safety_system.get_system_stats(),
            'api_system': self.api_system.get_comprehensive_stats()
        }
    
    async def cleanup(self):
        """Clean up system resources"""
        try:
            # Stop monitoring
            if self.is_active:
                await self.stop_monitoring()
            
            # Cancel background tasks
            for task in self.background_tasks:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            # Clean up API system
            await self.api_system.cleanup()
            
            logger.info("Mobile safety system cleaned up")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


# Platform-specific factory functions
def create_mobile_system(platform: str) -> MobileSafetySystem:
    """
    Create mobile safety system for specific platform
    
    Args:
        platform: Platform type ('ios', 'android', 'web')
        
    Returns:
        Configured mobile safety system
    """
    mobile_config = MobileConfig(
        platform=platform,
        device_id=f"{platform}_demo_device"
    )
    
    # Platform-specific optimizations
    if platform == 'ios':
        # iOS-specific settings
        mobile_config.adaptive_sampling = True
        mobile_config.battery_saver_mode = True
    elif platform == 'android':
        # Android-specific settings
        mobile_config.vibration_on_detection = True
        mobile_config.show_notifications = True
    else:
        # Web-specific settings
        mobile_config.require_explicit_consent = True
        mobile_config.gdpr_compliance = True
    
    return MobileSafetySystem(mobile_config)


# Demo function
async def demo_mobile_integration():
    """Demonstrate mobile integration"""
    # Create mobile system for current platform
    current_platform = platform.system().lower()
    if 'darwin' in current_platform:
        platform_type = 'ios'
    elif 'android' in current_platform:
        platform_type = 'android'
    else:
        platform_type = 'web'
    
    print(f"📱 Creating mobile safety system for {platform_type}...")
    
    mobile_system = create_mobile_system(platform_type)
    
    # Add demo callbacks
    def on_detection(detection_result):
        print(f"🎯 Mobile detection: {detection_result['confidence']:.3f}")
    
    def on_sos_alert(alert_data, confirmed):
        status = "confirmed" if confirmed else "cancelled"
        print(f"🚨 Mobile SOS: {alert_data.get('alert_id', 'unknown')} - {status}")
    
    def on_error(error_type, error_message):
        print(f"❌ Mobile error: {error_type} - {error_message}")
    
    mobile_system.add_detection_callback(on_detection)
    mobile_system.add_sos_callback(on_sos_alert)
    mobile_system.add_error_callback(on_error)
    
    try:
        # Initialize system
        print("🔧 Initializing mobile safety system...")
        initialized = await mobile_system.initialize()
        
        if initialized:
            print("✅ System initialized successfully")
            
            # Show status
            status = mobile_system.get_system_status()
            print(f"\n📊 System Status:")
            print(f"   Platform: {status['platform']}")
            print(f"   Permissions: {status['permissions']}")
            print(f"   Battery: {status['battery']['level']:.1%}")
            print(f"   Active: {status['active']}")
            
            # Start monitoring (brief demo)
            print("\n🎤 Starting voice monitoring (10 seconds)...")
            await mobile_system.start_monitoring()
            
            # Run for 10 seconds
            await asyncio.sleep(10)
            
            # Stop monitoring
            await mobile_system.stop_monitoring()
            print("⏹️  Monitoring stopped")
            
        else:
            print("❌ System initialization failed")
    
    except Exception as e:
        print(f"❌ Demo error: {e}")
    finally:
        await mobile_system.cleanup()
        print("🧹 System cleaned up")


if __name__ == "__main__":
    # Run demo
    asyncio.run(demo_mobile_integration())
