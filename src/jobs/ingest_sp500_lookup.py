import sys
import os
from dotenv import load_dotenv

from src.api_clients.wikipedia_client import fetch_sp500_constituents
from src.loaders.snowflake_loader import get_snowflake_session, overwrite_partition
from src.utils.dates import today

TABLE = "sp500_tickers_lookup"


def run(run_date: str):
    print(f"Starting S&P 500 lookup ingestion for {run_date}...")

    df = fetch_sp500_constituents(run_date)
    print(f"Fetched {len(df)} tickers from Wikipedia")

    session = get_snowflake_session()
    schema = os.environ["STUDENT_SCHEMA"]

    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {schema}.{TABLE} (
        ticker VARCHAR(50),
        security_name VARCHAR(500),
        gics_sector VARCHAR(100),
        gics_sub_industry VARCHAR(200),
        headquarters_location VARCHAR(200),
        date_added DATE,
        cik VARCHAR(50),
        founded_year VARCHAR(100),
        date DATE,
        extracted_at TIMESTAMP_NTZ
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

    print(f"Successfully wrote {len(df)} tickers to {fq_table} for date {run_date}")
    session.close()


if __name__ == "__main__":
    load_dotenv()
    run(sys.argv[1] if len(sys.argv) > 1 else today())
