# Kuda Bank Daily ETL Architecture

## 1. Pipeline Reliability
- **Idempotency:** Every task uses the `{{ ds }}` macro to filter data by day. This ensures backfills are safe.
- **Retries:** Configured with exponential backoff to handle transient network issues during BigQuery loads.

## 2. Data Quality (DQ) Gate
The `validate_data` task acts as a circuit breaker. If the upstream PostgreSQL data is corrupted, the pipeline fails before reaching the BigQuery warehouse.

## 3. Backfill Strategy
To backfill data for April 2026, simply run:
`airflow dags backfill -s 2026-04-01 -e 2026-04-30 kuda_cfo_reporting_v1`

## 4. SLA Monitoring (Stretch Goal)
- **SLA:** 6:00 AM WAT.
- **Slack Alert:** If the `load_to_bigquery` task is not complete by the SLA, a message is dispatched to `#data-ops` with the DAG run link.