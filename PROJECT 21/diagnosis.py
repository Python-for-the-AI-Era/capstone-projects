import requests
from playwright.sync_api import sync_playwright

URL = "https://www.jumia.com.ng/smartphones/"

def diagnose_issue():
    # 1. The Legacy Way (Fails)
    resp = requests.get(URL)
    print(f"Legacy Count: {resp.text.count('NGN')}") # Likely 0 or very low

    # 2. The Modern Way (Succeeds)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(URL)
        # Wait for the JS to actually put the price on the screen
        page.wait_for_selector(".prc") 
        content = page.content()
        print(f"Playwright Count: {content.count('NGN')}") 
        browser.close()