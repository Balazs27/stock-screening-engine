import sys
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

from src.api_clients.fmp_client import FMPClient
from src.loaders.snowflake_loader import (
    get_snowflake_session,
    get_sp500_tickers,
    overwrite_date_range,
)
from src.utils.dates import today

LOOKUP_TABLE = "sp500_tickers_lookup"
TABLE = "sp500_fmp_stock_news"
DEFAULT_LOOKBACK_DAYS = 1826  # ~5 years


def run(run_date: str, lookback_days: int = DEFAULT_LOOKBACK_DAYS, max_pages: int = 5000):
    print(f"Starting S&P 500 FMP stock news backfill for {run_date} (lookback={lookback_days}d, max_pages={max_pages})...")

    session = get_snowflake_session()
    schema = os.environ["STUDENT_SCHEMA"]

    tickers = get_sp500_tickers(session, f"{schema}.{LOOKUP_TABLE}", run_date)
    print(f"Found {len(tickers)} S&P 500 tickers")

    start_date = (datetime.strptime(run_date, "%Y-%m-%d") - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

    client = FMPClient()
    df = client.fetch_stock_news(tickers, run_date, max_pages=max_pages, start_date=start_date)

    if df.empty:
        print("No stock news data fetched.")
        session.close()
        return

    df = df[df["date"].notna() & (df["date"] >= start_date)]

    if df.empty:
        session.close()
        return

    bulk_start_date = df["date"].min()
    bulk_end_date = df["date"].max()

    fq_table = f"{schema}.{TABLE}"

    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {fq_table} (
        ticker VARCHAR,
        published_date TIMESTAMP_NTZ,
        title VARCHAR,
        date DATE,
        content VARCHAR,
        image_url VARCHAR,
        article_url VARCHAR,
        site VARCHAR,
        extracted_at TIMESTAMP_NTZ,
        PRIMARY KEY (article_url, ticker)
    )
    """

    overwrite_date_range(
        session=session,
        df=df,
        table_name=fq_table,
        start_date=bulk_start_date,
        end_date=bulk_end_date,
        create_table_sql=create_table_sql,
    )

    print(f"Successfully wrote {len(df)} stock news backfill records to {fq_table}")
    print(f"Date range: {bulk_start_date} to {bulk_end_date}")
    session.close()


if __name__ == "__main__":
    load_dotenv()
    run_date = sys.argv[1] if len(sys.argv) > 1 else today()
    lookback = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_LOOKBACK_DAYS
    run(run_date, lookback)
