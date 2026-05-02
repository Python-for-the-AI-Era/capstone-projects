async def save_ticket_v2(db, ticket_data):
    """
    STAGED MIGRATION:
    1. Extract event data from the ticket_data.
    2. UPSERT into the 'events' collection (get an event_id).
    3. Insert the ticket into 'tickets' with 'event_id' instead of 'event_details'.
    """
    event_info = ticket_data.pop("event_details")
    
    # 1. UPSERT event to get a stable ID
    event_result = await db.events.find_one_and_update(
        {"title": event_info["title"], "date": event_info["date"]},
        {"$set": event_info},
        upsert=True,
        return_document=True
    )
    
    # 2. SAVE ticket with reference
    ticket_data["event_id"] = event_result["_id"]
    await db.tickets.insert_one(ticket_data)