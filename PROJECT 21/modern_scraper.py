import asyncio
from playwright.async_api import async_playwright

async def scrape_jumia_api():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # TASK: Intercept the background API call that contains the price data
        captured_data = []

        async def handle_response(response):
            if "api/v1/catalog" in response.url:
                data = await response.json()
                captured_data.append(data)

        page.on("response", handle_response)
        await page.goto(URL, wait_until="networkidle")
        
        await browser.close()
        return captured_data