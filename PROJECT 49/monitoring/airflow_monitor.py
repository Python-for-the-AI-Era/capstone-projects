#!/usr/bin/env python3
"""
Airflow monitoring and alerting system for Finco Bank reconciliation.

This module provides comprehensive monitoring for Airflow DAGs including:
1. Real-time task monitoring
2. Performance metrics collection
3. Alert notifications for SLA violations
4. Historical performance analysis
"""

import argparse
import logging
import time
import json
import psycopg2
import requests
from datetime import datetime, timedelta
from pathlib import Path
import schedule
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from prometheus_client import CollectorRegistry, Gauge, Counter, Histogram, push_to_gateway
import structlog

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

@dataclass
class TaskMetrics:
    """Metrics for a specific task."""
    task_id: str
    dag_id: str
    execution_date: datetime
    state: str
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    duration: Optional[float]
    max_tries: int
    try_number: int
    error_message: Optional[str]

@dataclass
class DAGMetrics:
    """Metrics for a specific DAG."""
    dag_id: str
    execution_date: datetime
    state: str
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    duration: Optional[float]
    task_count: int
    success_count: int
    failed_count: int
    running_count: int
    sla_missed: bool

class AirflowMonitor:
    """Comprehensive Airflow monitoring system."""
    
    def __init__(self, db_host: str, db_name: str, db_user: str, db_password: str):
        """
        Initialize the monitor.
        
        Args:
            db_host: Database host
            db_name: Database name
            db_user: Database user
            db_password: Database password
        """
        self.db_host = db_host
        self.db_name = db_name
        self.db_user = db_user
        self.db_password = db_password
        
        # Prometheus metrics
        self.registry = CollectorRegistry()
        self.setup_prometheus_metrics()
        
        # Alert configuration
        self.alert_thresholds = {
            'task_duration_minutes': 30,
            'dag_duration_hours': 2,
            'failure_rate_percent': 10,
            'sla_miss_count': 1
        }
        
        logger.info("Airflow monitor initialized")
    
    def setup_prometheus_metrics(self):
        """Setup Prometheus metrics."""
        self.task_duration_gauge = Gauge(
            'airflow_task_duration_seconds',
            'Duration of Airflow tasks',
            ['dag_id', 'task_id', 'state'],
            registry=self.registry
        )
        
        self.dag_duration_gauge = Gauge(
            'airflow_dag_duration_seconds',
            'Duration of Airflow DAGs',
            ['dag_id', 'state'],
            registry=self.registry
        )
        
        self.task_counter = Counter(
            'airflow_task_total',
            'Total number of Airflow tasks',
            ['dag_id', 'task_id', 'state'],
            registry=self.registry
        )
        
        self.sla_miss_counter = Counter(
            'airflow_sla_miss_total',
            'Total number of SLA misses',
            ['dag_id'],
            registry=self.registry
        )
        
        self.active_dags_gauge = Gauge(
            'airflow_active_dags',
            'Number of active DAGs',
            registry=self.registry
        )
        
        self.failed_tasks_gauge = Gauge(
            'airflow_failed_tasks',
            'Number of failed tasks',
            ['dag_id'],
            registry=self.registry
        )
    
    def get_db_connection(self):
        """Get database connection."""
        return psycopg2.connect(
            host=self.db_host,
            database=self.db_name,
            user=self.db_user,
            password=self.db_password,
            connect_timeout=30
        )
    
    def get_task_metrics(self, dag_id: str, execution_date: datetime) -> List[TaskMetrics]:
        """Get metrics for all tasks in a DAG run."""
        metrics = []
        
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                SELECT 
                    task_id,
                    dag_id,
                    execution_date,
                    state,
                    start_date,
                    end_date,
                    EXTRACT(EPOCH FROM (end_date - start_date)) as duration,
                    max_tries,
                    try_number
                FROM task_instance 
                WHERE dag_id = %s
                AND execution_date = %s
                ORDER BY start_date DESC
                """, (dag_id, execution_date))
                
                for row in cursor.fetchall():
                    metrics.append(TaskMetrics(
                        task_id=row[0],
                        dag_id=row[1],
                        execution_date=row[2],
                        state=row[3],
                        start_date=row[4],
                        end_date=row[5],
                        duration=float(row[6]) if row[6] else None,
                        max_tries=row[7],
                        try_number=row[8],
                        error_message=None
                    ))
                
                cursor.close()
        
        except Exception as e:
            logger.error(f"Error getting task metrics for {dag_id}: {e}")
        
        return metrics
    
    def get_dag_metrics(self, dag_id: str, execution_date: datetime) -> Optional[DAGMetrics]:
        """Get metrics for a specific DAG run."""
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Get DAG run metrics
                cursor.execute("""
                SELECT 
                    dag_id,
                    execution_date,
                    state,
                    start_date,
                    end_date,
                    EXTRACT(EPOCH FROM (end_date - start_date)) as duration
                FROM dag_run 
                WHERE dag_id = %s
                AND execution_date = %s
                """, (dag_id, execution_date))
                
                dag_row = cursor.fetchone()
                if not dag_row:
                    return None
                
                # Get task counts
                cursor.execute("""
                SELECT 
                    state,
                    COUNT(*) as count
                FROM task_instance 
                WHERE dag_id = %s
                AND execution_date = %s
                GROUP BY state
                """, (dag_id, execution_date))
                
                task_counts = dict(cursor.fetchall())
                
                # Check for SLA misses
                cursor.execute("""
                SELECT COUNT(*) as sla_miss_count
                FROM sla_miss 
                WHERE dag_id = %s
                AND execution_date = %s
                """, (dag_id, execution_date))
                
                sla_miss_count = cursor.fetchone()[0]
                
                cursor.close()
                
                return DAGMetrics(
                    dag_id=dag_row[0],
                    execution_date=dag_row[1],
                    state=dag_row[2],
                    start_date=dag_row[3],
                    end_date=dag_row[4],
                    duration=float(dag_row[5]) if dag_row[5] else None,
                    task_count=sum(task_counts.values()),
                    success_count=task_counts.get('success', 0),
                    failed_count=task_counts.get('failed', 0),
                    running_count=task_counts.get('running', 0),
                    sla_missed=sla_miss_count > 0
                )
        
        except Exception as e:
            logger.error(f"Error getting DAG metrics for {dag_id}: {e}")
            return None
    
    def update_prometheus_metrics(self, dag_metrics: DAGMetrics, task_metrics: List[TaskMetrics]):
        """Update Prometheus metrics."""
        try:
            # Update DAG metrics
            if dag_metrics.duration:
                self.dag_duration_gauge.labels(
                    dag_id=dag_metrics.dag_id,
                    state=dag_metrics.state
                ).set(dag_metrics.duration)
            
            self.active_dags_gauge.set(1 if dag_metrics.state == 'running' else 0)
            self.failed_tasks_gauge.labels(dag_id=dag_metrics.dag_id).set(dag_metrics.failed_count)
            
            if dag_metrics.sla_missed:
                self.sla_miss_counter.labels(dag_id=dag_metrics.dag_id).inc()
            
            # Update task metrics
            for task in task_metrics:
                if task.duration:
                    self.task_duration_gauge.labels(
                        dag_id=task.dag_id,
                        task_id=task.task_id,
                        state=task.state
                    ).set(task.duration)
                
                self.task_counter.labels(
                    dag_id=task.dag_id,
                    task_id=task.task_id,
                    state=task.state
                ).inc()
        
        except Exception as e:
            logger.error(f"Error updating Prometheus metrics: {e}")
    
    def check_alert_conditions(self, dag_metrics: DAGMetrics, task_metrics: List[TaskMetrics]) -> List[Dict]:
        """Check for alert conditions."""
        alerts = []
        
        # Check for long-running tasks
        for task in task_metrics:
            if task.duration and task.duration > self.alert_thresholds['task_duration_minutes'] * 60:
                alerts.append({
                    'type': 'long_running_task',
                    'severity': 'warning',
                    'message': f"Task {task.task_id} in {task.dag_id} has been running for {task.duration/60:.1f} minutes",
                    'task_id': task.task_id,
                    'dag_id': task.dag_id,
                    'duration': task.duration
                })
        
        # Check for DAG duration
        if dag_metrics.duration and dag_metrics.duration > self.alert_thresholds['dag_duration_hours'] * 3600:
            alerts.append({
                'type': 'long_running_dag',
                'severity': 'warning',
                'message': f"DAG {dag_metrics.dag_id} has been running for {dag_metrics.duration/3600:.1f} hours",
                'dag_id': dag_metrics.dag_id,
                'duration': dag_metrics.duration
            })
        
        # Check for high failure rate
        if dag_metrics.task_count > 0:
            failure_rate = (dag_metrics.failed_count / dag_metrics.task_count) * 100
            if failure_rate > self.alert_thresholds['failure_rate_percent']:
                alerts.append({
                    'type': 'high_failure_rate',
                    'severity': 'critical',
                    'message': f"DAG {dag_metrics.dag_id} has {failure_rate:.1f}% failure rate",
                    'dag_id': dag_metrics.dag_id,
                    'failure_rate': failure_rate
                })
        
        # Check for SLA misses
        if dag_metrics.sla_missed:
            alerts.append({
                'type': 'sla_miss',
                'severity': 'critical',
                'message': f"DAG {dag_metrics.dag_id} missed SLA",
                'dag_id': dag_metrics.dag_id
            })
        
        # Check for stuck tasks (running for too long)
        for task in task_metrics:
            if task.state == 'running' and task.start_date:
                running_time = (datetime.now() - task.start_date).total_seconds()
                if running_time > self.alert_thresholds['task_duration_minutes'] * 60:
                    alerts.append({
                        'type': 'stuck_task',
                        'severity': 'critical',
                        'message': f"Task {task.task_id} in {task.dag_id} appears stuck (running for {running_time/60:.1f} minutes)",
                        'task_id': task.task_id,
                        'dag_id': task.dag_id,
                        'running_time': running_time
                    })
        
        return alerts
    
    def send_alert(self, alert: Dict):
        """Send alert notification."""
        try:
            # Send to Slack
            slack_webhook_url = os.getenv('SLACK_WEBHOOK_URL')
            if slack_webhook_url:
                self.send_slack_alert(alert, slack_webhook_url)
            
            # Send to email
            if alert['severity'] == 'critical':
                self.send_email_alert(alert)
            
            logger.warning("Alert sent", alert=alert)
        
        except Exception as e:
            logger.error(f"Error sending alert: {e}")
    
    def send_slack_alert(self, alert: Dict, webhook_url: str):
        """Send alert to Slack."""
        emoji = '🚨' if alert['severity'] == 'critical' else '⚠️'
        
        payload = {
            'channel': '#airflow-alerts',
            'username': 'Airflow Monitor',
            'icon_emoji': emoji,
            'text': f"{emoji} Airflow Alert: {alert['type'].replace('_', ' ').title()}",
            'attachments': [{
                'color': 'danger' if alert['severity'] == 'critical' else 'warning',
                'fields': [
                    {'title': 'Message', 'value': alert['message'], 'short': False},
                    {'title': 'Severity', 'value': alert['severity'].title(), 'short': True},
                    {'title': 'DAG ID', 'value': alert.get('dag_id', 'N/A'), 'short': True},
                    {'title': 'Task ID', 'value': alert.get('task_id', 'N/A'), 'short': True},
                    {'title': 'Timestamp', 'value': datetime.now().isoformat(), 'short': True}
                ]
            }]
        }
        
        response = requests.post(webhook_url, json=payload, timeout=30)
        response.raise_for_status()
    
    def send_email_alert(self, alert: Dict):
        """Send alert via email."""
        # Implementation would depend on email service
        logger.info(f"Email alert would be sent: {alert['message']}")
    
    def monitor_dag(self, dag_id: str, execution_date: datetime = None):
        """Monitor a specific DAG."""
        if execution_date is None:
            execution_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        logger.info("Monitoring DAG", dag_id=dag_id, execution_date=execution_date)
        
        # Get metrics
        dag_metrics = self.get_dag_metrics(dag_id, execution_date)
        if not dag_metrics:
            logger.warning("No DAG metrics found", dag_id=dag_id, execution_date=execution_date)
            return
        
        task_metrics = self.get_task_metrics(dag_id, execution_date)
        
        # Update Prometheus
        self.update_prometheus_metrics(dag_metrics, task_metrics)
        
        # Check for alerts
        alerts = self.check_alert_conditions(dag_metrics, task_metrics)
        
        # Send alerts
        for alert in alerts:
            self.send_alert(alert)
        
        # Log summary
        logger.info("DAG monitoring completed", 
                   dag_id=dag_id,
                   state=dag_metrics.state,
                   duration=dag_metrics.duration,
                   task_count=dag_metrics.task_count,
                   failed_count=dag_metrics.failed_count,
                   alerts_count=len(alerts))
    
    def monitor_all_dags(self):
        """Monitor all active DAGs."""
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Get all DAGs with recent runs
                cursor.execute("""
                SELECT DISTINCT dag_id
                FROM dag_run 
                WHERE execution_date >= %s
                ORDER BY dag_id
                """, (datetime.now() - timedelta(days=1),))
                
                dag_ids = [row[0] for row in cursor.fetchall()]
                cursor.close()
        
        except Exception as e:
            logger.error(f"Error getting DAG list: {e}")
            return
        
        for dag_id in dag_ids:
            try:
                self.monitor_dag(dag_id)
            except Exception as e:
                logger.error(f"Error monitoring DAG {dag_id}: {e}")
    
    def push_metrics_to_gateway(self, gateway_url: str):
        """Push metrics to Prometheus gateway."""
        try:
            push_to_gateway(gateway_url, job='airflow_monitor', registry=self.registry)
            logger.info("Metrics pushed to Prometheus gateway")
        except Exception as e:
            logger.error(f"Error pushing metrics to gateway: {e}")
    
    def generate_health_report(self) -> Dict:
        """Generate comprehensive health report."""
        report = {
            'timestamp': datetime.now().isoformat(),
            'dag_count': 0,
            'running_dags': 0,
            'failed_dags': 0,
            'total_tasks': 0,
            'failed_tasks': 0,
            'sla_misses': 0,
            'alerts': []
        }
        
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Get DAG counts
                cursor.execute("""
                SELECT 
                    COUNT(*) as total_dags,
                    SUM(CASE WHEN state = 'running' THEN 1 ELSE 0 END) as running_dags,
                    SUM(CASE WHEN state = 'failed' THEN 1 ELSE 0 END) as failed_dags
                FROM dag_run 
                WHERE execution_date >= %s
                """, (datetime.now() - timedelta(days=1),))
                
                dag_counts = cursor.fetchone()
                report['dag_count'] = dag_counts[0]
                report['running_dags'] = dag_counts[1]
                report['failed_dags'] = dag_counts[2]
                
                # Get task counts
                cursor.execute("""
                SELECT 
                    COUNT(*) as total_tasks,
                    SUM(CASE WHEN state = 'failed' THEN 1 ELSE 0 END) as failed_tasks
                FROM task_instance 
                WHERE execution_date >= %s
                """, (datetime.now() - timedelta(days=1),))
                
                task_counts = cursor.fetchone()
                report['total_tasks'] = task_counts[0]
                report['failed_tasks'] = task_counts[1]
                
                # Get SLA misses
                cursor.execute("""
                SELECT COUNT(*) as sla_misses
                FROM sla_miss 
                WHERE execution_date >= %s
                """, (datetime.now() - timedelta(days=1),))
                
                report['sla_misses'] = cursor.fetchone()[0]
                
                cursor.close()
        
        except Exception as e:
            logger.error(f"Error generating health report: {e}")
            report['error'] = str(e)
        
        return report


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Airflow monitoring system')
    parser.add_argument('--db-host', required=True, help='Database host')
    parser.add_argument('--db-name', required=True, help='Database name')
    parser.add_argument('--db-user', required=True, help='Database user')
    parser.add_argument('--db-password', required=True, help='Database password')
    parser.add_argument('--dag-id', help='Specific DAG to monitor')
    parser.add_argument('--gateway-url', help='Prometheus gateway URL')
    parser.add_argument('--schedule', action='store_true', help='Run in scheduled mode')
    parser.add_argument('--interval', type=int, default=300, help='Monitoring interval in seconds')
    
    args = parser.parse_args()
    
    # Initialize monitor
    monitor = AirflowMonitor(args.db_host, args.db_name, args.db_user, args.db_password)
    
    if args.schedule:
        logger.info("Starting scheduled monitoring")
        
        # Schedule monitoring
        schedule.every(args.interval).seconds.do(monitor.monitor_all_dags)
        
        if args.gateway_url:
            schedule.every(args.interval).seconds.do(
                lambda: monitor.push_metrics_to_gateway(args.gateway_url)
            )
        
        # Run scheduler
        while True:
            schedule.run_pending()
            time.sleep(1)
    
    else:
        # Single run
        if args.dag_id:
            monitor.monitor_dag(args.dag_id)
        else:
            monitor.monitor_all_dags()
        
        if args.gateway_url:
            monitor.push_metrics_to_gateway(args.gateway_url)
        
        # Generate health report
        health_report = monitor.generate_health_report()
        print(json.dumps(health_report, indent=2, default=str))


if __name__ == '__main__':
    main()
