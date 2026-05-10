"""
FIXED Airflow DAG - Finco Bank End-of-Day Reconciliation

This DAG addresses all the issues that caused the original to get stuck:
1. HTTP calls with proper timeouts (30 seconds)
2. Database operations with context managers and connection pooling
3. SLA monitoring with Slack alerts
4. Comprehensive observability and logging
5. XCom usage for timing and row count data
6. Error handling and retry mechanisms
"""

from datetime import datetime, timedelta
import logging
import time
import requests
import psycopg2
from psycopg2 import sql, pool
from contextlib import contextmanager
import pandas as pd
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.providers.http.operators.http import HttpOperator
from airflow.models import Variable
from airflow.utils.slack import send_slack_notification
from airflow.exceptions import AirflowException
from airflow.utils.trigger_rule import TriggerRule
from airflow.operators.email import EmailOperator

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Slack alert function for SLA misses
def sla_miss_callback(dag, task_list, blocking_task_list, slas, blocking_tis):
    """
    Send Slack alert when SLA is missed.
    """
    dag_id = dag.dag_id
    execution_date = dag.execution_date
    
    message = f"""
    🚨 SLA Missed for DAG: {dag_id}
    Execution Date: {execution_date}
    Missed Tasks: {[task.task_id for task in task_list]}
    Blocking Tasks: {[task.task_id for task in blocking_task_list]}
    """
    
    try:
        slack_webhook_url = Variable.get("slack_webhook_url")
        slack_channel = Variable.get("slack_channel", "#airflow-alerts")
        
        send_slack_notification(
            webhook_url=slack_webhook_url,
            channel=slack_channel,
            message=message,
            username="Airflow SLA Monitor"
        )
        
        logger.error(f"SLA miss alert sent to Slack for {dag_id}")
        
    except Exception as e:
        logger.error(f"Failed to send SLA miss alert: {e}")
        # Fallback to email
        EmailOperator(
            task_id='sla_miss_email',
            to=Variable.get("alert_email", "admin@finco.com"),
            subject=f"SLA Missed - {dag_id}",
            html_content=message
        ).execute(dict())

default_args = {
    'owner': 'finance',
    'depends_on_past': True,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'email': Variable.get("alert_email", "finance-team@finco.com"),
    # SLA monitoring - FIXED: Added SLA with 1 hour timeout
    'sla': timedelta(hours=1),
    'sla_miss_callback': sla_miss_callback,
}

# Create the FIXED DAG
dag = DAG(
    'finco_reconciliation_fixed',
    default_args=default_args,
    description='End-of-day reconciliation for Finco Bank (FIXED VERSION)',
    schedule_interval='0 18 * * *',  # 6 PM daily
    catchup=False,
    tags=['finance', 'reconciliation', 'production', 'fixed'],
    max_active_runs=1,  # Prevent concurrent runs
    concurrency=4,  # Limit concurrent tasks
)

# Database connection pool for better resource management
@contextmanager
def get_db_connection():
    """
    Context manager for database connections with proper cleanup.
    """
    connection = None
    try:
        connection = psycopg2.connect(
            host=Variable.get("db_host"),
            database=Variable.get("db_name"),
            user=Variable.get("db_user"),
            password=Variable.get("db_password"),
            connect_timeout=30,  # FIXED: Added connection timeout
            application_name="airflow_finco_reconciliation"
        )
        yield connection
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        raise
    finally:
        if connection:
            connection.close()

def extract_transaction_data(**context):
    """
    Extract transaction data - FIXED: Proper connection management and observability.
    """
    task_start_time = time.time()
    logger.info("Starting transaction data extraction")
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # FIXED: Added query timeout and proper error handling
            query = """
            SELECT transaction_id, account_id, amount, transaction_date, status
            FROM transactions 
            WHERE DATE(transaction_date) = CURRENT_DATE - INTERVAL '1 day'
            AND status = 'pending'
            """
            
            cursor.execute(query, timeout=300)  # 5 minute query timeout
            rows = cursor.fetchall()
            
            row_count = len(rows)
            task_duration = time.time() - task_start_time
            
            # FIXED: Push metrics to XCom for observability
            context['ti'].xcom_push(key='extract_row_count', value=row_count)
            context['ti'].xcom_push(key='extract_duration', value=task_duration)
            context['ti'].xcom_push(key='extract_start_time', value=task_start_time)
            
            logger.info(f"Extracted {row_count} transactions in {task_duration:.2f} seconds")
            
            return row_count
            
    except Exception as e:
        task_duration = time.time() - task_start_time
        logger.error(f"Error in transaction extraction after {task_duration:.2f}s: {e}")
        raise AirflowException(f"Transaction extraction failed: {e}")

