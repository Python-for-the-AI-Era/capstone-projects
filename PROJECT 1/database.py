from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import asyncio

# The CTO set a small pool for "safety" but didn't set a timeout
DATABASE_URL = "postgresql+asyncpg://user:password@localhost/paylot_db"

engine = create_async_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=0  # Tight limits making it easy to crash
    # MISSING: pool_timeout
)

AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

# FAULTY: This dependency doesn't use try/finally. 
# If a request errors or times out, the connection remains "checked out".
async def get_db():
    session = AsyncSessionLocal()
    yield session
    await session.close()