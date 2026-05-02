# Incident Report: Payroll Processing Stall

## 1. The Bottleneck: Serial Execution
Explain the math of `TotalTime = (N * Latency) / Workers`. 
Why did the serial loop make it impossible to scale?

## 2. The Fix: Distributed Chords
- Explain the **Group** pattern: Why is 5,000 small tasks better than 1 big task?
- **The Chord:** How do we ensure the "Success" email only sends after the *last* payment is confirmed?

## 3. Resilience: Token Buckets & Backoff
- How does the Redis **Token Bucket** prevent us from getting 429s from the bank?
- Why is `retry_backoff=True` essential for external API stability?

## 4. Performance Comparison
| Strategy | 5,000 Employees | Result |
| :--- | :--- | :--- |
| **Legacy (Serial)** | ~14 Hours | Failed (Silent) |
| **Refactored (Parallel)** | ~15 Minutes (with 20 workers) | Success |