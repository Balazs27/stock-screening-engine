import sys
import os
from dotenv import load_dotenv

from src.api_clients.fmp_client import FMPClient
from src.loaders.snowflake_loader import (
    get_snowflake_session,
    get_sp500_tickers,
    overwrite_partition,
)
from src.utils.dates import today

LOOKUP_TABLE = "sp500_tickers_lookup"
TABLE = "sp500_insider_trades"


def run(run_date: str):
    print(f"Starting S&P 500 insider trades (latest feed) ingestion for {run_date}...")

    session = get_snowflake_session()
    schema = os.environ["STUDENT_SCHEMA"]

    tickers = get_sp500_tickers(session, f"{schema}.{LOOKUP_TABLE}", run_date)
    print(f"Found {len(tickers)} S&P 500 tickers")

    client = FMPClient()
    df = client.fetch_insider_trades_latest(tickers, run_date)

    if df.empty:
        print("No insider trades data fetched.")
        session.close()
        return

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

    overwrite_partition(
        session=session,
        df=df,
        table_name=fq_table,
        partition_col="filing_date",
        partition_value=run_date,
        create_table_sql=create_table_sql,
    )

    print(f"Successfully wrote {len(df)} insider trades to {fq_table} for date {run_date}")
    session.close()


if __name__ == "__main__":
    load_dotenv()
    run(sys.argv[1] if len(sys.argv) > 1 else today())
