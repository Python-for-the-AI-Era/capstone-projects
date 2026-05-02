import time
import statistics

def benchmark_search(client, num_queries=1000):
    latencies = []
    for _ in range(num_queries):
        start = time.perf_counter()
        client.post("/search", json={"query": "land ownership rights", "k": 5})
        latencies.append((time.perf_counter() - start) * 1000) # ms
        
    print(f"P50: {statistics.median(latencies):.2f}ms")
    print(f"P99: {np.percentile(latencies, 99):.2f}ms")