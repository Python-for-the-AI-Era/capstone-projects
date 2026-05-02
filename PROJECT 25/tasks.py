from celery import Celery
from scrapers import scrape_jumia, scrape_konga
from notifications import send_sms

app = Celery('price_bot', broker='redis://localhost:6379/0')

@app.task
def check_all_prices():
    # 1. Fetch all monitors from DB
    # 2. For each monitor, run the appropriate scraper
    # 3. Save new price to PriceHistory
    # 4. IF price <= target_price:
    #    send_sms(phone, f"Price drop! {name} is now {price}")
    pass