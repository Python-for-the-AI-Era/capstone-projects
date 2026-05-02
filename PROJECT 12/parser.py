import time
import csv

def parse_heavy_financial_csv(file_path: str):
    """
    FAULTY SYNC LOGIC:
    This function takes 3-5 seconds to run. 
    Because it uses standard 'time.sleep' and synchronous 'csv', 
    it holds the Python GIL and the Event Loop hostage.
    """
    print(f"--- Starting heavy parse on {file_path} ---")
    start_time = time.time()
    
    # Simulating 40,000 rows of complex reconciliation logic
    total = 0
    for i in range(4000000):
        total += i * i  # Simulated CPU work
    
    time.sleep(3) # Simulated heavy I/O or processing time
    
    print(f"--- Finished parse in {time.time() - start_time:.2f}s ---")
    return {"status": "reconciled", "sum": total}