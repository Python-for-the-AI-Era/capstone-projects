"""
Prometheus metrics exporter for Scrapy crawler.

Exports Scrapy statistics to Prometheus for monitoring and alerting.
"""

import time
import logging
from typing import Dict, Any, Optional
from prometheus_client import Counter, Gauge, Histogram, start_http_server, REGISTRY
from scrapy import signals
from scrapy.exceptions import NotConfigured

logger = logging.getLogger(__name__)


class PrometheusStatsExtension:
    """
    Scrapy extension that exports statistics to Prometheus.
    
    Provides comprehensive metrics for monitoring crawler performance,
    error rates, and resource usage with automatic alerting.
    """
    
    def __init__(self, port: int = 9090, export_interval: int = 60,
                 alert_threshold_items_per_minute: int = 100):
        """
        Initialize Prometheus stats extension.
        
        Args:
            port: Port for Prometheus HTTP server
            export_interval: Interval in seconds between exports
            alert_threshold_items_per_minute: Alert threshold for items per minute
        """
        self.port = port
        self.export_interval = export_interval
        self.alert_threshold = alert_threshold_items_per_minute
        
        # Initialize Prometheus metrics
        self._init_metrics()
        
        # Statistics tracking
        self.crawler_stats = {}
        self.last_export_time = time.time()
        self.last_items_scraped = 0
        
        # Alert state
        self.alert_states = {
            'low_crawl_rate': False,
            'high_error_rate': False,
            'memory_usage': False
        }
        
        logger.info(f"PrometheusStatsExtension initialized on port {port}")
    
    def _init_metrics(self):
        """Initialize Prometheus metrics."""
        # Counters
        self.items_scraped_counter = Counter(
            'scrapy_items_scraped_total',
            'Total number of items scraped',
            ['spider', 'domain']
        )
        
        self.pages_crawled_counter = Counter(
            'scrapy_pages_crawled_total',
            'Total number of pages crawled',
            ['spider', 'domain']
        )
        
        self.requests_counter = Counter(
            'scrapy_requests_total',
            'Total number of requests made',
            ['spider', 'domain', 'status']
        )
        
        self.errors_counter = Counter(
            'scrapy_errors_total',
            'Total number of errors',
            ['spider', 'domain', 'error_type']
        )
        
        self.dropped_items_counter = Counter(
            'scrapy_dropped_items_total',
            'Total number of dropped items',
            ['spider', 'pipeline']
        )
        
        # Gauges
        self.crawl_rate_gauge = Gauge(
            'scrapy_crawl_rate',
            'Items scraped per minute',
            ['spider']
        )
        
        self.error_rate_gauge = Gauge(
            'scrapy_error_rate',
            'Error rate percentage',
            ['spider']
        )
        
        self.active_requests_gauge = Gauge(
            'scrapy_active_requests',
            'Number of active requests',
            ['spider']
        )
        
        self.queue_size_gauge = Gauge(
            'scrapy_queue_size',
            'Number of items in request queue',
            ['spider']
        )
        
        self.memory_usage_gauge = Gauge(
            'scrapy_memory_usage_bytes',
            'Memory usage in bytes',
            ['spider']
        )
        
        self.cpu_usage_gauge = Gauge(
            'scrapy_cpu_usage_percent',
            'CPU usage percentage',
            ['spider']
        )
        
        # Histograms
        self.response_time_histogram = Histogram(
            'scrapy_response_time_seconds',
            'Response time in seconds',
            ['spider', 'domain'],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
        )
        
        self.item_processing_time_histogram = Histogram(
            'scrapy_item_processing_time_seconds',
            'Item processing time in seconds',
            ['spider', 'pipeline'],
            buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0]
        )
        
        logger.info("Prometheus metrics initialized")
    
    @classmethod
    def from_crawler(cls, crawler):
        """Create instance from crawler."""
        port = crawler.settings.getint('PROMETHEUS_PORT', 9090)
        export_interval = crawler.settings.getint('STATS_EXPORT_INTERVAL', 60)
        alert_threshold = crawler.settings.getint('ALERT_THRESHOLD_ITEMS_PER_MINUTE', 100)
        
        if not crawler.settings.getbool('PROMETHEUS_ENABLED', True):
            raise NotConfigured("Prometheus extension is disabled")
        
        extension = cls(port, export_interval, alert_threshold)
        
        # Connect to signals
        crawler.signals.connect(extension.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(extension.spider_closed, signal=signals.spider_closed)
        crawler.signals.connect(extension.item_scraped, signal=signals.item_scraped)
        crawler.signals.connect(extension.request_scheduled, signal=signals.request_scheduled)
        crawler.signals.connect(extension.response_received, signal=signals.response_received)
        crawler.signals.connect(extension.item_dropped, signal=signals.item_dropped)
        crawler.signals.connect(extension.spider_error, signal=signals.spider_error)
        
        return extension
    
    def spider_opened(self, spider):
        """Called when spider is opened."""
        spider_name = spider.name
        
        # Initialize spider-specific stats
        self.crawler_stats[spider_name] = {
            'start_time': time.time(),
            'items_scraped': 0,
            'pages_crawled': 0,
            'requests': 0,
            'errors': 0,
            'last_items_scraped': 0,
            'last_export_time': time.time()
        }
        
        # Start Prometheus HTTP server
        try:
            start_http_server(self.port)
            logger.info(f"Prometheus HTTP server started on port {self.port}")
        except Exception as e:
            logger.error(f"Failed to start Prometheus HTTP server: {e}")
        
        logger.info(f"Prometheus monitoring started for spider: {spider_name}")
    
    def spider_closed(self, spider):
        """Called when spider is closed."""
        spider_name = spider.name
        
        # Export final statistics
        self._export_stats(spider)
        
        # Log final metrics
        if spider_name in self.crawler_stats:
            stats = self.crawler_stats[spider_name]
            duration = time.time() - stats['start_time']
            
            logger.info(f"Spider {spider_name} closed:")
            logger.info(f"  Duration: {duration:.2f} seconds")
            logger.info(f"  Items scraped: {stats['items_scraped']}")
            logger.info(f"  Pages crawled: {stats['pages_crawled']}")
            logger.info(f"  Errors: {stats['errors']}")
        
        logger.info(f"Prometheus monitoring stopped for spider: {spider_name}")
    
    def item_scraped(self, item, response, spider):
        """Called when item is scraped."""
        spider_name = spider.name
        
        # Update counters
        self.items_scraped_counter.labels(
            spider=spider_name,
            domain=response.url.split('/')[2] if len(response.url.split('/')) > 2 else 'unknown'
        ).inc()
        
        # Update stats
        if spider_name in self.crawler_stats:
            self.crawler_stats[spider_name]['items_scraped'] += 1
        
        # Check if we should export stats
        self._maybe_export_stats(spider)
    
    def request_scheduled(self, request, spider):
        """Called when request is scheduled."""
        spider_name = spider.name
        
        # Update counters
        self.requests_counter.labels(
            spider=spider_name,
            domain=request.url.split('/')[2] if len(request.url.split('/')) > 2 else 'unknown',
            status='scheduled'
        ).inc()
        
        # Update stats
        if spider_name in self.crawler_stats:
            self.crawler_stats[spider_name]['requests'] += 1
    
    def response_received(self, response, request, spider):
        """Called when response is received."""
        spider_name = spider.name
        
        # Update counters
        self.requests_counter.labels(
            spider=spider_name,
            domain=response.url.split('/')[2] if len(response.url.split('/')) > 2 else 'unknown',
            status=str(response.status)
        ).inc()
        
        # Record response time
        if 'download_latency' in request.meta:
            self.response_time_histogram.labels(
                spider=spider_name,
                domain=response.url.split('/')[2] if len(response.url.split('/')) > 2 else 'unknown'
            ).observe(request.meta['download_latency'])
        
        # Update pages crawled counter
        if response.status < 400:
            self.pages_crawled_counter.labels(
                spider=spider_name,
                domain=response.url.split('/')[2] if len(response.url.split('/')) > 2 else 'unknown'
            ).inc()
            
            if spider_name in self.crawler_stats:
                self.crawler_stats[spider_name]['pages_crawled'] += 1
    
    def item_dropped(self, item, response, exception, spider):
        """Called when item is dropped."""
        spider_name = spider.name
        
        # Update counters
        self.dropped_items_counter.labels(
            spider=spider_name,
            pipeline=exception.__class__.__name__
        ).inc()
        
        logger.warning(f"Item dropped: {exception}")
    
    def spider_error(self, failure, response, spider):
        """Called when spider encounters an error."""
        spider_name = spider.name
        
        # Update counters
        self.errors_counter.labels(
            spider=spider_name,
            domain=response.url.split('/')[2] if len(response.url.split('/')) > 2 else 'unknown',
            error_type=failure.value.__class__.__name__
        ).inc()
        
        # Update stats
        if spider_name in self.crawler_stats:
            self.crawler_stats[spider_name]['errors'] += 1
        
        logger.error(f"Spider error: {failure.value}")
    
    def _maybe_export_stats(self, spider):
        """Export stats if interval has passed."""
        spider_name = spider.name
        current_time = time.time()
        
        if spider_name in self.crawler_stats:
            last_export = self.crawler_stats[spider_name]['last_export_time']
            
            if current_time - last_export >= self.export_interval:
                self._export_stats(spider)
    
    def _export_stats(self, spider):
        """Export statistics to Prometheus."""
        spider_name = spider.name
        
        if spider_name not in self.crawler_stats:
            return
        
        stats = self.crawler_stats[spider_name]
        current_time = time.time()
        
        # Calculate crawl rate
        time_diff = current_time - stats['last_export_time']
        items_diff = stats['items_scraped'] - stats['last_items_scraped']
        crawl_rate = (items_diff / time_diff) * 60 if time_diff > 0 else 0
        
        # Calculate error rate
        total_requests = stats['requests']
        error_rate = (stats['errors'] / total_requests * 100) if total_requests > 0 else 0
        
        # Update gauges
        self.crawl_rate_gauge.labels(spider=spider_name).set(crawl_rate)
        self.error_rate_gauge.labels(spider=spider_name).set(error_rate)
        
        # Update system metrics
        self._update_system_metrics(spider_name)
        
        # Check alerts
        self._check_alerts(spider_name, crawl_rate, error_rate)
        
        # Update last export time
        stats['last_export_time'] = current_time
        stats['last_items_scraped'] = stats['items_scraped']
        
        logger.debug(f"Stats exported for {spider_name}: crawl_rate={crawl_rate:.2f}/min, error_rate={error_rate:.2f}%")
    
    def _update_system_metrics(self, spider_name):
        """Update system resource metrics."""
        try:
            import psutil
            
            # Memory usage
            memory_info = psutil.virtual_memory()
            self.memory_usage_gauge.labels(spider=spider_name).set(memory_info.used)
            
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            self.cpu_usage_gauge.labels(spider=spider_name).set(cpu_percent)
            
        except ImportError:
            # psutil not available
            pass
        except Exception as e:
            logger.error(f"Error updating system metrics: {e}")
    
    def _check_alerts(self, spider_name: str, crawl_rate: float, error_rate: float):
        """Check alert conditions and trigger alerts if needed."""
        # Check crawl rate alert
        if crawl_rate < self.alert_threshold and not self.alert_states['low_crawl_rate']:
            self.alert_states['low_crawl_rate'] = True
            self._trigger_alert('low_crawl_rate', spider_name, crawl_rate)
        elif crawl_rate >= self.alert_threshold and self.alert_states['low_crawl_rate']:
            self.alert_states['low_crawl_rate'] = False
        
        # Check error rate alert
        if error_rate > 10 and not self.alert_states['high_error_rate']:  # 10% error rate threshold
            self.alert_states['high_error_rate'] = True
            self._trigger_alert('high_error_rate', spider_name, error_rate)
        elif error_rate <= 10 and self.alert_states['high_error_rate']:
            self.alert_states['high_error_rate'] = False
        
        # Check memory usage alert
        try:
            import psutil
            memory_percent = psutil.virtual_memory().percent
            
            if memory_percent > 90 and not self.alert_states['memory_usage']:
                self.alert_states['memory_usage'] = True
                self._trigger_alert('memory_usage', spider_name, memory_percent)
            elif memory_percent <= 90 and self.alert_states['memory_usage']:
                self.alert_states['memory_usage'] = False
                
        except ImportError:
            pass
    
    def _trigger_alert(self, alert_type: str, spider_name: str, value: float):
        """Trigger alert for monitoring condition."""
        logger.warning(f"ALERT: {alert_type} for spider {spider_name} (value: {value})")
        
        # Here you could integrate with external alerting systems
        # like Slack, email, PagerDuty, etc.
        
        alert_message = {
            'alert_type': alert_type,
            'spider_name': spider_name,
            'value': value,
            'timestamp': time.time(),
            'threshold': self.alert_threshold if alert_type == 'low_crawl_rate' else None
        }
        
        # Log alert for monitoring
        logger.warning(f"Alert details: {alert_message}")
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get summary of all Prometheus metrics.
        
        Returns:
            Dictionary with metrics summary
        """
        try:
            # Collect all metrics
            metrics_data = {}
            
            for metric_family in REGISTRY.collect():
                metrics_data[metric_family.name] = []
                
                for sample in metric_family.samples:
                    metrics_data[metric_family.name].append({
                        'labels': sample.labels,
                        'value': sample.value,
                        'timestamp': sample.timestamp
                    })
            
            return metrics_data
            
        except Exception as e:
            logger.error(f"Error getting metrics summary: {e}")
            return {'error': str(e)}
    
    def reset_metrics(self):
        """Reset all Prometheus metrics."""
        try:
            # Clear all metrics
            collectors = list(REGISTRY._collector_to_names.keys())
            for collector in collectors:
                REGISTRY.unregister(collector)
            
            # Re-initialize metrics
            self._init_metrics()
            
            logger.info("Prometheus metrics reset")
            
        except Exception as e:
            logger.error(f"Error resetting metrics: {e}")
