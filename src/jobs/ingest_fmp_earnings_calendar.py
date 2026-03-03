import sys
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

from src.api_clients.fmp_client import FMPClient
from src.loaders.snowflake_loader import (
    get_snowflake_session,
    get_sp500_tickers,
)
from src.utils.dates import today

LOOKUP_TABLE = "sp500_tickers_lookup"
TABLE = "sp500_earnings_calendar"
DEFAULT_FORWARD_DAYS = 30
# Max 90-day date range, Retrieve historical values up to 5 years.


def run(run_date: str, forward_days: int = DEFAULT_FORWARD_DAYS, max_forward_days: int = 90):
    print(f"Starting S&P 500 earnings calendar ingestion for {run_date}...")

    session = get_snowflake_session()
    schema = os.environ["STUDENT_SCHEMA"]

    tickers = get_sp500_tickers(session, f"{schema}.{LOOKUP_TABLE}", run_date)
    print(f"Found {len(tickers)} S&P 500 tickers")

    # Limit forward_days to max_forward_days
    forward_days = min(forward_days, max_forward_days)

    end_date = datetime.strptime(run_date, "%Y-%m-%d").date() + timedelta(days=forward_days)

    client = FMPClient()
    df = client.fetch_earnings_calendar(tickers, run_date, str(end_date))

    if df.empty:
        print("No earnings calendar data fetched.")
        session.close()
        return

    fq_table = f"{schema}.{TABLE}"

    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {fq_table} (
        ticker VARCHAR,
        date DATE,
        eps_actual FLOAT,
        eps_estimated FLOAT,
        revenue_actual NUMBER,
        revenue_estimated NUMBER,
        last_updated DATE,
        extracted_at TIMESTAMP_NTZ,
        PRIMARY KEY (ticker, date)
    )
    """

    # Earnings calendar is a complete forward-looking snapshot — truncate and reload each run
    session.sql(create_table_sql).collect()
    session.sql(f"DELETE FROM {fq_table}").collect()
    session.create_dataframe(df).write.mode("append").save_as_table(fq_table)

    print(f"Successfully wrote {len(df)} earnings calendar events to {fq_table}")
    session.close()


if __name__ == "__main__":
    load_dotenv()
    run_date = sys.argv[1] if len(sys.argv) > 1 else today()
    fwd_days = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_FORWARD_DAYS
    run(run_date, fwd_days)
