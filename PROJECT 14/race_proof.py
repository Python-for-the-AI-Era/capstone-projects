import threading
from counter_legacy import GlobalCounter

def worker(counter, page_id, iterations):
    for _ in range(iterations):
        counter.increment(page_id)

def run_test():
    counter = GlobalCounter()
    threads = []
    num_threads = 100
    increments_per_thread = 1000
    expected = num_threads * increments_per_thread
    
    for _ in range(num_threads):
        t = threading.Thread(target=worker, args=(counter, "home", increments_per_thread))
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    actual = counter.counts.get("home", 0)
    print(f"Expected: {expected}")
    print(f"Actual:   {actual}")
    print(f"Loss:     {((expected - actual) / expected) * 100:.2f}%")

if __name__ == "__main__":
    run_test()