import pytest
from modern_scraper import scrape_jumia_api

@pytest.mark.asyncio
async def test_price_not_null():
    results = await scrape_jumia_api()
    assert len(results) > 0
    assert all(item['price'] is not None for item in results)