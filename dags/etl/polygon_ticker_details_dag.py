from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from airflow.providers.standard.sensors.external_task import ExternalTaskSensor
from datetime import datetime, timedelta

from src.jobs.ingest_polygon_ticker_details import run

default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="polygon_ticker_details",
    default_args=default_args,
    description="Fetch S&P 500 ticker details (market cap, shares) from Polygon",
    schedule="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["etl", "polygon", "daily"],
) as dag:

    wait_for_universe = ExternalTaskSensor(
        task_id="wait_for_universe",
        external_dag_id="sp500_lookup",
        external_task_id="ingest_sp500_lookup",
        timeout=3600,
        poke_interval=60,
        mode="poke",
    )

    ingest_ticker_details = PythonOperator(
        task_id="ingest_polygon_ticker_details",
        python_callable=run,
        op_kwargs={"run_date": "{{ ds }}"},
    )

    wait_for_universe >> ingest_ticker_details
