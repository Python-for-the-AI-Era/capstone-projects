"""
Cursor Tracking with Rate Limiting for Real-Time Collaborative Editor
Manages cursor positions and broadcasts them efficiently across users
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import json

from document_model import Operation, OperationType, position_to_line_column, line_column_to_position

logger = logging.getLogger(__name__)


@dataclass
class CursorPosition:
    """Represents a cursor position in a document"""
    user_id: str
    line: int
    column: int
    position: int  # Character position
    selection_start: Optional[int] = None
    selection_end: Optional[int] = None
    color: str = "#3498db"  # User's cursor color
    name: str = ""
    last_update: datetime = field(default_factory=datetime.utcnow)
    is_active: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'user_id': self.user_id,
            'line': self.line,
            'column': self.column,
            'position': self.position,
            'selection_start': self.selection_start,
            'selection_end': self.selection_end,
            'color': self.color,
            'name': self.name,
            'last_update': self.last_update.isoformat(),
            'is_active': self.is_active
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CursorPosition':
        """Create from dictionary"""
        return cls(
            user_id=data.get('user_id', ''),
            line=data.get('line', 0),
            column=data.get('column', 0),
            position=data.get('position', 0),
            selection_start=data.get('selection_start'),
            selection_end=data.get('selection_end'),
            color=data.get('color', '#3498db'),
            name=data.get('name', ''),
            last_update=datetime.fromisoformat(data.get('last_update', datetime.utcnow().isoformat())),
            is_active=data.get('is_active', True)
        )


class CursorRateLimiter:
    """
    Rate limiter for cursor updates to prevent flooding the network
    """
    
    def __init__(self, max_updates_per_second: int = 10, burst_size: int = 20):
        self.max_updates_per_second = max_updates_per_second
        self.burst_size = burst_size
        
        # Track last update times and token buckets for each user
        self.last_updates: Dict[str, float] = {}
        self.token_buckets: Dict[str, float] = {}
        self.last_refill: Dict[str, float] = {}
        
    def should_update(self, user_id: str) -> bool:
        """
        Check if cursor update should be sent
        Uses token bucket algorithm for rate limiting
        """
        current_time = time.time()
        
        # Initialize token bucket if not exists
        if user_id not in self.token_buckets:
            self.token_buckets[user_id] = self.burst_size
            self.last_refill[user_id] = current_time
        
        # Refill tokens
        time_since_refill = current_time - self.last_refill[user_id]
        tokens_to_add = time_since_refill * self.max_updates_per_second
        
        self.token_buckets[user_id] = min(
            self.token_buckets[user_id] + tokens_to_add,
            self.burst_size
        )
        self.last_refill[user_id] = current_time
        
        # Check if we have tokens
        if self.token_buckets[user_id] >= 1:
            self.token_buckets[user_id] -= 1
            self.last_updates[user_id] = current_time
            return True
        
        return False
    
    def get_next_allowed_time(self, user_id: str) -> float:
        """Get the next time an update will be allowed"""
        if user_id not in self.token_buckets:
            return time.time()
        
        if self.token_buckets[user_id] >= 1:
            return time.time()
        
        # Calculate when next token will be available
        tokens_needed = 1 - self.token_buckets[user_id]
        time_needed = tokens_needed / self.max_updates_per_second
        
        return time.time() + time_needed
    
    def get_rate_limit_info(self, user_id: str) -> Dict[str, Any]:
        """Get rate limiting information for a user"""
        current_time = time.time()
        
        if user_id not in self.token_buckets:
            return {
                'tokens_available': self.burst_size,
                'max_tokens': self.burst_size,
                'next_allowed_time': current_time,
                'updates_per_second': self.max_updates_per_second
            }
        
        return {
            'tokens_available': self.token_buckets[user_id],
            'max_tokens': self.burst_size,
            'next_allowed_time': self.get_next_allowed_time(user_id),
            'updates_per_second': self.max_updates_per_second
        }


class CursorTracker:
    """
    Tracks cursor positions for all users in a document
    """
    
    def __init__(self, doc_id: str, max_users: int = 50):
        self.doc_id = doc_id
        self.max_users = max_users
        self.cursors: Dict[str, CursorPosition] = {}  # user_id -> CursorPosition
        self.rate_limiter = CursorRateLimiter()
        self.user_colors: Dict[str, str] = {}
        self.inactive_timeout = timedelta(minutes=5)
        
        # Predefined colors for users
        self.available_colors = [
            "#3498db", "#e74c3c", "#2ecc71", "#f39c12", "#9b59b6",
            "#1abc9c", "#34495e", "#e67e22", "#95a5a6", "#d35400",
            "#c0392b", "#27ae60", "#2980b9", "#8e44ad", "#f1c40f"
        ]
        
        logger.info(f"Cursor tracker initialized for document {doc_id}")
    
    def update_cursor(self, user_id: str, line: int, column: int, 
                    selection_start: Optional[int] = None,
                    selection_end: Optional[int] = None,
                    user_name: str = "") -> bool:
        """
        Update cursor position for a user
        Returns True if update should be broadcast
        """
        # Check rate limit
        if not self.rate_limiter.should_update(user_id):
            return False
        
        # Get or create cursor position
        cursor = self.cursors.get(user_id)
        
        if cursor is None:
            # New user
            if len(self.cursors) >= self.max_users:
                logger.warning(f"Max users ({self.max_users}) reached for document {self.doc_id}")
                return False
            
            cursor = CursorPosition(
                user_id=user_id,
                line=line,
                column=column,
                position=0,  # Will be calculated
                selection_start=selection_start,
                selection_end=selection_end,
                color=self._get_user_color(user_id),
                name=user_name
            )
            self.cursors[user_id] = cursor
        else:
            # Update existing cursor
            cursor.line = line
            cursor.column = column
            cursor.selection_start = selection_start
            cursor.selection_end = selection_end
            cursor.last_update = datetime.utcnow()
            cursor.is_active = True
            if user_name:
                cursor.name = user_name
        
        return True
    
    def update_cursor_by_position(self, user_id: str, position: int,
                                selection_start: Optional[int] = None,
                                selection_end: Optional[int] = None,
                                user_name: str = "") -> bool:
        """
        Update cursor by character position
        Returns True if update should be broadcast
        """
        # Convert position to line/column (would need document content)
        # For now, we'll estimate based on typical line length
        line = position // 80  # Assume 80 characters per line
        column = position % 80
        
        cursor_pos = self.update_cursor(
            user_id, line, column, selection_start, selection_end, user_name
        )
        
        if cursor_pos and user_id in self.cursors:
            self.cursors[user_id].position = position
            if selection_start is not None:
                self.cursors[user_id].selection_start = selection_start
            if selection_end is not None:
                self.cursors[user_id].selection_end = selection_end
        
        return cursor_pos
    
    def remove_user(self, user_id: str) -> bool:
        """Remove a user from cursor tracking"""
        if user_id in self.cursors:
            del self.cursors[user_id]
            if user_id in self.user_colors:
                del self.user_colors[user_id]
            logger.info(f"Removed user {user_id} from cursor tracking")
            return True
        return False
    
    def get_user_cursor(self, user_id: str) -> Optional[CursorPosition]:
        """Get cursor position for a specific user"""
        return self.cursors.get(user_id)
    
    def get_all_cursors(self) -> List[CursorPosition]:
        """Get all active cursors"""
        return [cursor for cursor in self.cursors.values() if cursor.is_active]
    
    def get_cursor_broadcast_data(self, user_id: str = None) -> Dict[str, Any]:
        """
        Get cursor data suitable for broadcasting
        If user_id is provided, only returns that user's cursor
        """
        if user_id:
            cursor = self.cursors.get(user_id)
            if cursor:
                return cursor.to_dict()
            return {}
        
        # Return all cursors
        cursors = self.get_all_cursors()
        return {
            'doc_id': self.doc_id,
            'cursors': [cursor.to_dict() for cursor in cursors],
            'user_count': len(cursors),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def mark_inactive_users(self):
        """Mark users as inactive if they haven't updated recently"""
        current_time = datetime.utcnow()
        inactive_users = []
        
        for user_id, cursor in self.cursors.items():
            if current_time - cursor.last_update > self.inactive_timeout:
                cursor.is_active = False
                inactive_users.append(user_id)
        
        if inactive_users:
            logger.info(f"Marked {len(inactive_users)} users as inactive in document {self.doc_id}")
    
    def cleanup_inactive_users(self) -> int:
        """Remove inactive users from tracking"""
        current_time = datetime.utcnow()
        users_to_remove = []
        
        for user_id, cursor in self.cursors.items():
            if current_time - cursor.last_update > self.inactive_timeout * 2:
                users_to_remove.append(user_id)
        
        for user_id in users_to_remove:
            self.remove_user(user_id)
        
        return len(users_to_remove)
    
    def _get_user_color(self, user_id: str) -> str:
        """Get or assign a color for a user"""
        if user_id not in self.user_colors:
            # Assign next available color
            used_colors = set(self.user_colors.values())
            available_colors = [c for c in self.available_colors if c not in used_colors]
            
            if available_colors:
                self.user_colors[user_id] = available_colors[0]
            else:
                # Fallback to hash-based color
                self.user_colors[user_id] = self._hash_to_color(user_id)
        
        return self.user_colors[user_id]
    
    def _hash_to_color(self, user_id: str) -> str:
        """Generate a color from user ID hash"""
        hash_value = hash(user_id) % len(self.available_colors)
        return self.available_colors[hash_value]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get cursor tracking statistics"""
        active_cursors = self.get_all_cursors()
        
        return {
            'doc_id': self.doc_id,
            'total_users': len(self.cursors),
            'active_users': len(active_cursors),
            'inactive_users': len(self.cursors) - len(active_cursors),
            'max_users': self.max_users,
            'rate_limit_info': {
                'max_updates_per_second': self.rate_limiter.max_updates_per_second,
                'burst_size': self.rate_limiter.burst_size
            },
            'user_colors': list(self.user_colors.values()),
            'last_cleanup': datetime.utcnow().isoformat()
        }


class MultiDocumentCursorTracker:
    """
    Manages cursor tracking across multiple documents
    """
    
    def __init__(self):
        self.trackers: Dict[str, CursorTracker] = {}  # doc_id -> CursorTracker
        self.global_rate_limiter = CursorRateLimiter(max_updates_per_second=50)
        
    def get_tracker(self, doc_id: str) -> CursorTracker:
        """Get or create cursor tracker for a document"""
        if doc_id not in self.trackers:
            self.trackers[doc_id] = CursorTracker(doc_id)
        
        return self.trackers[doc_id]
    
    def update_cursor(self, doc_id: str, user_id: str, line: int, column: int,
                    selection_start: Optional[int] = None,
                    selection_end: Optional[int] = None,
                    user_name: str = "") -> bool:
        """Update cursor in a specific document"""
        tracker = self.get_tracker(doc_id)
        return tracker.update_cursor(
            user_id, line, column, selection_start, selection_end, user_name
        )
    
    def get_document_cursors(self, doc_id: str) -> List[CursorPosition]:
        """Get all cursors for a document"""
        if doc_id in self.trackers:
            return self.trackers[doc_id].get_all_cursors()
        return []
    
    def remove_user_from_document(self, doc_id: str, user_id: str) -> bool:
        """Remove user from a specific document"""
        if doc_id in self.trackers:
            return self.trackers[doc_id].remove_user(user_id)
        return False
    
    def remove_user_from_all_documents(self, user_id: str) -> List[str]:
        """Remove user from all documents"""
        removed_docs = []
        
        for doc_id, tracker in self.trackers.items():
            if tracker.remove_user(user_id):
                removed_docs.append(doc_id)
        
        return removed_docs
    
    def get_user_documents(self, user_id: str) -> List[str]:
        """Get all documents a user is active in"""
        user_docs = []
        
        for doc_id, tracker in self.trackers.items():
            if user_id in tracker.cursors and tracker.cursors[user_id].is_active:
                user_docs.append(doc_id)
        
        return user_docs
    
    def cleanup_inactive_users(self) -> Dict[str, int]:
        """Clean up inactive users across all documents"""
        cleanup_results = {}
        
        for doc_id, tracker in self.trackers.items():
            removed_count = tracker.cleanup_inactive_users()
            cleanup_results[doc_id] = removed_count
        
        return cleanup_results
    
    def get_global_statistics(self) -> Dict[str, Any]:
        """Get global cursor tracking statistics"""
        total_users = 0
        active_users = 0
        document_stats = {}
        
        for doc_id, tracker in self.trackers.items():
            stats = tracker.get_statistics()
            document_stats[doc_id] = stats
            total_users += stats['total_users']
            active_users += stats['active_users']
        
        return {
            'total_documents': len(self.trackers),
            'total_users': total_users,
            'active_users': active_users,
            'document_stats': document_stats,
            'global_rate_limit': {
                'max_updates_per_second': self.global_rate_limiter.max_updates_per_second,
                'burst_size': self.global_rate_limiter.burst_size
            },
            'timestamp': datetime.utcnow().isoformat()
        }


# Cursor event types for broadcasting
class CursorEventType:
    """Types of cursor events"""
    POSITION_UPDATE = "position_update"
    SELECTION_UPDATE = "selection_update"
    USER_JOINED = "user_joined"
    USER_LEFT = "user_left"
    USER_INACTIVE = "user_inactive"


@dataclass
class CursorEvent:
    """Cursor event for broadcasting"""
    type: str
    doc_id: str
    user_id: str
    data: Dict[str, Any]
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'type': self.type,
            'doc_id': self.doc_id,
            'user_id': self.user_id,
            'data': self.data,
            'timestamp': self.timestamp.isoformat()
        }


class CursorEventBroadcaster:
    """
    Broadcasts cursor events to connected users
    """
    
    def __init__(self):
        self.event_handlers: List[callable] = []
        
    def add_event_handler(self, handler: callable):
        """Add event handler for cursor events"""
        self.event_handlers.append(handler)
    
    def broadcast_event(self, event: CursorEvent):
        """Broadcast cursor event to all handlers"""
        for handler in self.event_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Error in cursor event handler: {e}")
    
    def create_position_event(self, doc_id: str, user_id: str, 
                           cursor_data: Dict[str, Any]) -> CursorEvent:
        """Create cursor position update event"""
        return CursorEvent(
            type=CursorEventType.POSITION_UPDATE,
            doc_id=doc_id,
            user_id=user_id,
            data=cursor_data,
            timestamp=datetime.utcnow()
        )
    
    def create_user_joined_event(self, doc_id: str, user_id: str, 
                               user_info: Dict[str, Any]) -> CursorEvent:
        """Create user joined event"""
        return CursorEvent(
            type=CursorEventType.USER_JOINED,
            doc_id=doc_id,
            user_id=user_id,
            data=user_info,
            timestamp=datetime.utcnow()
        )
    
    def create_user_left_event(self, doc_id: str, user_id: str) -> CursorEvent:
        """Create user left event"""
        return CursorEvent(
            type=CursorEventType.USER_LEFT,
            doc_id=doc_id,
            user_id=user_id,
            data={},
            timestamp=datetime.utcnow()
        )


# Global cursor tracker instance
global_cursor_tracker: Optional[MultiDocumentCursorTracker] = None
cursor_event_broadcaster: Optional[CursorEventBroadcaster] = None


def get_cursor_tracker() -> MultiDocumentCursorTracker:
    """Get global cursor tracker"""
    global global_cursor_tracker
    if global_cursor_tracker is None:
        global_cursor_tracker = MultiDocumentCursorTracker()
    return global_cursor_tracker


def get_event_broadcaster() -> CursorEventBroadcaster:
    """Get global cursor event broadcaster"""
    global cursor_event_broadcaster
    if cursor_event_broadcaster is None:
        cursor_event_broadcaster = CursorEventBroadcaster()
    return cursor_event_broadcaster


# Example usage
if __name__ == "__main__":
    # Test cursor tracking
    tracker = MultiDocumentCursorTracker()
    
    # Test rate limiting
    rate_limiter = CursorRateLimiter(max_updates_per_second=10)
    
    user_id = "test_user"
    
    print("Testing rate limiting:")
    for i in range(15):
        should_update = rate_limiter.should_update(user_id)
        print(f"Update {i+1}: {'Allowed' if should_update else 'Rate limited'}")
        
        if should_update:
            # Update cursor
            tracker.update_cursor("test_doc", user_id, i, i % 80)
    
    # Test cursor tracking
    print(f"\nCursor statistics:")
    stats = tracker.get_global_statistics()
    print(json.dumps(stats, indent=2))
    
    # Test cleanup
    print(f"\nCleaning up inactive users:")
    cleanup_results = tracker.cleanup_inactive_users()
    print(f"Cleaned up users: {cleanup_results}")
    
    # Test event broadcasting
    broadcaster = CursorEventBroadcaster()
    
    def event_handler(event: CursorEvent):
        print(f"Event: {event.type} for user {event.user_id} in doc {event.doc_id}")
    
    broadcaster.add_event_handler(event_handler)
    
    # Broadcast events
    event = broadcaster.create_position_event("test_doc", "test_user", {"line": 5, "column": 10})
    broadcaster.broadcast_event(event)
    
    print("\nCursor tracking test completed!")
