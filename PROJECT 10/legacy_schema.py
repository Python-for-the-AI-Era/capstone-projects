from motor.motor_asyncio import AsyncIOMotorClient
import datetime

# FAULTY SCHEMA: 2 million of these exist.
# If an event's 'venue' changes, we have to update 50,000 tickets.
sample_ticket = {
    "ticket_id": "TICK-9901",
    "user_id": "USER-123",
    "event_details": {  # This should be a Reference, not embedded!
        "title": "Burna Boy Live in Lagos",
        "date": datetime.datetime(2026, 12, 20),
        "venue": "Eko Energy City",
        "organizer": "Spaceship Ent"
    },
    "price": 25000,
    "purchased_at": datetime.datetime.now()
}