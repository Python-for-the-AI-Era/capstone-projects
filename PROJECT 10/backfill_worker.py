async def backfill_tickets(db):
    """
    TASK: Process 2M tickets in batches of 1000.
    Find tickets where 'event_id' is missing.
    For each: create/find event, update ticket, remove 'event_details'.
    """
    cursor = db.tickets.find({"event_id": {"$exists": False}}).limit(1000)
    
    # Student must implement the loop, error handling, 
    # and progress logging (e.g., "Processed 500,000/2,000,000").
    pass