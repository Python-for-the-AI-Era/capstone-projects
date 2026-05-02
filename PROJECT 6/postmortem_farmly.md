# Incident Report: 2:07 AM Production Outage

## 1. The Root Cause: SARGability
Explain why `EXTRACT(month FROM created_at)` prevented the database from using an index. 
Define "Full Table Scan" and why it killed CPU usage.

## 2. Optimization 1: Indexing
- What is a **Partial Index** and why did we only index `status='completed'`?
- How much space did we save compared to a full index?

## 3. Optimization 2: Query Refactoring
Show the "Before" vs. "After" SQL query. 
Explain why `BETWEEN '2026-06-01' AND '2026-06-30'` is faster.

## 4. Optimization 3: Caching & Safety
- **Redis Strategy:** What was your cache key naming convention?
- **Fail-safe:** How did you implement the `statement_timeout` to ensure the DB 
  kills long-running queries automatically in the future?

## 5. Performance Gains
| Metric | Before Fix | After Fix | After Cache |
| :--- | :--- | :--- | :--- |
| Query Time | 14.2 mins | ~0.05s | ~0.002s |
| CPU Load | 99% | 5% | 1% |