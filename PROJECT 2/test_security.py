import pytest
from httpx import AsyncClient
from main import app
from auth_utils import create_access_token

@pytest.mark.asyncio
async def test_bola_vulnerability():
    # User A (ID: 1) logs in
    token_a = create_access_token({"user_id": 1, "is_admin": False})
    headers_a = {"Authorization": f"Bearer {token_a}"}
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # User A tries to access User B's (ID: 2) medical record
        response = await ac.get("/records/2", headers=headers_a)
        
        # This SHOULD be 403 Forbidden, but currently it returns 200 OK
        assert response.status_code == 200 
        assert "John Doe" in response.json()["data"]
        print("\n[!] VULNERABILITY CONFIRMED: User A accessed User B's data!")