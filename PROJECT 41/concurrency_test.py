import asyncio
import httpx
import json
import time
from typing import List, Dict, Tuple
from dataclasses import dataclass
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class TestResult:
    """Results from a concurrency test"""
    strategy: str
    total_requests: int
    successful_orders: int
    out_of_stock_errors: int
    other_errors: int
    response_times: List[float]
    duplicate_orders: int
    test_duration: float


class ConcurrencyTester:
    """Comprehensive concurrency testing for race condition detection"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def setup_test_data(self):
        """Setup test data for race condition testing"""
        try:
            response = await self.client.post(f"{self.base_url}/setup-test-data")
            if response.status_code == 200:
                logger.info("Test data setup successful")
                return True
            else:
                logger.error(f"Failed to setup test data: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error setting up test data: {e}")
            return False
    
    async def reset_test_data(self):
        """Reset test data between tests"""
        try:
            response = await self.client.post(f"{self.base_url}/reset-test-data")
            if response.status_code == 200:
                logger.info("Test data reset successful")
                return True
            else:
                logger.error(f"Failed to reset test data: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error resetting test data: {e}")
            return False
    
    async def hammer_order_system(self, strategy: str = "atomic", num_requests: int = 50) -> TestResult:
        """
        TASK 1: Reproduce race condition with concurrent requests
        Fire multiple requests simultaneously to test for race conditions
        """
        logger.info(f"Testing {strategy} strategy with {num_requests} concurrent requests")
        
        # Reset test data before each test
        await self.reset_test_data()
        
        # Prepare requests
        url = f"{self.base_url}/order/product/42"
        tasks = []
        response_times = []
        
        # Create all tasks to fire simultaneously
        for i in range(num_requests):
            task = self._single_request(url, i, strategy)
            tasks.append(task)
        
        # Fire all requests at once
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        test_duration = time.time() - start_time
        
        # Analyze results
        successful_orders = 0
        out_of_stock_errors = 0
        other_errors = 0
        duplicate_orders = 0
        order_ids = set()
        
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Request failed with exception: {result}")
                other_errors += 1
                continue
            
            response_time, response = result
            
            if response_time:
                response_times.append(response_time)
            
            if response.status_code == 200:
                successful_orders += 1
                # Check for duplicate order IDs
                try:
                    data = response.json()
                    order_id = data.get("order_id")
                    if order_id:
                        if order_id in order_ids:
                            duplicate_orders += 1
                            logger.warning(f"Duplicate order ID detected: {order_id}")
                        else:
                            order_ids.add(order_id)
                except json.JSONDecodeError:
                    pass
            
            elif response.status_code == 400:
                # Check if it's an out of stock error
                try:
                    data = response.json()
                    if "Out of Stock" in data.get("detail", ""):
                        out_of_stock_errors += 1
                    else:
                        other_errors += 1
                except json.JSONDecodeError:
                    other_errors += 1
            else:
                other_errors += 1
        
        return TestResult(
            strategy=strategy,
            total_requests=num_requests,
            successful_orders=successful_orders,
            out_of_stock_errors=out_of_stock_errors,
            other_errors=other_errors,
            response_times=response_times,
            duplicate_orders=duplicate_orders,
            test_duration=test_duration
        )
    
    async def _single_request(self, url: str, user_id: int, strategy: str) -> Tuple[float, httpx.Response]:
        """Execute a single order request"""
        start_time = time.time()
        
        try:
            response = await self.client.post(
                url, 
                json={"user_id": user_id, "strategy": strategy}
            )
            response_time = time.time() - start_time
            return response_time, response
        except Exception as e:
            response_time = time.time() - start_time
            raise e
    
    async def test_all_strategies(self, num_requests: int = 50) -> List[TestResult]:
        """Test all locking strategies"""
        strategies = ["atomic", "pessimistic", "idempotent"]
        results = []
        
        for strategy in strategies:
            logger.info(f"\n{'='*60}")
            logger.info(f"Testing {strategy.upper()} strategy")
            logger.info(f"{'='*60}")
            
            result = await self.hammer_order_system(strategy, num_requests)
            results.append(result)
            
            # Print results immediately
            self._print_test_result(result)
            
            # Wait a bit between tests
            await asyncio.sleep(1)
        
        return results
    
    def _print_test_result(self, result: TestResult):
        """Print detailed test results"""
        print(f"\n📊 {result.strategy.upper()} Strategy Results:")
        print(f"   Total Requests: {result.total_requests}")
        print(f"   ✅ Successful Orders: {result.successful_orders}")
        print(f"   ❌ Out of Stock Errors: {result.out_of_stock_errors}")
        print(f"   ⚠️  Other Errors: {result.other_errors}")
        print(f"   🔄 Duplicate Orders: {result.duplicate_orders}")
        print(f"   ⏱️  Test Duration: {result.test_duration:.2f}s")
        
        if result.response_times:
            avg_time = sum(result.response_times) / len(result.response_times)
            min_time = min(result.response_times)
            max_time = max(result.response_times)
            print(f"   📈 Response Times: avg={avg_time:.3f}s, min={min_time:.3f}s, max={max_time:.3f}s")
        
        # Race condition detection
        if result.successful_orders > 1:
            print(f"   🚨 RACE CONDITION DETECTED! Multiple orders succeeded!")
        elif result.successful_orders == 1:
            print(f"   ✅ No race condition - exactly 1 order succeeded")
        else:
            print(f"   ⚠️  No orders succeeded")
        
        print(f"   📊 Success Rate: {(result.successful_orders / result.total_requests * 100):.1f}%")
    
    async def validate_fixes(self, num_requests: int = 50) -> Dict[str, bool]:
        """
        TASK 4: Test the fixes - validate that race conditions are resolved
        """
        logger.info("🔍 Validating race condition fixes...")
        
        results = await self.test_all_strategies(num_requests)
        
        validation_results = {}
        
        for result in results:
            # Check if race condition is fixed (should be exactly 1 successful order)
            is_fixed = result.successful_orders == 1 and result.duplicate_orders == 0
            validation_results[result.strategy] = is_fixed
            
            if is_fixed:
                logger.info(f"✅ {result.strategy} strategy: RACE CONDITION FIXED")
            else:
                logger.error(f"❌ {result.strategy} strategy: RACE CONDITION STILL EXISTS")
        
        return validation_results
    
    async def test_idempotency(self, num_retries: int = 10) -> bool:
        """
        TASK 5: Test idempotency - same user+product request should return same order
        """
        logger.info("🔄 Testing idempotency...")
        
        await self.reset_test_data()
        
        url = f"{self.base_url}/order/product/42"
        user_id = 999  # Fixed user ID for idempotency test
        product_id = 42
        
        # First request
        first_response = await self.client.post(
            url, 
            json={"user_id": user_id, "strategy": "idempotent"}
        )
        
        if first_response.status_code != 200:
            logger.error("First request failed")
            return False
        
        first_data = first_response.json()
        first_order_id = first_data.get("order_id")
        
        if not first_order_id:
            logger.error("No order ID in first response")
            return False
        
        # Retry the same request multiple times
        for i in range(num_retries):
            await asyncio.sleep(0.1)  # Small delay between retries
            
            retry_response = await self.client.post(
                url, 
                json={"user_id": user_id, "strategy": "idempotent"}
            )
            
            if retry_response.status_code != 200:
                logger.error(f"Retry {i+1} failed with status {retry_response.status_code}")
                return False
            
            retry_data = retry_response.json()
            retry_order_id = retry_data.get("order_id")
            is_existing = retry_data.get("existing_order", False)
            
            if retry_order_id != first_order_id:
                logger.error(f"Retry {i+1} returned different order ID: {retry_order_id} vs {first_order_id}")
                return False
            
            if not is_existing:
                logger.warning(f"Retry {i+1} didn't indicate existing order")
        
        logger.info(f"✅ Idempotency test passed - all {num_retries} retries returned same order ID: {first_order_id}")
        return True


# Legacy function for backward compatibility
async def hammer_order_system():
    """Legacy function for backward compatibility"""
    async with ConcurrencyTester() as tester:
        result = await tester.hammer_order_system("atomic", 50)
        print(f"Total Successes: {result.successful_orders}")
        if result.successful_orders > 1:
            print("🚨 RACE CONDITION DETECTED!")
        else:
            print("✅ No race condition detected")


# Main testing functions
async def run_comprehensive_test():
    """Run comprehensive race condition testing"""
    async with ConcurrencyTester() as tester:
        # Setup test data
        if not await tester.setup_test_data():
            print("❌ Failed to setup test data")
            return
        
        # Test all strategies
        results = await tester.test_all_strategies(50)
        
        # Validate fixes
        validation = await tester.validate_fixes(50)
        
        # Test idempotency
        idempotency_passed = await tester.test_idempotency(10)
        
        # Summary
        print(f"\n{'='*60}")
        print("📋 FINAL SUMMARY")
        print(f"{'='*60}")
        
        for strategy, is_fixed in validation.items():
            status = "✅ FIXED" if is_fixed else "❌ BROKEN"
            print(f"{strategy.capitalize()} strategy: {status}")
        
        idempotency_status = "✅ WORKING" if idempotency_passed else "❌ BROKEN"
        print(f"Idempotency: {idempotency_status}")


if __name__ == "__main__":
    asyncio.run(run_comprehensive_test())