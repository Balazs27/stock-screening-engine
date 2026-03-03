from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime, timedelta

from src.jobs.ingest_fmp_general_news import run

default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="fmp_global_news",
    default_args=default_args,
    description="Fetch general market news from FMP (/stable/news/general-latest)",
    schedule="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["etl", "fmp", "daily", "news"],
) as dag:

    ingest_fmp_global_news = PythonOperator(
        task_id="ingest_fmp_global_news",
        python_callable=run,
        op_kwargs={"run_date": "{{ ds }}"},
    )
