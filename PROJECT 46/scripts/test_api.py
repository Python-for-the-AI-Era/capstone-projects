#!/usr/bin/env python3
"""
API testing script for property price prediction.

This script tests the FastAPI endpoints with various scenarios
and validates the responses.
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Any
import requests
import numpy as np
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PropertyAPITester:
    """Test the property price prediction API."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        """
        Initialize the API tester.
        
        Args:
            base_url: Base URL of the API
        """
        self.base_url = base_url
        self.session = requests.Session()
        self.test_results = {}
        
        # Sample test data
        self.sample_properties = [
            {
                "name": "Lagos Luxury Apartment",
                "features": {
                    "city": "Lagos",
                    "lga": "Ikoyi",
                    "property_type": "Apartment",
                    "size_sqm": 120.5,
                    "bedrooms": 3,
                    "bathrooms": 2,
                    "age_years": 5,
                    "latitude": 6.4520,
                    "longitude": 3.4160,
                    "has_parking": True,
                    "has_pool": True,
                    "has_gym": True,
                    "has_security": True,
                    "has_elevator": True
                }
            },
            {
                "name": "Abuja Family House",
                "features": {
                    "city": "Abuja",
                    "lga": "Asokoro",
                    "property_type": "Detached House",
                    "size_sqm": 250.0,
                    "bedrooms": 4,
                    "bathrooms": 3,
                    "age_years": 2,
                    "latitude": 9.0840,
                    "longitude": 7.4960,
                    "has_parking": True,
                    "has_pool": False,
                    "has_gym": False,
                    "has_security": True,
                    "has_elevator": False
                }
            },
            {
                "name": "Port Harcourt Studio",
                "features": {
                    "city": "Port Harcourt",
                    "lga": "GRA",
                    "property_type": "Studio",
                    "size_sqm": 35.0,
                    "bedrooms": 1,
                    "bathrooms": 1,
                    "age_years": 8,
                    "latitude": 4.8156,
                    "longitude": 7.0498,
                    "has_parking": False,
                    "has_pool": False,
                    "has_gym": False,
                    "has_security": True,
                    "has_elevator": False
                }
            }
        ]
        
        logger.info(f"API tester initialized for {base_url}")
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all API tests."""
        logger.info("Starting comprehensive API testing...")
        
        test_results = {
            'timestamp': datetime.now().isoformat(),
            'base_url': self.base_url,
            'tests': {}
        }
        
        # Test basic endpoints
        test_results['tests']['health_check'] = self.test_health_check()
        test_results['tests']['model_info'] = self.test_model_info()
        test_results['tests']['supported_cities'] = self.test_supported_cities()
        test_results['tests']['property_types'] = self.test_property_types()
        
        # Test price estimation
        test_results['tests']['single_estimation'] = self.test_single_estimation()
        test_results['tests']['batch_estimation'] = self.test_batch_estimation()
        
        # Test edge cases
        test_results['tests']['edge_cases'] = self.test_edge_cases()
        
        # Test performance
        test_results['tests']['performance'] = self.test_performance()
        
        # Calculate overall results
        total_tests = sum(len(tests) for tests in test_results['tests'].values())
        passed_tests = sum(
            sum(1 for result in tests.values() if result.get('success', False))
            for tests in test_results['tests'].values()
        )
        
        test_results['summary'] = {
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'failed_tests': total_tests - passed_tests,
            'success_rate': (passed_tests / total_tests * 100) if total_tests > 0 else 0
        }
        
        self.test_results = test_results
        return test_results
    
    def test_health_check(self) -> Dict[str, Any]:
        """Test health check endpoint."""
        logger.info("Testing health check endpoint...")
        
        results = {}
        
        try:
            response = self.session.get(f"{self.base_url}/health")
            
            results['status_code'] = response.status_code
            results['success'] = response.status_code == 200
            
            if response.status_code == 200:
                data = response.json()
                results['data'] = data
                results['models_loaded'] = data.get('models_loaded', False)
                logger.info("Health check passed")
            else:
                results['error'] = response.text
                logger.error(f"Health check failed: {response.status_code}")
        
        except Exception as e:
            results['success'] = False
            results['error'] = str(e)
            logger.error(f"Health check exception: {e}")
        
        return results
    
    def test_model_info(self) -> Dict[str, Any]:
        """Test model info endpoint."""
        logger.info("Testing model info endpoint...")
        
        results = {}
        
        try:
            response = self.session.get(f"{self.base_url}/model/info")
            
            results['status_code'] = response.status_code
            results['success'] = response.status_code == 200
            
            if response.status_code == 200:
                data = response.json()
                results['data'] = data
                
                # Validate required fields
                required_fields = ['model_type', 'version', 'feature_count', 'supported_cities']
                missing_fields = [field for field in required_fields if field not in data]
                
                results['missing_fields'] = missing_fields
                results['validation_passed'] = len(missing_fields) == 0
                
                if results['validation_passed']:
                    logger.info("Model info test passed")
                else:
                    logger.warning(f"Model info missing fields: {missing_fields}")
            else:
                results['error'] = response.text
                logger.error(f"Model info failed: {response.status_code}")
        
        except Exception as e:
            results['success'] = False
            results['error'] = str(e)
            logger.error(f"Model info exception: {e}")
        
        return results
    
    def test_supported_cities(self) -> Dict[str, Any]:
        """Test supported cities endpoint."""
        logger.info("Testing supported cities endpoint...")
        
        results = {}
        
        try:
            response = self.session.get(f"{self.base_url}/cities/supported")
            
            results['status_code'] = response.status_code
            results['success'] = response.status_code == 200
            
            if response.status_code == 200:
                data = response.json()
                results['data'] = data
                
                cities = data.get('cities', [])
                results['city_count'] = len(cities)
                
                # Validate city structure
                if cities:
                    sample_city = cities[0]
                    required_fields = ['name', 'median_price_per_sqm']
                    missing_fields = [field for field in required_fields if field not in sample_city]
                    
                    results['missing_fields'] = missing_fields
                    results['validation_passed'] = len(missing_fields) == 0
                else:
                    results['validation_passed'] = False
                    results['missing_fields'] = ['No cities found']
                
                if results['validation_passed']:
                    logger.info(f"Supported cities test passed ({len(cities)} cities)")
                else:
                    logger.warning(f"Supported cities validation failed")
            else:
                results['error'] = response.text
                logger.error(f"Supported cities failed: {response.status_code}")
        
        except Exception as e:
            results['success'] = False
            results['error'] = str(e)
            logger.error(f"Supported cities exception: {e}")
        
        return results
    
    def test_property_types(self) -> Dict[str, Any]:
        """Test property types endpoint."""
        logger.info("Testing property types endpoint...")
        
        results = {}
        
        try:
            response = self.session.get(f"{self.base_url}/property/types")
            
            results['status_code'] = response.status_code
            results['success'] = response.status_code == 200
            
            if response.status_code == 200:
                data = response.json()
                results['data'] = data
                
                property_types = data.get('property_types', [])
                results['type_count'] = len(property_types)
                
                # Validate property type structure
                if property_types:
                    sample_type = property_types[0]
                    required_fields = ['name', 'description']
                    missing_fields = [field for field in required_fields if field not in sample_type]
                    
                    results['missing_fields'] = missing_fields
                    results['validation_passed'] = len(missing_fields) == 0
                else:
                    results['validation_passed'] = False
                    results['missing_fields'] = ['No property types found']
                
                if results['validation_passed']:
                    logger.info(f"Property types test passed ({len(property_types)} types)")
                else:
                    logger.warning(f"Property types validation failed")
            else:
                results['error'] = response.text
                logger.error(f"Property types failed: {response.status_code}")
        
        except Exception as e:
            results['success'] = False
            results['error'] = str(e)
            logger.error(f"Property types exception: {e}")
        
        return results
    
    def test_single_estimation(self) -> Dict[str, Any]:
        """Test single property price estimation."""
        logger.info("Testing single property estimation...")
        
        results = {}
        
        for i, prop in enumerate(self.sample_properties):
            prop_name = prop['name']
            logger.info(f"Testing {prop_name}...")
            
            try:
                response = self.session.post(
                    f"{self.base_url}/estimate",
                    json=prop['features']
                )
                
                prop_result = {
                    'status_code': response.status_code,
                    'success': response.status_code == 200
                }
                
                if response.status_code == 200:
                    data = response.json()
                    prop_result['data'] = data
                    
                    # Validate response structure
                    required_fields = ['low', 'mid', 'high', 'explanation', 'feature_importance']
                    missing_fields = [field for field in required_fields if field not in data]
                    
                    prop_result['missing_fields'] = missing_fields
                    prop_result['validation_passed'] = len(missing_fields) == 0
                    
                    # Validate price bounds
                    low = data.get('low', 0)
                    mid = data.get('mid', 0)
                    high = data.get('high', 0)
                    
                    prop_result['bounds_valid'] = low <= mid <= high
                    prop_result['prices_positive'] = all(p > 0 for p in [low, mid, high])
                    
                    # Validate explanations
                    explanations = data.get('explanation', [])
                    prop_result['explanation_count'] = len(explanations)
                    prop_result['explanation_valid'] = len(explanations) <= 3  # Top 3 features
                    
                    if prop_result['validation_passed'] and prop_result['bounds_valid']:
                        logger.info(f"✓ {prop_name} estimation passed")
                    else:
                        logger.warning(f"✗ {prop_name} estimation validation failed")
                else:
                    prop_result['error'] = response.text
                    logger.error(f"✗ {prop_name} estimation failed: {response.status_code}")
                
                results[prop_name] = prop_result
            
            except Exception as e:
                results[prop_name] = {
                    'success': False,
                    'error': str(e)
                }
                logger.error(f"✗ {prop_name} estimation exception: {e}")
        
        # Calculate overall success
        successful_props = sum(1 for result in results.values() if result.get('success', False))
        results['overall_success'] = successful_props == len(self.sample_properties)
        results['successful_count'] = successful_props
        results['total_count'] = len(self.sample_properties)
        
        return results
    
    def test_batch_estimation(self) -> Dict[str, Any]:
        """Test batch property price estimation."""
        logger.info("Testing batch property estimation...")
        
        results = {}
        
        try:
            # Prepare batch request
            batch_request = {
                "properties": [prop['features'] for prop in self.sample_properties],
                "batch_id": f"test_batch_{int(time.time())}"
            }
            
            start_time = time.time()
            response = self.session.post(
                f"{self.base_url}/estimate/batch",
                json=batch_request
            )
            processing_time = time.time() - start_time
            
            results['status_code'] = response.status_code
            results['success'] = response.status_code == 200
            results['processing_time'] = processing_time
            
            if response.status_code == 200:
                data = response.json()
                results['data'] = data
                
                # Validate response structure
                required_fields = ['batch_id', 'estimates', 'processing_time']
                missing_fields = [field for field in required_fields if field not in data]
                
                results['missing_fields'] = missing_fields
                results['validation_passed'] = len(missing_fields) == 0
                
                # Validate estimates
                estimates = data.get('estimates', [])
                results['estimate_count'] = len(estimates)
                results['expected_count'] = len(self.sample_properties)
                results['count_match'] = len(estimates) == len(self.sample_properties)
                
                # Validate each estimate
                valid_estimates = 0
                for i, estimate in enumerate(estimates):
                    required_fields = ['low', 'mid', 'high', 'explanation']
                    if all(field in estimate for field in required_fields):
                        low, mid, high = estimate['low'], estimate['mid'], estimate['high']
                        if low <= mid <= high and all(p > 0 for p in [low, mid, high]):
                            valid_estimates += 1
                
                results['valid_estimates'] = valid_estimates
                results['all_estimates_valid'] = valid_estimates == len(estimates)
                
                if results['validation_passed'] and results['count_match'] and results['all_estimates_valid']:
                    logger.info(f"✓ Batch estimation passed ({len(estimates)} properties)")
                else:
                    logger.warning("✗ Batch estimation validation failed")
            else:
                results['error'] = response.text
                logger.error(f"✗ Batch estimation failed: {response.status_code}")
        
        except Exception as e:
            results['success'] = False
            results['error'] = str(e)
            logger.error(f"✗ Batch estimation exception: {e}")
        
        return results
    
    def test_edge_cases(self) -> Dict[str, Any]:
        """Test edge cases and error handling."""
        logger.info("Testing edge cases...")
        
        results = {}
        
        # Test 1: Invalid city
        results['invalid_city'] = self._test_invalid_city()
        
        # Test 2: Invalid property type
        results['invalid_property_type'] = self._test_invalid_property_type()
        
        # Test 3: Invalid values (negative size)
        results['invalid_values'] = self._test_invalid_values()
        
        # Test 4: Missing required fields
        results['missing_fields'] = self._test_missing_fields()
        
        # Test 5: Empty batch
        results['empty_batch'] = self._test_empty_batch()
        
        return results
    
    def _test_invalid_city(self) -> Dict[str, Any]:
        """Test with invalid city."""
        try:
            features = self.sample_properties[0]['features'].copy()
            features['city'] = 'InvalidCity'
            
            response = self.session.post(f"{self.base_url}/estimate", json=features)
            
            return {
                'success': response.status_code == 422,  # Validation error
                'status_code': response.status_code,
                'expected_validation_error': True
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _test_invalid_property_type(self) -> Dict[str, Any]:
        """Test with invalid property type."""
        try:
            features = self.sample_properties[0]['features'].copy()
            features['property_type'] = 'InvalidType'
            
            response = self.session.post(f"{self.base_url}/estimate", json=features)
            
            return {
                'success': response.status_code == 422,  # Validation error
                'status_code': response.status_code,
                'expected_validation_error': True
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _test_invalid_values(self) -> Dict[str, Any]:
        """Test with invalid values."""
        try:
            features = self.sample_properties[0]['features'].copy()
            features['size_sqm'] = -100  # Invalid negative size
            
            response = self.session.post(f"{self.base_url}/estimate", json=features)
            
            return {
                'success': response.status_code == 422,  # Validation error
                'status_code': response.status_code,
                'expected_validation_error': True
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _test_missing_fields(self) -> Dict[str, Any]:
        """Test with missing required fields."""
        try:
            features = self.sample_properties[0]['features'].copy()
            del features['bedrooms']  # Remove required field
            
            response = self.session.post(f"{self.base_url}/estimate", json=features)
            
            return {
                'success': response.status_code == 422,  # Validation error
                'status_code': response.status_code,
                'expected_validation_error': True
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _test_empty_batch(self) -> Dict[str, Any]:
        """Test with empty batch."""
        try:
            batch_request = {
                "properties": [],
                "batch_id": "empty_test"
            }
            
            response = self.session.post(f"{self.base_url}/estimate/batch", json=batch_request)
            
            return {
                'success': response.status_code == 422,  # Validation error
                'status_code': response.status_code,
                'expected_validation_error': True
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def test_performance(self) -> Dict[str, Any]:
        """Test API performance."""
        logger.info("Testing API performance...")
        
        results = {}
        
        # Test single request performance
        results['single_request'] = self._test_single_request_performance()
        
        # Test concurrent requests
        results['concurrent_requests'] = self._test_concurrent_requests()
        
        # Test batch performance
        results['batch_performance'] = self._test_batch_performance()
        
        return results
    
    def _test_single_request_performance(self) -> Dict[str, Any]:
        """Test single request performance."""
        try:
            features = self.sample_properties[0]['features']
            
            times = []
            for _ in range(5):  # 5 iterations
                start_time = time.time()
                response = self.session.post(f"{self.base_url}/estimate", json=features)
                end_time = time.time()
                
                if response.status_code == 200:
                    times.append(end_time - start_time)
            
            if times:
                return {
                    'success': True,
                    'avg_time': np.mean(times),
                    'min_time': np.min(times),
                    'max_time': np.max(times),
                    'iterations': len(times),
                    'under_1s': np.mean(times) < 1.0
                }
            else:
                return {'success': False, 'error': 'No successful requests'}
        
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _test_concurrent_requests(self) -> Dict[str, Any]:
        """Test concurrent request performance."""
        try:
            import threading
            import queue
            
            results_queue = queue.Queue()
            
            def make_request():
                features = self.sample_properties[0]['features']
                start_time = time.time()
                response = self.session.post(f"{self.base_url}/estimate", json=features)
                end_time = time.time()
                results_queue.put({
                    'status_code': response.status_code,
                    'time': end_time - start_time
                })
            
            # Start 10 concurrent requests
            threads = []
            start_time = time.time()
            
            for _ in range(10):
                thread = threading.Thread(target=make_request)
                thread.start()
                threads.append(thread)
            
            # Wait for all threads to complete
            for thread in threads:
                thread.join()
            
            total_time = time.time() - start_time
            
            # Collect results
            results_list = []
            while not results_queue.empty():
                results_list.append(results_queue.get())
            
            successful_requests = [r for r in results_list if r['status_code'] == 200]
            
            return {
                'success': len(successful_requests) == 10,
                'total_time': total_time,
                'successful_requests': len(successful_requests),
                'avg_request_time': np.mean([r['time'] for r in successful_requests]) if successful_requests else 0,
                'concurrent_efficiency': total_time / len(successful_requests) if successful_requests else 0
            }
        
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _test_batch_performance(self) -> Dict[str, Any]:
        """Test batch request performance."""
        try:
            # Test different batch sizes
            batch_sizes = [1, 5, 10, 20]
            performance_results = {}
            
            for size in batch_sizes:
                # Create batch request
                batch_request = {
                    "properties": [self.sample_properties[0]['features']] * size,
                    "batch_id": f"perf_test_{size}"
                }
                
                start_time = time.time()
                response = self.session.post(f"{self.base_url}/estimate/batch", json=batch_request)
                end_time = time.time()
                
                performance_results[f'batch_size_{size}'] = {
                    'success': response.status_code == 200,
                    'time': end_time - start_time,
                    'time_per_item': (end_time - start_time) / size if response.status_code == 200 else None
                }
            
            return {
                'success': True,
                'performance_results': performance_results
            }
        
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def save_results(self, filepath: str):
        """Save test results to file."""
        with open(filepath, 'w') as f:
            json.dump(self.test_results, f, indent=2, default=str)
        logger.info(f"Test results saved to {filepath}")
    
    def print_summary(self):
        """Print test summary."""
        if not self.test_results:
            print("No test results available")
            return
        
        summary = self.test_results['summary']
        
        print("\n" + "="*60)
        print("API TEST SUMMARY")
        print("="*60)
        print(f"Total Tests: {summary['total_tests']}")
        print(f"Passed: {summary['passed_tests']}")
        print(f"Failed: {summary['failed_tests']}")
        print(f"Success Rate: {summary['success_rate']:.1f}%")
        
        print(f"\nTest Categories:")
        for category, tests in self.test_results['tests'].items():
            if isinstance(tests, dict) and 'success' in tests:
                status = "✓" if tests['success'] else "✗"
                print(f"  {status} {category}")
            elif isinstance(tests, dict):
                passed = sum(1 for test in tests.values() if isinstance(test, dict) and test.get('success', False))
                total = len(tests)
                status = "✓" if passed == total else "✗"
                print(f"  {status} {category} ({passed}/{total})")
        
        print("="*60)


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Test Property Price Prediction API')
    parser.add_argument('--url', default='http://localhost:8000', help='API base URL')
    parser.add_argument('--output', help='Output file for test results')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Run tests
    tester = PropertyAPITester(args.url)
    results = tester.run_all_tests()
    
    # Print summary
    tester.print_summary()
    
    # Save results
    if args.output:
        tester.save_results(args.output)
    
    # Exit with appropriate code
    success_rate = results['summary']['success_rate']
    return 0 if success_rate >= 90 else 1


if __name__ == '__main__':
    exit(main())
