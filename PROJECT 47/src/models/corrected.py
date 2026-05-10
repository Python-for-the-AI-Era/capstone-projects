"""
Database models for the data export feature - CORRECTED VERSION.

This module contains the User and Order models with proper relationships
and optimizations for efficient data loading.
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, selectinload
from sqlalchemy.sql import func
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

Base = declarative_base()


class User(Base):
    """User model with orders relationship."""
    
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationship to orders with eager loading configuration
    orders = relationship("Order", back_populates="user", lazy="selectin")
    
    def __repr__(self):
        return f"<User(id={self.id}, name='{self.name}', email='{self.email}')>"
    
    def get_total_order_amount(self):
        """Calculate total amount of all orders."""
        return sum(order.amount for order in self.orders)
    
    def get_order_count(self):
        """Get the number of orders."""
        return len(self.orders)


class Order(Base):
    """Order model with user relationship."""
    
    __tablename__ = 'orders'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    status = Column(String(50), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    description = Column(Text, nullable=True)
    
    # Relationship to user
    user = relationship("User", back_populates="orders")
    
    def __repr__(self):
        return f"<Order(id={self.id}, user_id={self.user_id}, amount={self.amount})>"
    
    @classmethod
    def get_user_orders_summary(cls, session, user_id):
        """Get order summary for a specific user."""
        result = session.query(
            func.count(cls.id).label('order_count'),
            func.sum(cls.amount).label('total_amount')
        ).filter(cls.user_id == user_id).first()
        
        return {
            'order_count': result.order_count or 0,
            'total_amount': result.total_amount or 0.0
        }


class ExportQuery:
    """Helper class for optimized export queries."""
    
    @staticmethod
    def get_users_with_orders(session, name_filter=None, status_filter=None):
        """
        Get users with their orders efficiently using eager loading.
        
        Args:
            session: SQLAlchemy session
            name_filter: Optional name filter
            status_filter: Optional order status filter
            
        Returns:
            List of User objects with loaded orders
        """
        try:
            query = session.query(User).options(selectinload(User.orders))
            
            # Apply name filter if provided
            if name_filter:
                query = query.filter(User.name.ilike(f'%{name_filter}%'))
            
            # Apply status filter to orders if provided
            if status_filter:
                query = query.join(User.orders).filter(Order.status == status_filter)
            
            users = query.all()
            logger.info(f"Retrieved {len(users)} users with orders")
            return users
            
        except Exception as e:
            logger.error(f"Error retrieving users with orders: {e}")
            raise
    
    @staticmethod
    def get_orders_with_users(session, status_filter=None):
        """
        Get orders with user information efficiently.
        
        Args:
            session: SQLAlchemy session
            status_filter: Optional status filter
            
        Returns:
            List of Order objects with loaded users
        """
        try:
            query = session.query(Order).options(selectinload(Order.user))
            
            if status_filter:
                query = query.filter(Order.status == status_filter)
            
            orders = query.all()
            logger.info(f"Retrieved {len(orders)} orders")
            return orders
            
        except Exception as e:
            logger.error(f"Error retrieving orders: {e}")
            raise
    
    @staticmethod
    def get_export_statistics(session):
        """Get export statistics for monitoring."""
        try:
            user_count = session.query(func.count(User.id)).scalar()
            order_count = session.query(func.count(Order.id)).scalar()
            
            total_revenue = session.query(func.sum(Order.amount)).scalar() or 0.0
            
            stats = {
                'total_users': user_count,
                'total_orders': order_count,
                'total_revenue': total_revenue,
                'avg_order_value': total_revenue / order_count if order_count > 0 else 0.0
            }
            
            logger.info(f"Export statistics: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Error getting export statistics: {e}")
            raise