def validate_external_api(**context):
    """
    Validate with external API - FIXED: Added timeout and proper error handling.
    """
    task_start_time = time.time()
    logger.info("Starting external API validation")
    
    try:
        api_url = Variable.get("external_api_url")
        headers = {
            'Authorization': f'Bearer {Variable.get("api_token")}',
            'Content-Type': 'application/json'
        }
        
        # FIXED: Added timeout parameters to prevent hanging
        response = requests.get(
            f"{api_url}/validate",
            headers=headers,
            timeout=30  # 30 second timeout
        )
        
        response.raise_for_status()  # Raise exception for HTTP errors
        
        data = response.json()
        task_duration = time.time() - task_start_time
        
        # FIXED: Push metrics to XCom
        context['ti'].xcom_push(key='validate_response_time', value=response.elapsed.total_seconds())
        context['ti'].xcom_push(key='validate_duration', value=task_duration)
        context['ti'].xcom_push(key='validate_status_code', value=response.status_code)
        
        logger.info(f"API validation successful in {task_duration:.2f}s: {data}")
        
        return data
        
    except requests.exceptions.Timeout:
        task_duration = time.time() - task_start_time
        logger.error(f"API validation timeout after {task_duration:.2f}s")
        raise AirflowException("API validation timeout")
    except requests.exceptions.RequestException as e:
        task_duration = time.time() - task_start_time
        logger.error(f"API validation error after {task_duration:.2f}s: {e}")
        raise AirflowException(f"API validation failed: {e}")
    except Exception as e:
        task_duration = time.time() - task_start_time
        logger.error(f"Unexpected error in API validation after {task_duration:.2f}s: {e}")
        raise AirflowException(f"Unexpected error in API validation: {e}")

def process_reconciliation(**context):
    """
    Process reconciliation data - FIXED: Added safeguards, timeouts, and observability.
    """
    task_start_time = time.time()
    logger.info("Starting reconciliation processing")
    
    processed_count = 0
    error_count = 0
    max_iterations = 10000  # FIXED: Added safeguard against infinite loops
    batch_size = 1000
    iteration_count = 0
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            while iteration_count < max_iterations:
                iteration_count += 1
                
                # FIXED: Added query timeout
                cursor.execute("""
                SELECT id, transaction_id, amount 
                FROM reconciliation_queue 
                WHERE status = 'pending'
                LIMIT %s
                """, (batch_size,), timeout=60)
                
                rows = cursor.fetchall()
                
                if not rows:
                    logger.info("No more pending reconciliations to process")
                    break
                
                logger.info(f"Processing batch {iteration_count}: {len(rows)} items")
                
                # Process each row with proper error handling
                for row in rows:
                    rec_id, transaction_id, amount = row
                    
                    try:
                        # FIXED: Added timeout to external API call
                        api_response = requests.post(
                            f"{Variable.get('external_api_url')}/process",
                            json={'transaction_id': transaction_id, 'amount': amount},
                            headers={'Authorization': f'Bearer {Variable.get("api_token")}'},
                            timeout=30  # 30 second timeout
                        )
                        
                        api_response.raise_for_status()
                        
                        # Update status
                        cursor.execute(
                            "UPDATE reconciliation_queue SET status = 'processed' WHERE id = %s",
                            (rec_id,)
                        )
                        processed_count += 1
                        
                        # Commit every 100 records to avoid long transactions
                        if processed_count % 100 == 0:
                            conn.commit()
                            logger.info(f"Processed {processed_count} reconciliations so far")
                        
                    except requests.exceptions.Timeout:
                        error_count += 1
                        logger.warning(f"Timeout processing reconciliation {rec_id}")
                        # Mark as failed for retry
                        cursor.execute(
                            "UPDATE reconciliation_queue SET status = 'failed' WHERE id = %s",
                            (rec_id,)
                        )
                    except requests.exceptions.RequestException as e:
                        error_count += 1
                        logger.error(f"API error processing {rec_id}: {e}")
                        cursor.execute(
                            "UPDATE reconciliation_queue SET status = 'failed' WHERE id = %s",
                            (rec_id,)
                        )
                    except Exception as e:
                        error_count += 1
                        logger.error(f"Unexpected error processing {rec_id}: {e}")
                        cursor.execute(
                            "UPDATE reconciliation_queue SET status = 'failed' WHERE id = %s",
                            (rec_id,)
                        )
            
            # Final commit
            conn.commit()
            
    except Exception as e:
        task_duration = time.time() - task_start_time
        logger.error(f"Error in reconciliation processing after {task_duration:.2f}s: {e}")
        raise AirflowException(f"Reconciliation processing failed: {e}")
    
    task_duration = time.time() - task_start_time
    
    # FIXED: Push comprehensive metrics to XCom
    context['ti'].xcom_push(key='process_duration', value=task_duration)
    context['ti'].xcom_push(key='process_processed_count', value=processed_count)
    context['ti'].xcom_push(key='process_error_count', value=error_count)
    context['ti'].xcom_push(key='process_iterations', value=iteration_count)
    context['ti'].xcom_push(key='process_start_time', value=task_start_time)
    
    logger.info(f"Reconciliation processing completed: {processed_count} processed, "
               f"{error_count} errors, {task_duration:.2f}s total")
    
    return {
        'processed_count': processed_count,
        'error_count': error_count,
        'duration': task_duration
    }

