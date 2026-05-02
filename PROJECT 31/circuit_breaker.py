import psutil
import os

def check_memory_threshold():
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info().rss / (1024 * 1024) # Convert to MB
    
    if mem_info > 2000: # 2GB Threshold
        print("CRITICAL: Memory threshold exceeded. Flushing local caches.")
        # Logic to clear local LangChain caches or global variables