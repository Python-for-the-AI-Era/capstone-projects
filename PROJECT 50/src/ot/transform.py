"""
Operational Transformation system for real-time collaborative editing.

This module implements conflict resolution and transformation algorithms
to handle concurrent edits in a collaborative code editor.
"""

import asyncio
import time
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import structlog

from ..models.document import Operation, OperationType, CursorPosition

logger = structlog.get_logger()


class TransformType(str, Enum):
    """Types of operational transformations."""
    INSERT_INSERT = "insert_insert"
    INSERT_DELETE = "insert_delete"
    DELETE_INSERT = "delete_insert"
    DELETE_DELETE = "delete_delete"


@dataclass
class TransformResult:
    """Result of an operational transformation."""
    
    operation: Operation
    success: bool
    transformed: bool
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'operation': self.operation.to_dict(),
            'success': self.success,
            'transformed': self.transformed,
            'error_message': self.error_message
        }


class OperationalTransformer:
    """
    Handles operational transformation for conflict resolution.
    
    Implements CRDT-like behavior for real-time collaborative editing.
    """
    
    def __init__(self):
        """Initialize the operational transformer."""
        self.transform_history: Dict[str, List[Operation]] = {}
        logger.info("Operational transformer initialized")
    
    async def transform_operation(
        self, 
        operation: Operation, 
        concurrent_operations: List[Operation],
        document_state: str
    ) -> TransformResult:
        """
        Transform an operation against concurrent operations.
        
        Args:
            operation: The operation to transform
            concurrent_operations: List of concurrent operations
            document_state: Current document state
            
        Returns:
            Transform result
        """
        try:
            transformed_op = operation
            
            # Apply transformations in order of timestamp
            sorted_concurrent = sorted(
                concurrent_operations, 
                key=lambda op: op.timestamp
            )
            
            for concurrent_op in sorted_concurrent:
                if concurrent_op.id == operation.id:
                    continue  # Skip self
                
                # Don't transform if operations are from the same user
                if concurrent_op.user_id == operation.user_id:
                    continue
                
                transform_result = await self._transform_pair(
                    transformed_op, 
                    concurrent_op, 
                    document_state
                )
                
                if not transform_result.success:
                    return TransformResult(
                        operation=operation,
                        success=False,
                        transformed=False,
                        error_message=transform_result.error_message
                    )
                
                transformed_op = transform_result.operation
            
            return TransformResult(
                operation=transformed_op,
                success=True,
                transformed=transformed_op.position != operation.position
            )
            
        except Exception as e:
            logger.error("Error transforming operation", 
                        operation_id=operation.id,
                        error=str(e))
            return TransformResult(
                operation=operation,
                success=False,
                transformed=False,
                error_message=str(e)
            )
    
    async def _transform_pair(
        self, 
        op1: Operation, 
        op2: Operation, 
        document_state: str
    ) -> TransformResult:
        """
        Transform a pair of operations.
        
        Args:
            op1: First operation
            op2: Second operation
            document_state: Current document state
            
        Returns:
            Transform result
        """
        try:
            # Determine transform type
            transform_type = self._get_transform_type(op1, op2)
            
            if transform_type == TransformType.INSERT_INSERT:
                return await self._transform_insert_insert(op1, op2)
            elif transform_type == TransformType.INSERT_DELETE:
                return await self._transform_insert_delete(op1, op2)
            elif transform_type == TransformType.DELETE_INSERT:
                return await self._transform_delete_insert(op1, op2)
            elif transform_type == TransformType.DELETE_DELETE:
                return await self._transform_delete_delete(op1, op2)
            else:
                return TransformResult(
                    operation=op1,
                    success=True,
                    transformed=False
                )
                
        except Exception as e:
            logger.error("Error transforming operation pair", 
                        op1_id=op1.id,
                        op2_id=op2.id,
                        error=str(e))
            return TransformResult(
                operation=op1,
                success=False,
                transformed=False,
                error_message=str(e)
            )
    
    def _get_transform_type(self, op1: Operation, op2: Operation) -> TransformType:
        """Get the type of transformation needed."""
        if op1.type == OperationType.INSERT and op2.type == OperationType.INSERT:
            return TransformType.INSERT_INSERT
        elif op1.type == OperationType.INSERT and op2.type == OperationType.DELETE:
            return TransformType.INSERT_DELETE
        elif op1.type == OperationType.DELETE and op2.type == OperationType.INSERT:
            return TransformType.DELETE_INSERT
        elif op1.type == OperationType.DELETE and op2.type == OperationType.DELETE:
            return TransformType.DELETE_DELETE
        else:
            # Default case
            return TransformType.INSERT_INSERT
    
    async def _transform_insert_insert(self, op1: Operation, op2: Operation) -> TransformResult:
        """
        Transform two insert operations.
        
        If both operations insert at the same position, the one with
        the earlier timestamp gets priority.
        """
        if op1.position < op2.position:
            # op1 comes before op2, no transformation needed
            return TransformResult(
                operation=op1,
                success=True,
                transformed=False
            )
        elif op1.position > op2.position:
            # op1 comes after op2, adjust position
            transformed_op = Operation(
                id=op1.id,
                type=op1.type,
                position=op1.position + len(op2.content or ""),
                content=op1.content,
                length=op1.length,
                attributes=op1.attributes,
                user_id=op1.user_id,
                timestamp=op1.timestamp,
                session_id=op1.session_id
            )
            return TransformResult(
                operation=transformed_op,
                success=True,
                transformed=True
            )
        else:
            # Same position - use timestamp to decide order
            if op1.timestamp < op2.timestamp:
                # op1 comes first, no transformation
                return TransformResult(
                    operation=op1,
                    success=True,
                    transformed=False
                )
            elif op1.timestamp > op2.timestamp:
                # op1 comes after, adjust position
                transformed_op = Operation(
                    id=op1.id,
                    type=op1.type,
                    position=op1.position + len(op2.content or ""),
                    content=op1.content,
                    length=op1.length,
                    attributes=op1.attributes,
                    user_id=op1.user_id,
                    timestamp=op1.timestamp,
                    session_id=op1.session_id
                )
                return TransformResult(
                    operation=transformed_op,
                    success=True,
                    transformed=True
                )
            else:
                # Same timestamp - use user ID as tiebreaker
                if op1.user_id < op2.user_id:
                    return TransformResult(
                        operation=op1,
                        success=True,
                        transformed=False
                    )
                else:
                    transformed_op = Operation(
                        id=op1.id,
                        type=op1.type,
                        position=op1.position + len(op2.content or ""),
                        content=op1.content,
                        length=op1.length,
                        attributes=op1.attributes,
                        user_id=op1.user_id,
                        timestamp=op1.timestamp,
                        session_id=op1.session_id
                    )
                    return TransformResult(
                        operation=transformed_op,
                        success=True,
                        transformed=True
                    )
    
    async def _transform_insert_delete(self, op1: Operation, op2: Operation) -> TransformResult:
        """
        Transform insert and delete operations.
        
        If the delete operation removes characters before the insert,
        the insert position needs to be adjusted.
        """
        delete_end = op2.position + (op2.length or 1)
        
        if op1.position <= op2.position:
            # Insert comes before delete, no transformation needed
            return TransformResult(
                operation=op1,
                success=True,
                transformed=False
            )
        elif op1.position >= delete_end:
            # Insert comes after delete, adjust position
            transformed_op = Operation(
                id=op1.id,
                type=op1.type,
                position=op1.position - (op2.length or 1),
                content=op1.content,
                length=op1.length,
                attributes=op1.attributes,
                user_id=op1.user_id,
                timestamp=op1.timestamp,
                session_id=op1.session_id
            )
            return TransformResult(
                operation=transformed_op,
                success=True,
                transformed=True
            )
        else:
            # Insert is within the deleted range - this is a conflict
            # For simplicity, we'll place the insert at the delete position
            transformed_op = Operation(
                id=op1.id,
                type=op1.type,
                position=op2.position,
                content=op1.content,
                length=op1.length,
                attributes=op1.attributes,
                user_id=op1.user_id,
                timestamp=op1.timestamp,
                session_id=op1.session_id
            )
            return TransformResult(
                operation=transformed_op,
                success=True,
                transformed=True
            )
    
    async def _transform_delete_insert(self, op1: Operation, op2: Operation) -> TransformResult:
        """
        Transform delete and insert operations.
        
        If the insert operation adds characters before the delete,
        the delete position needs to be adjusted.
        """
        if op1.position < op2.position:
            # Delete comes before insert, no transformation needed
            return TransformResult(
                operation=op1,
                success=True,
                transformed=False
            )
        elif op1.position >= op2.position:
            # Delete comes after or at insert position, adjust
            transformed_op = Operation(
                id=op1.id,
                type=op1.type,
                position=op1.position + len(op2.content or ""),
                content=op1.content,
                length=op1.length,
                attributes=op1.attributes,
                user_id=op1.user_id,
                timestamp=op1.timestamp,
                session_id=op1.session_id
            )
            return TransformResult(
                operation=transformed_op,
                success=True,
                transformed=True
            )
        else:
            # This case shouldn't happen with proper ordering
            return TransformResult(
                operation=op1,
                success=True,
                transformed=False
            )
    
    async def _transform_delete_delete(self, op1: Operation, op2: Operation) -> TransformResult:
        """
        Transform two delete operations.
        
        If both operations delete overlapping ranges, the second operation
        needs to be adjusted to account for the first deletion.
        """
        op1_end = op1.position + (op1.length or 1)
        op2_end = op2.position + (op2.length or 1)
        
        if op1_end <= op2.position:
            # op1 ends before op2 starts, no transformation needed
            return TransformResult(
                operation=op1,
                success=True,
                transformed=False
            )
        elif op2_end <= op1.position:
            # op2 ends before op1 starts, adjust op1 position
            transformed_op = Operation(
                id=op1.id,
                type=op1.type,
                position=op1.position - (op2.length or 1),
                content=op1.content,
                length=op1.length,
                attributes=op1.attributes,
                user_id=op1.user_id,
                timestamp=op1.timestamp,
                session_id=op1.session_id
            )
            return TransformResult(
                operation=transformed_op,
                success=True,
                transformed=True
            )
        else:
            # Overlapping deletions - this is complex
            # For simplicity, we'll adjust the position and length
            overlap_start = max(op1.position, op2.position)
            overlap_end = min(op1_end, op2_end)
            overlap_length = overlap_end - overlap_start
            
            transformed_op = Operation(
                id=op1.id,
                type=op1.type,
                position=op1.position,
                content=op1.content,
                length=max(1, (op1.length or 1) - overlap_length),
                attributes=op1.attributes,
                user_id=op1.user_id,
                timestamp=op1.timestamp,
                session_id=op1.session_id
            )
            return TransformResult(
                operation=transformed_op,
                success=True,
                transformed=True
            )
    
    async def transform_cursor_position(
        self, 
        cursor: CursorPosition, 
        operations: List[Operation]
    ) -> CursorPosition:
        """
        Transform cursor position against operations.
        
        Args:
            cursor: Original cursor position
            operations: List of operations to apply
            
        Returns:
            Transformed cursor position
        """
        try:
            transformed_cursor = cursor
            
            # Sort operations by timestamp
            sorted_ops = sorted(operations, key=lambda op: op.timestamp)
            
            for operation in sorted_ops:
                if operation.user_id == cursor.user_id:
                    continue  # Skip own operations
                
                transformed_cursor = await self._transform_cursor_with_operation(
                    transformed_cursor, operation
                )
            
            return transformed_cursor
            
        except Exception as e:
            logger.error("Error transforming cursor position", 
                        user_id=cursor.user_id,
                        error=str(e))
            return cursor
    
    async def _transform_cursor_with_operation(
        self, 
        cursor: CursorPosition, 
        operation: Operation
    ) -> CursorPosition:
        """
        Transform cursor position with a single operation.
        
        Args:
            cursor: Cursor position
            operation: Operation to apply
            
        Returns:
            Transformed cursor position
        """
        # Convert line/column to absolute position (simplified)
        # In practice, this would need proper line/column calculation
        cursor_pos = cursor.line * 100 + cursor.column  # Simplified
        
        if operation.type == OperationType.INSERT:
            if operation.position <= cursor_pos:
                # Insert is before or at cursor, move cursor right
                cursor_pos += len(operation.content or "")
        elif operation.type == OperationType.DELETE:
            if operation.position < cursor_pos:
                delete_end = operation.position + (operation.length or 1)
                if delete_end <= cursor_pos:
                    # Delete is entirely before cursor, move cursor left
                    cursor_pos -= (operation.length or 1)
                else:
                    # Delete includes cursor, move cursor to delete position
                    cursor_pos = operation.position
        
        # Convert back to line/column (simplified)
        new_line = cursor_pos // 100
        new_column = cursor_pos % 100
        
        return CursorPosition(
            user_id=cursor.user_id,
            session_id=cursor.session_id,
            line=new_line,
            column=new_column,
            selection_start=cursor.selection_start,
            selection_end=cursor.selection_end,
            timestamp=cursor.timestamp,
            user_name=cursor.user_name,
            user_color=cursor.user_color
        )
    
    def add_operation_to_history(self, document_id: str, operation: Operation):
        """
        Add operation to transformation history.
        
        Args:
            document_id: Document identifier
            operation: Operation to add
        """
        if document_id not in self.transform_history:
            self.transform_history[document_id] = []
        
        self.transform_history[document_id].append(operation)
        
        # Keep only recent operations (last 1000)
        if len(self.transform_history[document_id]) > 1000:
            self.transform_history[document_id] = self.transform_history[document_id][-1000:]
    
    def get_operation_history(self, document_id: str, since_timestamp: float = None) -> List[Operation]:
        """
        Get operation history for a document.
        
        Args:
            document_id: Document identifier
            since_timestamp: Get operations since this timestamp
            
        Returns:
            List of operations
        """
        if document_id not in self.transform_history:
            return []
        
        operations = self.transform_history[document_id]
        
        if since_timestamp:
            operations = [op for op in operations if op.timestamp >= since_timestamp]
        
        return operations
    
    def clear_operation_history(self, document_id: str):
        """
        Clear operation history for a document.
        
        Args:
            document_id: Document identifier
        """
        if document_id in self.transform_history:
            del self.transform_history[document_id]
        
        logger.info("Operation history cleared", document_id=document_id)


