import secrets
from passlib.hash import bcrypt

def generate_reset_link(user_id: str):
    raw_token = secrets.token_urlsafe(32)
    token_hash = bcrypt.hash(raw_token)
    
    # Save token_hash, user_id, and expires_at to DB
    # Send raw_token to user via email: 
    # https://recova.app/reset?token={raw_token}
    return raw_token

def verify_and_use_token(db_session, submitted_raw_token: str):
    # 1. Fetch record (you may need to look up by user_id or scan recent hashes)
    # 2. Check Expiry: if record.expires_at < datetime.utcnow(): raise Error
    # 3. Check Usage: if record.is_used: raise Error
    # 4. Check Validity: if not bcrypt.verify(submitted_raw_token, record.token_hash): raise Error
    
    # SUCCESS: Mark as used immediately
    record.is_used = True
    db_session.commit()
    return record.user_id