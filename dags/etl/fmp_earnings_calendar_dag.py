from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from airflow.providers.standard.sensors.external_task import ExternalTaskSensor
from datetime import datetime, timedelta

from src.jobs.ingest_fmp_earnings_calendar import run

default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="fmp_earnings_calendar",
    default_args=default_args,
    description="Fetch S&P 500 earnings calendar from FMP (30-day forward window)",
    schedule="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["etl", "fmp", "daily"],
) as dag:

    wait_for_universe = ExternalTaskSensor(
        task_id="wait_for_universe",
        external_dag_id="sp500_lookup",
        external_task_id="ingest_sp500_lookup",
        timeout=3600,
        poke_interval=60,
        mode="poke",
    )

    ingest_earnings_calendar = PythonOperator(
        task_id="ingest_fmp_earnings_calendar",
        python_callable=run,
        op_kwargs={"run_date": "{{ ds }}"},
    )

    wait_for_universe >> ingest_earnings_calendar
