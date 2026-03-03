from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime, timedelta

from src.jobs.ingest_fmp_key_metrics_backfill import run

default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=10),
}

with DAG(
    dag_id="fmp_key_metrics_backfill",
    default_args=default_args,
    description="Backfill 5 years of key metrics from FMP",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["etl", "fmp", "backfill"],
) as dag:

    ingest_fmp_key_metrics_backfill = PythonOperator(
        task_id="ingest_fmp_key_metrics_backfill",
        python_callable=run,
        op_kwargs={"run_date": "{{ ds }}"},
    )
