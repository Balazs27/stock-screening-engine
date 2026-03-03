from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime, timedelta

from src.jobs.ingest_polygon_benchmark_prices_backfill import run

default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=10),
}

with DAG(
    dag_id="polygon_benchmark_prices_backfill",
    default_args=default_args,
    description="Backfill historical benchmark and sector ETF prices from Polygon",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["etl", "polygon", "backfill", "benchmarks"],
) as dag:

    backfill_polygon_benchmark_prices = PythonOperator(
        task_id="backfill_polygon_benchmark_prices",
        python_callable=run,
        op_kwargs={"run_date": "{{ ds }}"},
    )
