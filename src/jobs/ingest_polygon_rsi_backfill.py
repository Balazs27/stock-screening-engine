import sys
import os
from dotenv import load_dotenv

from src.api_clients.polygon_client import PolygonClient
from src.loaders.snowflake_loader import (
    get_snowflake_session,
    get_sp500_tickers,
    overwrite_date_range,
)
from src.utils.dates import today

LOOKUP_TABLE = "sp500_tickers_lookup"
TABLE = "sp500_rsi_backfill"
DEFAULT_WINDOW = 14
DEFAULT_LIMIT = 730


def run(run_date: str, window: int = DEFAULT_WINDOW, limit: int = DEFAULT_LIMIT):
    print(f"Starting S&P 500 RSI backfill for {run_date} (window={window}, limit={limit})...")

    session = get_snowflake_session()
    schema = os.environ["STUDENT_SCHEMA"]

    tickers = get_sp500_tickers(session, f"{schema}.{LOOKUP_TABLE}", run_date)
    print(f"Found {len(tickers)} S&P 500 tickers")

    client = PolygonClient()
    df = client.fetch_indicator(tickers, run_date, indicator="rsi", window=window, limit=limit)

    if df.empty:
        print("No RSI data fetched.")
        session.close()
        return

    # Derive actual date from timestamp (fetch_indicator sets date=run_date for all rows)
    df["date"] = df["timestamp"].apply(
        lambda x: x.strftime("%Y-%m-%d") if x else None
    )

    start_date = df["date"].min()
    end_date = df["date"].max()

    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {schema}.{TABLE} (
        ticker VARCHAR(50),
        timestamp TIMESTAMP_NTZ,
        rsi_value FLOAT,
        window_size INTEGER,
        timespan VARCHAR(50),
        series_type VARCHAR(50),
        date DATE,
        extracted_at TIMESTAMP_NTZ,
        PRIMARY KEY (ticker, date)
    )
    """

    fq_table = f"{schema}.{TABLE}"

    overwrite_date_range(
        session=session,
        df=df,
        table_name=fq_table,
        start_date=start_date,
        end_date=end_date,
        create_table_sql=create_table_sql,
    )

    print(f"Successfully wrote {len(df)} RSI data points to {fq_table}")
    print(f"Date range: {start_date} to {end_date}")
    session.close()


if __name__ == "__main__":
    load_dotenv()
    run_date = sys.argv[1] if len(sys.argv) > 1 else today()
    window = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_WINDOW
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else DEFAULT_LIMIT
    run(run_date, window, limit)
