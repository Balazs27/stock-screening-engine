import sys
import os
from dotenv import load_dotenv

from src.api_clients.fred_client import FREDClient
from src.loaders.snowflake_loader import (
    get_snowflake_session,
    overwrite_partition,
)
from src.utils.dates import today

TABLE = "sp500_macro_rates"


def run(run_date: str):
    print(f"Starting macro rates ingestion for {run_date}...")

    session = get_snowflake_session()
    schema = os.environ["STUDENT_SCHEMA"]

    client = FREDClient()
    df = client.fetch_macro_rates(run_date, run_date)

    if df.empty:
        print("No macro rate data fetched (FRED may not have published data for this date).")
        session.close()
        return

    fq_table = f"{schema}.{TABLE}"

    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {fq_table} (
        series_id VARCHAR,
        date DATE,
        value FLOAT,
        extracted_at TIMESTAMP_NTZ,
        PRIMARY KEY (series_id, date)
    )
    """

    overwrite_partition(
        session=session,
        df=df,
        table_name=fq_table,
        partition_col="date",
        partition_value=run_date,
        create_table_sql=create_table_sql,
    )

    print(f"Successfully wrote {len(df)} macro rate observations to {fq_table} for date {run_date}")
    session.close()


if __name__ == "__main__":
    load_dotenv()
    run(sys.argv[1] if len(sys.argv) > 1 else today())
