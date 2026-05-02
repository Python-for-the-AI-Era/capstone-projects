import tracemalloc

def start_audit():
    tracemalloc.start()
    # Capture initial state
    snapshot1 = tracemalloc.take_snapshot()
    
    # Run 1000 simulated conversations...
    
    snapshot2 = tracemalloc.take_snapshot()
    top_stats = snapshot2.compare_to(snapshot1, 'lineno')
    
    for stat in top_stats[:5]:
        print(stat) # Proves that message objects are accumulating