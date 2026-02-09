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
TABLE = "sp500_macd"
DEFAULT_SHORT_WINDOW = 12
DEFAULT_LONG_WINDOW = 26
DEFAULT_SIGNAL_WINDOW = 9
DEFAULT_LIMIT = 1


def run(
    run_date: str,
    short_window: int = DEFAULT_SHORT_WINDOW,
    long_window: int = DEFAULT_LONG_WINDOW,
    signal_window: int = DEFAULT_SIGNAL_WINDOW,
    limit: int = DEFAULT_LIMIT,
):
    print(f"Starting S&P 500 MACD ingestion for {run_date} "
          f"(short={short_window}, long={long_window}, signal={signal_window}, limit={limit})...")

    session = get_snowflake_session()
    schema = os.environ["STUDENT_SCHEMA"]

    tickers = get_sp500_tickers(session, f"{schema}.{LOOKUP_TABLE}", run_date)
    print(f"Found {len(tickers)} S&P 500 tickers")

    client = PolygonClient()
    df = client.fetch_macd(
        tickers, run_date,
        short_window=short_window,
        long_window=long_window,
        signal_window=signal_window,
        limit=limit,
    )

    if df.empty:
        print("No MACD data fetched.")
        session.close()
        return

    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {schema}.{TABLE} (
        ticker VARCHAR(50),
        timestamp TIMESTAMP_NTZ,
        macd_value FLOAT,
        signal_value FLOAT,
        histogram_value FLOAT,
        short_window INTEGER,
        long_window INTEGER,
        signal_window INTEGER,
        timespan VARCHAR(50),
        series_type VARCHAR(50),
        date DATE,
        extracted_at TIMESTAMP_NTZ,
        PRIMARY KEY (ticker, date)
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

    print(f"Successfully wrote {len(df)} MACD data points to {fq_table} for date {run_date}")
    session.close()


if __name__ == "__main__":
    load_dotenv()
    run_date = sys.argv[1] if len(sys.argv) > 1 else today()
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_LIMIT
    run(run_date, limit=limit)
