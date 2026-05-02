import pytest
from auth import SECRET
import jwt

@pytest.mark.asyncio
async def test_tenant_isolation_failure():
    # Token for User in Org A (ID: 1)
    token_a = jwt.encode({"user_id": 1, "org_id": 1}, SECRET)
    # Token for User in Org B (ID: 2)
    token_b = jwt.encode({"user_id": 2, "org_id": 2}, SECRET)
    
    # 1. Org A creates a private form (ID: 101)
    # 2. Org B attempts to GET /forms/101
    
    # Currently, this returns 200 OK. 
    # AFTER THE FIX, it must return 404 Not Found (to prevent ID enumeration).
    pass