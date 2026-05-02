class PrometheusStatsCollector:
    def __init__(self, spider):
        self.spider = spider

    def export_stats(self):
        stats = self.spider.crawler.stats.get_stats()
        scraped_count = stats.get('item_scraped_count', 0)
        # Logic to push to Prometheus Pushgateway
        if scraped_count < 100:
            self.trigger_alert("Low scrape rate detected!")