class ConflictResolver:
    """
    Resolves conflicts in collaborative editing.
    
    Implements last-writer-wins for cursor positions and
    operational transformation for text conflicts.
    """
    
    def __init__(self, transformer: OperationalTransformer):
        """
        Initialize conflict resolver.
        
        Args:
            transformer: Operational transformer instance
        """
        self.transformer = transformer
        self.conflict_history: Dict[str, List[Dict[str, Any]]] = {}
        logger.info("Conflict resolver initialized")
    
    async def resolve_operation_conflict(
        self, 
        document_id: str, 
        operations: List[Operation]
    ) -> List[Operation]:
        """
        Resolve conflicts between operations.
        
        Args:
            document_id: Document identifier
            operations: List of conflicting operations
            
        Returns:
            List of resolved operations
        """
        try:
            resolved_operations = []
            
            # Sort operations by timestamp
            sorted_ops = sorted(operations, key=lambda op: op.timestamp)
            
            for operation in sorted_ops:
                # Transform against previously resolved operations
                transform_result = await self.transformer.transform_operation(
                    operation, resolved_operations, ""
                )
                
                if transform_result.success:
                    resolved_operations.append(transform_result.operation)
                    
                    # Log conflict if transformation occurred
                    if transform_result.transformed:
                        self._log_conflict(document_id, operation, resolved_operations)
                else:
                    logger.warning("Operation conflict resolution failed", 
                                 operation_id=operation.id,
                                 error=transform_result.error_message)
            
            return resolved_operations
            
        except Exception as e:
            logger.error("Error resolving operation conflicts", 
                        document_id=document_id,
                        error=str(e))
            return operations
    
    async def resolve_cursor_conflict(
        self, 
        document_id: str, 
        cursors: List[CursorPosition]
    ) -> List[CursorPosition]:
        """
        Resolve conflicts between cursor positions.
        
        Args:
            document_id: Document identifier
            cursors: List of cursor positions
            
        Returns:
            List of resolved cursor positions
        """
        try:
            resolved_cursors = []
            
            # Group cursors by session
            session_cursors = {}
            for cursor in cursors:
                if cursor.session_id not in session_cursors:
                    session_cursors[cursor.session_id] = []
                session_cursors[cursor.session_id].append(cursor)
            
            # For each session, keep only the latest cursor position
            for session_id, session_cursor_list in session_cursors.items():
                # Sort by timestamp and keep the latest
                latest_cursor = max(session_cursor_list, key=lambda c: c.timestamp)
                resolved_cursors.append(latest_cursor)
            
            return resolved_cursors
            
        except Exception as e:
            logger.error("Error resolving cursor conflicts", 
                        document_id=document_id,
                        error=str(e))
            return cursors
    
    def _log_conflict(
        self, 
        document_id: str, 
        operation: Operation, 
        resolved_operations: List[Operation]
    ):
        """
        Log a conflict resolution.
        
        Args:
            document_id: Document identifier
            operation: Original operation
            resolved_operations: List of resolved operations
        """
        conflict_record = {
            'timestamp': time.time(),
            'operation_id': operation.id,
            'operation_type': operation.type.value,
            'original_position': operation.position,
            'resolved_operations': len(resolved_operations),
            'user_id': operation.user_id
        }
        
        if document_id not in self.conflict_history:
            self.conflict_history[document_id] = []
        
        self.conflict_history[document_id].append(conflict_record)
        
        # Keep only recent conflicts (last 100)
        if len(self.conflict_history[document_id]) > 100:
            self.conflict_history[document_id] = self.conflict_history[document_id][-100]
        
        logger.info("Conflict resolved", 
                   document_id=document_id,
                   operation_id=operation.id,
                   user_id=operation.user_id)
    
    def get_conflict_history(self, document_id: str) -> List[Dict[str, Any]]:
        """
        Get conflict history for a document.
        
        Args:
            document_id: Document identifier
            
        Returns:
            List of conflict records
        """
        return self.conflict_history.get(document_id, [])
    
    def get_conflict_stats(self, document_id: str) -> Dict[str, Any]:
        """
        Get conflict statistics for a document.
        
        Args:
            document_id: Document identifier
            
        Returns:
            Conflict statistics
        """
        conflicts = self.get_conflict_history(document_id)
        
        if not conflicts:
            return {
                'total_conflicts': 0,
                'conflicts_by_type': {},
                'conflicts_by_user': {},
                'recent_conflicts': []
            }
        
        # Analyze conflicts
        conflicts_by_type = {}
        conflicts_by_user = {}
        
        for conflict in conflicts:
            op_type = conflict['operation_type']
            user_id = conflict['user_id']
            
            conflicts_by_type[op_type] = conflicts_by_type.get(op_type, 0) + 1
            conflicts_by_user[user_id] = conflicts_by_user.get(user_id, 0) + 1
        
        return {
            'total_conflicts': len(conflicts),
            'conflicts_by_type': conflicts_by_type,
            'conflicts_by_user': conflicts_by_user,
            'recent_conflicts': conflicts[-10:]  # Last 10 conflicts
        }
