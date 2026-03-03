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
TABLE = "sp500_ticker_details"


def run(run_date: str):
    print(f"Starting S&P 500 ticker details ingestion for {run_date}...")

    session = get_snowflake_session()
    schema = os.environ["STUDENT_SCHEMA"]

    tickers = get_sp500_tickers(session, f"{schema}.{LOOKUP_TABLE}", run_date)
    print(f"Found {len(tickers)} S&P 500 tickers")

    client = PolygonClient()
    df = client.fetch_ticker_details(tickers, run_date)

    if df.empty:
        print("No ticker details fetched.")
        session.close()
        return

    fq_table = f"{schema}.{TABLE}"

    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {fq_table} (
        ticker VARCHAR,
        name VARCHAR,
        market VARCHAR,
        locale VARCHAR,
        primary_exchange VARCHAR,
        type VARCHAR,
        active BOOLEAN,
        currency_name VARCHAR,
        cik VARCHAR,
        market_cap NUMBER,
        share_class_shares_outstanding NUMBER,
        weighted_shares_outstanding NUMBER,
        list_date DATE,
        sic_code VARCHAR,
        sic_description VARCHAR,
        total_employees NUMBER,
        homepage_url VARCHAR,
        description VARCHAR,
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

    print(f"Successfully wrote {len(df)} ticker details to {fq_table} for date {run_date}")
    session.close()


if __name__ == "__main__":
    load_dotenv()
    run(sys.argv[1] if len(sys.argv) > 1 else today())
