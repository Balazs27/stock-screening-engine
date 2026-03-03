from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime, timedelta

from src.jobs.ingest_fred_macro_rates_backfill import run

default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=10),
}

with DAG(
    dag_id="fred_macro_rates_backfill",
    default_args=default_args,
    description="Backfill historical macro rate series from FRED",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["etl", "fred", "backfill", "macro"],
) as dag:

    backfill_fred_macro_rates = PythonOperator(
        task_id="backfill_fred_macro_rates",
        python_callable=run,
        op_kwargs={"run_date": "{{ ds }}"},
    )
