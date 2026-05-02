from concurrent.futures import ProcessPoolExecutor
import asyncio

# TASK: Initialize the executor
# TASK: Use loop.run_in_executor to offload parse_heavy_financial_csv
# TASK: Demonstrate the difference between ThreadPool (I/O) 
#       and ProcessPool (CPU-bound/GIL-bypass).