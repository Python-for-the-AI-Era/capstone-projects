from playwright.async_api import async_playwright

async def get_jumia_price(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(url)
        # Jumia specific selector
        price_text = await page.inner_text(".prc")
        price = float(price_text.replace("₦", "").replace(",", "").strip())
        await browser.close()
        return price