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
TABLE = "sp500_stock_snapshot"


def run(run_date: str):
    print(f"Starting S&P 500 stock snapshot ingestion for {run_date}...")

    session = get_snowflake_session()
    schema = os.environ["STUDENT_SCHEMA"]

    tickers = get_sp500_tickers(session, f"{schema}.{LOOKUP_TABLE}", run_date)
    print(f"Found {len(tickers)} S&P 500 tickers")

    client = PolygonClient()
    df = client.fetch_stock_snapshot(tickers, run_date)

    if df.empty:
        print("No stock snapshot data fetched.")
        session.close()
        return

    fq_table = f"{schema}.{TABLE}"

    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {fq_table} (
        ticker VARCHAR,
        name VARCHAR,
        type VARCHAR,
        market_status VARCHAR,
        session_change FLOAT,
        session_change_percent FLOAT,
        session_early_trading_change FLOAT,
        session_early_trading_change_percent FLOAT,
        session_regular_trading_change FLOAT,
        session_regular_trading_change_percent FLOAT,
        session_close FLOAT,
        session_high FLOAT,
        session_low FLOAT,
        session_open FLOAT,
        session_volume NUMBER,
        session_previous_close FLOAT,
        session_price FLOAT,
        session_vwap FLOAT,
        last_minute_close FLOAT,
        last_minute_high FLOAT,
        last_minute_low FLOAT,
        last_minute_open FLOAT,
        last_minute_volume NUMBER,
        last_minute_vwap FLOAT,
        last_minute_transactions NUMBER,
        date DATE,
        extracted_at TIMESTAMP_NTZ,
        PRIMARY KEY (ticker, date)
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

    print(f"Successfully wrote {len(df)} stock snapshots to {fq_table} for date {run_date}")
    session.close()


if __name__ == "__main__":
    load_dotenv()
    run_date = sys.argv[1] if len(sys.argv) > 1 else today()
    run(run_date)
