from fastapi import Request, HTTPException, status

async def verify_token_middleware(request: Request):
    token = request.headers.get("Authorization").split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # SECURITY CHECK: Is this token explicitly banned?
        if await is_token_revoked(payload["jti"]):
            raise HTTPException(status_code=401, detail="Token revoked")
            
        # SECURITY CHECK: Was this issued before a password change?
        # (Compare iat with user's password_changed_at timestamp)
        
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")