"""
PROBLEMATIC Airflow DAG - Finco Bank End-of-Day Reconciliation

This DAG demonstrates the issues that cause it to get stuck:
1. HTTP calls without timeouts
2. Database operations without proper connection management
3. No SLA monitoring
4. No observability/logging
5. No XCom usage for timing data
"""

from datetime import datetime, timedelta
import logging
import time
import requests
import psycopg2
from psycopg2 import sql
import pandas as pd
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.providers.http.operators.http import HttpOperator
from airflow.models import Variable

# Configure logging (minimal - part of the problem)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

default_args = {
    'owner': 'finance',
    'depends_on_past': True,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
    # No SLA defined - this is part of the problem
}

# Create the problematic DAG
dag = DAG(
    'finco_reconciliation_stuck',
    default_args=default_args,
    description='End-of-day reconciliation for Finco Bank (PROBLEMATIC VERSION)',
    schedule_interval='0 18 * * *',  # 6 PM daily
    catchup=False,
    tags=['finance', 'reconciliation', 'production'],
    # No SLA monitoring - this is part of the problem
)


def extract_transaction_data():
    """
    Extract transaction data - PROBLEMATIC: No timeout, no connection management.
    """
    logger.info("Starting transaction data extraction")
    
    # PROBLEMATIC: Database connection without context manager
    conn = psycopg2.connect(
        host=Variable.get("db_host"),
        database=Variable.get("db_name"),
        user=Variable.get("db_user"),
        password=Variable.get("db_password")
    )
    
    cursor = conn.cursor()
    
    # PROBLEMATIC: No timeout on query, could hang
    query = """
    SELECT transaction_id, account_id, amount, transaction_date, status
    FROM transactions 
    WHERE DATE(transaction_date) = CURRENT_DATE - INTERVAL '1 day'
    AND status = 'pending'
    """
    
    cursor.execute(query)
    rows = cursor.fetchall()
    
    # PROBLEMATIC: Connection not properly closed on exception
    conn.commit()
    cursor.close()
    conn.close()
    
    logger.info(f"Extracted {len(rows)} transactions")
    return len(rows)


def validate_external_api():
    """
    Validate with external API - PROBLEMATIC: HTTP call without timeout.
    """
    logger.info("Validating with external API")
    
    # PROBLEMATIC: HTTP call without timeout - can hang indefinitely
    api_url = Variable.get("external_api_url")
    headers = {
        'Authorization': f'Bearer {Variable.get("api_token")}',
        'Content-Type': 'application/json'
    }
    
    # PROBLEMATIC: No timeout parameter - this is the main cause of hanging
    response = requests.get(
        f"{api_url}/validate",
        headers=headers,
        # No timeout parameter - will hang if server is unresponsive
    )
    
    if response.status_code == 200:
        data = response.json()
        logger.info(f"API validation successful: {data}")
        return data
    else:
        logger.error(f"API validation failed: {response.status_code}")
        raise Exception(f"API validation failed: {response.status_code}")


def process_reconciliation():
    """
    Process reconciliation data - PROBLEMATIC: No observability, infinite loop risk.
    """
    logger.info("Processing reconciliation data")
    
    # PROBLEMATIC: No timing information, no row count tracking
    start_time = time.time()
    
    # Database connection without proper management
    conn = psycopg2.connect(
        host=Variable.get("db_host"),
        database=Variable.get("db_name"),
        user=Variable.get("db_user"),
        password=Variable.get("db_password")
    )
    
    cursor = conn.cursor()
    
    # PROBLEMATIC: Potential infinite loop if data is inconsistent
    processed_count = 0
    max_iterations = 1000000  # No safeguard for infinite loops
    
    while processed_count < max_iterations:
        # Query for pending reconciliations
        cursor.execute("""
        SELECT id, transaction_id, amount 
        FROM reconciliation_queue 
        WHERE status = 'pending'
        LIMIT 1000
        """)
        
        rows = cursor.fetchall()
        
        if not rows:
            break
        
        # Process each row
        for row in rows:
            rec_id, transaction_id, amount = row
            
            # PROBLEMATIC: External API call without timeout inside loop
            try:
                api_response = requests.post(
                    f"{Variable.get('external_api_url')}/process",
                    json={'transaction_id': transaction_id, 'amount': amount},
                    headers={'Authorization': f'Bearer {Variable.get("api_token")}'}
                    # No timeout - can hang each iteration
                )
                
                if api_response.status_code == 200:
                    # Update status
                    cursor.execute(
                        "UPDATE reconciliation_queue SET status = 'processed' WHERE id = %s",
                        (rec_id,)
                    )
                    processed_count += 1
                else:
                    logger.error(f"Failed to process {rec_id}")
                    
            except Exception as e:
                logger.error(f"Error processing {rec_id}: {e}")
                # Continue processing - could lead to infinite loop
        
        conn.commit()
    
    # PROBLEMATIC: No XCom push, no timing information
    end_time = time.time()
    duration = end_time - start_time
    
    logger.info(f"Processed {processed_count} reconciliations")
    # No XCom push - timing data lost
    
    cursor.close()
    conn.close()


