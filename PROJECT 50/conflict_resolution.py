"""
Advanced Conflict Resolution and Operational Transformation
Implements sophisticated OT algorithms for real-time collaborative editing
"""

import asyncio
import logging
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json

from document_model import Operation, OperationType, DocumentState, OperationalTransform

logger = logging.getLogger(__name__)


class ConflictType(Enum):
    """Types of conflicts that can occur"""
    CONCURRENT_INSERT = "concurrent_insert"
    CONCURRENT_DELETE = "concurrent_delete"
    INSERT_DELETE_CONFLICT = "insert_delete_conflict"
    CURSOR_CONFLICT = "cursor_conflict"
    VERSION_MISMATCH = "version_mismatch"


@dataclass
class Conflict:
    """Represents a conflict between operations"""
    type: ConflictType
    operations: List[Operation]
    resolved_operations: List[Operation] = field(default_factory=list)
    resolution_strategy: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'type': self.type.value,
            'operations': [op.to_dict() for op in self.operations],
            'resolved_operations': [op.to_dict() for op in self.resolved_operations],
            'resolution_strategy': self.resolution_strategy,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class OperationQueue:
    """Queue for managing operations with priority and ordering"""
    operations: List[Operation] = field(default_factory=list)
    max_size: int = 1000
    
    def add(self, operation: Operation) -> bool:
        """Add operation to queue"""
        if len(self.operations) >= self.max_size:
            # Remove oldest operation
            self.operations.pop(0)
        
        self.operations.append(operation)
        return True
    
    def get_since(self, version: int) -> List[Operation]:
        """Get operations since a specific version"""
        return [op for op in self.operations if op.version > version]
    
    def clear_before(self, version: int):
        """Clear operations before a specific version"""
        self.operations = [op for op in self.operations if op.version >= version]