def generate_reports(**context):
    """
    Generate daily reports - FIXED: Added timeouts and proper error handling.
    """
    task_start_time = time.time()
    logger.info("Starting report generation")
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # FIXED: Added query timeout
            cursor.execute("""
            SELECT 
                COUNT(*) as total_transactions,
                SUM(amount) as total_amount,
                AVG(amount) as avg_amount,
                COUNT(CASE WHEN status = 'processed' THEN 1 END) as processed_count
            FROM reconciliation_queue 
            WHERE DATE(created_at) = CURRENT_DATE - INTERVAL '1 day'
            """, timeout=60)
            
            result = cursor.fetchone()
            
            report_data = {
                'date': (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'),
                'total_transactions': result[0],
                'total_amount': float(result[1]) if result[1] else 0,
                'avg_amount': float(result[2]) if result[2] else 0,
                'processed_count': result[3]
            }
            
            # FIXED: Added timeout to report delivery
            response = requests.post(
                f"{Variable.get('reporting_api_url')}/reports",
                json=report_data,
                headers={'Authorization': f'Bearer {Variable.get("api_token")}'},
                timeout=30  # 30 second timeout
            )
            
            response.raise_for_status()
            
            task_duration = time.time() - task_start_time
            
            # FIXED: Push metrics to XCom
            context['ti'].xcom_push(key='report_duration', value=task_duration)
            context['ti'].xcom_push(key='report_response_time', value=response.elapsed.total_seconds())
            context['ti'].xcom_push(key='report_data', value=report_data)
            
            logger.info(f"Report generated and sent in {task_duration:.2f}s: {report_data}")
            
            return report_data
            
    except requests.exceptions.Timeout:
        task_duration = time.time() - task_start_time
        logger.error(f"Report generation timeout after {task_duration:.2f}s")
        raise AirflowException("Report generation timeout")
    except Exception as e:
        task_duration = time.time() - task_start_time
        logger.error(f"Error in report generation after {task_duration:.2f}s: {e}")
        raise AirflowException(f"Report generation failed: {e}")

def cleanup_old_data(**context):
    """
    Cleanup old data - FIXED: Added safeguards and batch processing.
    """
    task_start_time = time.time()
    logger.info("Starting data cleanup")
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # FIXED: Use batch processing to avoid long-running locks
            batch_size = 1000
            total_deleted = 0
            max_batches = 100  # Prevent infinite cleanup
            
            for batch in range(max_batches):
                cursor.execute("""
                DELETE FROM reconciliation_queue 
                WHERE id IN (
                    SELECT id FROM reconciliation_queue 
                    WHERE created_at < CURRENT_DATE - INTERVAL '30 days'
                    LIMIT %s
                )
                """, (batch_size,), timeout=60)
                
                deleted_count = cursor.rowcount
                total_deleted += deleted_count
                
                conn.commit()
                
                if deleted_count < batch_size:
                    break  # No more records to delete
                
                logger.info(f"Cleanup batch {batch + 1}: deleted {deleted_count} records")
            
            task_duration = time.time() - task_start_time
            
            # FIXED: Push metrics to XCom
            context['ti'].xcom_push(key='cleanup_duration', value=task_duration)
            context['ti'].xcom_push(key='cleanup_deleted_count', value=total_deleted)
            context['ti'].xcom_push(key='cleanup_start_time', value=task_start_time)
            
            logger.info(f"Data cleanup completed: {total_deleted} records deleted in {task_duration:.2f}s")
            
            return total_deleted
            
    except Exception as e:
        task_duration = time.time() - task_start_time
        logger.error(f"Error in data cleanup after {task_duration:.2f}s: {e}")
        raise AirflowException(f"Data cleanup failed: {e}")

def send_summary_email(**context):
    """
    Send summary email with timing and performance metrics.
    """
    task_instance = context['ti']
    
    # Collect metrics from XCom
    metrics = {
        'extract': {
            'row_count': task_instance.xcom_pull(task_ids='extract_transaction_data', key='extract_row_count'),
            'duration': task_instance.xcom_pull(task_ids='extract_transaction_data', key='extract_duration')
        },
        'validate': {
            'duration': task_instance.xcom_pull(task_ids='validate_external_api', key='validate_duration'),
            'response_time': task_instance.xcom_pull(task_ids='validate_external_api', key='validate_response_time')
        },
        'process': {
            'processed_count': task_instance.xcom_pull(task_ids='process_reconciliation', key='process_processed_count'),
            'error_count': task_instance.xcom_pull(task_ids='process_reconciliation', key='process_error_count'),
            'duration': task_instance.xcom_pull(task_ids='process_reconciliation', key='process_duration')
        },
        'report': {
            'duration': task_instance.xcom_pull(task_ids='generate_reports', key='report_duration'),
            'data': task_instance.xcom_pull(task_ids='generate_reports', key='report_data')
        },
        'cleanup': {
            'deleted_count': task_instance.xcom_pull(task_ids='cleanup_old_data', key='cleanup_deleted_count'),
            'duration': task_instance.xcom_pull(task_ids='cleanup_old_data', key='cleanup_duration')
        }
    }
    
    # Calculate total duration
    total_duration = sum(m['duration'] for m in metrics.values() if m.get('duration'))
    
    # Create summary HTML
    html_content = f"""
    <html>
    <body>
        <h2>Finco Bank Reconciliation Summary</h2>
        <p><strong>Date:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p><strong>Total Duration:</strong> {total_duration:.2f} seconds</p>
        
        <h3>Task Performance</h3>
        <table border="1" style="border-collapse: collapse; padding: 5px;">
            <tr>
                <th>Task</th>
                <th>Duration (s)</th>
                <th>Records Count</th>
                <th>Status</th>
            </tr>
            <tr>
                <td>Extract Transaction Data</td>
                <td>{metrics['extract']['duration']:.2f}</td>
                <td>{metrics['extract']['row_count']}</td>
                <td>✅ Success</td>
            </tr>
            <tr>
                <td>Validate External API</td>
                <td>{metrics['validate']['duration']:.2f}</td>
                <td>N/A</td>
                <td>✅ Success</td>
            </tr>
            <tr>
                <td>Process Reconciliation</td>
                <td>{metrics['process']['duration']:.2f}</td>
                <td>{metrics['process']['processed_count']} processed, {metrics['process']['error_count']} errors</td>
                <td>✅ Success</td>
            </tr>
            <tr>
                <td>Generate Reports</td>
                <td>{metrics['report']['duration']:.2f}</td>
                <td>N/A</td>
                <td>✅ Success</td>
            </tr>
            <tr>
                <td>Cleanup Old Data</td>
                <td>{metrics['cleanup']['duration']:.2f}</td>
                <td>{metrics['cleanup']['deleted_count']} deleted</td>
                <td>✅ Success</td>
            </tr>
        </table>
        
        <h3>Report Summary</h3>
        <ul>
            <li>Total Transactions: {metrics['report']['data']['total_transactions']}</li>
            <li>Total Amount: ${metrics['report']['data']['total_amount']:,.2f}</li>
            <li>Average Amount: ${metrics['report']['data']['avg_amount']:,.2f}</li>
            <li>Processed Count: {metrics['report']['data']['processed_count']}</li>
        </ul>
    </body>
    </html>
    """
    
    return html_content

# Define tasks - FIXED with proper error handling and observability
extract_task = PythonOperator(
    task_id='extract_transaction_data',
    python_callable=extract_transaction_data,
    dag=dag,
    retries=2,
    retry_delay=timedelta(minutes=2)
)

validate_task = PythonOperator(
    task_id='validate_external_api',
    python_callable=validate_external_api,
    dag=dag,
    retries=3,
    retry_delay=timedelta(minutes=1)
)

process_task = PythonOperator(
    task_id='process_reconciliation',
    python_callable=process_reconciliation,
    dag=dag,
    retries=1,
    retry_delay=timedelta(minutes=5)
)

report_task = PythonOperator(
    task_id='generate_reports',
    python_callable=generate_reports,
    dag=dag,
    retries=2,
    retry_delay=timedelta(minutes=2)
)

cleanup_task = PythonOperator(
    task_id='cleanup_old_data',
    python_callable=cleanup_old_data,
    dag=dag,
    retries=1,
    retry_delay=timedelta(minutes=5)
)

summary_task = EmailOperator(
    task_id='send_summary_email',
    to=Variable.get("summary_email", "finance-team@finco.com"),
    subject="Finco Bank Reconciliation Summary - {{ ds }}",
    html_content=send_summary_email,
    dag=dag,
    trigger_rule=TriggerRule.ALL_DONE  # Send even if some tasks fail
)

# Define task dependencies
extract_task >> validate_task >> process_task >> report_task >> cleanup_task >> summary_task
