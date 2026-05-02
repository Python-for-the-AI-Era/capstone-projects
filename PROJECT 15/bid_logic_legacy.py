import redis.asyncio as redis

class AuctionManager:
    def __init__(self, r: redis.Redis):
        self.r = r

    async def place_bid_faulty(self, auction_id: str, bid_amount: float):
        """
        CRITICAL RACE CONDITION:
        1. Thread A reads current_price (e.g., 100)
        2. Thread B reads current_price (e.g., 100)
        3. Thread A checks 110 > 100 (True)
        4. Thread B checks 105 > 100 (True)
        5. Thread B updates price to 105
        6. Thread A updates price to 110 (A lower bid 'wins' the spot temporarily!)
        """
        current_price = await self.r.get(f"auction:{auction_id}:price")
        if not current_price or bid_amount > float(current_price):
            await self.r.set(f"auction:{auction_id}:price", bid_amount)
            return True
        return False