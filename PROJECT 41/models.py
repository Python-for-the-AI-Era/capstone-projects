from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime, timedelta

Base = declarative_base()


class Product(Base):
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String)
    price = Column(Integer, nullable=False)  # Price in kobo (Naira * 100)
    
    # Relationship to inventory
    inventory = relationship("Inventory", back_populates="product", uselist=False)
    
    def __repr__(self):
        return f"<Product(id={self.id}, name='{self.name}', price={self.price})>"


class Inventory(Base):
    __tablename__ = "inventory"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), unique=True, nullable=False)
    stock = Column(Integer, nullable=False, default=0)
    reserved = Column(Integer, nullable=False, default=0)  # Items reserved in pending orders
    last_updated = Column(DateTime, server_default=func.now())
    
    # Relationship to product
    product = relationship("Product", back_populates="inventory")
    
    def __repr__(self):
        return f"<Inventory(product_id={self.product_id}, stock={self.stock}, reserved={self.reserved})>"


class Order(Base):
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    quantity = Column(Integer, nullable=False, default=1)
    status = Column(String, default="pending")  # pending, confirmed, failed, cancelled
    total_amount = Column(Integer, nullable=False)  # Price * quantity in kobo
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationship to product
    product = relationship("Product")
    
    # Index for idempotency checks
    __table_args__ = (
        Index('idx_user_product_pending', 'user_id', 'product_id', 'created_at'),
    )
    
    def __repr__(self):
        return f"<Order(id={self.id}, user_id={self.user_id}, product_id={self.product_id}, status='{self.status}')>"


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, nullable=False, index=True)  # user_id:product_id format
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    
    def __repr__(self):
        return f"<IdempotencyKey(key='{self.key}', expires_at={self.expires_at})>"


class OrderAttempt(Base):
    __tablename__ = "order_attempts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    product_id = Column(Integer, nullable=False, index=True)
    attempt_time = Column(DateTime, server_default=func.now())
    success = Column(Boolean, nullable=False, default=False)
    error_message = Column(String)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    
    # Index for tracking concurrent attempts
    __table_args__ = (
        Index('idx_user_product_attempt', 'user_id', 'product_id', 'attempt_time'),
    )
    
    def __repr__(self):
        return f"<OrderAttempt(user_id={self.user_id}, product_id={self.product_id}, success={self.success})>"
