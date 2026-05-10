#!/usr/bin/env python3
"""
Test client for the Document Similarity Search Engine
"""

import requests
import time
import json
import random

# Sample legal queries for testing
test_queries = [
    "land ownership dispute between family members",
    "breach of contract in commercial transaction",
    "employment termination without cause",
    "intellectual property infringement case",
    "corporate governance and shareholder rights",
    "tax evasion and financial fraud",
    "environmental regulation compliance",
    "consumer protection law violation",
    "bankruptcy and debt restructuring",
    "family law divorce proceedings",
    "criminal defense constitutional rights",
    "civil rights discrimination case",
    "medical malpractice negligence",
    "insurance claim bad faith",
    "real estate contract disputes"
]

def test_search_api(base_url="http://127.0.0.1:8000", num_tests=100):
    """Test the search API with various queries"""
    print(f"Testing search API at {base_url}")
    print(f"Running {num_tests} test queries...")
    
    latencies = []
    successful_requests = 0
    
    for i in range(num_tests):
        query = random.choice(test_queries)
        k = random.randint(3, 10)
        
        start_time = time.perf_counter()
        
        try:
            response = requests.post(
                f"{base_url}/search",
                json={"query": query, "k": k},
                timeout=10
            )
            
            latency = (time.perf_counter() - start_time) * 1000  # Convert to ms
            latencies.append(latency)
            
            if response.status_code == 200:
                successful_requests += 1
                response_data = response.json()
                results = response_data.get('results', [])
                
                if i % 20 == 0:  # Print sample results every 20 requests
                    print(f"\nQuery {i+1}: '{query}'")
                    print(f"Latency: {latency:.2f}ms")
                    print(f"Results: {len(results)} documents")
                    for j, result in enumerate(results[:3]):
                        print(f"  {j+1}. ID: {result['doc_id']}, Score: {result['score']:.4f}")
                        print(f"     Title: {result['title'][:80]}...")
            else:
                print(f"Error: HTTP {response.status_code} - {response.text}")
                
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            continue
    
    # Calculate statistics
    if latencies:
        latencies.sort()
        p50 = latencies[len(latencies)//2]
        p95 = latencies[int(len(latencies)*0.95)]
        p99 = latencies[int(len(latencies)*0.99)]
        avg_latency = sum(latencies) / len(latencies)
        
        print(f"\n=== Performance Results ===")
        print(f"Successful requests: {successful_requests}/{num_tests} ({successful_requests/num_tests*100:.1f}%)")
        print(f"Average latency: {avg_latency:.2f}ms")
        print(f"P50 latency: {p50:.2f}ms")
        print(f"P95 latency: {p95:.2f}ms")
        print(f"P99 latency: {p99:.2f}ms")
        
        if p99 < 100:
            print("✅ P99 latency meets <100ms target!")
        else:
            print("❌ P99 latency exceeds 100ms target")
    else:
        print("No successful requests completed")

def test_specific_query(base_url="http://127.0.0.1:8000", query="land ownership rights"):
    """Test a specific query and show detailed results"""
    print(f"\nTesting specific query: '{query}'")
    
    try:
        response = requests.post(
            f"{base_url}/search",
            json={"query": query, "k": 5},
            timeout=10
        )
        
        if response.status_code == 200:
            response_data = response.json()
            results = response_data.get('results', [])
            print(f"Found {len(results)} results:")
            
            for i, result in enumerate(results, 1):
                print(f"\n{i}. Document ID: {result['doc_id']}")
                print(f"   Similarity Score: {result['score']:.4f}")
                print(f"   Title: {result['title']}")
        else:
            print(f"Error: HTTP {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test client for Document Similarity Search Engine")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="Base URL of the API")
    parser.add_argument("--query", help="Test a specific query")
    parser.add_argument("--benchmark", action="store_true", help="Run benchmark with 1000 queries")
    parser.add_argument("--tests", type=int, default=100, help="Number of test queries to run")
    
    args = parser.parse_args()
    
    if args.query:
        test_specific_query(args.url, args.query)
    elif args.benchmark:
        test_search_api(args.url, 1000)
    else:
        test_search_api(args.url, args.tests)
