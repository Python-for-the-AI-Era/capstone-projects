# DataGov API: Rate Limiting Specification

## 1. The Strategy: Sliding Window Log
Explain why we used **Redis Sorted Sets (ZSETs)** instead of simple **INCR**. 
Why is a fixed window (e.g., reset at the top of the hour) unfair to users?

## 2. Atomicity via Lua
Explain why we sent code (Lua) to the data (Redis). 
What is a **Race Condition** in the context of rate limiting?

## 3. Tiered Configuration
| Tier | Limit | Window | Burst Allowed? |
| :--- | :--- | :--- | :--- |
| Free | 100/hr | 3600s | No |
| Paid | 10,000/hr | 3600s | Yes (Stretch Goal) |
| Enterprise | Unlimited | N/A | N/A |

## 4. Header Implementation
Show an example of the headers returned:
- `X-RateLimit-Limit`: 100
- `X-RateLimit-Remaining`: 45
- `X-RateLimit-Reset`: 1714656000 (Epoch)