"""
Tests for document model and management.
"""

import pytest
import asyncio
import time
from datetime import datetime
import redis.asyncio as redis
import asyncpg

from src.models.document import DocumentManager, DocumentState, Operation, OperationType, CursorPosition
from src.storage.database import DatabaseManager


@pytest.fixture
async def redis_client():
    """Create Redis client for testing."""
    client = redis.Redis(host="localhost", port=6379, db=1, decode_responses=True)
    # Clear test database
    await client.flushdb()
    yield client
    await client.close()


@pytest.fixture
async def db_pool():
    """Create database pool for testing."""
    db_manager = DatabaseManager()
    db_manager.connection_string = "postgresql://postgres:password@localhost:5432/test_codecollab"
    await db_manager.initialize()
    yield db_manager.pool
    await db_manager.close()


@pytest.fixture
async def document_manager(redis_client, db_pool):
    """Create document manager for testing."""
    manager = DocumentManager(redis_client, db_pool)
    yield manager


class TestDocumentState:
    """Test DocumentState model."""
    
    def test_document_state_creation(self):
        """Test creating a document state."""
        document = DocumentState(
            document_id="test-doc",
            content="Hello, World!",
            version=1
        )
        
        assert document.document_id == "test-doc"
        assert document.content == "Hello, World!"
        assert document.version == 1
        assert document.active_users == []
    
    def test_document_state_serialization(self):
        """Test document state serialization."""
        document = DocumentState(
            document_id="test-doc",
            content="Hello, World!",
            version=1
        )
        
        json_str = document.json()
        parsed = DocumentState.parse_raw(json_str)
        
        assert parsed.document_id == document.document_id
        assert parsed.content == document.content
        assert parsed.version == document.version


class TestOperation:
    """Test Operation model."""
    
    def test_operation_creation(self):
        """Test creating an operation."""
        operation = Operation(
            id="op-1",
            type=OperationType.INSERT,
            position=5,
            content="World",
            user_id="user-1"
        )
        
        assert operation.id == "op-1"
        assert operation.type == OperationType.INSERT
        assert operation.position == 5
        assert operation.content == "World"
        assert operation.user_id == "user-1"
    
    def test_operation_serialization(self):
        """Test operation serialization."""
        operation = Operation(
            id="op-1",
            type=OperationType.INSERT,
            position=5,
            content="World",
            user_id="user-1"
        )
        
        op_dict = operation.to_dict()
        parsed = Operation.from_dict(op_dict)
        
        assert parsed.id == operation.id
        assert parsed.type == operation.type
        assert parsed.position == operation.position
        assert parsed.content == operation.content
        assert parsed.user_id == operation.user_id
    
    def test_insert_operation(self):
        """Test insert operation."""
        operation = Operation(
            id="op-1",
            type=OperationType.INSERT,
            position=5,
            content="World",
            user_id="user-1"
        )
        
        assert operation.type == OperationType.INSERT
        assert operation.content == "World"
        assert operation.length is None
    
    def test_delete_operation(self):
        """Test delete operation."""
        operation = Operation(
            id="op-2",
            type=OperationType.DELETE,
            position=5,
            length=3,
            user_id="user-1"
        )
        
        assert operation.type == OperationType.DELETE
        assert operation.length == 3
        assert operation.content is None


class TestCursorPosition:
    """Test CursorPosition model."""
    
    def test_cursor_position_creation(self):
        """Test creating a cursor position."""
        cursor = CursorPosition(
            user_id="user-1",
            session_id="session-1",
            line=5,
            column=10,
            user_name="Alice",
            user_color="#ff0000"
        )
        
        assert cursor.user_id == "user-1"
        assert cursor.session_id == "session-1"
        assert cursor.line == 5
        assert cursor.column == 10
        assert cursor.user_name == "Alice"
        assert cursor.user_color == "#ff0000"
    
    def test_cursor_position_serialization(self):
        """Test cursor position serialization."""
        cursor = CursorPosition(
            user_id="user-1",
            session_id="session-1",
            line=5,
            column=10
        )
        
        cursor_dict = cursor.to_dict()
        parsed = CursorPosition.from_dict(cursor_dict)
        
        assert parsed.user_id == cursor.user_id
        assert parsed.session_id == cursor.session_id
        assert parsed.line == cursor.line
        assert parsed.column == cursor.column


