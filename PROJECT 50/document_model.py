"""
Document Model and Operational Transformation for Real-Time Collaborative Editor
Implements OT (Operational Transformation) logic for conflict-free collaborative editing
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Optional, Union, Any
from dataclasses import dataclass, field
from enum import Enum
import json
import uuid

logger = logging.getLogger(__name__)


class OperationType(Enum):
    """Types of operations that can be applied to a document"""
    INSERT = "insert"
    DELETE = "delete"
    RETAIN = "retain"
    CURSOR = "cursor"


@dataclass
class Operation:
    """
    Represents an operation that transforms a document state
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: OperationType = OperationType.INSERT
    char: str = ""
    position: int = 0
    user_id: str = ""
    version: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    length: int = 1  # For delete operations
    cursor_data: Optional[Dict[str, Any]] = None  # For cursor operations
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert operation to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'type': self.type.value,
            'char': self.char,
            'position': self.position,
            'user_id': self.user_id,
            'version': self.version,
            'timestamp': self.timestamp.isoformat(),
            'length': self.length,
            'cursor_data': self.cursor_data
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Operation':
        """Create operation from dictionary"""
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            type=OperationType(data.get('type', 'insert')),
            char=data.get('char', ''),
            position=data.get('position', 0),
            user_id=data.get('user_id', ''),
            version=data.get('version', 0),
            timestamp=datetime.fromisoformat(data.get('timestamp', datetime.utcnow().isoformat())),
            length=data.get('length', 1),
            cursor_data=data.get('cursor_data')
        )
    
    def is_text_operation(self) -> bool:
        """Check if this is a text-changing operation"""
        return self.type in [OperationType.INSERT, OperationType.DELETE]
    
    def is_cursor_operation(self) -> bool:
        """Check if this is a cursor operation"""
        return self.type == OperationType.CURSOR


