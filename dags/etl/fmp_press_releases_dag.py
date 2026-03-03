from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime, timedelta

from src.jobs.ingest_fmp_press_releases import run

default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="fmp_press_releases",
    default_args=default_args,
    description="Fetch press releases from FMP (/stable/news/press-releases-latest)",
    schedule="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["etl", "fmp", "daily", "news"],
) as dag:

    ingest_fmp_press_releases = PythonOperator(
        task_id="ingest_fmp_press_releases",
        python_callable=run,
        op_kwargs={"run_date": "{{ ds }}"},
    )
