import os
from pathlib import Path
from datetime import datetime, timedelta

from cosmos import DbtTaskGroup, ProjectConfig, ProfileConfig, ExecutionConfig
from airflow.decorators import dag
from airflow.providers.standard.sensors.external_task import ExternalTaskSensor
from dotenv import load_dotenv

# --- Environment Setup ---
dbt_env_path = os.path.join(os.environ["AIRFLOW_HOME"], "dbt_project", "dbt.env")
load_dotenv(dbt_env_path)

airflow_home = os.environ["AIRFLOW_HOME"]
PATH_TO_DBT_PROJECT = Path(f"{airflow_home}/dbt_project")
PATH_TO_DBT_PROFILES = PATH_TO_DBT_PROJECT / "profiles.yml"

# --- Cosmos Configuration ---
profile_config = ProfileConfig(
    profile_name="stock_screening_engine",
    target_name="dev",
    profiles_yml_filepath=PATH_TO_DBT_PROFILES,
)

# --- ETL Dependencies ---
# All daily ETL DAGs that must complete before dbt runs.
# Format: { dag_id: terminal_task_id }
DAILY_ETL_DEPENDENCIES = {
    # Universe (root dependency)
    "sp500_lookup": "ingest_sp500_lookup",
    # Polygon market data
    "polygon_daily_prices": "ingest_polygon_prices",
    "polygon_daily_rsi": "ingest_polygon_rsi",
    "polygon_daily_macd": "ingest_polygon_macd",
    "polygon_daily_news": "ingest_polygon_news",
    # FMP fundamentals --> These are annual pipelines, no need to wait for them, they do not run on a daily cadence!
    #"fmp_income_statement": "ingest_fmp_income_statement",
    #"fmp_balance_sheet": "ingest_fmp_balance_sheet",
    #"fmp_cash_flow": "ingest_fmp_cash_flow",
    #"fmp_news_daily": "ingest_fmp_news",
}

default_args = {
    "owner": "airflow",
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
    "execution_timeout": timedelta(minutes=30),
}


@dag(
    dag_id="stock_screening_dbt_daily",
    start_date=datetime(2026, 1, 1),
    schedule="@daily",
    catchup=False,
    default_args=default_args,
    tags=["dbt", "stock", "daily"],
)
def stock_screening_dbt_daily_dag():

    # --- Gate: Wait for all daily ETL pipelines to complete ---
    etl_sensors = []
    for dag_id, task_id in DAILY_ETL_DEPENDENCIES.items():
        sensor = ExternalTaskSensor(
            task_id=f"wait_for_{dag_id}",
            external_dag_id=dag_id,
            external_task_id=task_id,
            timeout=7200,
            poke_interval=60,
            mode="reschedule",
        )
        etl_sensors.append(sensor)

    # --- dbt Build: staging → intermediate → dimensions → marts + tests ---
    # Cosmos renders each model as an Airflow task, wired by ref() dependencies.
    # TestBehavior.AFTER_EACH runs tests immediately after each model (= dbt build).
    dbt_build = DbtTaskGroup(
        group_id="dbt_stock_engine",
        project_config=ProjectConfig(PATH_TO_DBT_PROJECT),
        profile_config=profile_config,
        execution_config=ExecutionConfig(),
    )

    # All ETL sensors must pass before any dbt model starts
    etl_sensors >> dbt_build


stock_screening_dbt_daily_dag()
