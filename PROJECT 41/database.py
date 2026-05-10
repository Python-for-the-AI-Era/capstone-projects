from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from models import Base
from config import settings
import logging

logger = logging.getLogger(__name__)

# Create async engine
engine = create_async_engine(
    settings.database_url,
    echo=True,  # Set to False in production
    future=True
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Create sync engine for migrations (Alembic needs sync engine)
sync_engine = None


async def create_tables():
    """Create all database tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created successfully")


async def drop_tables():
    """Drop all database tables (for testing)"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    logger.info("Database tables dropped successfully")


async def get_db():
    """Get database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# Test database setup
test_engine = None
TestAsyncSessionLocal = None


def setup_test_database():
    """Setup test database engine"""
    global test_engine, TestAsyncSessionLocal
    
    test_engine = create_async_engine(
        settings.test_database_url,
        echo=False,  # Reduce noise in tests
        future=True
    )
    
    TestAsyncSessionLocal = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )


async def create_test_tables():
    """Create test database tables"""
    if not test_engine:
        setup_test_database()
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_test_tables():
    """Drop test database tables"""
    if test_engine:
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)


async def get_test_db():
    """Get test database session"""
    if not TestAsyncSessionLocal:
        setup_test_database()
    
    async with TestAsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
