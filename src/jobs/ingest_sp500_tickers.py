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
TABLE = "sp500_stock_tickers"


def run(run_date: str):
    print(f"Starting S&P 500 reference tickers ingestion for {run_date}...")

    session = get_snowflake_session()
    schema = os.environ["STUDENT_SCHEMA"]

    # Step 1: Get S&P 500 universe from lookup table
    sp500_tickers = set(get_sp500_tickers(session, f"{schema}.{LOOKUP_TABLE}", run_date))
    print(f"Found {len(sp500_tickers)} S&P 500 tickers in lookup table")

    # Step 2: Fetch ALL reference tickers from Polygon (paginated)
    client = PolygonClient()
    all_tickers = client.fetch_reference_tickers()

    # Step 3: Filter to S&P 500 + normalize
    import pandas as pd

    seen = set()
    filtered = []
    for t in all_tickers:
        symbol = t.get("ticker")
        if symbol in sp500_tickers and symbol not in seen:
            t["date"] = run_date
            if "currency_name" in t and t["currency_name"]:
                t["currency_name"] = t["currency_name"].upper()
            filtered.append(t)
            seen.add(symbol)

    print(f"Filtered to {len(filtered)} S&P 500 tickers with metadata")

    if not filtered:
        print("No matching S&P 500 tickers found in Polygon API")
        session.close()
        return

    df = pd.DataFrame(filtered)

    # Step 4: Write to Snowflake
    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {schema}.{TABLE} (
        ticker VARCHAR(50),
        name VARCHAR(500),
        market VARCHAR(50),
        locale VARCHAR(50),
        primary_exchange VARCHAR(100),
        type VARCHAR(50),
        active BOOLEAN,
        currency_name VARCHAR(50),
        cik VARCHAR(50),
        composite_figi VARCHAR(50),
        share_class_figi VARCHAR(50),
        date DATE,
        last_updated_utc VARCHAR(100)
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

    print(f"Successfully wrote {len(filtered)} tickers to {fq_table} for date {run_date}")
    session.close()


if __name__ == "__main__":
    load_dotenv()
    run(sys.argv[1] if len(sys.argv) > 1 else today())
