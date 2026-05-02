import hashlib
from sqlalchemy import create_engine, text

class NewsArchiverPipeline:
    def open_spider(self, spider):
        self.engine = create_engine("postgresql://user:pass@localhost/research_db")

    def process_item(self, item, spider):
        # Task 2: Fingerprinting for Deduplication
        content_hash = hashlib.md5(item['url'].encode()).hexdigest()
        
        query = text("""
            INSERT INTO news_archive (url_hash, url, title, content, crawled_at)
            VALUES (:h, :u, :t, :c, NOW())
            ON CONFLICT (url_hash) DO NOTHING
        """)
        
        with self.engine.begin() as conn:
            conn.execute(query, {"h": content_hash, "u": item['url'], "t": item['title'], "c": item['content']})
        return item