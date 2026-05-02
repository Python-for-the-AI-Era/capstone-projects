from sqlalchemy import Column, Integer, String, DateTime, Index
from sqlalchemy.orm import DeclarativeBase
import datetime

class Base(DeclarativeBase):
    pass

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    amount = Column(Integer)
    status = Column(String) # 'completed', 'pending', 'cancelled'
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # FAULTY: There is no index on created_at or status.
    # Every query for "June sales" will scan every single row.