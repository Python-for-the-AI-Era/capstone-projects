"""
XCom Observability System for Real-time Airflow Monitoring
Comprehensive real-time monitoring using Airflow XCom for task performance tracking
"""

import logging
import json
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from pathlib import Path
import sqlite3
from contextlib import contextmanager
import requests
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


@dataclass
class TaskObservabilityData:
    """Observability data for a task"""
    dag_id: str
    task_id: str
    execution_date: str
    run_id: str
    start_time: datetime
    end_time: Optional[datetime]
    duration: Optional[float]
    state: str
    rows_processed: int
    error_count: int
    retry_count: int
    memory_usage_mb: float
    cpu_usage_percent: float
    custom_metrics: Dict[str, Any]
    timestamp: datetime


@dataclass
class DAGObservabilitySummary:
    """Summary of DAG observability data"""
    dag_id: str
    execution_date: str
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    running_tasks: int
    total_duration: float
    total_rows_processed: int
    total_errors: int
    average_task_duration: float
    slowest_task: Optional[str]
    fastest_task: Optional[str]
    task_performance: Dict[str, Dict[str, Any]]
    timestamp: datetime


class XComObservabilityManager:
    """
    Manages XCom-based observability data collection and analysis
    """
    
    def __init__(self, db_path: str = "xcom_observability.db"):
        self.db_path = db_path
        self.observers = []
        self.real_time_callbacks = []
        self.task_data = defaultdict(list)
        self.dag_summaries = {}
        
        # Initialize database
        self._init_database()
        
        logger.info("XComObservabilityManager initialized")
    
    def _init_database(self):
        """Initialize SQLite database for storing observability data"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create task observability table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS task_observability (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        dag_id TEXT NOT NULL,
                        task_id TEXT NOT NULL,
                        execution_date TEXT NOT NULL,
                        run_id TEXT NOT NULL,
                        start_time TEXT NOT NULL,
                        end_time TEXT,
                        duration REAL,
                        state TEXT NOT NULL,
                        rows_processed INTEGER DEFAULT 0,
                        error_count INTEGER DEFAULT 0,
                        retry_count INTEGER DEFAULT 0,
                        memory_usage_mb REAL DEFAULT 0,
                        cpu_usage_percent REAL DEFAULT 0,
                        custom_metrics TEXT,
                        timestamp TEXT NOT NULL,
                        UNIQUE(dag_id, task_id, execution_date, run_id)
                    )
                ''')
                
                # Create DAG summary table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS dag_summary (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        dag_id TEXT NOT NULL,
                        execution_date TEXT NOT NULL,
                        total_tasks INTEGER NOT NULL,
                        completed_tasks INTEGER DEFAULT 0,
                        failed_tasks INTEGER DEFAULT 0,
                        running_tasks INTEGER DEFAULT 0,
                        total_duration REAL DEFAULT 0,
                        total_rows_processed INTEGER DEFAULT 0,
                        total_errors INTEGER DEFAULT 0,
                        average_task_duration REAL DEFAULT 0,
                        slowest_task TEXT,
                        fastest_task TEXT,
                        task_performance TEXT,
                        timestamp TEXT NOT NULL,
                        UNIQUE(dag_id, execution_date)
                    )
                ''')
                
                # Create indexes
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_task_dag_execution ON task_observability(dag_id, execution_date)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_task_timestamp ON task_observability(timestamp)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_dag_timestamp ON dag_summary(timestamp)')
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise
    
    def register_observer(self, observer_func: Callable[[TaskObservabilityData], None]):
        """Register observer function for real-time monitoring"""
        self.observers.append(observer_func)
        logger.info(f"Registered observer: {observer_func.__name__}")
    
    def register_real_time_callback(self, callback: Callable[[DAGObservabilitySummary], None]):
        """Register real-time callback for DAG summaries"""
        self.real_time_callbacks.append(callback)
        logger.info(f"Registered real-time callback: {callback.__name__}")
    
    def push_task_data(self, task_data: TaskObservabilityData):
        """Push task observability data to XCom and local storage"""
        try:
            # Store in database
            self._store_task_data(task_data)
            
            # Store in memory for real-time access
            key = f"{task_data.dag_id}.{task_data.execution_date}"
            self.task_data[key].append(task_data)
            
            # Notify observers
            for observer in self.observers:
                try:
                    observer(task_data)
                except Exception as e:
                    logger.error(f"Error in observer {observer.__name__}: {e}")
            
            # Update DAG summary
            self._update_dag_summary(task_data.dag_id, task_data.execution_date)
            
            logger.debug(f"Pushed task data for {task_data.dag_id}.{task_data.task_id}")
            
        except Exception as e:
            logger.error(f"Error pushing task data: {e}")
    
    def _store_task_data(self, task_data: TaskObservabilityData):
        """Store task data in database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO task_observability
                    (dag_id, task_id, execution_date, run_id, start_time, end_time,
                     duration, state, rows_processed, error_count, retry_count,
                     memory_usage_mb, cpu_usage_percent, custom_metrics, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    task_data.dag_id,
                    task_data.task_id,
                    task_data.execution_date,
                    task_data.run_id,
                    task_data.start_time.isoformat(),
                    task_data.end_time.isoformat() if task_data.end_time else None,
                    task_data.duration,
                    task_data.state,
                    task_data.rows_processed,
                    task_data.error_count,
                    task_data.retry_count,
                    task_data.memory_usage_mb,
                    task_data.cpu_usage_percent,
                    json.dumps(task_data.custom_metrics),
                    task_data.timestamp.isoformat()
                ))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error storing task data: {e}")
            raise
    
    def _update_dag_summary(self, dag_id: str, execution_date: str):
        """Update DAG summary with latest task data"""
        try:
            key = f"{dag_id}.{execution_date}"
            task_list = self.task_data.get(key, [])
            
            if not task_list:
                return
            
            # Calculate summary metrics
            total_tasks = len(task_list)
            completed_tasks = len([t for t in task_list if t.state == 'success'])
            failed_tasks = len([t for t in task_list if t.state in ['failed', 'upstream_failed']])
            running_tasks = len([t for t in task_list if t.state == 'running'])
            
            total_duration = sum([t.duration for t in task_list if t.duration])
            total_rows_processed = sum([t.rows_processed for t in task_list])
            total_errors = sum([t.error_count for t in task_list])
            
            completed_task_durations = [t.duration for t in task_list if t.duration and t.state == 'success']
            average_task_duration = sum(completed_task_durations) / len(completed_task_durations) if completed_task_durations else 0
            
            # Find slowest and fastest tasks
            task_durations = {t.task_id: t.duration for t in task_list if t.duration}
            slowest_task = max(task_durations.items(), key=lambda x: x[1])[0] if task_durations else None
            fastest_task = min(task_durations.items(), key=lambda x: x[1])[0] if task_durations else None
            
            # Task performance details
            task_performance = {}
            for task in task_list:
                task_performance[task.task_id] = {
                    'duration': task.duration,
                    'rows_processed': task.rows_processed,
                    'state': task.state,
                    'retry_count': task.retry_count,
                    'memory_usage_mb': task.memory_usage_mb,
                    'cpu_usage_percent': task.cpu_usage_percent,
                    'custom_metrics': task.custom_metrics
                }
            
            # Create summary
            summary = DAGObservabilitySummary(
                dag_id=dag_id,
                execution_date=execution_date,
                total_tasks=total_tasks,
                completed_tasks=completed_tasks,
                failed_tasks=failed_tasks,
                running_tasks=running_tasks,
                total_duration=total_duration,
                total_rows_processed=total_rows_processed,
                total_errors=total_errors,
                average_task_duration=average_task_duration,
                slowest_task=slowest_task,
                fastest_task=fastest_task,
                task_performance=task_performance,
                timestamp=datetime.now()
            )
            
            # Store in database
            self._store_dag_summary(summary)
            
            # Store in memory
            self.dag_summaries[key] = summary
            
            # Notify real-time callbacks
            for callback in self.real_time_callbacks:
                try:
                    callback(summary)
                except Exception as e:
                    logger.error(f"Error in real-time callback {callback.__name__}: {e}")
            
        except Exception as e:
            logger.error(f"Error updating DAG summary: {e}")
    
    def _store_dag_summary(self, summary: DAGObservabilitySummary):
        """Store DAG summary in database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO dag_summary
                    (dag_id, execution_date, total_tasks, completed_tasks, failed_tasks,
                     running_tasks, total_duration, total_rows_processed, total_errors,
                     average_task_duration, slowest_task, fastest_task, task_performance, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    summary.dag_id,
                    summary.execution_date,
                    summary.total_tasks,
                    summary.completed_tasks,
                    summary.failed_tasks,
                    summary.running_tasks,
                    summary.total_duration,
                    summary.total_rows_processed,
                    summary.total_errors,
                    summary.average_task_duration,
                    summary.slowest_task,
                    summary.fastest_task,
                    json.dumps(summary.task_performance),
                    summary.timestamp.isoformat()
                ))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error storing DAG summary: {e}")
            raise
    
    def get_task_data(self, dag_id: str, execution_date: str = None, 
                     task_id: str = None, limit: int = 100) -> List[TaskObservabilityData]:
        """Get task observability data"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                query = '''
                    SELECT dag_id, task_id, execution_date, run_id, start_time, end_time,
                           duration, state, rows_processed, error_count, retry_count,
                           memory_usage_mb, cpu_usage_percent, custom_metrics, timestamp
                    FROM task_observability
                    WHERE dag_id = ?
                '''
                params = [dag_id]
                
                if execution_date:
                    query += ' AND execution_date = ?'
                    params.append(execution_date)
                
                if task_id:
                    query += ' AND task_id = ?'
                    params.append(task_id)
                
                query += ' ORDER BY timestamp DESC LIMIT ?'
                params.append(limit)
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                results = []
                for row in rows:
                    task_data = TaskObservabilityData(
                        dag_id=row[0],
                        task_id=row[1],
                        execution_date=row[2],
                        run_id=row[3],
                        start_time=datetime.fromisoformat(row[4]),
                        end_time=datetime.fromisoformat(row[5]) if row[5] else None,
                        duration=row[6],
                        state=row[7],
                        rows_processed=row[8],
                        error_count=row[9],
                        retry_count=row[10],
                        memory_usage_mb=row[11],
                        cpu_usage_percent=row[12],
                        custom_metrics=json.loads(row[13]) if row[13] else {},
                        timestamp=datetime.fromisoformat(row[14])
                    )
                    results.append(task_data)
                
                return results
                
        except Exception as e:
            logger.error(f"Error getting task data: {e}")
            return []
    
    def get_dag_summary(self, dag_id: str, execution_date: str = None) -> Optional[DAGObservabilitySummary]:
        """Get DAG observability summary"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                query = '''
                    SELECT dag_id, execution_date, total_tasks, completed_tasks, failed_tasks,
                           running_tasks, total_duration, total_rows_processed, total_errors,
                           average_task_duration, slowest_task, fastest_task, task_performance, timestamp
                    FROM dag_summary
                    WHERE dag_id = ?
                '''
                params = [dag_id]
                
                if execution_date:
                    query += ' AND execution_date = ?'
                    params.append(execution_date)
                
                query += ' ORDER BY timestamp DESC LIMIT 1'
                
                cursor.execute(query, params)
                row = cursor.fetchone()
                
                if row:
                    return DAGObservabilitySummary(
                        dag_id=row[0],
                        execution_date=row[1],
                        total_tasks=row[2],
                        completed_tasks=row[3],
                        failed_tasks=row[4],
                        running_tasks=row[5],
                        total_duration=row[6],
                        total_rows_processed=row[7],
                        total_errors=row[8],
                        average_task_duration=row[9],
                        slowest_task=row[10],
                        fastest_task=row[11],
                        task_performance=json.loads(row[12]) if row[12] else {},
                        timestamp=datetime.fromisoformat(row[13])
                    )
                
                return None
                
        except Exception as e:
            logger.error(f"Error getting DAG summary: {e}")
            return None
    
    def get_performance_report(self, dag_id: str, days: int = 7) -> Dict[str, Any]:
        """Generate performance report for a DAG"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get task performance data
                cursor.execute('''
                    SELECT task_id, AVG(duration) as avg_duration, AVG(rows_processed) as avg_rows,
                           COUNT(*) as runs, SUM(CASE WHEN state = 'success' THEN 1 ELSE 0 END) as successes
                    FROM task_observability
                    WHERE dag_id = ? AND timestamp >= ?
                    GROUP BY task_id
                    ORDER BY avg_duration DESC
                ''', (dag_id, cutoff_date.isoformat()))
                
                task_performance = cursor.fetchall()
                
                # Get DAG summary data
                cursor.execute('''
                    SELECT execution_date, total_duration, completed_tasks, failed_tasks
                    FROM dag_summary
                    WHERE dag_id = ? AND timestamp >= ?
                    ORDER BY execution_date
                ''', (dag_id, cutoff_date.isoformat()))
                
                dag_performance = cursor.fetchall()
                
                # Calculate statistics
                total_runs = len(dag_performance)
                successful_runs = len([d for d in dag_performance if d[2] > 0 and d[3] == 0])
                success_rate = successful_runs / max(total_runs, 1)
                
                avg_duration = sum([d[1] for d in dag_performance]) / max(len(dag_performance), 1)
                
                report = {
                    'dag_id': dag_id,
                    'period_days': days,
                    'total_runs': total_runs,
                    'success_rate': success_rate,
                    'average_duration': avg_duration,
                    'task_performance': [
                        {
                            'task_id': row[0],
                            'avg_duration': row[1],
                            'avg_rows_processed': row[2],
                            'total_runs': row[3],
                            'success_rate': row[4] / max(row[3], 1)
                        }
                        for row in task_performance
                    ],
                    'generated_at': datetime.now().isoformat()
                }
                
                return report
                
        except Exception as e:
            logger.error(f"Error generating performance report: {e}")
            return {}
    
    def export_observability_data(self, dag_id: str, execution_date: str, 
                                 output_file: str = None) -> str:
        """Export observability data to JSON file"""
        try:
            if output_file is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = f"observability_{dag_id}_{execution_date}_{timestamp}.json"
            
            # Get all data
            task_data = self.get_task_data(dag_id, execution_date)
            dag_summary = self.get_dag_summary(dag_id, execution_date)
            
            # Create export data
            export_data = {
                'dag_id': dag_id,
                'execution_date': execution_date,
                'dag_summary': asdict(dag_summary) if dag_summary else None,
                'task_data': [asdict(task) for task in task_data],
                'exported_at': datetime.now().isoformat()
            }
            
            # Write to file
            with open(output_file, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
            
            logger.info(f"Observability data exported to {output_file}")
            return output_file
            
        except Exception as e:
            logger.error(f"Error exporting observability data: {e}")
            raise


class ObservabilityMixin:
    """
    Mixin for Airflow operators to automatically push observability data
    """
    
    def push_observability_data(self, context, **kwargs):
        """Push observability data to XCom"""
        try:
            # Get basic task information
            task_instance = context['task_instance']
            dag_run = context['dag_run']
            
            # Calculate duration
            start_time = task_instance.start_date
            end_time = task_instance.end_date or datetime.now(start_time.tzinfo)
            duration = (end_time - start_time).total_seconds()
            
            # Get system metrics
            try:
                import psutil
                process = psutil.Process()
                memory_usage_mb = process.memory_info().rss / 1024 / 1024
                cpu_usage_percent = process.cpu_percent()
            except:
                memory_usage_mb = 0
                cpu_usage_percent = 0
            
            # Create observability data
            obs_data = TaskObservabilityData(
                dag_id=task_instance.dag_id,
                task_id=task_instance.task_id,
                execution_date=str(dag_run.execution_date),
                run_id=str(dag_run.run_id),
                start_time=start_time,
                end_time=end_time,
                duration=duration,
                state=task_instance.state,
                rows_processed=kwargs.get('rows_processed', 0),
                error_count=kwargs.get('error_count', 0),
                retry_count=task_instance.try_number,
                memory_usage_mb=memory_usage_mb,
                cpu_usage_percent=cpu_usage_percent,
                custom_metrics=kwargs.get('custom_metrics', {}),
                timestamp=datetime.now()
            )
            
            # Push to XCom
            context['ti'].xcom_push(key='observability_data', value=asdict(obs_data))
            
            # Also push specific metrics for easy access
            context['ti'].xcom_push(key='task_duration', value=duration)
            context['ti'].xcom_push(key='rows_processed', value=obs_data.rows_processed)
            context['ti'].xcom_push(key='task_memory_mb', value=memory_usage_mb)
            
            logger.info(f"Pushed observability data for {task_instance.dag_id}.{task_instance.task_id}")
            
        except Exception as e:
            logger.error(f"Error pushing observability data: {e}")
    
    def log_performance_metrics(self, context, operation: str, **kwargs):
        """Log performance metrics"""
        try:
            metrics = {
                'operation': operation,
                'timestamp': datetime.now().isoformat(),
                'dag_id': context['dag'].dag_id,
                'task_id': context['task'].task_id,
                'execution_date': str(context['dag_run'].execution_date),
                **kwargs
            }
            
            logger.info(f"Performance metrics: {metrics}")
            
            # Push to XCom as well
            context['ti'].xcom_push(key='performance_metrics', value=metrics)
            
        except Exception as e:
            logger.error(f"Error logging performance metrics: {e}")


# Real-time monitoring dashboard
class RealTimeMonitor:
    """
    Real-time monitoring dashboard for Airflow DAGs
    """
    
    def __init__(self, observability_manager: XComObservabilityManager):
        self.obs_manager = observability_manager
        self.active_dags = {}
        self.alert_thresholds = {
            'max_task_duration': 3600,  # 1 hour
            'max_memory_usage': 1024,  # 1GB
            'failure_rate': 0.1  # 10%
        }
        
        # Register callbacks
        self.obs_manager.register_real_time_callback(self.on_dag_summary_update)
        
        logger.info("RealTimeMonitor initialized")
    
    def on_dag_summary_update(self, summary: DAGObservabilitySummary):
        """Handle real-time DAG summary updates"""
        self.active_dags[f"{summary.dag_id}.{summary.execution_date}"] = summary
        
        # Check for alerts
        self._check_alerts(summary)
        
        # Log update
        logger.info(f"Updated DAG summary: {summary.dag_id} - {summary.completed_tasks}/{summary.total_tasks} tasks completed")
    
    def _check_alerts(self, summary: DAGObservabilitySummary):
        """Check for performance alerts"""
        alerts = []
        
        # Check for slow tasks
        if summary.slowest_task and summary.average_task_duration > self.alert_thresholds['max_task_duration']:
            alerts.append({
                'type': 'slow_tasks',
                'message': f"DAG {summary.dag_id} has slow tasks (avg: {summary.average_task_duration:.1f}s)",
                'severity': 'warning'
            })
        
        # Check for memory usage
        high_memory_tasks = [
            task_id for task_id, perf in summary.task_performance.items()
            if perf.get('memory_usage_mb', 0) > self.alert_thresholds['max_memory_usage']
        ]
        
        if high_memory_tasks:
            alerts.append({
                'type': 'high_memory',
                'message': f"DAG {summary.dag_id} has tasks with high memory usage: {high_memory_tasks}",
                'severity': 'warning'
            })
        
        # Check for failures
        if summary.total_tasks > 0:
            failure_rate = summary.failed_tasks / summary.total_tasks
            if failure_rate > self.alert_thresholds['failure_rate']:
                alerts.append({
                    'type': 'high_failure_rate',
                    'message': f"DAG {summary.dag_id} has high failure rate: {failure_rate:.1%}",
                    'severity': 'critical'
                })
        
        # Send alerts
        for alert in alerts:
            self._send_alert(alert)
    
    def _send_alert(self, alert: Dict[str, Any]):
        """Send alert (would integrate with monitoring system)"""
        logger.warning(f"ALERT: {alert['message']}")
        
        # In production, this would send to Slack, PagerDuty, etc.
        # For now, just log the alert
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get data for real-time dashboard"""
        return {
            'active_dags': len(self.active_dags),
            'dag_summaries': {
                key: asdict(summary) for key, summary in self.active_dags.items()
            },
            'timestamp': datetime.now().isoformat()
        }


# Utility functions for Airflow operators
def create_observability_task(dag_id: str, task_id: str, **kwargs):
    """Create an observability-enabled task"""
    def observability_function(**context):
        # Your task logic here
        result = perform_task_logic(**context)
        
        # Push observability data
        mixin = ObservabilityMixin()
        mixin.push_observability_data(context, rows_processed=result.get('rows_processed', 0))
        
        return result
    
    return observability_function


def perform_task_logic(**context):
    """Example task logic"""
    # Simulate work
    time.sleep(1)
    
    return {
        'rows_processed': 1000,
        'status': 'success'
    }


# Example usage
if __name__ == "__main__":
    # Example usage
    obs_manager = XComObservabilityManager()
    
    # Create sample data
    sample_data = TaskObservabilityData(
        dag_id="daily_reconciliation_v2",
        task_id="process_reconciliation",
        execution_date="2024-01-15",
        run_id="manual__2024-01-15T10:00:00+00:00",
        start_time=datetime.now() - timedelta(minutes=5),
        end_time=datetime.now(),
        duration=300,
        state="success",
        rows_processed=50000,
        error_count=0,
        retry_count=0,
        memory_usage_mb=256,
        cpu_usage_percent=15,
        custom_metrics={"api_calls": 10, "db_queries": 5},
        timestamp=datetime.now()
    )
    
    # Push data
    obs_manager.push_task_data(sample_data)
    
    # Get summary
    summary = obs_manager.get_dag_summary("daily_reconciliation_v2", "2024-01-15")
    if summary:
        print(f"DAG Summary: {summary.total_tasks} tasks, {summary.completed_tasks} completed")
    
    # Generate report
    report = obs_manager.get_performance_report("daily_reconciliation_v2")
    print(f"Performance Report: {report}")