class TestDocumentManager:
    """Test DocumentManager."""
    
    @pytest.mark.asyncio
    async def test_create_document(self, document_manager):
        """Test creating a document."""
        document = await document_manager.create_document(
            document_id="test-doc",
            initial_content="Hello, World!"
        )
        
        assert document.document_id == "test-doc"
        assert document.content == "Hello, World!"
        assert document.version == 0
        assert document.active_users == []
    
    @pytest.mark.asyncio
    async def test_get_document(self, document_manager):
        """Test getting a document."""
        # Create document first
        created = await document_manager.create_document(
            document_id="test-doc",
            initial_content="Hello, World!"
        )
        
        # Get document
        retrieved = await document_manager.get_document("test-doc")
        
        assert retrieved is not None
        assert retrieved.document_id == created.document_id
        assert retrieved.content == created.content
        assert retrieved.version == created.version
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_document(self, document_manager):
        """Test getting a non-existent document."""
        document = await document_manager.get_document("nonexistent")
        assert document is None
    
    @pytest.mark.asyncio
    async def test_apply_insert_operation(self, document_manager):
        """Test applying an insert operation."""
        # Create document
        document = await document_manager.create_document(
            document_id="test-doc",
            initial_content="Hello!"
        )
        
        # Apply insert operation
        operation = Operation(
            id="op-1",
            type=OperationType.INSERT,
            position=5,
            content=", World",
            user_id="user-1"
        )
        
        success = await document_manager.apply_operation("test-doc", operation)
        
        assert success
        
        # Check updated document
        updated = await document_manager.get_document("test-doc")
        assert updated.content == "Hello, World!"
        assert updated.version == 1
    
    @pytest.mark.asyncio
    async def test_apply_delete_operation(self, document_manager):
        """Test applying a delete operation."""
        # Create document
        document = await document_manager.create_document(
            document_id="test-doc",
            initial_content="Hello, World!"
        )
        
        # Apply delete operation
        operation = Operation(
            id="op-1",
            type=OperationType.DELETE,
            position=5,
            length=7,  # Delete ", World"
            user_id="user-1"
        )
        
        success = await document_manager.apply_operation("test-doc", operation)
        
        assert success
        
        # Check updated document
        updated = await document_manager.get_document("test-doc")
        assert updated.content == "Hello!"
        assert updated.version == 1
    
    @pytest.mark.asyncio
    async def test_apply_operation_invalid_position(self, document_manager):
        """Test applying operation with invalid position."""
        # Create document
        document = await document_manager.create_document(
            document_id="test-doc",
            initial_content="Hello!"
        )
        
        # Apply operation with invalid position
        operation = Operation(
            id="op-1",
            type=OperationType.INSERT,
            position=100,  # Invalid position
            content="World",
            user_id="user-1"
        )
        
        success = await document_manager.apply_operation("test-doc", operation)
        
        assert not success
    
    @pytest.mark.asyncio
    async def test_add_remove_user(self, document_manager):
        """Test adding and removing users."""
        # Create document
        document = await document_manager.create_document(
            document_id="test-doc",
            initial_content="Hello!"
        )
        
        # Add user
        await document_manager.add_user("test-doc", "user-1", "session-1")
        
        updated = await document_manager.get_document("test-doc")
        assert "user-1" in updated.active_users
        
        # Remove user
        await document_manager.remove_user("test-doc", "user-1", "session-1")
        
        updated = await document_manager.get_document("test-doc")
        assert "user-1" not in updated.active_users
    
    @pytest.mark.asyncio
    async def test_update_cursor_position(self, document_manager):
        """Test updating cursor position."""
        # Create document
        document = await document_manager.create_document(
            document_id="test-doc",
            initial_content="Hello!"
        )
        
        # Update cursor position
        cursor = CursorPosition(
            user_id="user-1",
            session_id="session-1",
            line=1,
            column=5,
            user_name="Alice"
        )
        
        await document_manager.update_cursor_position("test-doc", cursor)
        
        # Get cursor positions
        cursors = await document_manager.get_cursor_positions("test-doc")
        
        assert len(cursors) == 1
        assert cursors[0].user_id == "user-1"
        assert cursors[0].line == 1
        assert cursors[0].column == 5
        assert cursors[0].user_name == "Alice"
    
    @pytest.mark.asyncio
    async def test_get_operations_since(self, document_manager):
        """Test getting operations since a version."""
        # Create document
        document = await document_manager.create_document(
            document_id="test-doc",
            initial_content="Hello!"
        )
        
        # Apply operations
        op1 = Operation(
            id="op-1",
            type=OperationType.INSERT,
            position=5,
            content=", World",
            user_id="user-1"
        )
        
        op2 = Operation(
            id="op-2",
            type=OperationType.INSERT,
            position=12,
            content="!",
            user_id="user-1"
        )
        
        await document_manager.apply_operation("test-doc", op1)
        await document_manager.apply_operation("test-doc", op2)
        
        # Get operations since version 1
        operations = await document_manager.get_operations_since("test-doc", 1)
        
        assert len(operations) >= 1
    
    @pytest.mark.asyncio
    async def test_create_snapshot(self, document_manager):
        """Test creating a document snapshot."""
        # Create document
        document = await document_manager.create_document(
            document_id="test-doc",
            initial_content="Hello!"
        )
        
        # Apply operation
        operation = Operation(
            id="op-1",
            type=OperationType.INSERT,
            position=5,
            content=", World",
            user_id="user-1"
        )
        
        await document_manager.apply_operation("test-doc", operation)
        
        # Create snapshot
        success = await document_manager.create_snapshot("test-doc")
        
        assert success
        
        # Check document has snapshot time
        updated = await document_manager.get_document("test-doc")
        assert updated.last_snapshot_at is not None
    
    @pytest.mark.asyncio
    async def test_get_document_stats(self, document_manager):
        """Test getting document statistics."""
        # Create document
        document = await document_manager.create_document(
            document_id="test-doc",
            initial_content="Hello!"
        )
        
        # Add user
        await document_manager.add_user("test-doc", "user-1", "session-1")
        
        # Update cursor
        cursor = CursorPosition(
            user_id="user-1",
            session_id="session-1",
            line=1,
            column=5
        )
        
        await document_manager.update_cursor_position("test-doc", cursor)
        
        # Get stats
        stats = await document_manager.get_document_stats("test-doc")
        
        assert stats['document_id'] == "test-doc"
        assert stats['version'] == 0
        assert stats['content_length'] == 6  # "Hello!"
        assert stats['active_users'] == 1
        assert stats['connected_cursors'] == 1


if __name__ == "__main__":
    pytest.main([__file__])
