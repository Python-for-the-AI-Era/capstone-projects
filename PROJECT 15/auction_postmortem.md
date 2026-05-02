# BidNow Engineering: Atomic Auction Engine

## 1. The Race Condition Proof
Explain why the Python `if` statement failed under load. 
Discuss the "Check-then-Act" anti-pattern in distributed systems.

## 2. The Lua Solution
Explain why we moved the logic into Redis. 
- **Atomicity:** Why can't another bid "sneak in" during the Lua execution?
- **Efficiency:** How does this reduce network round-trips?

## 3. Real-Time Architecture
- **Redis Pub/Sub:** How does this decouple the bid processing from the WebSocket broadcasting?
- **Scaling:** If we have 1 million bidders, how would we scale the WebSocket workers?

## 4. Benchmarks (Load Test)
| Metrics | Results |
| :--- | :--- |
| **Concurrent Bidders** | 5,000 |
| **Bids per second** | 50,000 |
| **P99 Latency** | < 15ms |
| **Data Integrity** | 100% (No out-of-order wins) |