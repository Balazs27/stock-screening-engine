from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime, timedelta

from src.jobs.ingest_sp500_lookup import run

default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="sp500_lookup",
    default_args=default_args,
    description="Fetch S&P 500 universe from Wikipedia",
    schedule="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["etl", "wikipedia", "daily"],
) as dag:

    ingest_sp500_lookup = PythonOperator(
        task_id="ingest_sp500_lookup",
        python_callable=run,
        op_kwargs={"run_date": "{{ ds }}"},
    )
