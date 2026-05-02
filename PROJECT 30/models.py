from sqlalchemy import Column, String, DateTime, Boolean, Integer
from datetime import datetime, timedelta

class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, index=True)
    # BUG 1 FIX: Store the HASH, not the raw token
    token_hash = Column(String, nullable=False)
    # BUG 2 FIX: Enforce a time limit
    expires_at = Column(DateTime, default=lambda: datetime.utcnow() + timedelta(hours=1))
    # BUG 3 FIX: Prevent replay attacks
    is_used = Column(Boolean, default=False)