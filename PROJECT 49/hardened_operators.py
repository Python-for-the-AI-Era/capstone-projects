"""
Hardened Airflow Operators with Timeouts and Error Handling
Production-ready operators that prevent hanging and ensure reliability
"""

import logging
import time
import json
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from contextlib import contextmanager
import requests
import psycopg2
from psycopg2 import sql, OperationalError, DatabaseError
import signal
import threading

from airflow.exceptions import AirflowException, AirflowTaskTimeout
from airflow.models import BaseOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.providers.http.operators.http import SimpleHttpOperator
from airflow.operators.python import PythonOperator
from airflow.hooks.base_hook import BaseHook

logger = logging.getLogger(__name__)


@dataclass
class TimeoutConfig:
    """Configuration for timeouts and retries"""
    http_timeout: int = 30
    db_timeout: int = 60
    max_retries: int = 3
    retry_delay: int = 5
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: int = 300


@dataclass
class OperationMetrics:
    """Metrics for operation performance"""
    start_time: datetime
    end_time: Optional[datetime]
    duration: Optional[float]
    rows_processed: int
    success: bool
    error_message: Optional[str]
    retry_count: int
    timeout_triggered: bool


class CircuitBreaker:
    """
    Circuit breaker pattern for external service calls
    Prevents cascading failures when services are down
    """
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 300):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
        
    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        if self.state == 'OPEN':
            if time.time() - self.last_failure_time > self.timeout:
                self.state = 'HALF_OPEN'
            else:
                raise AirflowException("Circuit breaker is OPEN")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        """Handle successful call"""
        self.failure_count = 0
        self.state = 'CLOSED'
    
    def _on_failure(self):
        """Handle failed call"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = 'OPEN'


class TimeoutHTTPHook(BaseHook):
    """
    HTTP Hook with built-in timeout and retry logic
    """
    
    def __init__(self, timeout_config: TimeoutConfig):
        self.timeout_config = timeout_config
        self.circuit_breaker = CircuitBreaker(
            timeout_config.circuit_breaker_threshold,
            timeout_config.circuit_breaker_timeout
        )
        super().__init__()
    
    def get_conn(self):
        """Get HTTP connection with timeout"""
        session = requests.Session()
        
        # Set default timeout
        for method in ('get', 'post', 'put', 'delete', 'patch'):
            setattr(session, method, self._wrap_method(getattr(session, method)))
        
        return session
    
    def _wrap_method(self, method):
        """Wrap HTTP method with timeout and circuit breaker"""
        def wrapped_method(*args, **kwargs):
            # Ensure timeout is set
            if 'timeout' not in kwargs:
                kwargs['timeout'] = self.timeout_config.http_timeout
            
            # Use circuit breaker
            return self.circuit_breaker.call(method, *args, **kwargs)
        
        return wrapped_method


class TimeoutDatabaseHook(BaseHook):
    """
    Database Hook with built-in timeout and connection management
    """
    
    def __init__(self, timeout_config: TimeoutConfig):
        self.timeout_config = timeout_config
        self._connection = None
        super().__init__()
    
    def get_conn(self):
        """Get database connection with timeout"""
        if self._connection is None or self._connection.closed:
            self._connection = self._create_connection()
        return self._connection
    
    def _create_connection(self):
        """Create database connection with timeout"""
        conn_id = self.get_connection_id()
        conn = self.get_connection(conn_id)
        
        # Set statement timeout
        cursor = conn.cursor()
        cursor.execute(f"SET statement_timeout = {self.timeout_config.db_timeout * 1000}")
        conn.commit()
        
        return conn
    
    @contextmanager
    def transaction(self):
        """Context manager for database transactions"""
        conn = self.get_conn()
        try:
            conn.autocommit = False
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.autocommit = True


class HardenedReconciliationOperator(BaseOperator):
    """
    Hardened reconciliation operator with comprehensive error handling
    """
    
    template_fields = ['sql_query', 'api_endpoint']
    
    def __init__(
        self,
        sql_query: str,
        api_endpoint: str,
        timeout_config: TimeoutConfig = None,
        batch_size: int = 1000,
        max_runtime_minutes: int = 60,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.sql_query = sql_query
        self.api_endpoint = api_endpoint
        self.timeout_config = timeout_config or TimeoutConfig()
        self.batch_size = batch_size
        self.max_runtime_minutes = max_runtime_minutes
        self.metrics = OperationMetrics(
            start_time=datetime.now(),
            end_time=None,
            duration=None,
            rows_processed=0,
            success=False,
            error_message=None,
            retry_count=0,
            timeout_triggered=False
        )
        
        # Initialize hooks
        self.http_hook = TimeoutHTTPHook(self.timeout_config)
        self.db_hook = TimeoutDatabaseHook(self.timeout_config)
    
    def execute(self, context):
        """Execute reconciliation with comprehensive error handling"""
        self.log.info("Starting hardened reconciliation process")
        
        # Set up timeout for entire operation
        def timeout_handler(signum, frame):
            raise AirflowTaskTimeout(f"Task exceeded {self.max_runtime_minutes} minutes runtime")
        
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(self.max_runtime_minutes * 60)
        
        try:
            # Process reconciliation
            result = self._process_reconciliation(context)
            
            # Update metrics
            self.metrics.end_time = datetime.now()
            self.metrics.duration = (self.metrics.end_time - self.metrics.start_time).total_seconds()
            self.metrics.success = True
            
            # Push metrics to XCom
            context['ti'].xcom_push(key='reconciliation_metrics', value=asdict(self.metrics))
            
            self.log.info(f"Reconciliation completed successfully: {self.metrics.rows_processed} rows in {self.metrics.duration:.2f}s")
            return result
            
        except AirflowTaskTimeout as e:
            self.metrics.timeout_triggered = True
            self.metrics.error_message = str(e)
            self._handle_timeout(context, e)
            raise
        except Exception as e:
            self.metrics.error_message = str(e)
            self._handle_error(context, e)
            raise
        finally:
            signal.alarm(0)  # Cancel timeout
    
    def _process_reconciliation(self, context) -> Dict[str, Any]:
        """Process reconciliation with batching and error handling"""
        total_rows = 0
        successful_batches = 0
        failed_batches = 0
        
        # Get database connection
        with self.db_hook.transaction() as conn:
            cursor = conn.cursor()
            
            # Execute main query
            self.log.info("Executing reconciliation query")
            cursor.execute(self.sql_query)
            
            # Process results in batches
            while True:
                rows = cursor.fetchmany(self.batch_size)
                if not rows:
                    break
                
                try:
                    # Process batch
                    batch_result = self._process_batch(rows, context)
                    total_rows += len(rows)
                    successful_batches += 1
                    
                    # Log progress
                    self.log.info(f"Processed batch {successful_batches}: {len(rows)} rows")
                    
                    # Push batch metrics to XCom
                    batch_metrics = {
                        'batch_number': successful_batches,
                        'rows_in_batch': len(rows),
                        'total_rows_processed': total_rows,
                        'timestamp': datetime.now().isoformat()
                    }
                    context['ti'].xcom_push(key='batch_metrics', value=batch_metrics)
                    
                except Exception as e:
                    failed_batches += 1
                    self.log.error(f"Batch {successful_batches + failed_batches} failed: {e}")
                    
                    # Decide whether to continue or fail
                    if failed_batches >= self.timeout_config.max_retries:
                        raise AirflowException(f"Too many failed batches: {failed_batches}")
                    
                    # Continue with next batch
                    continue
        
        self.metrics.rows_processed = total_rows
        
        return {
            'total_rows': total_rows,
            'successful_batches': successful_batches,
            'failed_batches': failed_batches,
            'success_rate': successful_batches / (successful_batches + failed_batches) if (successful_batches + failed_batches) > 0 else 0
        }
    
    def _process_batch(self, rows: List[tuple], context) -> bool:
        """Process a batch of rows with API call"""
        # Convert rows to API format
        records = []
        for row in rows:
            records.append({
                'id': row[0],
                'amount': float(row[1]),
                'date': row[2].isoformat() if hasattr(row[2], 'isoformat') else str(row[2]),
                'account_id': row[3]
            })
        
        # Make API call with timeout
        session = self.http_hook.get_conn()
        
        try:
            response = session.post(
                self.api_endpoint,
                json={'records': records},
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status()
            
            return True
            
        except requests.exceptions.Timeout as e:
            raise AirflowException(f"API timeout after {self.timeout_config.http_timeout}s: {e}")
        except requests.exceptions.ConnectionError as e:
            raise AirflowException(f"API connection error: {e}")
        except requests.exceptions.HTTPError as e:
            raise AirflowException(f"API HTTP error: {e}")
        except Exception as e:
            raise AirflowException(f"Unexpected API error: {e}")
    
    def _handle_timeout(self, context, exception: AirflowTaskTimeout):
        """Handle task timeout"""
        self.log.error(f"Task timeout: {exception}")
        
        # Send alert
        self._send_alert(context, "TIMEOUT", str(exception))
        
        # Kill any hanging subprocesses
        self._cleanup_hanging_processes()
    
    def _handle_error(self, context, exception: Exception):
        """Handle general error"""
        self.log.error(f"Task error: {exception}")
        
        # Send alert for critical errors
        if isinstance(exception, (OperationalError, DatabaseError)):
            self._send_alert(context, "DATABASE_ERROR", str(exception))
        elif isinstance(exception, requests.exceptions.RequestException):
            self._send_alert(context, "API_ERROR", str(exception))
    
    def _send_alert(self, context, alert_type: str, message: str):
        """Send alert to monitoring system"""
        try:
            alert_data = {
                'dag_id': self.dag_id,
                'task_id': self.task_id,
                'execution_date': context['execution_date'],
                'alert_type': alert_type,
                'message': message,
                'timestamp': datetime.now().isoformat(),
                'metrics': asdict(self.metrics)
            }
            
            # In production, this would send to Slack/PagerDuty/etc.
            self.log.info(f"ALERT: {alert_type} - {message}")
            
        except Exception as e:
            self.log.error(f"Failed to send alert: {e}")
    
    def _cleanup_hanging_processes(self):
        """Clean up any hanging processes"""
        try:
            import psutil
            current_process = psutil.Process()
            
            # Kill child processes
            for child in current_process.children(recursive=True):
                try:
                    child.kill()
                    self.log.info(f"Killed hanging process: {child.pid}")
                except psutil.NoSuchProcess:
                    pass
                    
        except Exception as e:
            self.log.error(f"Error cleaning up processes: {e}")


class HardenedPostgresOperator(PostgresOperator):
    """
    Hardened Postgres operator with timeout and error handling
    """
    
    def __init__(
        self,
        timeout_config: TimeoutConfig = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.timeout_config = timeout_config or TimeoutConfig()
        self.metrics = OperationMetrics(
            start_time=datetime.now(),
            end_time=None,
            duration=None,
            rows_processed=0,
            success=False,
            error_message=None,
            retry_count=0,
            timeout_triggered=False
        )
    
    def execute(self, context):
        """Execute SQL with timeout and error handling"""
        self.log.info("Executing hardened Postgres operation")
        
        try:
            # Get connection with timeout
            db_hook = TimeoutDatabaseHook(self.timeout_config)
            
            with db_hook.transaction() as conn:
                cursor = conn.cursor()
                
                # Set query timeout
                cursor.execute(f"SET statement_timeout = {self.timeout_config.db_timeout * 1000}")
                
                # Execute main query
                start_time = time.time()
                cursor.execute(self.sql)
                
                # Get affected rows
                if cursor.description:
                    rows = cursor.fetchall()
                    self.metrics.rows_processed = len(rows)
                else:
                    self.metrics.rows_processed = cursor.rowcount
                
                duration = time.time() - start_time
                self.log.info(f"SQL completed in {duration:.2f}s, {self.metrics.rows_processed} rows affected")
            
            # Update metrics
            self.metrics.end_time = datetime.now()
            self.metrics.duration = duration
            self.metrics.success = True
            
            # Push metrics to XCom
            context['ti'].xcom_push(key='postgres_metrics', value=asdict(self.metrics))
            
            return self.metrics.rows_processed
            
        except OperationalError as e:
            self.metrics.error_message = str(e)
            if 'timeout' in str(e).lower() or 'statement timeout' in str(e).lower():
                self.metrics.timeout_triggered = True
                raise AirflowTaskTimeout(f"Postgres query timeout: {e}")
            else:
                raise AirflowException(f"Postgres operational error: {e}")
        except Exception as e:
            self.metrics.error_message = str(e)
            raise AirflowException(f"Postgres error: {e}")


class HardenedHttpOperator(SimpleHttpOperator):
    """
    Hardened HTTP operator with timeout and circuit breaker
    """
    
    def __init__(
        self,
        timeout_config: TimeoutConfig = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.timeout_config = timeout_config or TimeoutConfig()
        self.metrics = OperationMetrics(
            start_time=datetime.now(),
            end_time=None,
            duration=None,
            rows_processed=0,
            success=False,
            error_message=None,
            retry_count=0,
            timeout_triggered=False
        )
    
    def execute(self, context):
        """Execute HTTP request with timeout and circuit breaker"""
        self.log.info("Executing hardened HTTP operation")
        
        # Override default timeout
        if not self.http_conn_id:
            self.timeout = self.timeout_config.http_timeout
        
        try:
            start_time = time.time()
            
            # Execute HTTP request
            response = super().execute(context)
            
            duration = time.time() - start_time
            self.log.info(f"HTTP request completed in {duration:.2f}s")
            
            # Update metrics
            self.metrics.end_time = datetime.now()
            self.metrics.duration = duration
            self.metrics.success = True
            self.metrics.rows_processed = 1  # HTTP request counts as 1 operation
            
            # Push metrics to XCom
            context['ti'].xcom_push(key='http_metrics', value=asdict(self.metrics))
            
            return response
            
        except requests.exceptions.Timeout as e:
            self.metrics.timeout_triggered = True
            self.metrics.error_message = str(e)
            raise AirflowTaskTimeout(f"HTTP request timeout after {self.timeout_config.http_timeout}s: {e}")
        except requests.exceptions.RequestException as e:
            self.metrics.error_message = str(e)
            raise AirflowException(f"HTTP request error: {e}")
        except Exception as e:
            self.metrics.error_message = str(e)
            raise AirflowException(f"Unexpected HTTP error: {e}")


class ObservabilityMixin:
    """
    Mixin for adding observability to operators
    """
    
    def push_observability_data(self, context, data: Dict[str, Any]):
        """Push observability data to XCom"""
        try:
            observability_data = {
                'dag_id': self.dag_id,
                'task_id': self.task_id,
                'execution_date': context['execution_date'],
                'task_start_time': context['task'].start_date,
                'timestamp': datetime.now().isoformat(),
                'data': data
            }
            
            context['ti'].xcom_push(key='observability', value=observability_data)
            
        except Exception as e:
            self.log.error(f"Failed to push observability data: {e}")
    
    def log_performance_metrics(self, context, operation: str, duration: float, **kwargs):
        """Log performance metrics"""
        metrics = {
            'operation': operation,
            'duration': duration,
            'timestamp': datetime.now().isoformat(),
            **kwargs
        }
        
        self.log.info(f"Performance: {metrics}")
        self.push_observability_data(context, {'performance_metrics': metrics})


# Utility functions for creating hardened operators
def create_hardened_reconciliation_task(
    task_id: str,
    sql_query: str,
    api_endpoint: str,
    timeout_config: TimeoutConfig = None,
    **kwargs
) -> HardenedReconciliationOperator:
    """Create a hardened reconciliation operator"""
    return HardenedReconciliationOperator(
        task_id=task_id,
        sql_query=sql_query,
        api_endpoint=api_endpoint,
        timeout_config=timeout_config or TimeoutConfig(),
        **kwargs
    )


def create_hardened_postgres_task(
    task_id: str,
    sql: str,
    timeout_config: TimeoutConfig = None,
    **kwargs
) -> HardenedPostgresOperator:
    """Create a hardened Postgres operator"""
    return HardenedPostgresOperator(
        task_id=task_id,
        sql=sql,
        timeout_config=timeout_config or TimeoutConfig(),
        **kwargs
    )


def create_hardened_http_task(
    task_id: str,
    endpoint: str,
    method: str = 'POST',
    timeout_config: TimeoutConfig = None,
    **kwargs
) -> HardenedHttpOperator:
    """Create a hardened HTTP operator"""
    return HardenedHttpOperator(
        task_id=task_id,
        endpoint=endpoint,
        method=method,
        timeout_config=timeout_config or TimeoutConfig(),
        **kwargs
    )


# Example usage in DAG
if __name__ == "__main__":
    # Example of how to use hardened operators
    from airflow import DAG
    from datetime import datetime
    
    timeout_config = TimeoutConfig(
        http_timeout=30,
        db_timeout=60,
        max_retries=3,
        retry_delay=5
    )
    
    with DAG(
        'hardened_reconciliation_dag',
        start_date=datetime(2024, 1, 1),
        schedule_interval='@daily'
    ) as dag:
        
        # Hardened tasks
        fetch_data = create_hardened_postgres_task(
            task_id='fetch_reconciliation_data',
            sql='SELECT id, amount, date, account_id FROM transactions WHERE date = {{ ds }}',
            timeout_config=timeout_config
        )
        
        process_data = create_hardened_reconciliation_task(
            task_id='process_reconciliation',
            sql_query='SELECT id, amount, date, account_id FROM transactions WHERE date = {{ ds }}',
            api_endpoint='https://core-banking.api/reconcile',
            timeout_config=timeout_config
        )
        
        fetch_data >> process_data