class AdvancedOperationalTransform:
    """
    Advanced operational transformation with sophisticated conflict resolution
    """
    
    def __init__(self):
        self.conflict_history: List[Conflict] = []
        self.operation_queues: Dict[str, OperationQueue] = {}  # doc_id -> queue
        
    def transform_operation(self, doc_id: str, operation: Operation, 
                          current_state: DocumentState) -> Tuple[Operation, Optional[Conflict]]:
        """
        Transform an operation against the current document state
        Returns transformed operation and any conflict that occurred
        """
        # Get operations that need to be transformed against
        ops_to_transform = current_state.get_operations_since(operation.version)
        
        if not ops_to_transform:
            # No transformation needed
            return operation, None
        
        # Check for conflicts
        conflict = self._detect_conflicts(operation, ops_to_transform)
        
        if conflict:
            # Resolve conflict
            resolved_op = self._resolve_conflict(operation, ops_to_transform, conflict)
            return resolved_op, conflict
        else:
            # Apply standard transformation
            transformed_op = operation
            for prev_op in ops_to_transform:
                transformed_op = OperationalTransform.transform(transformed_op, prev_op)
            
            return transformed_op, None
    
    def _detect_conflicts(self, operation: Operation, 
                         previous_operations: List[Operation]) -> Optional[Conflict]:
        """Detect conflicts between operation and previous operations"""
        for prev_op in previous_operations:
            conflict_type = self._classify_conflict(operation, prev_op)
            
            if conflict_type:
                return Conflict(
                    type=conflict_type,
                    operations=[operation, prev_op]
                )
        
        return None
    
    def _classify_conflict(self, op1: Operation, op2: Operation) -> Optional[ConflictType]:
        """Classify the type of conflict between two operations"""
        # Check for version mismatch
        if op1.version < op2.version:
            return ConflictType.VERSION_MISMATCH
        
        # Check for concurrent insert at same position
        if (op1.type == OperationType.INSERT and 
            op2.type == OperationType.INSERT and 
            op1.position == op2.position):
            return ConflictType.CONCURRENT_INSERT
        
        # Check for concurrent delete affecting same position
        if (op1.type == OperationType.DELETE and 
            op2.type == OperationType.DELETE and 
            self._ranges_overlap(op1.position, op1.length, op2.position, op2.length)):
            return ConflictType.CONCURRENT_DELETE
        
        # Check for insert/delete conflict
        if (op1.type == OperationType.INSERT and op2.type == OperationType.DELETE and
            op2.position <= op1.position <= op2.position + op2.length):
            return ConflictType.INSERT_DELETE_CONFLICT
        
        if (op1.type == OperationType.DELETE and op2.type == OperationType.INSERT and
            op1.position <= op2.position <= op1.position + op1.length):
            return ConflictType.INSERT_DELETE_CONFLICT
        
        # Cursor conflicts are handled separately
        if op1.type == OperationType.CURSOR and op2.type == OperationType.CURSOR:
            return ConflictType.CURSOR_CONFLICT
        
        return None
    
    def _ranges_overlap(self, pos1: int, len1: int, pos2: int, len2: int) -> bool:
        """Check if two ranges overlap"""
        return not (pos1 + len1 <= pos2 or pos2 + len2 <= pos1)
    
    def _resolve_conflict(self, operation: Operation, 
                         previous_operations: List[Operation], 
                         conflict: Conflict) -> Operation:
        """Resolve conflict between operations"""
        if conflict.type == ConflictType.CONCURRENT_INSERT:
            return self._resolve_concurrent_insert(operation, previous_operations)
        elif conflict.type == ConflictType.CONCURRENT_DELETE:
            return self._resolve_concurrent_delete(operation, previous_operations)
        elif conflict.type == ConflictType.INSERT_DELETE_CONFLICT:
            return self._resolve_insert_delete_conflict(operation, previous_operations)
        elif conflict.type == ConflictType.VERSION_MISMATCH:
            return self._resolve_version_mismatch(operation, previous_operations)
        elif conflict.type == ConflictType.CURSOR_CONFLICT:
            return self._resolve_cursor_conflict(operation, previous_operations)
        else:
            # Default to standard transformation
            transformed_op = operation
            for prev_op in previous_operations:
                transformed_op = OperationalTransform.transform(transformed_op, prev_op)
            return transformed_op
    
    def _resolve_concurrent_insert(self, operation: Operation, 
                                  previous_operations: List[Operation]) -> Operation:
        """Resolve concurrent insert conflict using timestamp ordering"""
        # Find all concurrent inserts at the same position
        concurrent_inserts = [op for op in previous_operations 
                             if op.type == OperationType.INSERT and op.position == operation.position]
        
        if not concurrent_inserts:
            return operation
        
        # Sort by timestamp (earlier operations come first)
        all_inserts = concurrent_inserts + [operation]
        all_inserts.sort(key=lambda op: op.timestamp)
        
        # Apply operations in timestamp order
        resolved_op = operation
        for i, op in enumerate(all_inserts):
            if op.id == operation.id:
                # This is our operation, calculate its final position
                resolved_op.position = operation.position + i
                break
        
        conflict.resolved_operations = all_inserts
        conflict.resolution_strategy = "timestamp_ordering"
        
        return resolved_op
    
    def _resolve_concurrent_delete(self, operation: Operation, 
                                  previous_operations: List[Operation]) -> Operation:
        """Resolve concurrent delete conflict"""
        # Find overlapping deletes
        overlapping_deletes = [op for op in previous_operations 
                              if op.type == OperationType.DELETE and 
                              self._ranges_overlap(op.position, op.length, 
                                                   operation.position, operation.length)]
        
        if not overlapping_deletes:
            return operation
        
        # Merge overlapping deletes
        all_deletes = overlapping_deletes + [operation]
        
        # Calculate merged delete range
        min_pos = min(op.position for op in all_deletes)
        max_pos = max(op.position + op.length for op in all_deletes)
        
        resolved_op = Operation(
            type=OperationType.DELETE,
            position=min_pos,
            length=max_pos - min_pos,
            user_id=operation.user_id,
            version=operation.version
        )
        
        conflict.resolved_operations = [resolved_op]
        conflict.resolution_strategy = "merge_deletes"
        
        return resolved_op
    
    def _resolve_insert_delete_conflict(self, operation: Operation, 
                                       previous_operations: List[Operation]) -> Operation:
        """Resolve insert/delete conflict"""
        # Find the conflicting delete operation
        delete_op = None
        for op in previous_operations:
            if op.type == OperationType.DELETE:
                if (operation.type == OperationType.INSERT and 
                    op.position <= operation.position <= op.position + op.length):
                    delete_op = op
                    break
                elif (operation.type == OperationType.DELETE and 
                      operation.position <= op.position <= operation.position + operation.length):
                    delete_op = op
                    break
        
        if not delete_op:
            return operation
        
        if operation.type == OperationType.INSERT:
            # Insert into deleted range - operation should be discarded
            conflict.resolved_operations = [delete_op]
            conflict.resolution_strategy = "delete_wins"
            return None  # Discard the insert
        else:
            # Delete overlapping with another delete - merge them
            min_pos = min(operation.position, delete_op.position)
            max_end = max(operation.position + operation.length, 
                         delete_op.position + delete_op.length)
            
            resolved_op = Operation(
                type=OperationType.DELETE,
                position=min_pos,
                length=max_end - min_pos,
                user_id=operation.user_id,
                version=operation.version
            )
            
            conflict.resolved_operations = [resolved_op]
            conflict.resolution_strategy = "merge_deletes"
            
            return resolved_op
    
    def _resolve_version_mismatch(self, operation: Operation, 
                                 previous_operations: List[Operation]) -> Operation:
        """Resolve version mismatch by transforming against all previous operations"""
        resolved_op = operation
        
        # Update version to latest
        latest_version = max(op.version for op in previous_operations) if previous_operations else 0
        resolved_op.version = latest_version + 1
        
        # Transform against all previous operations
        for prev_op in previous_operations:
            resolved_op = OperationalTransform.transform(resolved_op, prev_op)
        
        conflict.resolved_operations = [resolved_op]
        conflict.resolution_strategy = "version_update"
        
        return resolved_op
    
    def _resolve_cursor_conflict(self, operation: Operation, 
                                previous_operations: List[Operation]) -> Operation:
        """Resolve cursor conflict using last-writer-wins"""
        # Find the most recent cursor operation for the same user
        user_cursor_ops = [op for op in previous_operations 
                          if op.type == OperationType.CURSOR and op.user_id == operation.user_id]
        
        if user_cursor_ops:
            # Use the most recent cursor position
            latest_cursor = max(user_cursor_ops, key=lambda op: op.timestamp)
            return latest_cursor
        
        return operation
    
    def get_conflict_history(self, doc_id: str = None, 
                           conflict_type: ConflictType = None) -> List[Conflict]:
        """Get conflict history"""
        conflicts = self.conflict_history
        
        if doc_id:
            # Filter by document (would need to add doc_id to Conflict)
            pass
        
        if conflict_type:
            conflicts = [c for c in conflicts if c.type == conflict_type]
        
        return conflicts
    
    def get_conflict_statistics(self) -> Dict[str, Any]:
        """Get conflict resolution statistics"""
        if not self.conflict_history:
            return {}
        
        total_conflicts = len(self.conflict_history)
        conflicts_by_type = {}
        strategies_used = {}
        
        for conflict in self.conflict_history:
            # Count by type
            if conflict.type not in conflicts_by_type:
                conflicts_by_type[conflict.type] = 0
            conflicts_by_type[conflict.type] += 1
            
            # Count strategies
            if conflict.resolution_strategy:
                if conflict.resolution_strategy not in strategies_used:
                    strategies_used[conflict.resolution_strategy] = 0
                strategies_used[conflict.resolution_strategy] += 1
        
        return {
            'total_conflicts': total_conflicts,
            'conflicts_by_type': {ct.value: count for ct, count in conflicts_by_type.items()},
            'resolution_strategies': strategies_used,
            'resolution_rate': len([c for c in self.conflict_history if c.resolved_operations]) / total_conflicts
        }


