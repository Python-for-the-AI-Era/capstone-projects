"""
Persistence Layer for Real-Time Collaborative Editor
Handles PostgreSQL snapshots and Redis-based operation storage
"""

import asyncio
import logging
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import asyncpg
import redis.asyncio as aioredis
from pathlib import Path

from document_model import DocumentState, Operation, OperationType

logger = logging.getLogger(__name__)


@dataclass
class DocumentSnapshot:
    """Represents a document snapshot in PostgreSQL"""
    doc_id: str
    content: str
    version: int
    operation_count: int
    created_at: datetime
    user_count: int = 0
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'doc_id': self.doc_id,
            'content': self.content,
            'version': self.version,
            'operation_count': self.operation_count,
            'created_at': self.created_at.isoformat(),
            'user_count': self.user_count,
            'metadata': self.metadata or {}
        }


@dataclass
class PersistenceConfig:
    """Configuration for persistence layer"""
    postgres_dsn: str = "postgresql://user:password@localhost/collaborative_editor"
    redis_url: str = "redis://localhost:6379"
    snapshot_interval_seconds: int = 30
    max_operations_in_memory: int = 1000
    snapshot_retention_days: int = 30
    cleanup_interval_hours: int = 24
    batch_size: int = 100


class PostgreSQLPersistence:
    """
    PostgreSQL-based persistence for document snapshots
    """
    
    def __init__(self, config: PersistenceConfig):
        self.config = config
        self.pool: Optional[asyncpg.Pool] = None
        
    async def initialize(self):
        """Initialize database connection pool"""
        try:
            self.pool = await asyncpg.create_pool(
                self.config.postgres_dsn,
                min_size=5,
                max_size=20,
                command_timeout=60
            )
            
            # Create tables if they don't exist
            await self._create_tables()
            
            logger.info("PostgreSQL persistence initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL: {e}")
            raise
    
    async def _create_tables(self):
        """Create database tables"""
        async with self.pool.acquire() as conn:
            # Documents table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    doc_id VARCHAR(255) PRIMARY KEY,
                    title VARCHAR(255),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    owner_id VARCHAR(255),
                    is_public BOOLEAN DEFAULT FALSE,
                    metadata JSONB DEFAULT '{}'
                )
            """)
            
            # Document snapshots table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS document_snapshots (
                    id SERIAL PRIMARY KEY,
                    doc_id VARCHAR(255) REFERENCES documents(doc_id) ON DELETE CASCADE,
                    content TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    operation_count INTEGER NOT NULL,
                    user_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    metadata JSONB DEFAULT '{}',
                    INDEX idx_doc_snapshot_created (doc_id, created_at),
                    INDEX idx_doc_snapshot_version (doc_id, version)
                )
            """)
            
            # Operations table (for audit trail)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS operation_audit (
                    id SERIAL PRIMARY KEY,
                    doc_id VARCHAR(255) REFERENCES documents(doc_id) ON DELETE CASCADE,
                    operation_id VARCHAR(255) NOT NULL,
                    operation_type VARCHAR(50) NOT NULL,
                    position INTEGER NOT NULL,
                    char_data TEXT,
                    length INTEGER DEFAULT 1,
                    user_id VARCHAR(255) NOT NULL,
                    version INTEGER NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    metadata JSONB DEFAULT '{}',
                    INDEX idx_op_audit_doc_created (doc_id, created_at),
                    INDEX idx_op_audit_user_created (user_id, created_at)
                )
            """)
    
    async def create_document(self, doc_id: str, title: str = "", 
                            owner_id: str = "", is_public: bool = False,
                            metadata: Dict[str, Any] = None) -> bool:
        """Create a new document"""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO documents (doc_id, title, owner_id, is_public, metadata)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (doc_id) DO NOTHING
                """, doc_id, title, owner_id, is_public, metadata or {})
                
                return True
                
        except Exception as e:
            logger.error(f"Error creating document {doc_id}: {e}")
            return False
    
    async def save_snapshot(self, snapshot: DocumentSnapshot) -> bool:
        """Save document snapshot to PostgreSQL"""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO document_snapshots 
                    (doc_id, content, version, operation_count, user_count, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """, 
                snapshot.doc_id, 
                snapshot.content, 
                snapshot.version, 
                snapshot.operation_count, 
                snapshot.user_count, 
                snapshot.metadata or {})
                
                return True
                
        except Exception as e:
            logger.error(f"Error saving snapshot for {snapshot.doc_id}: {e}")
            return False
    
    async def get_latest_snapshot(self, doc_id: str) -> Optional[DocumentSnapshot]:
        """Get the latest snapshot for a document"""
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT doc_id, content, version, operation_count, 
                           user_count, created_at, metadata
                    FROM document_snapshots
                    WHERE doc_id = $1
                    ORDER BY version DESC
                    LIMIT 1
                """, doc_id)
                
                if row:
                    return DocumentSnapshot(
                        doc_id=row['doc_id'],
                        content=row['content'],
                        version=row['version'],
                        operation_count=row['operation_count'],
                        user_count=row['user_count'],
                        created_at=row['created_at'],
                        metadata=row['metadata']
                    )
                
                return None
                
        except Exception as e:
            logger.error(f"Error getting latest snapshot for {doc_id}: {e}")
            return None
    
    async def get_snapshot_at_version(self, doc_id: str, version: int) -> Optional[DocumentSnapshot]:
        """Get snapshot at a specific version"""
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT doc_id, content, version, operation_count, 
                           user_count, created_at, metadata
                    FROM document_snapshots
                    WHERE doc_id = $1 AND version <= $2
                    ORDER BY version DESC
                    LIMIT 1
                """, doc_id, version)
                
                if row:
                    return DocumentSnapshot(
                        doc_id=row['doc_id'],
                        content=row['content'],
                        version=row['version'],
                        operation_count=row['operation_count'],
                        user_count=row['user_count'],
                        created_at=row['created_at'],
                        metadata=row['metadata']
                    )
                
                return None
                
        except Exception as e:
            logger.error(f"Error getting snapshot at version {version} for {doc_id}: {e}")
            return None
    
    async def log_operation(self, operation: Operation) -> bool:
        """Log operation to audit table"""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO operation_audit 
                    (doc_id, operation_id, operation_type, position, char_data, 
                     length, user_id, version, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """, 
                operation.user_id,  # Using user_id as doc_id for now (would need doc_id in Operation)
                operation.id,
                operation.type.value,
                operation.position,
                operation.char,
                operation.length,
                operation.user_id,
                operation.version,
                json.dumps({'timestamp': operation.timestamp.isoformat()})
                )
                
                return True
                
        except Exception as e:
            logger.error(f"Error logging operation: {e}")
            return False
    
    async def get_document_history(self, doc_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get document operation history"""
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT operation_id, operation_type, position, char_data,
                           length, user_id, version, created_at, metadata
                    FROM operation_audit
                    WHERE doc_id = $1
                    ORDER BY version DESC
                    LIMIT $2
                """, doc_id, limit)
                
                return [dict(row) for row in rows]
                
        except Exception as e:
            logger.error(f"Error getting document history for {doc_id}: {e}")
            return []
    
    async def cleanup_old_snapshots(self):
        """Clean up old snapshots based on retention policy"""
        cutoff_date = datetime.utcnow() - timedelta(days=self.config.snapshot_retention_days)
        
        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute("""
                    DELETE FROM document_snapshots
                    WHERE created_at < $1
                """, cutoff_date)
                
                deleted_count = int(result.split()[-1])
                logger.info(f"Cleaned up {deleted_count} old snapshots")
                
        except Exception as e:
            logger.error(f"Error cleaning up old snapshots: {e}")
    
    async def get_document_info(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get document information"""
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT d.doc_id, d.title, d.created_at, d.updated_at,
                           d.owner_id, d.is_public, d.metadata,
                           s.version as latest_version,
                           s.user_count as current_users,
                           s.created_at as last_snapshot
                    FROM documents d
                    LEFT JOIN document_snapshots s ON d.doc_id = s.doc_id
                    WHERE d.doc_id = $1
                    ORDER BY s.version DESC
                    LIMIT 1
                """, doc_id)
                
                if row:
                    return dict(row)
                
                return None
                
        except Exception as e:
            logger.error(f"Error getting document info for {doc_id}: {e}")
            return None
    
    async def close(self):
        """Close database connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("PostgreSQL connection pool closed")


class RedisOperationStore:
    """
    Redis-based operation storage for real-time operations
    """
    
    def __init__(self, config: PersistenceConfig):
        self.config = config
        self.redis_client: Optional[aioredis.Redis] = None
        
    async def initialize(self):
        """Initialize Redis connection"""
        try:
            self.redis_client = aioredis.from_url(self.config.redis_url)
            await self.redis_client.ping()
            logger.info("Redis operation store initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize Redis: {e}")
            raise
    
    async def store_operation(self, doc_id: str, operation: Operation) -> bool:
        """Store operation in Redis"""
        try:
            key = f"ops:{doc_id}"
            
            # Store operation as JSON
            op_data = operation.to_dict()
            
            # Add to sorted set with version as score
            await self.redis_client.zadd(key, {json.dumps(op_data): operation.version})
            
            # Keep only recent operations
            await self.redis_client.zremrangebyrank(
                key, 0, -self.config.max_operations_in_memory - 1
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error storing operation in Redis: {e}")
            return False
    
    async def get_operations_since(self, doc_id: str, version: int) -> List[Operation]:
        """Get operations since a specific version"""
        try:
            key = f"ops:{doc_id}"
            
            # Get operations with version > specified version
            op_data_list = await self.redis_client.zrangebyscore(
                key, version + 1, "+inf"
            )
            
            operations = []
            for op_data in op_data_list:
                try:
                    op_dict = json.loads(op_data)
                    operation = Operation.from_dict(op_dict)
                    operations.append(operation)
                except Exception as e:
                    logger.error(f"Error parsing operation data: {e}")
            
            return operations
            
        except Exception as e:
            logger.error(f"Error getting operations from Redis: {e}")
            return []
    
    async def clear_old_operations(self, doc_id: str, keep_version: int):
        """Clear operations older than specified version"""
        try:
            key = f"ops:{doc_id}"
            
            # Remove operations with version <= keep_version
            await self.redis_client.zremrangebyscore(key, 0, keep_version)
            
        except Exception as e:
            logger.error(f"Error clearing old operations: {e}")
    
    async def get_operation_count(self, doc_id: str) -> int:
        """Get count of stored operations for a document"""
        try:
            key = f"ops:{doc_id}"
            return await self.redis_client.zcard(key)
            
        except Exception as e:
            logger.error(f"Error getting operation count: {e}")
            return 0
    
    async def close(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Redis connection closed")


class PersistenceManager:
    """
    Manages persistence across PostgreSQL and Redis
    """
    
    def __init__(self, config: PersistenceConfig):
        self.config = config
        self.postgres = PostgreSQLPersistence(config)
        self.redis = RedisOperationStore(config)
        self.snapshot_tasks: Dict[str, asyncio.Task] = {}
        
    async def initialize(self):
        """Initialize all persistence components"""
        await self.postgres.initialize()
        await self.redis.initialize()
        
        # Start background cleanup task
        asyncio.create_task(self._cleanup_loop())
        
        logger.info("Persistence manager initialized")
    
    async def create_document(self, doc_id: str, title: str = "", 
                            owner_id: str = "", is_public: bool = False,
                            metadata: Dict[str, Any] = None) -> bool:
        """Create a new document"""
        return await self.postgres.create_document(
            doc_id, title, owner_id, is_public, metadata
        )
    
    async def save_operation(self, doc_id: str, operation: Operation) -> bool:
        """Save operation to Redis and log to PostgreSQL"""
        # Store in Redis for real-time access
        redis_success = await self.redis.store_operation(doc_id, operation)
        
        # Log to PostgreSQL for audit
        postgres_success = await self.postgres.log_operation(operation)
        
        return redis_success and postgres_success
    
    async def get_operations_since(self, doc_id: str, version: int) -> List[Operation]:
        """Get operations since a specific version"""
        return await self.redis.get_operations_since(doc_id, version)
    
    async def save_snapshot(self, doc_id: str, document_state: DocumentState) -> bool:
        """Save document snapshot"""
        snapshot = DocumentSnapshot(
            doc_id=doc_id,
            content=document_state.content,
            version=document_state.version,
            operation_count=len(document_state.operations),
            user_count=len(document_state.user_cursors),
            created_at=datetime.utcnow(),
            metadata={
                'last_modified': document_state.last_modified.isoformat(),
                'operation_ids': [op.id for op in document_state.operations[-10:]]  # Last 10 ops
            }
        )
        
        success = await self.postgres.save_snapshot(snapshot)
        
        if success:
            # Clear old operations from Redis
            await self.redis.clear_old_operations(doc_id, document_state.version)
        
        return success
    
    async def get_document_state(self, doc_id: str) -> Optional[DocumentState]:
        """Get document state from latest snapshot and operations"""
        # Get latest snapshot
        snapshot = await self.postgres.get_latest_snapshot(doc_id)
        
        if not snapshot:
            return None
        
        # Get operations since snapshot
        operations = await self.redis.get_operations_since(doc_id, snapshot.version)
        
        # Rebuild document state
        from document_model import DocumentState
        state = DocumentState(
            content=snapshot.content,
            version=snapshot.version,
            operations=operations,
            user_cursors={},
            last_modified=snapshot.created_at
        )
        
        # Apply operations
        for op in operations:
            state = state.apply_operation(op)
        
        return state
    
    async def start_snapshot_task(self, doc_id: str, document_state_provider):
        """Start background snapshot task for a document"""
        if doc_id in self.snapshot_tasks:
            return  # Already running
        
        task = asyncio.create_task(self._snapshot_loop(doc_id, document_state_provider))
        self.snapshot_tasks[doc_id] = task
        
        logger.info(f"Started snapshot task for document {doc_id}")
    
    async def stop_snapshot_task(self, doc_id: str):
        """Stop background snapshot task for a document"""
        if doc_id in self.snapshot_tasks:
            self.snapshot_tasks[doc_id].cancel()
            del self.snapshot_tasks[doc_id]
            logger.info(f"Stopped snapshot task for document {doc_id}")
    
    async def _snapshot_loop(self, doc_id: str, document_state_provider):
        """Background loop for taking snapshots"""
        while True:
            try:
                await asyncio.sleep(self.config.snapshot_interval_seconds)
                
                # Get current document state
                document_state = document_state_provider(doc_id)
                if document_state:
                    await self.save_snapshot(doc_id, document_state)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in snapshot loop for {doc_id}: {e}")
                await asyncio.sleep(10)  # Brief pause on error
    
    async def _cleanup_loop(self):
        """Background loop for cleanup tasks"""
        while True:
            try:
                # Wait for cleanup interval
                await asyncio.sleep(self.config.cleanup_interval_hours * 3600)
                
                # Clean up old snapshots
                await self.postgres.cleanup_old_snapshots()
                
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(3600)  # Wait 1 hour on error
    
    async def get_document_info(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive document information"""
        # Get basic info from PostgreSQL
        info = await self.postgres.get_document_info(doc_id)
        
        if not info:
            return None
        
        # Add real-time stats
        operation_count = await self.redis.get_operation_count(doc_id)
        
        info.update({
            'pending_operations': operation_count,
            'snapshot_interval': self.config.snapshot_interval_seconds,
            'last_cleanup': datetime.utcnow().isoformat()
        })
        
        return info
    
    async def close(self):
        """Close all persistence connections"""
        # Stop all snapshot tasks
        for doc_id in list(self.snapshot_tasks.keys()):
            await self.stop_snapshot_task(doc_id)
        
        # Close connections
        await self.postgres.close()
        await self.redis.close()
        
        logger.info("Persistence manager closed")


