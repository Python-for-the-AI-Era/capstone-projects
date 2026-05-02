from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class ProductMonitor(Base):
    __tablename__ = "product_monitors"
    id = Column(Integer, primary_key=True)
    url = Column(String, nullable=False)
    target_price = Column(Float, nullable=False)
    user_phone = Column(String, nullable=False) # e.g., "+234..."

class PriceHistory(Base):
    __tablename__ = "price_history"
    id = Column(Integer, primary_key=True)
    monitor_id = Column(Integer, ForeignKey("product_monitors.id"))
    price = Column(Float)
    scraped_at = Column(DateTime)