class ConflictResolutionManager:
    """
    Manages conflict resolution for multiple documents
    """
    
    def __init__(self):
        self.ot_engine = AdvancedOperationalTransform()
        self.document_versions: Dict[str, int] = {}  # doc_id -> version
        
    def process_operation(self, doc_id: str, operation: Operation, 
                         current_state: DocumentState) -> Tuple[Operation, Optional[Conflict]]:
        """
        Process an operation with conflict resolution
        Returns transformed operation and any conflict
        """
        # Update document version
        if doc_id not in self.document_versions:
            self.document_versions[doc_id] = 0
        
        # Transform operation
        transformed_op, conflict = self.ot_engine.transform_operation(
            doc_id, operation, current_state
        )
        
        if transformed_op:
            # Update version
            self.document_versions[doc_id] = max(
                self.document_versions[doc_id], 
                transformed_op.version
            )
            
            # Store conflict in history
            if conflict:
                self.ot_engine.conflict_history.append(conflict)
        
        return transformed_op, conflict
    
    def get_document_version(self, doc_id: str) -> int:
        """Get current document version"""
        return self.document_versions.get(doc_id, 0)
    
    def get_conflict_report(self, doc_id: str = None) -> Dict[str, Any]:
        """Generate conflict resolution report"""
        stats = self.ot_engine.get_conflict_statistics()
        conflicts = self.ot_engine.get_conflict_history()
        
        if doc_id:
            # Filter conflicts by document (would need enhancement)
            pass
        
        return {
            'document_version': self.get_document_version(doc_id) if doc_id else 'all',
            'conflict_statistics': stats,
            'recent_conflicts': [
                conflict.to_dict() for conflict in conflicts[-10:]
            ],
            'generated_at': datetime.utcnow().isoformat()
        }


