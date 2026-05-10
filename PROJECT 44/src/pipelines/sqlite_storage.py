"""
SQLite storage pipeline for fault-tolerant data storage.

Provides atomic writes and fault tolerance for news article data
with automatic backup and recovery capabilities.
"""

import sqlite3
import json
import logging
import time
import os
from datetime import datetime
from typing import Dict, Any, Optional, List
from contextlib import contextmanager

from scrapy.exceptions import DropItem

logger = logging.getLogger(__name__)


class SQLiteStoragePipeline:
    """
    SQLite storage pipeline with fault tolerance.
    
    Provides atomic writes, automatic backups, and recovery
    for reliable data storage during long-running crawls.
    """
    
    def __init__(self, db_path: str = 'data/crawler_data.db', 
                 backup_interval: int = 1000, batch_size: int = 100):
        """
        Initialize SQLite storage pipeline.
        
        Args:
            db_path: Path to SQLite database file
            backup_interval: Number of items between backups
            batch_size: Number of items to batch write
        """
        self.db_path = db_path
        self.backup_interval = backup_interval
        self.batch_size = batch_size
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Initialize database
        self._init_database()
        
        # Batch storage
        self.batch_items = []
        self.items_since_backup = 0
        
        # Statistics
        self.stats = {
            'items_stored': 0,
            'items_failed': 0,
            'batches_written': 0,
            'backups_created': 0,
            'errors': []
        }
        
        logger.info(f"SQLiteStoragePipeline initialized: {db_path}")
    
    def _init_database(self):
        """Initialize database tables."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Create articles table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    author TEXT,
                    publication_date TEXT,
                    category TEXT,
                    domain TEXT NOT NULL,
                    word_count INTEGER,
                    image_urls TEXT,
                    links TEXT,
                    crawl_time REAL NOT NULL,
                    referer TEXT,
                    source TEXT,
                    processed BOOLEAN DEFAULT 1,
                    error TEXT,
                    sentiment_score REAL,
                    bias_indicators TEXT,
                    language TEXT,
                    keywords TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create indexes for performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_url ON articles(url)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_domain ON articles(domain)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_crawl_time ON articles(crawl_time)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_created_at ON articles(created_at)')
            
            # Create stats table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS crawl_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    spider_name TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    items_scraped INTEGER DEFAULT 0,
                    pages_crawled INTEGER DEFAULT 0,
                    errors INTEGER DEFAULT 0,
                    domains_crawled TEXT,
                    crawl_rate REAL DEFAULT 0,
                    error_rate REAL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create errors table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS crawl_errors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    spider_name TEXT NOT NULL,
                    url TEXT,
                    error_type TEXT NOT NULL,
                    error_message TEXT,
                    timestamp REAL NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            logger.info("Database initialized successfully")
    
    @contextmanager
    def _get_connection(self):
        """Get database connection with error handling."""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging for better concurrency
            conn.execute("PRAGMA synchronous=NORMAL")  # Balance between safety and performance
            conn.execute("PRAGMA cache_size=10000")  # 10MB cache
            conn.execute("PRAGMA temp_store=MEMORY")  # Store temp tables in memory
            yield conn
        except sqlite3.Error as e:
            logger.error(f"Database connection error: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()
    
    def process_item(self, item, spider):
        """
        Process and store news article item.
        
        Args:
            item: NewsArticleItem to store
            spider: Spider instance
            
        Returns:
            Stored item
            
        Raises:
            DropItem: If item fails to store
        """
        try:
            # Add to batch
            self.batch_items.append(item)
            
            # Write batch if it's full
            if len(self.batch_items) >= self.batch_size:
                self._write_batch(spider)
            
            return item
            
        except Exception as e:
            self.stats['items_failed'] += 1
            error_msg = f"Failed to store item {item.get('url', 'unknown')}: {e}"
            logger.error(error_msg)
            
            # Log error to database
            self._log_error(spider, item.get('url'), type(e).__name__, str(e))
            
            raise DropItem(error_msg)
    
    def _write_batch(self, spider):
        """Write batch of items to database."""
        if not self.batch_items:
            return
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Prepare batch insert data
                insert_data = []
                for item in self.batch_items:
                    insert_data.append((
                        item.get('url'),
                        item.get('title'),
                        item.get('content'),
                        item.get('author'),
                        item.get('publication_date'),
                        item.get('category'),
                        item.get('domain'),
                        item.get('word_count'),
                        json.dumps(item.get('image_urls', [])),
                        json.dumps(item.get('links', [])),
                        item.get('crawl_time'),
                        item.get('referer'),
                        item.get('source'),
                        item.get('processed', True),
                        item.get('error'),
                        item.get('sentiment_score'),
                        json.dumps(item.get('bias_indicators', [])),
                        item.get('language'),
                        json.dumps(item.get('keywords', []))
                    ))
                
                # Batch insert
                cursor.executemany('''
                    INSERT OR REPLACE INTO articles (
                        url, title, content, author, publication_date, category,
                        domain, word_count, image_urls, links, crawl_time,
                        referer, source, processed, error, sentiment_score,
                        bias_indicators, language, keywords
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', insert_data)
                
                conn.commit()
                
                # Update statistics
                self.stats['items_stored'] += len(self.batch_items)
                self.stats['batches_written'] += 1
                self.items_since_backup += len(self.batch_items)
                
                logger.debug(f"Batch written: {len(self.batch_items)} items")
                
                # Check if backup is needed
                if self.items_since_backup >= self.backup_interval:
                    self._create_backup(spider)
                
                # Clear batch
                self.batch_items = []
                
        except Exception as e:
            logger.error(f"Batch write failed: {e}")
            self.stats['items_failed'] += len(self.batch_items)
            raise
    
    def _create_backup(self, spider):
        """Create database backup."""
        try:
            backup_path = f"{self.db_path}.backup_{int(time.time())}"
            
            with self._get_connection() as conn:
                conn.execute(f"VACUUM INTO '{backup_path}'")
            
            # Remove old backups (keep last 5)
            self._cleanup_old_backups()
            
            self.stats['backups_created'] += 1
            self.items_since_backup = 0
            
            logger.info(f"Backup created: {backup_path}")
            
        except Exception as e:
            logger.error(f"Backup failed: {e}")
    
    def _cleanup_old_backups(self):
        """Remove old backup files."""
        try:
            import glob
            backup_files = glob.glob(f"{self.db_path}.backup_*")
            
            # Sort by modification time (newest first)
            backup_files.sort(key=os.path.getmtime, reverse=True)
            
            # Keep only the 5 most recent backups
            for backup_file in backup_files[5:]:
                os.remove(backup_file)
                logger.debug(f"Removed old backup: {backup_file}")
                
        except Exception as e:
            logger.error(f"Backup cleanup failed: {e}")
    
    def _log_error(self, spider, url: str, error_type: str, error_message: str):
        """Log error to database."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO crawl_errors (
                        spider_name, url, error_type, error_message, timestamp
                    ) VALUES (?, ?, ?, ?, ?)
                ''', (spider.name, url, error_type, error_message, time.time()))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to log error: {e}")
    
    def close_spider(self, spider):
        """Called when spider is closed."""
        # Write any remaining items in batch
        if self.batch_items:
            try:
                self._write_batch(spider)
            except Exception as e:
                logger.error(f"Failed to write final batch: {e}")
        
        # Create final backup
        try:
            self._create_backup(spider)
        except Exception as e:
            logger.error(f"Failed to create final backup: {e}")
        
        # Log statistics
        logger.info(f"SQLiteStoragePipeline closed for {spider.name}")
        logger.info(f"Items stored: {self.stats['items_stored']}")
        logger.info(f"Items failed: {self.stats['items_failed']}")
        logger.info(f"Batches written: {self.stats['batches_written']}")
        logger.info(f"Backups created: {self.stats['backups_created']}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get storage statistics.
        
        Returns:
            Dictionary with storage statistics
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Get database stats
                cursor.execute("SELECT COUNT(*) FROM articles")
                total_articles = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM crawl_errors")
                total_errors = cursor.fetchone()[0]
                
                cursor.execute("SELECT domain, COUNT(*) FROM articles GROUP BY domain ORDER BY COUNT(*) DESC")
                domain_stats = cursor.fetchall()
                
                cursor.execute("SELECT created_at FROM articles ORDER BY created_at DESC LIMIT 1")
                last_item = cursor.fetchone()
                
                return {
                    'total_articles': total_articles,
                    'total_errors': total_errors,
                    'domain_stats': dict(domain_stats),
                    'last_item_time': last_item[0] if last_item else None,
                    'pipeline_stats': self.stats.copy()
                }
                
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {'error': str(e)}
    
    def recover_from_backup(self, backup_path: str = None):
        """
        Recover database from backup.
        
        Args:
            backup_path: Path to backup file (if None, use latest)
        """
        try:
            if not backup_path:
                # Find latest backup
                import glob
                backup_files = glob.glob(f"{self.db_path}.backup_*")
                if not backup_files:
                    raise FileNotFoundError("No backup files found")
                
                backup_files.sort(key=os.path.getmtime, reverse=True)
                backup_path = backup_files[0]
            
            # Close any existing connections
            import sqlite3
            sqlite3.connect(self.db_path).close()
            
            # Replace database with backup
            os.replace(backup_path, self.db_path)
            
            logger.info(f"Database recovered from: {backup_path}")
            
        except Exception as e:
            logger.error(f"Recovery failed: {e}")
            raise
    
    def export_to_json(self, output_path: str, limit: int = None):
        """
        Export articles to JSON file.
        
        Args:
            output_path: Path to output JSON file
            limit: Maximum number of articles to export
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                query = "SELECT * FROM articles ORDER BY created_at DESC"
                if limit:
                    query += f" LIMIT {limit}"
                
                cursor.execute(query)
                columns = [desc[0] for desc in cursor.description]
                
                articles = []
                for row in cursor.fetchall():
                    article = dict(zip(columns, row))
                    
                    # Parse JSON fields
                    if article['image_urls']:
                        article['image_urls'] = json.loads(article['image_urls'])
                    if article['links']:
                        article['links'] = json.loads(article['links'])
                    if article['bias_indicators']:
                        article['bias_indicators'] = json.loads(article['bias_indicators'])
                    if article['keywords']:
                        article['keywords'] = json.loads(article['keywords'])
                    
                    articles.append(article)
                
                # Write to JSON file
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(articles, f, indent=2, ensure_ascii=False, default=str)
                
                logger.info(f"Exported {len(articles)} articles to {output_path}")
                
        except Exception as e:
            logger.error(f"Export failed: {e}")
            raise
