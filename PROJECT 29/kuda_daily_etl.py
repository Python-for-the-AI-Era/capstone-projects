from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta

default_args = {
    'owner': 'praise',
    'depends_on_past': True,
    'email_on_failure': True,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'kuda_cfo_reporting_v1',
    default_args=default_args,
    start_date=datetime(2026, 5, 1),
    schedule='@daily',
    catchup=True, # Allows backfilling historical data
) as dag:
    
    # TASK 1: Extract (PostgreSQL to Parquet)
    # TASK 2: Validate (Data Quality Check)
    # TASK 3: Transform (Currency & Fraud Scoring)
    # TASK 4: Load (BigQuery)
    # TASK 5: Notify (CFO Email)

    extract >> validate >> transform >> load >> notify