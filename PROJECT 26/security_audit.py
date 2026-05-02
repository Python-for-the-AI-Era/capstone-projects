import pytest

@pytest.mark.asyncio
async def test_revocation_on_password_change():
    # 1. Generate token
    token = create_access_token("user_123")
    # 2. Simulate password change (Revoke all)
    await revoke_token(extract_jti(token), 1800)
    # 3. Try to use it
    with pytest.raises(HTTPException) as exc:
        await verify_token_middleware(mock_request(token))
    assert exc.value.status_code == 401