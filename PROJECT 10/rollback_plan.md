# Migration Plan: Eventful Tickets (Denormalized -> Referenced)

## 1. Phase 1: Dual Writes
We are now writing to both collections. New code supports `event_id`. 
Old code still reads from `event_details` (which we are keeping temporarily).

## 2. Phase 2: The Backfill
Using the `backfill_worker.py` to update 2 million documents. 
**Performance Note:** We are using an index on `{"event_id": 1}` to quickly 
find un-migrated documents.

## 3. Phase 3: Validation
- **Sample Size:** 10,000 documents.
- **Check:** Does `ticket.event_id` lead to an Event document with the correct title?

## 4. Rollback Strategy
If the app crashes during Phase 1:
1. Revert API code to v1 (legacy_schema.py).
2. The `event_details` field is still present in old records, so no data is lost.
3. Drop the new `events` collection and the `event_id` field from tickets.

## 5. Storage Gains
- **Storage Before:** ~4.2 GB
- **Storage After:** ~1.1 GB (74% reduction)