import pytest
from httpx import AsyncClient
from main import app
from database import Base, engine, get_db

# Day 1: Setup the Async Testing Environment
@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"

@pytest.fixture(scope="function")
async def client():
    """Provides a fresh AsyncClient for every test."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest.fixture(scope="function")
async def test_user_token(client):
    """Fixture to provide a valid JWT for authenticated routes."""
    # Logic to create a user and return their token
    return "bearer_token_here"