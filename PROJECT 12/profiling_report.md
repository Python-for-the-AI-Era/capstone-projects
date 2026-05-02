# Recon Performance Audit: Event Loop Blocking

## 1. The Evidence: Slow Callbacks
Show the logs from `PYTHONASYNCIODEBUG=1`. 
Example: `Executing <Task...> took 3.204 seconds`. Explain what this means for other users.

## 2. Offloading Strategies
- **ThreadPoolExecutor:** Why use this for I/O bound tasks?
- **ProcessPoolExecutor:** Why is this necessary for the heavy math in `parse_heavy_financial_csv` to bypass the GIL?

## 3. Latency Metrics (Before vs. After)
| Endpoint | Concurrent With Reconcile (Before) | Concurrent With Reconcile (After) |
| :--- | :--- | :--- |
| `/health` | 3.5 seconds (BLOCKED) | 0.008 seconds (CLEAN) |
| `/reconcile` | 3.5 seconds | 3.6 seconds (Total Wall Time) |

## 4. The Polars Streaming Fix (Stretch Goal)
Explain how using `polars.read_csv_batched` prevents the API from crashing when a user uploads a 2GB file.