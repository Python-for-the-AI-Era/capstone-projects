from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync

def get_stealth_browser(pw):
    browser = pw.chromium.launch(headless=False) # Headful is safer for high-security portals
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36...",
        viewport={'width': 1920, 'height': 1080},
        locale="en-GB"
    )
    page = context.new_page()
    stealth_sync(page) # Injects scripts to hide playwright's presence
    return browser, page