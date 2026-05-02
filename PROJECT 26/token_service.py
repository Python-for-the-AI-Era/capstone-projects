import jwt
from datetime import datetime, timedelta, timezone
import secrets

SECRET_KEY = "your-distil-secret-key"
ALGORITHM = "HS256"

def create_access_token(user_id: str):
    """
    FIX: Added 'exp' (expiry) and 'jti' (unique ID).
    A short expiry (15-30 mins) minimizes the window of 
    opportunity for an attacker.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(minutes=30),
        "jti": secrets.token_hex(16) # Unique ID for revocation
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)