@dataclass
class DocumentState:
    """
    Represents the current state of a document
    """
    content: str = ""
    version: int = 0
    operations: List[Operation] = field(default_factory=list)
    user_cursors: Dict[str, Dict[str, int]] = field(default_factory=dict)  # user_id -> {line, column}
    last_modified: datetime = field(default_factory=datetime.utcnow)
    
    def apply_operation(self, op: Operation) -> 'DocumentState':
        """Apply an operation to the document state"""
        if op.type == OperationType.INSERT:
            return self._apply_insert(op)
        elif op.type == OperationType.DELETE:
            return self._apply_delete(op)
        elif op.type == OperationType.CURSOR:
            return self._apply_cursor(op)
        else:
            logger.warning(f"Unknown operation type: {op.type}")
            return self
    
    def _apply_insert(self, op: Operation) -> 'DocumentState':
        """Apply insert operation"""
        # Ensure position is within bounds
        position = max(0, min(op.position, len(self.content)))
        
        # Insert character at position
        new_content = (
            self.content[:position] + 
            op.char + 
            self.content[position:]
        )
        
        return DocumentState(
            content=new_content,
            version=self.version + 1,
            operations=self.operations + [op],
            user_cursors=self.user_cursors,
            last_modified=datetime.utcnow()
        )
    
    def _apply_delete(self, op: Operation) -> 'DocumentState':
        """Apply delete operation"""
        # Ensure position is within bounds
        position = max(0, min(op.position, len(self.content)))
        
        # Delete characters at position
        end_position = min(position + op.length, len(self.content))
        new_content = (
            self.content[:position] + 
            self.content[end_position:]
        )
        
        return DocumentState(
            content=new_content,
            version=self.version + 1,
            operations=self.operations + [op],
            user_cursors=self.user_cursors,
            last_modified=datetime.utcnow()
        )
    
    def _apply_cursor(self, op: Operation) -> 'DocumentState':
        """Apply cursor operation"""
        if op.cursor_data:
            self.user_cursors[op.user_id] = op.cursor_data
        
        return DocumentState(
            content=self.content,
            version=self.version,
            operations=self.operations + [op],
            user_cursors=self.user_cursors,
            last_modified=datetime.utcnow()
        )
    
    def get_operations_since(self, version: int) -> List[Operation]:
        """Get all operations since a specific version"""
        return [op for op in self.operations if op.version > version]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert document state to dictionary"""
        return {
            'content': self.content,
            'version': self.version,
            'operations': [op.to_dict() for op in self.operations],
            'user_cursors': self.user_cursors,
            'last_modified': self.last_modified.isoformat()
        }


class OperationalTransform:
    """
    Implements operational transformation for conflict resolution
    """
    
    @staticmethod
    def transform(op_a: Operation, op_b: Operation) -> Operation:
        """
        Transform operation A as if operation B has already been applied
        This is the core of conflict resolution in collaborative editing
        """
        if op_a.type == OperationType.INSERT:
            return OperationalTransform._transform_insert(op_a, op_b)
        elif op_a.type == OperationType.DELETE:
            return OperationalTransform._transform_delete(op_a, op_b)
        elif op_a.type == OperationType.CURSOR:
            return OperationalTransform._transform_cursor(op_a, op_b)
        else:
            return op_a
    
    @staticmethod
    def _transform_insert(op_a: Operation, op_b: Operation) -> Operation:
        """Transform insert operation"""
        if op_b.type == OperationType.INSERT:
            if op_a.position >= op_b.position:
                # Insert B comes before A, so shift A's position
                op_a.position += len(op_b.char)
        elif op_b.type == OperationType.DELETE:
            if op_a.position >= op_b.position:
                # Delete B comes before A, so shift A's position
                op_a.position -= op_b.length
        
        return op_a
    
    @staticmethod
    def _transform_delete(op_a: Operation, op_b: Operation) -> Operation:
        """Transform delete operation"""
        if op_b.type == OperationType.INSERT:
            if op_a.position >= op_b.position:
                # Insert B comes before A, so shift A's position
                op_a.position += len(op_b.char)
        elif op_b.type == OperationType.DELETE:
            if op_a.position >= op_b.position:
                # Delete B comes before A, so shift A's position
                op_a.position -= op_b.length
        
        return op_a
    
    @staticmethod
    def _transform_cursor(op_a: Operation, op_b: Operation) -> Operation:
        """Transform cursor operation (no transformation needed for cursors)"""
        return op_a
    
    @staticmethod
    def transform_multiple(ops: List[Operation], base_version: int) -> List[Operation]:
        """
        Transform multiple operations against a base version
        Returns operations transformed as if they were applied sequentially
        """
        transformed_ops = []
        
        for i, op in enumerate(ops):
            # Transform op against all previous ops
            for prev_op in ops[:i]:
                op = OperationalTransform.transform(op, prev_op)
            transformed_ops.append(op)
        
        return transformed_ops
    
    @staticmethod
    def resolve_conflicts(ops: List[Operation]) -> List[Operation]:
        """
        Resolve conflicts between operations
        Implements last-writer-wins for cursor positions
        """
        # Group operations by type
        text_ops = [op for op in ops if op.is_text_operation()]
        cursor_ops = [op for op in ops if op.is_cursor_operation()]
        
        # Transform text operations
        transformed_text_ops = []
        for i, op in enumerate(text_ops):
            # Transform against all previous operations
            for prev_op in text_ops[:i]:
                op = OperationalTransform.transform(op, prev_op)
            transformed_text_ops.append(op)
        
        # For cursor operations, apply last-writer-wins
        cursor_ops_by_user = {}
        for op in cursor_ops:
            cursor_ops_by_user[op.user_id] = op  # Last one wins
        
        return transformed_text_ops + list(cursor_ops_by_user.values())


class DocumentManager:
    """
    Manages document state and operations
    """
    
    def __init__(self):
        self.documents: Dict[str, DocumentState] = {}
        self.operation_history: Dict[str, List[Operation]] = {}
        
    def create_document(self, doc_id: str, initial_content: str = "") -> DocumentState:
        """Create a new document"""
        doc = DocumentState(content=initial_content)
        self.documents[doc_id] = doc
        self.operation_history[doc_id] = []
        logger.info(f"Created document {doc_id} with {len(initial_content)} characters")
        return doc
    
    def get_document(self, doc_id: str) -> Optional[DocumentState]:
        """Get document state"""
        return self.documents.get(doc_id)
    
    def apply_operation(self, doc_id: str, op: Operation) -> bool:
        """
        Apply an operation to a document
        Returns True if successful, False if document not found
        """
        doc = self.get_document(doc_id)
        if not doc:
            logger.warning(f"Document {doc_id} not found")
            return False
        
        # Apply operation
        new_doc = doc.apply_operation(op)
        self.documents[doc_id] = new_doc
        self.operation_history[doc_id].append(op)
        
        # Keep operation history manageable (last 1000 ops)
        if len(self.operation_history[doc_id]) > 1000:
            self.operation_history[doc_id] = self.operation_history[doc_id][-1000:]
        
        return True
    
    def apply_operations(self, doc_id: str, ops: List[Operation]) -> bool:
        """
        Apply multiple operations to a document
        Returns True if successful, False if document not found
        """
        doc = self.get_document(doc_id)
        if not doc:
            logger.warning(f"Document {doc_id} not found")
            return False
        
        # Resolve conflicts and transform operations
        transformed_ops = OperationalTransform.resolve_conflicts(ops)
        
        # Apply operations sequentially
        for op in transformed_ops:
            if not self.apply_operation(doc_id, op):
                return False
        
        return True
    
    def get_operations_since(self, doc_id: str, version: int) -> List[Operation]:
        """Get operations since a specific version"""
        doc = self.get_document(doc_id)
        if not doc:
            return []
        
        return doc.get_operations_since(version)
    
    def get_user_cursors(self, doc_id: str) -> Dict[str, Dict[str, int]]:
        """Get all user cursors for a document"""
        doc = self.get_document(doc_id)
        if not doc:
            return {}
        
        return doc.user_cursors
    
    def get_document_info(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive document information"""
        doc = self.get_document(doc_id)
        if not doc:
            return None
        
        return {
            'doc_id': doc_id,
            'content': doc.content,
            'version': doc.version,
            'length': len(doc.content),
            'operation_count': len(doc.operations),
            'user_count': len(doc.user_cursors),
            'user_cursors': doc.user_cursors,
            'last_modified': doc.last_modified.isoformat()
        }
    
    def reset_document(self, doc_id: str, content: str = "") -> bool:
        """Reset document to initial state"""
        doc = DocumentState(content=content)
        self.documents[doc_id] = doc
        self.operation_history[doc_id] = []
        logger.info(f"Reset document {doc_id}")
        return True
    
    def delete_document(self, doc_id: str) -> bool:
        """Delete a document"""
        if doc_id in self.documents:
            del self.documents[doc_id]
            del self.operation_history[doc_id]
            logger.info(f"Deleted document {doc_id}")
            return True
        return False


