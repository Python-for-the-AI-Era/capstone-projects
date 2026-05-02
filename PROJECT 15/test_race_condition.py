import asyncio
from main import place_bid # The student's fixed version

async def test_concurrent_bids():
    auction_id = "test_item_001"
    bid_amount = 500.0
    
    # We launch 100 simultaneous tasks
    tasks = [place_bid(auction_id, bid_amount, f"user_{i}") for i in range(100)]
    results = await asyncio.gather(*tasks)
    
    successes = [r for r in results if r == "ACCEPTED"]
    print(f"Total Bids: 100")
    print(f"Successes: {len(successes)}") # SHOULD BE EXACTLY 1
    
    assert len(successes) == 1