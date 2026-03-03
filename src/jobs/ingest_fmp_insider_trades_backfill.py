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
TABLE = "sp500_insider_trades"
DEFAULT_LOOKBACK_DAYS = 1826  # ~5 years


def run(run_date: str, lookback_days: int = DEFAULT_LOOKBACK_DAYS, max_pages: int = 5000):
    print(f"Starting S&P 500 insider trades (latest) backfill for {run_date} (lookback={lookback_days}d, max_pages={max_pages})...")

    session = get_snowflake_session()
    schema = os.environ["STUDENT_SCHEMA"]

    tickers = get_sp500_tickers(session, f"{schema}.{LOOKUP_TABLE}", run_date)
    print(f"Found {len(tickers)} S&P 500 tickers")

    start_date = (datetime.strptime(run_date, "%Y-%m-%d") - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

    client = FMPClient()
    df = client.fetch_insider_trades_latest(tickers, start_date, max_pages=max_pages)

    if df.empty:
        print("No insider trades data fetched.")
        session.close()
        return

    df = df[df["filing_date"].notna() & (df["filing_date"] >= start_date)]

    if df.empty:
        session.close()
        return

    bulk_start_date = df["filing_date"].min()
    bulk_end_date = df["filing_date"].max()

    fq_table = f"{schema}.{TABLE}"

    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {fq_table} (
        ticker VARCHAR,
        filing_date DATE,
        transaction_date DATE,
        reporting_cik VARCHAR,
        company_cik VARCHAR,
        transaction_type VARCHAR,
        securities_owned NUMBER,
        reporting_name VARCHAR,
        type_of_owner VARCHAR,
        acquisition_or_disposition VARCHAR,
        direct_or_indirect VARCHAR,
        form_type VARCHAR,
        securities_transacted NUMBER,
        price FLOAT,
        security_name VARCHAR,
        url VARCHAR,
        extracted_at TIMESTAMP_NTZ,
        PRIMARY KEY (ticker, filing_date, reporting_name, transaction_type)
    )
    """

    session.sql(create_table_sql).collect()
    session.sql(
        f"DELETE FROM {fq_table} WHERE filing_date BETWEEN '{bulk_start_date}' AND '{bulk_end_date}'"
    ).collect()
    session.create_dataframe(df).write.mode("append").save_as_table(fq_table)

    print(f"Successfully wrote {len(df)} insider trades (latest) backfill records to {fq_table}")
    print(f"Date range: {bulk_start_date} to {bulk_end_date}")
    session.close()


if __name__ == "__main__":
    load_dotenv()
    run_date = sys.argv[1] if len(sys.argv) > 1 else today()
    lookback = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_LOOKBACK_DAYS
    run(run_date, lookback)
