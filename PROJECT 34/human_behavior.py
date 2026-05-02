import asyncio
import random

async def human_load_page(page, url):
    # 1. Random delay before navigation
    await asyncio.sleep(random.uniform(3, 7))
    
    await page.goto(url, wait_until="networkidle")
    
    # 2. Simulate reading behavior (scrolling)
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
    await asyncio.sleep(random.uniform(1, 3))
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")