# Utility functions
def create_insert_operation(position: int, char: str, user_id: str) -> Operation:
    """Create an insert operation"""
    return Operation(
        type=OperationType.INSERT,
        char=char,
        position=position,
        user_id=user_id
    )


def create_delete_operation(position: int, length: int, user_id: str) -> Operation:
    """Create a delete operation"""
    return Operation(
        type=OperationType.DELETE,
        length=length,
        position=position,
        user_id=user_id
    )


def create_cursor_operation(user_id: str, line: int, column: int) -> Operation:
    """Create a cursor operation"""
    return Operation(
        type=OperationType.CURSOR,
        user_id=user_id,
        cursor_data={'line': line, 'column': column}
    )


def position_to_line_column(content: str, position: int) -> tuple[int, int]:
    """Convert character position to line and column numbers"""
    if position <= 0:
        return (0, 0)
    
    lines = content[:position].split('\n')
    line = len(lines) - 1
    column = len(lines[-1])
    
    return (line, column)


def line_column_to_position(content: str, line: int, column: int) -> int:
    """Convert line and column numbers to character position"""
    lines = content.split('\n')
    
    if line >= len(lines):
        return len(content)
    
    # Sum lengths of all lines before the target line
    position = sum(len(l) + 1 for l in lines[:line])  # +1 for newline
    position += min(column, len(lines[line]))
    
    return min(position, len(content))


# Example usage
if __name__ == "__main__":
    # Create document manager
    doc_manager = DocumentManager()
    
    # Create a document
    doc_id = "test_doc"
    doc = doc_manager.create_document(doc_id, "Hello World")
    print(f"Created document: {doc.content}")
    
    # Apply operations
    op1 = create_insert_operation(5, " ", "user1")
    op2 = create_insert_operation(6, "Python", "user2")
    
    doc_manager.apply_operation(doc_id, op1)
    print(f"After op1: {doc_manager.get_document(doc_id).content}")
    
    doc_manager.apply_operation(doc_id, op2)
    print(f"After op2: {doc_manager.get_document(doc_id).content}")
    
    # Apply cursor operation
    cursor_op = create_cursor_operation("user1", 0, 10)
    doc_manager.apply_operation(doc_id, cursor_op)
    
    print(f"Cursors: {doc_manager.get_user_cursors(doc_id)}")
    print(f"Document info: {doc_manager.get_document_info(doc_id)}")
    
    # Test operational transformation
    ops = [
        create_insert_operation(5, " ", "user1"),
        create_insert_operation(5, "A", "user2"),
        create_insert_operation(6, "B", "user3")
    ]
    
    transformed = OperationalTransform.resolve_conflicts(ops)
    print(f"Transformed {len(transformed)} operations")
    
    # Apply transformed operations
    doc_manager.reset_document(doc_id, "Hello World")
    doc_manager.apply_operations(doc_id, transformed)
    print(f"Final content: {doc_manager.get_document(doc_id).content}")
