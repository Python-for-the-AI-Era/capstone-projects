async def check_for_captcha(page):
    # Common Cloudflare or Google selectors
    captcha_selectors = [".cf-turnstile", "#g-recaptcha", "iframe[title*='challenge']"]
    
    for selector in captcha_selectors:
        if await page.query_selector(selector):
            print("🚨 CAPTCHA DETECTED. Pausing for 10 minutes or manual intervention.")
            # Trigger a desktop notification or log
            await asyncio.sleep(600) 
            return True
    return False