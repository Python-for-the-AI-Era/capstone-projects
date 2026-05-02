async def run_migration_analysis(db):
    """
    TASK: Use a MongoDB Aggregation Pipeline to:
    1. Count total ticket documents.
    2. Count UNIQUE event titles.
    3. Calculate the average size of the 'event_details' object.
    """
    pipeline = [
        {"$group": {"_id": "$event_details.title", "count": {"$sum": 1}}},
        {"$group": {"_id": None, "unique_events": {"$sum": 1}}}
    ]
    # Student must implement logic to show that 2M tickets only represent ~500 events.
    pass