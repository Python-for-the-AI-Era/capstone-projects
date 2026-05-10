#!/usr/bin/env python3
"""
Comprehensive test suite for race condition fixes in order processing system
"""

import asyncio
import pytest
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_test_db, create_test_tables, drop_test_tables
from models import Product, Inventory, Order, OrderAttempt
from order_service import OrderService
from main import app
from fastapi.testclient import TestClient


class TestRaceConditionFixes:
    """Test suite for race condition fixes"""
    
    @pytest.fixture
    async def test_db(self):
        """Setup test database"""
        await create_test_tables()
        async for session in get_test_db():
            yield session
        await drop_test_tables()
    
    @pytest.fixture
    async def setup_test_data(self, test_db: AsyncSession):
        """Setup test data for race condition testing"""
        # Create test product
        product = Product(id=42, name="Test Product", description="Test", price=10000)
        test_db.add(product)
        
        # Create inventory with 1 item
        inventory = Inventory(product_id=42, stock=1, reserved=0)
        test_db.add(inventory)
        
        await test_db.commit()
        yield
        
        # Clean up
        await test_db.execute(OrderAttempt.__table__.delete())
        await test_db.execute(Order.__table__.delete())
        await test_db.commit()
    
    @pytest.mark.asyncio
    async def test_atomic_update_race_condition(self, test_db: AsyncSession, setup_test_data):
        """Test that atomic UPDATE prevents race conditions"""
        service = OrderService(test_db)
        
        # Simulate concurrent requests
        tasks = []
        for i in range(50):
            task = service.create_order_atomic_update(i, 42)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Analyze results
        successful_orders = 0
        out_of_stock_errors = 0
        
        for result in results:
            if isinstance(result, Exception):
                continue
            
            if isinstance(result, dict) and result.get("status") == "success":
                successful_orders += 1
            else:
                out_of_stock_errors += 1
        
        # Assertions
        assert successful_orders == 1, f"Expected 1 successful order, got {successful_orders}"
        assert out_of_stock_errors == 49, f"Expected 49 out-of-stock errors, got {out_of_stock_errors}"
        
        # Verify database state
        inventory_query = "SELECT stock FROM inventory WHERE product_id = 42"
        result = await test_db.execute(inventory_query)
        stock = result.scalar()
        
        assert stock == 0, f"Expected stock to be 0, got {stock}"
    
    @pytest.mark.asyncio
    async def test_pessimistic_lock_race_condition(self, test_db: AsyncSession, setup_test_data):
        """Test that pessimistic locking prevents race conditions"""
        service = OrderService(test_db)
        
        # Simulate concurrent requests
        tasks = []
        for i in range(50):
            task = service.create_order_pessimistic_lock(i, 42)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Analyze results
        successful_orders = 0
        out_of_stock_errors = 0
        
        for result in results:
            if isinstance(result, Exception):
                continue
            
            if isinstance(result, dict) and result.get("status") == "success":
                successful_orders += 1
            else:
                out_of_stock_errors += 1
        
        # Assertions
        assert successful_orders == 1, f"Expected 1 successful order, got {successful_orders}"
        assert out_of_stock_errors == 49, f"Expected 49 out-of-stock errors, got {out_of_stock_errors}"
    
    @pytest.mark.asyncio
    async def test_idempotency_protection(self, test_db: AsyncSession, setup_test_data):
        """Test that idempotency prevents duplicate orders"""
        service = OrderService(test_db)
        
        # First request
        first_result = await service.create_order_with_idempotency(999, 42)
        
        # Multiple retries of the same request
        retry_tasks = []
        for i in range(10):
            task = service.create_order_with_idempotency(999, 42)
            retry_tasks.append(task)
        
        retry_results = await asyncio.gather(*retry_tasks, return_exceptions=True)
        
        # Analyze results
        successful_orders = 0
        existing_orders = 0
        
        for result in retry_results:
            if isinstance(result, Exception):
                continue
            
            if isinstance(result, dict):
                if result.get("existing_order"):
                    existing_orders += 1
                elif result.get("status") == "success":
                    successful_orders += 1
        
        # Assertions
        assert first_result["status"] == "success"
        assert existing_orders == 10, f"Expected 10 existing orders, got {existing_orders}"
        assert successful_orders == 0, f"Expected 0 new successful orders, got {successful_orders}"
        
        # Verify only one order was created
        order_query = "SELECT COUNT(*) FROM orders WHERE user_id = 999 AND product_id = 42"
        result = await test_db.execute(order_query)
        order_count = result.scalar()
        
        assert order_count == 1, f"Expected 1 order in database, got {order_count}"
    
    @pytest.mark.asyncio
    async def test_out_of_stock_handling(self, test_db: AsyncSession):
        """Test proper handling when stock is 0"""
        # Setup with 0 stock
        inventory = Inventory(product_id=42, stock=0, reserved=0)
        test_db.add(inventory)
        await test_db.commit()
        
        service = OrderService(test_db)
        
        # Try to create order
        with pytest.raises(Exception) as exc_info:
            await service.create_order_atomic_update(1, 42)
        
        assert "Out of Stock" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_concurrent_api_endpoints(self, setup_test_data):
        """Test race condition via HTTP API endpoints"""
        with TestClient(app) as client:
            # Setup test data via API
            client.post("/setup-test-data")
            
            # Fire 50 concurrent requests
            async with httpx.AsyncClient() as http_client:
                tasks = []
                for i in range(50):
                    task = http_client.post(
                        "http://test/order/product/42",
                        json={"user_id": i, "strategy": "atomic"}
                    )
                    tasks.append(task)
                
                responses = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Analyze results
                successful_orders = 0
                out_of_stock_errors = 0
                
                for response in responses:
                    if isinstance(response, Exception):
                        continue
                    
                    if response.status_code == 200:
                        successful_orders += 1
                    elif response.status_code == 400:
                        data = response.json()
                        if "Out of Stock" in data.get("detail", ""):
                            out_of_stock_errors += 1
                
                # Assertions
                assert successful_orders == 1, f"Expected 1 successful order, got {successful_orders}"
                assert out_of_stock_errors == 49, f"Expected 49 out-of-stock errors, got {out_of_stock_errors}"


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
