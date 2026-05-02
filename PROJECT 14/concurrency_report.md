# Forensic Report: Analytics Data Loss

## 1. Why the GIL Failed Us
Explain that while the GIL prevents multiple threads from executing Python *bytecode* simultaneously, it does NOT prevent a thread from being interrupted between the `BINARY_SUBSCR` (Read) and `STORE_SUBSCR` (Write) instructions.

## 2. Comparison of Fixes
| Strategy | Correct? | Ops/Sec | Complexity | Recommended Use |
| :--- | :--- | :--- | :--- | :--- |
| **Legacy** | NO | High | Low | Never (Single thread only) |
| **Locking** | YES | Low | Low | Low-traffic local apps |
| **Queue** | YES | Medium | Medium | When writing to a DB |
| **Redis** | YES | High | Low | Distributed microservices |

## 3. The Winner: Local Batching (Stretch Goal)
Explain how counting locally for 100ms and then sending a single `INCRBY` to Redis provides 99% accuracy with 1000x less network overhead.

## 4. Visualizing the Race Condition