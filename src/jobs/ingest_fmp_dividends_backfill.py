import sys
import os
from dotenv import load_dotenv

from src.api_clients.fmp_client import FMPClient
from src.loaders.snowflake_loader import (
    get_snowflake_session,
    get_sp500_tickers,
    overwrite_date_range,
)
from src.utils.dates import today

LOOKUP_TABLE = "sp500_tickers_lookup"
TABLE = "sp500_dividends"
DEFAULT_LOOKBACK_DAYS = 1826  # ~5 years


def run(run_date: str, lookback_days: int = DEFAULT_LOOKBACK_DAYS):
    print(f"Starting S&P 500 dividends backfill for {run_date} (lookback={lookback_days}d)...")

    session = get_snowflake_session()
    schema = os.environ["STUDENT_SCHEMA"]

    tickers = get_sp500_tickers(session, f"{schema}.{LOOKUP_TABLE}", run_date)
    print(f"Found {len(tickers)} S&P 500 tickers")

    client = FMPClient()
    df = client.fetch_dividends(tickers)

    if df.empty:
        print("No dividend data fetched.")
        session.close()
        return

    from datetime import datetime, timedelta
    cutoff = (datetime.strptime(run_date, "%Y-%m-%d") - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    df = df[df["date"].notna() & (df["date"] >= cutoff)]

    if df.empty:
        print(f"No data within lookback window (>= {cutoff}).")
        session.close()
        return

    start_date = df["date"].min()
    end_date = df["date"].max()

    fq_table = f"{schema}.{TABLE}"

    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {fq_table} (
        ticker VARCHAR,
        date DATE,
        record_date DATE,
        payment_date DATE,
        declaration_date DATE,
        adj_dividend FLOAT,
        dividend FLOAT,
        yield FLOAT,
        extracted_at TIMESTAMP_NTZ,
        PRIMARY KEY (ticker, date)
    )
    """

    overwrite_date_range(
        session=session,
        df=df,
        table_name=fq_table,
        start_date=start_date,
        end_date=end_date,
        create_table_sql=create_table_sql,
    )

    print(f"Successfully wrote {len(df)} dividend backfill records to {fq_table}")
    print(f"Date range: {start_date} to {end_date}")
    session.close()


if __name__ == "__main__":
    load_dotenv()
    run_date = sys.argv[1] if len(sys.argv) > 1 else today()
    lookback = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_LOOKBACK_DAYS
    run(run_date, lookback)