def generate_reports():
    """
    Generate daily reports - PROBLEMATIC: No error handling, no observability.
    """
    logger.info("Generating daily reports")
    
    # PROBLEMATIC: No start time logging, no row count tracking
    conn = psycopg2.connect(
        host=Variable.get("db_host"),
        database=Variable.get("db_name"),
        user=Variable.get("db_user"),
        password=Variable.get("db_password")
    )
    
    # PROBLEMATIC: Complex query without timeout
    cursor = conn.cursor()
    cursor.execute("""
    SELECT 
        COUNT(*) as total_transactions,
        SUM(amount) as total_amount,
        AVG(amount) as avg_amount,
        COUNT(CASE WHEN status = 'processed' THEN 1 END) as processed_count
    FROM reconciliation_queue 
    WHERE DATE(created_at) = CURRENT_DATE - INTERVAL '1 day'
    """)
    
    result = cursor.fetchone()
    
    # PROBLEMATIC: HTTP call without timeout for report delivery
    report_data = {
        'date': (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'),
        'total_transactions': result[0],
        'total_amount': float(result[1]) if result[1] else 0,
        'avg_amount': float(result[2]) if result[2] else 0,
        'processed_count': result[3]
    }
    
    # Send report via API without timeout
    response = requests.post(
        f"{Variable.get('reporting_api_url')}/reports",
        json=report_data,
        headers={'Authorization': f'Bearer {Variable.get("api_token")}'}
        # No timeout - can hang
    )
    
    logger.info(f"Report generated and sent: {response.status_code}")
    
    cursor.close()
    conn.close()


def cleanup_old_data():
    """
    Cleanup old data - PROBLEMATIC: No safeguards, can hang.
    """
    logger.info("Cleaning up old data")
    
    conn = psycopg2.connect(
        host=Variable.get("db_host"),
        database=Variable.get("db_name"),
        user=Variable.get("db_user"),
        password=Variable.get("db_password")
    )
    
    cursor = conn.cursor()
    
    # PROBLEMATIC: No limit on DELETE, can lock tables for hours
    cursor.execute("""
    DELETE FROM reconciliation_queue 
    WHERE created_at < CURRENT_DATE - INTERVAL '30 days'
    """)
    
    deleted_count = cursor.rowcount
    conn.commit()
    
    logger.info(f"Cleaned up {deleted_count} old records")
    
    cursor.close()
    conn.close()


# Define tasks - all will show as 'running' when stuck
extract_task = PythonOperator(
    task_id='extract_transaction_data',
    python_callable=extract_transaction_data,
    dag=dag
)

validate_task = PythonOperator(
    task_id='validate_external_api',
    python_callable=validate_external_api,
    dag=dag
)

process_task = PythonOperator(
    task_id='process_reconciliation',
    python_callable=process_reconciliation,
    dag=dag
)

report_task = PythonOperator(
    task_id='generate_reports',
    python_callable=generate_reports,
    dag=dag
)

cleanup_task = PythonOperator(
    task_id='cleanup_old_data',
    python_callable=cleanup_old_data,
    dag=dag
)

# Define task dependencies
extract_task >> validate_task >> process_task >> report_task >> cleanup_task
