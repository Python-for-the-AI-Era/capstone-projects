import hashlib
import redis
from playwright.sync_api import sync_playwright

r = redis.Redis(host='localhost', port=6379, db=0)

def get_page_content(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")
        content = page.content()
        
        # Task 3: Deduplication via Hashing
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        is_new = r.set(f"hash:{url}", content_hash, nx=False, get=True) != content_hash.encode()
        
        browser.close()
        return content if is_new else None