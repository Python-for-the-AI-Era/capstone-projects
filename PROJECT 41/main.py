import logging
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional, List
import asyncio
import uvicorn

from database import get_db, create_tables
from order_service import OrderService
from config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="DropBox Nigeria Order Processing System",
    description="Race condition-free order processing with multiple locking strategies",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class OrderRequest(BaseModel):
    user_id: int
    product_id: int
    strategy: Optional[str] = "atomic"  # atomic, pessimistic, idempotent

class OrderResponse(BaseModel):
    status: str
    order_id: Optional[int] = None
    remaining_stock: Optional[int] = None
    message: Optional[str] = None
    existing_order: Optional[bool] = None

class InventoryStatus(BaseModel):
    product_id: int
    stock: int
    reserved: int
    available: int

class OrderStatistics(BaseModel):
    total_attempts: int
    successful_orders: int
    success_rate: float

# API Endpoints
@app.post("/order/product/{product_id}", response_model=OrderResponse)
async def create_order_endpoint(
    product_id: int,
    order_request: OrderRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Create an order with configurable locking strategy
    """
    service = OrderService(db)
    
    try:
        # Validate strategy
        if order_request.strategy not in ["atomic", "pessimistic", "idempotent"]:
            raise HTTPException(status_code=400, detail="Invalid strategy. Use: atomic, pessimistic, or idempotent")
        
        # Route to appropriate strategy
        if order_request.strategy == "atomic":
            result = await service.create_order_atomic_update(order_request.user_id, product_id)
        elif order_request.strategy == "pessimistic":
            result = await service.create_order_pessimistic_lock(order_request.user_id, product_id)
        elif order_request.strategy == "idempotent":
            result = await service.create_order_with_idempotency(order_request.user_id, product_id)
        
        return OrderResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in order creation: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/inventory/product/{product_id}", response_model=InventoryStatus)
async def get_inventory_status(
    product_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get current inventory status for a product"""
    service = OrderService(db)
    return await service.get_inventory_status(product_id)

@app.get("/statistics", response_model=OrderStatistics)
async def get_order_statistics(
    product_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get order statistics for monitoring"""
    service = OrderService(db)
    return await service.get_order_statistics(product_id)

@app.post("/setup-test-data")
async def setup_test_data(db: AsyncSession = Depends(get_db)):
    """Setup test data for race condition testing"""
    from sqlalchemy import text
    from models import Product, Inventory
    
    try:
        # Create test product
        product_query = text("""
            INSERT INTO products (id, name, description, price) 
            VALUES (42, 'Test Product', 'A product for testing race conditions', 10000)
            ON CONFLICT (id) DO NOTHING
        """)
        await db.execute(product_query)
        
        # Initialize inventory with 1 item
        inventory_query = text("""
            INSERT INTO inventory (product_id, stock, reserved) 
            VALUES (42, 1, 0)
            ON CONFLICT (product_id) DO UPDATE SET 
            stock = 1, reserved = 0
        """)
        await db.execute(inventory_query)
        
        await db.commit()
        
        return {"status": "success", "message": "Test data setup complete"}
        
    except Exception as e:
        logger.error(f"Error setting up test data: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to setup test data")

@app.post("/reset-test-data")
async def reset_test_data(db: AsyncSession = Depends(get_db)):
    """Reset test data for testing"""
    from sqlalchemy import text
    
    try:
        # Reset inventory to 1 item
        reset_query = text("""
            UPDATE inventory 
            SET stock = 1, reserved = 0 
            WHERE product_id = 42
        """)
        await db.execute(reset_query)
        
        # Clear order attempts and idempotency keys
        await db.execute(text("DELETE FROM order_attempts WHERE product_id = 42"))
        await db.execute(text("DELETE FROM idempotency_keys WHERE key LIKE '%:42%'"))
        
        await db.commit()
        
        return {"status": "success", "message": "Test data reset complete"}
        
    except Exception as e:
        logger.error(f"Error resetting test data: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to reset test data")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "order-processing"}

@app.on_event("startup")
async def startup_event():
    """Initialize database tables on startup"""
    try:
        await create_tables()
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")

# Legacy endpoints for backward compatibility
@app.post("/order/legacy/product/{product_id}")
async def create_order_legacy(
    product_id: int,
    order_request: dict,
    db: AsyncSession = Depends(get_db)
):
    """Legacy endpoint for backward compatibility"""
    service = OrderService(db)
    result = await service.create_order_atomic_update(order_request["user_id"], product_id)
    return result

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_level="info"
    )
