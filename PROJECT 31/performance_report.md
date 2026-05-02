# Forensic Report: AI Chatbot Memory Leak

## 1. Problem Identification
Using `tracemalloc`, we identified that `ConversationBufferMemory` was holding 
100% of all chat history in the local Python heap. As the user base grew, 
the RAM usage grew linearly until OOM (Out of Memory) crash.

## 2. Implemented Solutions
- **Bounded Context:** Switched to `ConversationSummaryBufferMemory`. Even a 
  month-long conversation will never exceed 2,000 tokens in the prompt.
- **Externalized State:** Moved all history to **Redis**. The Python server is now 
  effectively stateless. If the server dies, the user's history survives in Redis.
- **Auto-Cleanup:** Implemented a 24-hour TTL. Data is self-cleaning.

## 3. Load Test Results
| Duration | Old Architecture (RAM) | New Architecture (RAM) |
| :--- | :--- | :--- |
| 1 Hour | 450MB | 180MB |
| 12 Hours | 1.8GB | 195MB |
| 48 Hours | CRASHED | 198MB (Stable) |

## 4. Maintenance
We have added a `psutil` circuit breaker. If local RAM usage hits 2GB, 
an alert is sent to Sentry, and the process performs an emergency flush.