# Utility functions for testing
def create_conflict_scenario():
    """Create a test scenario with conflicts"""
    from document_model import create_insert_operation, create_delete_operation
    
    # Scenario 1: Concurrent insert at same position
    op1 = create_insert_operation(5, "A", "user1")
    op2 = create_insert_operation(5, "B", "user2")
    
    # Scenario 2: Insert/delete conflict
    op3 = create_insert_operation(10, "C", "user3")
    op4 = create_delete_operation(8, 5, "user4")
    
    # Scenario 3: Concurrent delete overlap
    op5 = create_delete_operation(15, 10, "user5")
    op6 = create_delete_operation(20, 10, "user6")
    
    return [op1, op2, op3, op4, op5, op6]


if __name__ == "__main__":
    # Test conflict resolution
    from document_model import DocumentManager, DocumentState
    
    # Create test environment
    doc_manager = DocumentManager()
    conflict_manager = ConflictResolutionManager()
    
    # Create document
    doc_id = "test_conflict_doc"
    doc = doc_manager.create_document(doc_id, "Hello World")
    
    print(f"Initial document: {doc.content}")
    
    # Create conflict scenario
    operations = create_conflict_scenario()
    
    # Process operations with conflict resolution
    for i, op in enumerate(operations):
        print(f"\nProcessing operation {i+1}: {op.type.value} at position {op.position}")
        
        # Get current state
        current_state = doc_manager.get_document(doc_id)
        
        # Process with conflict resolution
        resolved_op, conflict = conflict_manager.process_operation(
            doc_id, op, current_state
        )
        
        if resolved_op:
            doc_manager.apply_operation(doc_id, resolved_op)
            print(f"Applied: {resolved_op.type.value}")
            print(f"Document: {doc_manager.get_document(doc_id).content}")
        else:
            print("Operation discarded due to conflict")
        
        if conflict:
            print(f"Conflict detected: {conflict.type.value}")
            print(f"Resolution strategy: {conflict.resolution_strategy}")
    
    # Generate conflict report
    report = conflict_manager.get_conflict_report(doc_id)
    print(f"\nConflict Report:")
    print(json.dumps(report, indent=2))
    
    # Test advanced transformation
    print(f"\nTesting advanced transformation...")
    
    # Create concurrent operations
    concurrent_ops = [
        create_insert_operation(5, "X", "user1"),
        create_insert_operation(5, "Y", "user2"),
        create_insert_operation(5, "Z", "user3")
    ]
    
    # Transform them
    transformed_ops = OperationalTransform.resolve_conflicts(concurrent_ops)
    
    print(f"Original operations: {len(concurrent_ops)}")
    print(f"Transformed operations: {len(transformed_ops)}")
    
    for i, op in enumerate(transformed_ops):
        print(f"  {i+1}: {op.type.value} '{op.char}' at position {op.position}")
