import sys
import os
from dotenv import load_dotenv

from src.api_clients.polygon_client import PolygonClient
from src.loaders.snowflake_loader import (
    get_snowflake_session,
    get_sp500_tickers,
    overwrite_partition,
)
from src.utils.dates import today

LOOKUP_TABLE = "sp500_tickers_lookup"
TABLE = "sp500_sma"
DEFAULT_WINDOW = 30
DEFAULT_LIMIT = 120


def run(run_date: str, window: int = DEFAULT_WINDOW, limit: int = DEFAULT_LIMIT):
    print(f"Starting S&P 500 SMA ingestion for {run_date} (window={window}, limit={limit})...")

    session = get_snowflake_session()
    schema = os.environ["STUDENT_SCHEMA"]

    tickers = get_sp500_tickers(session, f"{schema}.{LOOKUP_TABLE}", run_date)
    print(f"Found {len(tickers)} S&P 500 tickers")

    client = PolygonClient()
    df = client.fetch_indicator(tickers, run_date, indicator="sma", window=window, limit=limit)

    if df.empty:
        print("No SMA data fetched.")
        session.close()
        return

    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {schema}.{TABLE} (
        ticker VARCHAR(50),
        timestamp TIMESTAMP_NTZ,
        sma_value FLOAT,
        window_size INTEGER,
        timespan VARCHAR(50),
        series_type VARCHAR(50),
        date DATE
    )
    """

    fq_table = f"{schema}.{TABLE}"

    overwrite_partition(
        session=session,
        df=df,
        table_name=fq_table,
        partition_col="date",
        partition_value=run_date,
        create_table_sql=create_table_sql,
    )

    print(f"Successfully wrote {len(df)} SMA data points to {fq_table} for date {run_date}")
    session.close()


if __name__ == "__main__":
    load_dotenv()
    run_date = sys.argv[1] if len(sys.argv) > 1 else today()
    window = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_WINDOW
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else DEFAULT_LIMIT
    run(run_date, window, limit)