# Global persistence manager instance
persistence_manager: Optional[PersistenceManager] = None


async def initialize_persistence(config: PersistenceConfig = None):
    """Initialize global persistence manager"""
    global persistence_manager
    
    if config is None:
        config = PersistenceConfig()
    
    persistence_manager = PersistenceManager(config)
    await persistence_manager.initialize()
    
    logger.info("Global persistence manager initialized")


def get_persistence_manager() -> Optional[PersistenceManager]:
    """Get global persistence manager"""
    return persistence_manager


# Example usage
if __name__ == "__main__":
    async def test_persistence():
        """Test persistence functionality"""
        config = PersistenceConfig()
        manager = PersistenceManager(config)
        
        try:
            await manager.initialize()
            
            # Create document
            doc_id = "test_doc"
            await manager.create_document(doc_id, "Test Document")
            
            # Create test document state
            from document_model import DocumentState, create_insert_operation
            state = DocumentState(content="Hello World", version=1)
            
            # Save snapshot
            await manager.save_snapshot(doc_id, state)
            
            # Get document state
            retrieved_state = await manager.get_document_state(doc_id)
            print(f"Retrieved content: {retrieved_state.content if retrieved_state else 'None'}")
            
            # Get document info
            info = await manager.get_document_info(doc_id)
            print(f"Document info: {info}")
            
        finally:
            await manager.close()
    
    asyncio.run(test_persistence())
