import sys
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

from src.api_clients.fred_client import FREDClient
from src.loaders.snowflake_loader import (
    get_snowflake_session,
    overwrite_date_range,
)
from src.utils.dates import today

TABLE = "sp500_macro_rates"
DEFAULT_LOOKBACK_DAYS = 1826  # ~5 years


def run(run_date: str, lookback_days: int = DEFAULT_LOOKBACK_DAYS):
    end_date = datetime.strptime(run_date, "%Y-%m-%d").date()
    start_date = end_date - timedelta(days=lookback_days)

    print(f"Starting macro rates backfill: {start_date} to {end_date} ({lookback_days} days)...")

    session = get_snowflake_session()
    schema = os.environ["STUDENT_SCHEMA"]

    client = FREDClient()
    df = client.fetch_macro_rates(str(start_date), str(end_date))

    if df.empty:
        print("No macro rate data fetched.")
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

    overwrite_date_range(
        session=session,
        df=df,
        table_name=fq_table,
        start_date=str(start_date),
        end_date=str(end_date),
        create_table_sql=create_table_sql,
    )

    print(f"Successfully wrote {len(df)} macro rate observations to {fq_table}")
    print(f"Date range: {start_date} to {end_date}")
    session.close()


if __name__ == "__main__":
    load_dotenv()
    run_date = sys.argv[1] if len(sys.argv) > 1 else today()
    lookback = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_LOOKBACK_DAYS
    run(run_date, lookback)
