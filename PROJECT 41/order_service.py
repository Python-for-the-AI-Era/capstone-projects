import logging
from datetime import datetime, timedelta
from sqlalchemy import text, select, update, delete
from sqlalchemy.orm import selectinload
from fastapi import HTTPException
from models import Order, Product, Inventory, IdempotencyKey, OrderAttempt
from config import settings

logger = logging.getLogger(__name__)


class OrderService:
    """Service class for handling order creation with race condition protection"""
    
    def __init__(self, db_session):
        self.db = db_session
    
    async def create_order_atomic_update(self, user_id: int, product_id: int):
        """
        TASK 3: Atomic Update with RETURNING
        This happens in a single database step. No two processes can "split" this.
        """
        try:
            # Atomic UPDATE with RETURNING - the most efficient solution
            query = text("""
                UPDATE inventory 
                SET stock = stock - 1 
                WHERE product_id = :product_id AND stock > 0 
                RETURNING stock
            """)
            
            result = await self.db.execute(query, {"product_id": product_id})
            updated_row = result.fetchone()
            
            if not updated_row:
                # If no row was updated, it means stock was 0
                await self._log_order_attempt(user_id, product_id, False, "Out of stock")
                raise HTTPException(status_code=400, detail="Out of Stock")
            
            remaining_stock = updated_row[0]
            
            # Create the order record
            order = await self._create_order_record(user_id, product_id)
            
            await self._log_order_attempt(user_id, product_id, True)
            
            logger.info(f"Order created successfully: order_id={order.id}, user_id={user_id}, product_id={product_id}, remaining_stock={remaining_stock}")
            
            return {
                "status": "success", 
                "order_id": order.id,
                "remaining_stock": remaining_stock
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in atomic update order creation: {e}")
            await self._log_order_attempt(user_id, product_id, False, str(e))
            raise HTTPException(status_code=500, detail="Internal server error")
    
    async def create_order_pessimistic_lock(self, user_id: int, product_id: int):
        """
        TASK 2: Fix with SELECT FOR UPDATE
        Use pessimistic locking to prevent race conditions
        """
        try:
            # Start transaction
            async with self.db.begin():
                # Lock the inventory row for this product
                query = text("""
                    SELECT stock FROM inventory 
                    WHERE product_id = :product_id 
                    FOR UPDATE SKIP LOCKED
                """)
                
                result = await self.db.execute(query, {"product_id": product_id})
                inventory_row = result.fetchone()
                
                if not inventory_row:
                    await self._log_order_attempt(user_id, product_id, False, "Product not found")
                    raise HTTPException(status_code=404, detail="Product not found")
                
                current_stock = inventory_row[0]
                
                if current_stock <= 0:
                    await self._log_order_attempt(user_id, product_id, False, "Out of stock")
                    raise HTTPException(status_code=400, detail="Out of Stock")
                
                # Update inventory
                update_query = text("""
                    UPDATE inventory 
                    SET stock = stock - 1 
                    WHERE product_id = :product_id
                """)
                
                await self.db.execute(update_query, {"product_id": product_id})
                
                # Create order
                order = await self._create_order_record(user_id, product_id)
                
                await self._log_order_attempt(user_id, product_id, True)
                
                logger.info(f"Order created with pessimistic lock: order_id={order.id}, user_id={user_id}, product_id={product_id}")
                
                return {
                    "status": "success",
                    "order_id": order.id,
                    "remaining_stock": current_stock - 1
                }
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in pessimistic lock order creation: {e}")
            await self._log_order_attempt(user_id, product_id, False, str(e))
            raise HTTPException(status_code=500, detail="Internal server error")
    
    async def create_order_with_idempotency(self, user_id: int, product_id: int):
        """
        TASK 5: Add idempotency with 60-second retry protection
        """
        try:
            # Check for idempotency key
            idempotency_key = f"{user_id}:{product_id}"
            
            # Clean up expired idempotency keys
            await self._cleanup_expired_idempotency_keys()
            
            # Check if this exact request was made recently
            existing_key_query = text("""
                SELECT order_id FROM idempotency_keys 
                WHERE key = :key AND expires_at > NOW()
            """)
            
            result = await self.db.execute(existing_key_query, {"key": idempotency_key})
            existing_key = result.fetchone()
            
            if existing_key and existing_key[0]:
                # Return the existing order
                order_query = select(Order).where(Order.id == existing_key[0])
                order_result = await self.db.execute(order_query)
                order = order_result.scalar_one_or_none()
                
                if order:
                    logger.info(f"Returning existing order due to idempotency: order_id={order.id}, user_id={user_id}, product_id={product_id}")
                    return {
                        "status": "success",
                        "order_id": order.id,
                        "message": "Order already processed (idempotent request)",
                        "existing_order": True
                    }
            
            # Proceed with order creation using atomic update
            result = await self.create_order_atomic_update(user_id, product_id)
            
            if result["status"] == "success":
                # Store idempotency key
                idempotency_record = IdempotencyKey(
                    key=idempotency_key,
                    order_id=result["order_id"],
                    expires_at=datetime.utcnow() + timedelta(seconds=settings.idempotency_window_seconds)
                )
                self.db.add(idempotency_record)
                await self.db.commit()
            
            return result
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in idempotent order creation: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")
    
    async def _create_order_record(self, user_id: int, product_id: int) -> Order:
        """Create the order record in the database"""
        # Get product details for pricing
        product_query = select(Product).where(Product.id == product_id)
        product_result = await self.db.execute(product_query)
        product = product_result.scalar_one_or_none()
        
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        # Create order
        order = Order(
            user_id=user_id,
            product_id=product_id,
            quantity=1,
            total_amount=product.price,
            status="confirmed"
        )
        
        self.db.add(order)
        await self.db.flush()  # Get the ID without committing
        
        return order
    
    async def _log_order_attempt(self, user_id: int, product_id: int, success: bool, error_message: str = None):
        """Log order attempt for monitoring"""
        attempt = OrderAttempt(
            user_id=user_id,
            product_id=product_id,
            success=success,
            error_message=error_message
        )
        self.db.add(attempt)
        await self.db.commit()
    
    async def _cleanup_expired_idempotency_keys(self):
        """Clean up expired idempotency keys"""
        cleanup_query = text("""
            DELETE FROM idempotency_keys 
            WHERE expires_at <= NOW()
        """)
        await self.db.execute(cleanup_query)
    
    async def get_inventory_status(self, product_id: int):
        """Get current inventory status for a product"""
        query = text("""
            SELECT stock, reserved FROM inventory 
            WHERE product_id = :product_id
        """)
        
        result = await self.db.execute(query, {"product_id": product_id})
        inventory_row = result.fetchone()
        
        if not inventory_row:
            raise HTTPException(status_code=404, detail="Product not found")
        
        return {
            "product_id": product_id,
            "stock": inventory_row[0],
            "reserved": inventory_row[1],
            "available": inventory_row[0] - inventory_row[1]
        }
    
    async def get_order_statistics(self, product_id: int = None):
        """Get order statistics for monitoring"""
        base_query = "SELECT COUNT(*) as total_orders, COUNT(CASE WHEN success = true THEN 1 END) as successful_orders FROM order_attempts"
        
        if product_id:
            base_query += " WHERE product_id = :product_id"
        
        query = text(base_query)
        params = {"product_id": product_id} if product_id else {}
        
        result = await self.db.execute(query, params)
        stats = result.fetchone()
        
        return {
            "total_attempts": stats[0] if stats else 0,
            "successful_orders": stats[1] if stats else 0,
            "success_rate": (stats[1] / stats[0] * 100) if stats and stats[0] > 0 else 0
        }


# Backward compatibility functions
async def create_order(db_session, user_id, product_id):
    """Legacy function for backward compatibility"""
    service = OrderService(db_session)
    return await service.create_order_atomic_update(user_id, product_id)


async def create_order_with_lock(db_session, user_id, product_id):
    """Create order with pessimistic locking"""
    service = OrderService(db_session)
    return await service.create_order_pessimistic_lock(user_id, product_id)


async def create_order_idempotent(db_session, user_id, product_id):
    """Create order with idempotency protection"""
    service = OrderService(db_session)
    return await service.create_order_with_idempotency(user_id, product_id)